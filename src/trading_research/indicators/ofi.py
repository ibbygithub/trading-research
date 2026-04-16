"""Order Flow Imbalance (OFI).

OFI measures the directional pressure of order flow per bar:
  raw_ofi = (buy_volume - sell_volume) / (buy_volume + sell_volume)

Range: [-1, +1].  +1 = 100% buy-side pressure; -1 = 100% sell-side.

Rolling OFI smooths the raw signal over a window, reducing noise.

Null handling: if buy_volume or sell_volume is null for a bar, that bar's
raw_ofi is NaN, and rolling windows with insufficient non-NaN values also
produce NaN.  Strategies using OFI must handle nulls explicitly.
"""

from __future__ import annotations

import pandas as pd


def compute_ofi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute rolling Order Flow Imbalance.

    Parameters
    ----------
    df:
        DataFrame with ``buy_volume`` and ``sell_volume`` columns
        (both nullable).
    period:
        Rolling mean window (default 14).

    Returns
    -------
    pd.Series named ``"ofi_{period}"`` in range [-1, +1]; NaN where
    insufficient order-flow data is available.
    """
    buy = pd.to_numeric(df["buy_volume"], errors="coerce")
    sell = pd.to_numeric(df["sell_volume"], errors="coerce")

    total = buy + sell
    raw_ofi = (buy - sell) / total.replace(0, float("nan"))

    rolling_ofi = raw_ofi.rolling(period, min_periods=period).mean()
    return rolling_ofi.rename(f"ofi_{period}")
