"""Donchian Channel."""

from __future__ import annotations

import pandas as pd


def compute_donchian(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Compute Donchian Channel (rolling high/low).

    Columns returned
    ----------------
    donchian_upper : rolling max of ``high`` over ``period`` bars
    donchian_lower : rolling min of ``low`` over ``period`` bars
    donchian_mid   : (upper + lower) / 2

    Parameters
    ----------
    df:
        DataFrame with ``high`` and ``low`` columns.
    period:
        Lookback window (default 20).

    Returns
    -------
    pd.DataFrame; first ``period - 1`` rows are NaN.
    """
    upper = df["high"].rolling(period).max()
    lower = df["low"].rolling(period).min()
    mid = (upper + lower) / 2.0

    return pd.DataFrame(
        {
            "donchian_upper": upper,
            "donchian_lower": lower,
            "donchian_mid": mid,
        },
        index=df.index,
    )
