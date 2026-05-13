"""FX Donchian Breakout with Daily EMA Trend Confirmation.

Designed by the quant mentor for 6C (Canadian Dollar) on 60-minute bars.
The strategy buys 20-bar high breakouts when the daily EMA(50)/EMA(200)
trend is up, and sells 20-bar low breakouts when the daily trend is down.
The premise is that 6C exhibits bimodal regime structure (oil-driven trends
interspersed with chop) and a breakout strategy with a longer-term trend
filter catches the trending regimes while avoiding the chop.

Entry logic
-----------
LONG — both conditions on the signal bar's close:
  1. close > donchian_upper.shift(1)
     (current bar made a new 20-bar high vs the *prior* 20 bars,
     shifted to avoid look-ahead)
  2. daily_ema_50 > daily_ema_200
     (long-term trend is up; daily EMAs are projected from daily bars
     onto 60m via the features layer with built-in 1-bar shift)

SHORT — mirror image.

Exits
-----
  target : signal_bar_close ± target_atr_mult * atr_14
  stop   : signal_bar_close ∓ stop_atr_mult * atr_14
  time   : engine handles via max_holding_bars (typically 48 for ~2 days)
  eod    : explicitly disabled in YAML (eod_flat: false) — breakouts can
           hold overnight when an oil-driven move is in progress.

Look-ahead prevention
---------------------
Donchian channel is shifted by 1 bar before comparison. Daily EMAs come
from features.py which projects them with a 1-bar shift (see
indicators/features.py). All other indicators use only data through the
bar's close. Engine fills next-bar-open.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "close",
    "donchian_upper",
    "donchian_lower",
    "atr_14",
    "daily_ema_50",
    "daily_ema_200",
)


def generate_signals(
    df: pd.DataFrame,
    *,
    target_atr_mult: float = 3.0,
    stop_atr_mult: float = 1.5,
) -> pd.DataFrame:
    """Generate Donchian-breakout signals filtered by daily EMA trend.

    Parameters
    ----------
    df:
        Features DataFrame (index = tz-aware UTC DatetimeIndex). Must contain
        columns from ``REQUIRED_COLUMNS``. The Donchian period and daily EMA
        periods are determined by the feature set used to build ``df``;
        base-v1 uses Donchian(20) and daily EMA(50)/EMA(200).
    target_atr_mult:
        ATR multiples for the take-profit distance from signal-bar close.
    stop_atr_mult:
        ATR multiples for the stop distance from signal-bar close.

    Returns
    -------
    DataFrame with columns ``signal``, ``stop``, ``target`` indexed identically
    to ``df``.
    """
    _validate_columns(df)

    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        raise ValueError("df.index must be a tz-aware DatetimeIndex.")

    close = df["close"].to_numpy(dtype=float, na_value=np.nan)
    atr = df["atr_14"].to_numpy(dtype=float, na_value=np.nan)
    ema_fast = df["daily_ema_50"].to_numpy(dtype=float, na_value=np.nan)
    ema_slow = df["daily_ema_200"].to_numpy(dtype=float, na_value=np.nan)

    # Shift Donchian by 1 so close is compared against the *prior* 20-bar
    # high/low — the current bar is not in its own benchmark.
    donchian_upper_prev = df["donchian_upper"].shift(1).to_numpy(dtype=float, na_value=np.nan)
    donchian_lower_prev = df["donchian_lower"].shift(1).to_numpy(dtype=float, na_value=np.nan)

    n = len(df)
    signal = np.zeros(n, dtype=np.int8)
    stop_arr = np.full(n, np.nan, dtype=float)
    target_arr = np.full(n, np.nan, dtype=float)

    finite_inputs = (
        np.isfinite(close)
        & np.isfinite(atr)
        & np.isfinite(ema_fast)
        & np.isfinite(ema_slow)
        & np.isfinite(donchian_upper_prev)
        & np.isfinite(donchian_lower_prev)
    )

    trend_up = ema_fast > ema_slow
    trend_down = ema_fast < ema_slow
    breakout_up = close > donchian_upper_prev
    breakout_down = close < donchian_lower_prev

    long_mask = finite_inputs & trend_up & breakout_up
    short_mask = finite_inputs & trend_down & breakout_down

    long_stop = close - stop_atr_mult * atr
    long_target = close + target_atr_mult * atr
    short_stop = close + stop_atr_mult * atr
    short_target = close - target_atr_mult * atr

    valid_long = long_mask & np.isfinite(long_stop) & np.isfinite(long_target)
    valid_short = short_mask & np.isfinite(short_stop) & np.isfinite(short_target)

    conflict = valid_long & valid_short
    valid_long = valid_long & ~conflict
    valid_short = valid_short & ~conflict

    signal[valid_long] = 1
    signal[valid_short] = -1
    stop_arr[valid_long] = long_stop[valid_long]
    stop_arr[valid_short] = short_stop[valid_short]
    target_arr[valid_long] = long_target[valid_long]
    target_arr[valid_short] = short_target[valid_short]

    return pd.DataFrame(
        {"signal": signal, "stop": stop_arr, "target": target_arr},
        index=df.index,
    )


def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(
            f"Features DataFrame is missing required columns: {missing}. "
            f"Build the base-v1 feature set first."
        )
