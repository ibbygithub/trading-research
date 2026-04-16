"""Relative Strength Index (RSI)."""

from __future__ import annotations

import pandas as pd


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute RSI using Wilder's smoothing.

    Standard RSI formula:
        delta = close.diff()
        avg_gain = Wilder EMA of max(delta, 0)
        avg_loss = Wilder EMA of max(-delta, 0)
        RS = avg_gain / avg_loss
        RSI = 100 - 100 / (1 + RS)

    Wilder smoothing uses alpha = 1/period (ewm span = 2*period - 1).

    Parameters
    ----------
    df:
        DataFrame with a ``close`` column.
    period:
        RSI lookback period (default 14).

    Returns
    -------
    pd.Series named ``"rsi_{period}"`` in range [0, 100]; first ``period``
    rows are NaN.
    """
    close = df["close"]
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    span = 2 * period - 1
    avg_gain = gain.ewm(span=span, adjust=False).mean()
    avg_loss = loss.ewm(span=span, adjust=False).mean()

    # When avg_loss == 0 (all gains), RSI = 100 by convention.
    # .where(cond, other) keeps values where cond is True, replaces with `other` otherwise.
    avg_loss_nz = avg_loss.where(avg_loss != 0.0)  # NaN where avg_loss = 0
    rs = avg_gain / avg_loss_nz
    rsi = (100.0 - (100.0 / (1.0 + rs))).where(avg_loss != 0.0, 100.0)

    rsi.iloc[:period] = float("nan")
    return rsi.rename(f"rsi_{period}")
