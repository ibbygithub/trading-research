"""Average Directional Index (ADX) — regime classifier.

ADX < 20  : ranging, mean-reversion strategies are in their element.
ADX 20-25 : borderline.
ADX > 25  : trending, mean-reversion strategies should down-weight or stop.
ADX > 40  : strong trend.
"""

from __future__ import annotations

import pandas as pd


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ADX using Wilder's smoothing.

    Algorithm:
        1. True Range (TR), +DM, -DM per bar.
        2. Wilder-smooth each over ``period`` bars (alpha = 1/period).
        3. +DI = 100 × smoothed(+DM) / smoothed(TR)
           -DI = 100 × smoothed(-DM) / smoothed(TR)
        4. DX  = 100 × |+DI - -DI| / (+DI + -DI)
        5. ADX = Wilder EMA of DX over ``period`` bars.

    Parameters
    ----------
    df:
        DataFrame with ``high``, ``low``, ``close`` columns.
    period:
        Wilder smoothing period (default 14).

    Returns
    -------
    pd.Series named ``"adx_{period}"`` in range [0, 100];
    first ``2 * period`` rows are NaN (two warm-up phases).
    """
    high = df["high"]
    low = df["low"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    span = 2 * period - 1  # Wilder: alpha = 1/period
    smoothed_tr = tr.ewm(span=span, adjust=False).mean()
    smoothed_plus_dm = plus_dm.ewm(span=span, adjust=False).mean()
    smoothed_minus_dm = minus_dm.ewm(span=span, adjust=False).mean()

    plus_di = 100.0 * smoothed_plus_dm / smoothed_tr.replace(0, float("nan"))
    minus_di = 100.0 * smoothed_minus_dm / smoothed_tr.replace(0, float("nan"))

    dx_denom = (plus_di + minus_di).replace(0, float("nan"))
    dx = 100.0 * (plus_di - minus_di).abs() / dx_denom

    adx = dx.ewm(span=span, adjust=False).mean()

    # Mask two warm-up phases: once for DM/TR smoothing, once for ADX smoothing.
    adx.iloc[: 2 * period] = float("nan")
    return adx.rename(f"adx_{period}")
