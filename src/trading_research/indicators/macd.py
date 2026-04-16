"""MACD (Moving Average Convergence/Divergence) with histogram derived features.

Conventional 12/26/9 settings on every timeframe — this is intentional.
Traders react to the consensus chart; adjusting settings per timeframe means
reacting to a picture nobody else is looking at.

Derived histogram features encode the "fading momentum" pattern:
MACD histogram above zero but each bar smaller than the last for 3-4 bars
→ look to short (and mirror for longs).
"""

from __future__ import annotations

import pandas as pd


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD line, signal line, histogram, and histogram derived features.

    Columns returned
    ----------------
    macd                        : EMA(fast) - EMA(slow)
    macd_signal                 : EMA(signal) of macd
    macd_hist                   : macd - macd_signal
    macd_hist_above_zero        : bool, current histogram > 0
    macd_hist_slope             : first difference of histogram (hist[i] - hist[i-1])
    macd_hist_bars_since_zero_cross : int, bars since sign of histogram last flipped
    macd_hist_decline_streak    : signed int; positive = rising streak (each bar larger
                                  than last), negative = declining streak (each bar
                                  smaller than last).

    Decline streak encoding:
    - +N means the histogram has been growing (in absolute direction matching sign)
      for N consecutive bars.
    - -N means the histogram has been shrinking for N consecutive bars.
    - Resets to ±1 when the direction changes within the same sign regime.
    - Resets to 0 across a zero crossing.
    - This is the "above zero but shrinking for 3-4 bars → look to short" feature.
      Filter: hist_above_zero & hist_decline_streak <= -3

    First ``slow + signal - 1`` rows are NaN for the core MACD columns.
    Derived features are computed from valid histogram values only.

    Parameters
    ----------
    df:
        DataFrame with a ``close`` column.
    fast, slow, signal:
        MACD parameters (default 12/26/9).
    """
    close = df["close"]

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line

    warmup = slow + signal - 1
    macd_line.iloc[:warmup] = float("nan")
    signal_line.iloc[:warmup] = float("nan")
    hist.iloc[:warmup] = float("nan")

    above_zero = hist > 0

    slope = hist.diff()

    bars_since_cross = _bars_since_zero_cross(hist)
    decline_streak = _decline_streak(hist)

    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": hist,
            "macd_hist_above_zero": above_zero,
            "macd_hist_slope": slope,
            "macd_hist_bars_since_zero_cross": bars_since_cross,
            "macd_hist_decline_streak": decline_streak,
        },
        index=df.index,
    )


def _bars_since_zero_cross(hist: pd.Series) -> pd.Series:
    """Count bars since the histogram last crossed zero.

    Increments each bar; resets to 0 at each sign flip. NaN while histogram
    is in warmup (NaN) period.
    """
    result = pd.array([pd.NA] * len(hist), dtype="Int64")
    current = pd.NA
    prev_sign = None

    for i, val in enumerate(hist):
        if pd.isna(val):
            current = pd.NA
            prev_sign = None
            continue
        sign = 1 if val > 0 else (-1 if val < 0 else 0)
        if prev_sign is None or sign != prev_sign:
            current = 0
        else:
            current = (current if not pd.isna(current) else -1) + 1
        result[i] = current
        prev_sign = sign

    return pd.Series(result, index=hist.index, name="macd_hist_bars_since_zero_cross")


def _decline_streak(hist: pd.Series) -> pd.Series:
    """Signed streak for fading-momentum detection.

    For a histogram bar at index i (where hist[i] is not NaN):
    - Compare |hist[i]| vs |hist[i-1]|.
    - If |hist[i]| > |hist[i-1]|: momentum is strengthening → streak > 0.
    - If |hist[i]| < |hist[i-1]|: momentum is fading → streak < 0.
    - If equal: continue previous streak direction.
    - Resets to ±1 on direction change.
    - Resets to +1 at a zero crossing (first bar of new sign regime).

    Returns signed integers; NaN in warmup.
    """
    result = pd.array([pd.NA] * len(hist), dtype="Int64")
    streak = pd.NA
    prev_abs = None
    prev_sign = None

    for i, val in enumerate(hist):
        if pd.isna(val):
            streak = pd.NA
            prev_abs = None
            prev_sign = None
            result[i] = pd.NA
            continue

        sign = 1 if val > 0 else -1
        abs_val = abs(val)

        # Zero crossing or first valid bar: reset.
        if prev_sign is None or sign != prev_sign:
            streak = 1
        elif prev_abs is None:
            streak = 1
        else:
            # Within same sign regime.
            if abs_val > prev_abs:
                # Growing: increment positive or reset to +1.
                streak = (streak + 1) if (not pd.isna(streak) and streak > 0) else 1
            elif abs_val < prev_abs:
                # Shrinking: increment negative or reset to -1.
                streak = (streak - 1) if (not pd.isna(streak) and streak < 0) else -1
            # Equal: keep streak unchanged.

        result[i] = streak
        prev_abs = abs_val
        prev_sign = sign

    return pd.Series(result, index=hist.index, name="macd_hist_decline_streak")
