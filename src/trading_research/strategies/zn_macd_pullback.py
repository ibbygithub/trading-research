"""ZN Multi-Timeframe MACD Histogram Pullback strategy.

Entry logic
-----------
LONG — all five conditions must be true on the signal bar:
  1. daily_macd_hist > 0          (daily bias: bullish)
  2. htf_60m_macd_hist > 0        (60m bias: bullish)
  3. htf_60m_macd_hist_slope >= 0 (60m not declining: stable or recovering)
  4. macd_hist < 0                (5m pulled back below zero)
  5. macd_hist_decline_streak <= -streak_bars
                                  (5m pullback is fading — each bar less negative)

SHORT — mirror image:
  1. daily_macd_hist < 0
  2. htf_60m_macd_hist < 0
  3. htf_60m_macd_hist_slope >= 0 (same: 60m not declining further)
  4. macd_hist > 0
  5. macd_hist_decline_streak <= -streak_bars (each bar less positive)

Exits
-----
  stop   : signal bar close ± (atr_stop_mult × atr_14)
  target : MACD zero-cross — exit when the 5m histogram crosses back above zero
           (for longs: emit signal=-1 when daily>0 and macd_hist>=0)
           (for shorts: emit signal=+1 when daily<0 and macd_hist<=0)
  eod    : engine closes at RTH close (15:00 ET) — not set here

  The zero-cross exit emits an opposing signal on the exit bar. The engine's
  NaN-stop guard prevents these exit-only signals from opening new positions.

60m HTF alignment
-----------------
The base-v1 feature set only projects daily bias. 60m MACD is computed
here from the 60m CLEAN parquet and merged onto the 5m index.

Look-ahead prevention: shift the 60m MACD by 1 bar BEFORE merging, so
each 5m bar within a 60m period sees the *previous* completed 60m bar's
values. The first bars of the series will be NaN and are skipped (no entry).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from trading_research.indicators.macd import compute_macd

# Default data root — same anchor pattern used across the project.
_DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def generate_signals(
    df: pd.DataFrame,
    *,
    streak_bars: int = 3,
    atr_stop_mult: float = 2.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal_period: int = 9,
    data_root: Path | None = None,
) -> pd.DataFrame:
    """Generate entry and exit signals for the ZN MACD pullback strategy.

    Parameters
    ----------
    df:
        5m features DataFrame (index = tz-aware UTC DatetimeIndex).
        Required columns: ``macd_hist``, ``macd_hist_decline_streak``,
        ``daily_macd_hist``, ``atr_14``.
    streak_bars:
        Consecutive fading bars required on the 5m histogram.
    atr_stop_mult:
        ATR multiplier for stop distance from signal bar close.
    macd_fast, macd_slow, macd_signal_period:
        MACD parameters used when computing 60m MACD from the CLEAN parquet.
    data_root:
        Override for the ``data/`` directory. Used in tests.

    Returns
    -------
    DataFrame with same index as ``df`` and columns:
        ``signal``   : int8  — +1 long entry / close short, -1 short entry / close long, 0 flat
        ``stop``     : float — stop price (NaN on non-entry bars)
        ``target``   : float — always NaN (exit is MACD zero-cross, not a price target)

    Signal semantics
    ----------------
    - signal=+1 with finite stop  : enter long
    - signal=-1 with finite stop  : enter short
    - signal=-1 with NaN stop     : close any active long (zero-cross exit)
    - signal=+1 with NaN stop     : close any active short (zero-cross exit)
    The engine's NaN-stop guard prevents exit signals from opening positions.
    """
    root = data_root or _DEFAULT_DATA_ROOT

    # ------------------------------------------------------------------
    # Step 1 — Load 60m HTF bias
    # ------------------------------------------------------------------
    htf = _load_60m_macd(root, macd_fast, macd_slow, macd_signal_period)

    # Align 60m values to 5m index: each 5m bar sees the most recent
    # completed 60m bar (backward merge preserves that).
    # Build a merge-key DataFrame from the index directly — avoids depending
    # on the index having a name (in tests the index may be unnamed).
    ts_series = df.index.to_series().rename("timestamp_utc").reset_index(drop=True)
    df_ts = pd.DataFrame({"timestamp_utc": ts_series})

    htf_aligned = pd.merge_asof(
        df_ts,
        htf,
        on="timestamp_utc",
        direction="backward",
    )
    htf_60m_hist = htf_aligned["htf_60m_macd_hist"].values
    htf_60m_slope = htf_aligned["htf_60m_macd_hist_slope"].values

    # ------------------------------------------------------------------
    # Step 2 — Pull required columns from df
    # ------------------------------------------------------------------
    close = df["close"].values
    macd_hist = df["macd_hist"].values
    streak = df["macd_hist_decline_streak"].values
    daily_hist = df["daily_macd_hist"].values
    atr = df["atr_14"].values

    n = len(df)
    signal = np.zeros(n, dtype=np.int8)
    stop_arr = np.full(n, np.nan)
    target_arr = np.full(n, np.nan)   # Always NaN: exit is MACD zero-cross

    # ------------------------------------------------------------------
    # Step 3 — Apply entry conditions vectorised
    # ------------------------------------------------------------------

    # Convert streak to float so comparisons handle pd.NA / Int64 cleanly.
    streak_f = _to_float(streak)

    # Long conditions
    c1_long = daily_hist > 0
    c2_long = htf_60m_hist > 0
    c3_long = htf_60m_slope >= 0
    c4_long = macd_hist < 0
    c5_long = streak_f <= -streak_bars

    long_mask = c1_long & c2_long & c3_long & c4_long & c5_long

    # Short conditions
    c1_short = daily_hist < 0
    c2_short = htf_60m_hist < 0
    c3_short = htf_60m_slope >= 0
    c4_short = macd_hist > 0
    c5_short = streak_f <= -streak_bars

    short_mask = c1_short & c2_short & c3_short & c4_short & c5_short

    # ------------------------------------------------------------------
    # Step 4 — Compute stops; suppress entry when stop is invalid
    # ------------------------------------------------------------------
    long_stop = close - atr_stop_mult * atr
    short_stop = close + atr_stop_mult * atr

    valid_long = long_mask & np.isfinite(long_stop)
    valid_short = short_mask & np.isfinite(short_stop)

    # Long and short cannot both be true on the same bar (they are mutually
    # exclusive by construction since daily_hist > 0 vs < 0). If for some
    # reason there's an edge-case overlap, prefer flat.
    conflict = valid_long & valid_short
    valid_long = valid_long & ~conflict
    valid_short = valid_short & ~conflict

    # ------------------------------------------------------------------
    # Step 5 — Zero-cross exit signals
    # ------------------------------------------------------------------
    # Emit an opposing signal when the 5m histogram crosses back through zero.
    # These are assigned first; entry signals override them below.
    # Overlap is impossible by construction:
    #   - long entry requires macd_hist < 0; long exit requires macd_hist >= 0
    #   - short entry requires daily < 0; long exit requires daily > 0
    long_exit = (daily_hist > 0) & (macd_hist >= 0)
    short_exit = (daily_hist < 0) & (macd_hist <= 0)

    signal[long_exit] = -1    # close any active long
    signal[short_exit] = 1   # close any active short

    # Entry signals override exit signals (no overlap possible).
    signal[valid_long] = 1
    signal[valid_short] = -1

    # Stops only set on entry bars; exit-only bars have NaN stop.
    # The engine uses NaN stop as the guard that prevents phantom entries.
    stop_arr[valid_long] = long_stop[valid_long]
    stop_arr[valid_short] = short_stop[valid_short]

    return pd.DataFrame(
        {"signal": signal, "stop": stop_arr, "target": target_arr},
        index=df.index,
    )


# ---------------------------------------------------------------------------
# 60m HTF MACD loader
# ---------------------------------------------------------------------------


def _load_60m_macd(
    data_root: Path,
    fast: int,
    slow: int,
    signal_period: int,
) -> pd.DataFrame:
    """Load 60m CLEAN parquet, compute MACD, return aligned HTF DataFrame.

    The returned DataFrame has:
        timestamp_utc           : tz-aware UTC (shifted forward by 1 bar)
        htf_60m_macd_hist       : MACD histogram value
        htf_60m_macd_hist_slope : bar-to-bar change in histogram

    Shift(1) is applied BEFORE returning so that when merged onto the 5m
    index each 5m bar sees the *previous* completed 60m bar's values.
    This is the same look-ahead prevention used for daily bias in features.py.
    """
    clean_dir = data_root / "clean"
    matches = sorted(clean_dir.glob("ZN_backadjusted_60m_*.parquet"))
    if not matches:
        raise FileNotFoundError(
            f"No ZN 60m backadjusted parquet found in {clean_dir}. "
            "Run: uv run trading-research rebuild clean --symbol ZN"
        )
    path = matches[-1]

    df60 = pd.read_parquet(path, engine="pyarrow")
    df60["timestamp_utc"] = pd.to_datetime(df60["timestamp_utc"], utc=True)
    df60 = df60.sort_values("timestamp_utc").reset_index(drop=True)

    macd_df = compute_macd(df60, fast=fast, slow=slow, signal=signal_period)
    hist = macd_df["macd_hist"]
    slope = hist.diff()

    # Shift by 1 bar: the 5m bars within a 60m period see the *previous*
    # completed 60m bar's MACD, not the one still forming.
    result = pd.DataFrame(
        {
            "timestamp_utc": df60["timestamp_utc"],
            "htf_60m_macd_hist": hist.shift(1).values,
            "htf_60m_macd_hist_slope": slope.shift(1).values,
        }
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float(arr) -> np.ndarray:
    """Convert a possibly Int64 / object array to float64, NaN-safe."""
    try:
        return np.array(arr, dtype=float)
    except (TypeError, ValueError):
        # Handles pandas nullable Int64 arrays with pd.NA.
        return np.array(
            [float(v) if v is not pd.NA and v is not None else np.nan for v in arr],
            dtype=float,
        )
