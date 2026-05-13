"""FX Session-VWAP Mean Reversion with ADX Trend Filter.

Designed by the quant mentor for 6A (Australian Dollar) on 15-minute bars.
The strategy fades extensions of price away from session VWAP, but only when
ADX confirms the market is range-bound (no strong trend). The ADX filter is
the lesson learned from `vwap-reversion-v1` failing on 6E: VWAP mean
reversion in a trending FX market gets repeatedly run over.

Entry logic
-----------
LONG — all three conditions on the signal bar's close:
  1. close < (vwap_session - entry_atr_mult * atr_14)
  2. adx_14 < adx_max
  3. Bar timestamp falls in the London/NY overlap window (UTC).

SHORT — mirror image.

Exits
-----
  target : vwap_session price at signal time
  stop   : signal_bar_close ± stop_atr_mult * atr_14
  eod    : engine handles via eod_flat=True

Look-ahead prevention
---------------------
All values used (close, vwap_session, atr_14, adx_14) are computed from data
through the bar's close. The engine uses next-bar-open fills, so signals
generated on bar T's close are acted on bar T+1's open.
"""

from __future__ import annotations

from datetime import time as dtime

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "close",
    "vwap_session",
    "atr_14",
    "adx_14",
)


def generate_signals(
    df: pd.DataFrame,
    *,
    entry_atr_mult: float = 1.5,
    stop_atr_mult: float = 1.5,
    adx_max: float = 22.0,
    overlap_start_utc: str = "12:00",
    overlap_end_utc: str = "17:00",
) -> pd.DataFrame:
    """Generate VWAP-mean-reversion signals with ADX trend filter.

    Parameters
    ----------
    df:
        Features DataFrame (index = tz-aware UTC DatetimeIndex). Must contain
        columns from ``REQUIRED_COLUMNS``.
    entry_atr_mult:
        ATR multiples beyond VWAP that define the entry threshold. 1.5 means
        a long is taken when close < vwap - 1.5 * ATR.
    stop_atr_mult:
        ATR multiples for the stop distance from signal-bar close.
    adx_max:
        ADX threshold below which the market is classified as range-bound.
        Entry is suppressed when adx_14 >= adx_max.
    overlap_start_utc, overlap_end_utc:
        London/NY overlap window in UTC, inclusive of start, exclusive of end.
        Format ``"HH:MM"``.

    Returns
    -------
    DataFrame with columns ``signal``, ``stop``, ``target`` indexed identically
    to ``df``.
    """
    _validate_columns(df)

    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        raise ValueError("df.index must be a tz-aware DatetimeIndex.")

    start_t = _parse_hhmm(overlap_start_utc)
    end_t = _parse_hhmm(overlap_end_utc)

    close = df["close"].to_numpy(dtype=float, na_value=np.nan)
    vwap = df["vwap_session"].to_numpy(dtype=float, na_value=np.nan)
    atr = df["atr_14"].to_numpy(dtype=float, na_value=np.nan)
    adx = df["adx_14"].to_numpy(dtype=float, na_value=np.nan)

    n = len(df)
    signal = np.zeros(n, dtype=np.int8)
    stop_arr = np.full(n, np.nan, dtype=float)
    target_arr = np.full(n, np.nan, dtype=float)

    bar_times = df.index.tz_convert("UTC").time
    in_window = np.array([_in_window(t, start_t, end_t) for t in bar_times], dtype=bool)

    finite_inputs = (
        np.isfinite(close)
        & np.isfinite(vwap)
        & np.isfinite(atr)
        & np.isfinite(adx)
    )
    not_trending = adx < adx_max
    long_extension = close < (vwap - entry_atr_mult * atr)
    short_extension = close > (vwap + entry_atr_mult * atr)

    long_mask = in_window & finite_inputs & not_trending & long_extension
    short_mask = in_window & finite_inputs & not_trending & short_extension

    long_stop = close - stop_atr_mult * atr
    short_stop = close + stop_atr_mult * atr

    valid_long = long_mask & np.isfinite(long_stop)
    valid_short = short_mask & np.isfinite(short_stop)

    conflict = valid_long & valid_short
    valid_long = valid_long & ~conflict
    valid_short = valid_short & ~conflict

    signal[valid_long] = 1
    signal[valid_short] = -1
    stop_arr[valid_long] = long_stop[valid_long]
    stop_arr[valid_short] = short_stop[valid_short]
    target_arr[valid_long | valid_short] = vwap[valid_long | valid_short]

    return pd.DataFrame(
        {"signal": signal, "stop": stop_arr, "target": target_arr},
        index=df.index,
    )


def _parse_hhmm(s: str) -> dtime:
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Expected HH:MM, got {s!r}")
    return dtime(int(parts[0]), int(parts[1]))


def _in_window(t: dtime, start: dtime, end: dtime) -> bool:
    return start <= t < end


def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(
            f"Features DataFrame is missing required columns: {missing}. "
            f"Build the base-v1 feature set first."
        )
