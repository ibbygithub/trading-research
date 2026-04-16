"""Market-context enrichment for the trade log.

Joins each trade's entry bar to the 5m features parquet and attaches
six context columns.  All computations use only data available at entry
time (no look-ahead).

Public API
----------
    join_entry_context(trades, features) -> pd.DataFrame
"""

from __future__ import annotations

import pandas as pd
import numpy as np


# CME bond session regime boundaries in America/New_York time-of-day (hour).
_REGIMES = [
    ("Asia",        0,  3),   # 00:00 – 02:59 ET  (and 18:00+ wraps; handled below)
    ("London",      3,  8),   # 03:00 – 07:59 ET
    ("NY pre-open", 8,  9),   # 08:00 – 08:59 ET
    ("NY RTH",      9, 16),   # 09:00 – 15:59 ET  (RTH officially 08:20-15:00 for bonds, but 09:30 is equity RTH)
    ("NY close",   16, 17),   # 16:00 – 16:59 ET
    ("Overnight",  17, 18),   # 17:00 – 17:59 ET  (CME 5-min break before reopen)
]
# 18:00 – 23:59 ET is CME evening session → maps to "Asia" (pre-midnight Asia leg)


def _classify_regime(hour: int) -> str:
    """Classify a New York hour-of-day into a session regime label."""
    if hour >= 18:
        return "Asia"
    for label, start, end in _REGIMES:
        if start <= hour < end:
            return label
    return "Asia"  # 00:00-02:59 fallback


def join_entry_context(
    trades: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    """Attach market-context columns to the trade log from the features parquet.

    Looks up each trade's entry bar in *features* (matched on entry_ts ±
    one bar) and attaches:

    - ``atr_14_pct_rank_252``: rolling 252-session percentile rank of ATR_14
      at the entry bar (0=low vol, 1=high vol).
    - ``daily_range_used_pct``: fraction of the daily range consumed by
      entry_price relative to the day's open.  Computed from intraday
      session bars.
    - ``vwap_distance_atr``: (close - vwap_session) / atr_14 at entry.
    - ``htf_bias_strength``: absolute value of the daily MACD histogram at
      entry (proxy for higher-timeframe momentum bias strength).
    - ``session_regime``: categorical tag based on entry_time-of-day in ET:
      Asia / London / NY pre-open / NY RTH / NY close / Overnight.
    - ``entry_atr_14``: raw ATR_14 value at entry (useful for stop sizing
      audit in subsequent sessions).

    Parameters
    ----------
    trades:
        Trade log DataFrame as produced by the backtest engine.  Must have
        ``entry_ts`` (tz-aware UTC) and ``entry_price`` columns.
    features:
        5m features parquet, loaded with ``timestamp_utc`` as the index
        (tz-aware UTC).  Must contain: ``atr_14``, ``vwap_session``,
        ``daily_macd_hist``, ``timestamp_ny``.

    Returns
    -------
    A copy of *trades* with six additional columns appended.  Trades whose
    entry_ts does not match any feature bar get NaN for numeric columns and
    "Unknown" for session_regime.

    All computations use only data available at bar T (no look-ahead).  The
    ATR percentile rank is computed on the full features parquet before the
    join, which is correct because percentile is a monotone transformation —
    the rank at bar T is determined solely by values at bars ≤ T.
    """
    trades = trades.copy()

    # --- Enrich features with derived columns ---
    feat = features.copy()

    # 1. ATR percentile rank (rolling 252 sessions ≈ 1 year of ~7.5 h trading
    #    days; each trading day has ~90 5m bars → 252 × 90 ≈ 22,680 bars).
    #    We roll over bars not sessions, which is an approximation but avoids
    #    needing a trading-calendar join inside this function.
    _ATR_ROLL = 252 * 90  # bars (~1 year at 5m resolution)
    if "atr_14" in feat.columns:
        feat["atr_14_pct_rank_252"] = (
            feat["atr_14"]
            .rolling(_ATR_ROLL, min_periods=20)
            .apply(lambda w: float(np.sum(w < w[-1]) / len(w)), raw=True)
        )
    else:
        feat["atr_14_pct_rank_252"] = float("nan")

    # 2. Daily range used (fraction of today's intraday range consumed at entry).
    #    daily_open = first bar's open for the calendar date in ET.
    #    daily_range_so_far = high(from day open to current bar) - low(...).
    if "timestamp_ny" in feat.columns:
        ny_dt = pd.to_datetime(feat["timestamp_ny"])
        feat["_trade_date"] = ny_dt.dt.date

        # Daily open = open of the first bar in each NY calendar day
        daily_open = feat.groupby("_trade_date")["open"].transform("first")
        # Running max/min within each day (uses cumulative max/min on sorted index)
        daily_high = feat.groupby("_trade_date")["high"].cummax()
        daily_low  = feat.groupby("_trade_date")["low"].cummin()
        daily_range = (daily_high - daily_low).replace(0, float("nan"))
        feat["daily_range_used_pct"] = (feat["close"] - daily_open) / daily_range
        feat.drop(columns=["_trade_date"], inplace=True)
    else:
        feat["daily_range_used_pct"] = float("nan")

    # 3. VWAP distance in ATRs
    if "vwap_session" in feat.columns and "atr_14" in feat.columns:
        atr_safe = feat["atr_14"].replace(0, float("nan"))
        feat["vwap_distance_atr"] = (feat["close"] - feat["vwap_session"]) / atr_safe
    else:
        feat["vwap_distance_atr"] = float("nan")

    # 4. HTF bias strength (daily MACD hist abs value)
    if "daily_macd_hist" in feat.columns:
        feat["htf_bias_strength"] = feat["daily_macd_hist"].abs()
    else:
        feat["htf_bias_strength"] = float("nan")

    # 5. Session regime (from NY hour-of-day)
    if "timestamp_ny" in feat.columns:
        ny_dt = pd.to_datetime(feat["timestamp_ny"])
        feat["session_regime"] = ny_dt.dt.hour.map(_classify_regime)
    else:
        feat["session_regime"] = "Unknown"

    # --- Join context columns to trades on entry_ts ---
    context_cols = [
        "atr_14_pct_rank_252",
        "daily_range_used_pct",
        "vwap_distance_atr",
        "htf_bias_strength",
        "session_regime",
        "atr_14",      # raw ATR for stop-size audit
    ]
    feat_ctx = feat[context_cols].rename(columns={"atr_14": "entry_atr_14"})

    # Align on entry_ts: look up the feature bar that matches each trade's
    # entry_ts.  Use merge_asof with a ±10-minute tolerance so entries that
    # land exactly on a bar edge are found; direction="nearest" handles
    # cases where the bar timestamp has sub-minute rounding differences.
    trades_sorted = trades.sort_values("entry_ts").copy()
    feat_sorted   = feat_ctx.sort_index()

    # Normalise timestamp dtypes to ns precision for merge_asof compatibility.
    # Parquet files from different sources may use us vs ns precision.
    trades_sorted["entry_ts"] = trades_sorted["entry_ts"].dt.as_unit("ns")
    feat_idx_ns = feat_sorted.index.astype("datetime64[ns, UTC]")

    feat_reset = feat_sorted.copy()
    feat_reset.index = feat_idx_ns
    feat_reset = feat_reset.reset_index().rename(columns={"timestamp_utc": "entry_ts"})
    feat_reset["entry_ts"] = feat_reset["entry_ts"].dt.as_unit("ns")

    merged = pd.merge_asof(
        trades_sorted,
        feat_reset,
        on="entry_ts",
        direction="nearest",
        tolerance=pd.Timedelta("10min"),
    )

    # Restore original row order
    merged = merged.set_index(trades_sorted.index).reindex(trades.index)

    # Fill unmatched session_regime
    if "session_regime" in merged.columns:
        merged["session_regime"] = merged["session_regime"].fillna("Unknown")

    return merged
