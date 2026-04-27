"""ZN Session VWAP Mean Reversion strategy — v2.

Entry logic
-----------
LONG — all conditions must be true on the signal bar:
  1. close < vwap_session - vwap_session_std_2_0   (price below lower 2σ band)
  2. daily_macd_hist > 0                            (daily bias: bullish)
  3. bar is within RTH: 13:20–20:00 UTC (08:20–15:00 ET)

SHORT — mirror image:
  1. close > vwap_session + vwap_session_std_2_0   (price above upper 2σ band)
  2. daily_macd_hist < 0                            (daily bias: bearish)
  3. bar is within RTH

Exits
-----
  target : price crosses back through session VWAP
           long exit  → emit signal=-1 (NaN stop) when close >= vwap_session
           short exit → emit signal=+1 (NaN stop) when close <= vwap_session
  stop   : signal bar close ± (atr_stop_mult × atr_14)  — set by engine
  eod    : engine closes at 15:00 ET

No MACD confirmation on the 5m frame. The band touch is the primary signal;
daily MACD provides the directional filter. Simplest testable hypothesis.

Look-ahead notes
----------------
  vwap_session       — cumulative from session open through bar T (clean)
  vwap_session_std_2_0 — same cumulative window, volume-weighted σ × 2 (clean)
  daily_macd_hist    — projected from prior day's completed bar, shifted 1D (clean)
  atr_14             — Wilder ATR computed through bar T close (clean)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# RTH window for ZN: 08:20–15:00 ET = 13:20–20:00 UTC
_RTH_START_UTC = 13 * 60 + 20   # minutes since midnight UTC
_RTH_END_UTC   = 20 * 60 + 0


def generate_signals(
    df: pd.DataFrame,
    *,
    atr_stop_mult: float = 2.0,
    vwap_band_sigma: float = 2.0,
    blackout_calendars: list[str] | None = None,
    data_root=None,  # accepted but unused; keeps engine interface consistent
) -> pd.DataFrame:
    """Generate entry and exit signals for the ZN VWAP reversion strategy.

    Parameters
    ----------
    df:
        5m features DataFrame (index = tz-aware UTC DatetimeIndex).
        Required columns: ``close``, ``vwap_session``, ``vwap_session_std_2_0``,
        ``daily_macd_hist``, ``atr_14``.
    atr_stop_mult:
        ATR multiplier for stop distance from signal bar close.
    vwap_band_sigma:
        Which pre-computed σ column to use. 2.0 → ``vwap_session_std_2_0``.
        Only 1.0, 1.5, 2.0, 3.0 are available in the base-v1 feature set.
    blackout_calendars:
        Calendar names for event-day suppression (``"fomc"``, ``"cpi"``, ``"nfp"``).
        Entry signals on matching dates are zeroed; exit signals are preserved.
    data_root:
        Ignored. Present for engine interface compatibility.

    Returns
    -------
    DataFrame with same index as ``df`` and columns:
        ``signal``  : int8  — +1 long entry / close short, -1 short entry / close long, 0 flat
        ``stop``    : float — stop price (NaN on non-entry bars)
        ``target``  : float — always NaN (exit is VWAP crossing, not a fixed price)

    Signal semantics
    ----------------
    - signal=+1 with finite stop  : enter long
    - signal=-1 with finite stop  : enter short
    - signal=-1 with NaN stop     : close any active long (VWAP crossing)
    - signal=+1 with NaN stop     : close any active short (VWAP crossing)
    The engine's NaN-stop guard prevents exit signals from opening positions.
    """
    # ------------------------------------------------------------------
    # Step 1 — Resolve the σ band column name
    # ------------------------------------------------------------------
    sigma_col = _sigma_column(vwap_band_sigma)
    _require_columns(df, ["close", "vwap_session", sigma_col, "daily_macd_hist", "atr_14"])

    close      = df["close"].to_numpy(dtype=float)
    vwap       = df["vwap_session"].to_numpy(dtype=float)
    vwap_dev   = df[sigma_col].to_numpy(dtype=float)   # deviation amount, not band price
    daily_hist = df["daily_macd_hist"].to_numpy(dtype=float)
    atr        = df["atr_14"].to_numpy(dtype=float)

    n = len(df)
    signal     = np.zeros(n, dtype=np.int8)
    stop_arr   = np.full(n, np.nan)
    target_arr = np.full(n, np.nan)   # engine uses VWAP crossing; price target is dynamic

    # ------------------------------------------------------------------
    # Step 2 — RTH mask: 13:20–20:00 UTC inclusive
    # ------------------------------------------------------------------
    minutes_utc = df.index.hour * 60 + df.index.minute
    rth_mask = (minutes_utc >= _RTH_START_UTC) & (minutes_utc < _RTH_END_UTC)

    # ------------------------------------------------------------------
    # Step 3 — Band levels
    # ------------------------------------------------------------------
    lower_band = vwap - vwap_dev
    upper_band = vwap + vwap_dev

    # ------------------------------------------------------------------
    # Step 4 — Entry conditions
    # ------------------------------------------------------------------
    long_entry  = rth_mask & (close < lower_band) & (daily_hist > 0)
    short_entry = rth_mask & (close > upper_band) & (daily_hist < 0)

    # ------------------------------------------------------------------
    # Step 5 — Stops; suppress entry when stop or band is invalid
    # ------------------------------------------------------------------
    long_stop  = close - atr_stop_mult * atr
    short_stop = close + atr_stop_mult * atr

    valid_long  = long_entry  & np.isfinite(long_stop)  & np.isfinite(lower_band)
    valid_short = short_entry & np.isfinite(short_stop) & np.isfinite(upper_band)

    # Mutually exclusive by construction (daily_hist > 0 vs < 0), but guard anyway.
    conflict    = valid_long & valid_short
    valid_long  = valid_long  & ~conflict
    valid_short = valid_short & ~conflict

    # ------------------------------------------------------------------
    # Step 6 — VWAP-crossing exit signals (assigned before entries)
    # ------------------------------------------------------------------
    # Exit signals fire regardless of RTH — if price reverts during RTH
    # and we're still holding near close, the engine handles EOD anyway.
    # NaN stop on these bars prevents the engine from opening a new position.
    long_exit  = (daily_hist > 0) & (close >= vwap) & np.isfinite(vwap)
    short_exit = (daily_hist < 0) & (close <= vwap) & np.isfinite(vwap)

    signal[long_exit]  = -1   # close any active long
    signal[short_exit] =  1   # close any active short

    # Entry signals override exit signals (no overlap by construction:
    # long entry requires close < lower_band < vwap; long exit requires close >= vwap).
    signal[valid_long]  =  1
    signal[valid_short] = -1

    stop_arr[valid_long]  = long_stop[valid_long]
    stop_arr[valid_short] = short_stop[valid_short]

    # ------------------------------------------------------------------
    # Step 7 — Event-day blackout: suppress entry signals on FOMC/CPI/NFP
    # ------------------------------------------------------------------
    if blackout_calendars:
        from trading_research.strategies.event_blackout import load_blackout_dates

        blackout_set = load_blackout_dates(blackout_calendars)
        et_dates = df.index.tz_convert("America/New_York").date
        entry_on_blackout = (
            np.array([d in blackout_set for d in et_dates], dtype=bool)
            & np.isfinite(stop_arr)
        )
        signal[entry_on_blackout]   = 0
        stop_arr[entry_on_blackout] = np.nan

    return pd.DataFrame(
        {"signal": signal, "stop": stop_arr, "target": target_arr},
        index=df.index,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIGMA_COLUMNS = {
    1.0: "vwap_session_std_1_0",
    1.5: "vwap_session_std_1_5",
    2.0: "vwap_session_std_2_0",
    3.0: "vwap_session_std_3_0",
}


def _sigma_column(sigma: float) -> str:
    col = _SIGMA_COLUMNS.get(sigma)
    if col is None:
        raise ValueError(
            f"vwap_band_sigma={sigma!r} not available. "
            f"Choose from: {sorted(_SIGMA_COLUMNS)}"
        )
    return col


def _require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"generate_signals: missing required columns: {missing}. "
            "Rebuild the feature parquet with the base-v1 feature set."
        )
