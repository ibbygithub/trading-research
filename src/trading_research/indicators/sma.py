"""Simple Moving Average."""

from __future__ import annotations

import pandas as pd


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Compute a simple moving average.

    Parameters
    ----------
    series:
        Numeric series (typically close prices).
    period:
        Lookback window.

    Returns
    -------
    pd.Series; first ``period - 1`` rows are NaN (warm-up).
    """
    return series.rolling(period).mean().rename(f"sma_{period}")
