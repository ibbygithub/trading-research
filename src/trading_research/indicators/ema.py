"""Exponential Moving Average."""

from __future__ import annotations

import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Compute an exponential moving average.

    Uses ``pandas.Series.ewm`` with ``span=period`` (standard EMA
    definition: alpha = 2 / (period + 1)).

    First ``period - 1`` rows are NaN to signal warm-up.  Strictly
    speaking EWM produces values from row 0, but those early values are
    unreliable — masking them forces callers to be honest about look-ahead.

    Parameters
    ----------
    series:
        Close prices (or any numeric series).
    period:
        Number of bars in the EMA window (e.g., 20, 50, 200).

    Returns
    -------
    pd.Series with the same index as ``series``.
    """
    result = series.ewm(span=period, adjust=False).mean()
    # Mask warm-up rows so downstream code can't silently use unreliable values.
    result.iloc[: period - 1] = float("nan")
    return result.rename(f"ema_{period}")
