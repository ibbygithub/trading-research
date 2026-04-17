"""Average True Range (ATR)."""

from __future__ import annotations

import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ATR using Wilder's smoothing.

    True Range is the maximum of:
    - high − low
    - |high − previous close|
    - |low  − previous close|

    Smoothing uses Wilder's EMA: alpha = 1/period  (ewm span = 2*period - 1).

    Parameters
    ----------
    df:
        DataFrame with columns ``high``, ``low``, ``close``.
    period:
        Smoothing period (default 14).

    Returns
    -------
    pd.Series named ``"atr_{period}"``; first ``period`` rows are NaN.
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # Wilder smoothing: span = 2*period - 1 is equivalent to alpha = 1/period.
    atr = tr.ewm(span=2 * period - 1, adjust=False).mean()

    # Mask warm-up rows (first row has no prev_close, so TR is unreliable too).
    atr.iloc[:period] = float("nan")
    return atr.rename(f"atr_{period}")
