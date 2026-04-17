"""Bollinger Bands."""

from __future__ import annotations

import pandas as pd


def compute_bollinger(
    df: pd.DataFrame, period: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """Compute Bollinger Bands.

    Columns returned
    ----------------
    bb_mid    : ``period``-bar SMA of close
    bb_upper  : mid + ``num_std`` × rolling std
    bb_lower  : mid − ``num_std`` × rolling std
    bb_pct_b  : (close − lower) / (upper − lower); primary mean-reversion signal.
                0 = at lower band, 1 = at upper band, 0.5 = at midline.
                Values outside [0, 1] mean price is beyond a band.
    bb_width  : (upper − lower) / mid; normalised bandwidth (low = squeeze).

    Parameters
    ----------
    df:
        DataFrame with a ``close`` column.
    period:
        SMA and rolling std window (default 20).
    num_std:
        Number of standard deviations for the bands (default 2.0).

    Returns
    -------
    pd.DataFrame with columns as above; first ``period - 1`` rows are NaN.
    """
    close = df["close"]
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()

    upper = mid + num_std * std
    lower = mid - num_std * std
    band_width = upper - lower

    pct_b = (close - lower) / band_width.replace(0, float("nan"))
    width = band_width / mid.replace(0, float("nan"))

    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_pct_b": pct_b,
            "bb_width": width,
        },
        index=df.index,
    )
