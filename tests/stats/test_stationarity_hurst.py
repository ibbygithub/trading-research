"""Hurst exponent tests.

R/S method applied to a time series:
  - White noise (i.i.d. returns):           H ≈ 0.5
  - Random walk (cumulative sum of noise):  H ≈ 1.0  (I(1) process)
  - Negatively autocorrelated series:       H < 0.5  (anti-persistent / mean-reverting)
  - Positively autocorrelated (trending):   H > 0.5

The design doc's mean-reversion detection (H < 0.45) requires NEGATIVELY autocorrelated
series at the LEVEL — e.g. AR(1) with φ < 0, or oscillating VWAP spreads.

Reference: design doc §2.2, §4.2, §8.2.  Tolerances ±0.10 per §8.2.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trading_research.stats.stationarity import HurstResult, hurst_exponent

N = 2000  # longer series for more stable Hurst estimates


def _white_noise(n: int = N) -> pd.Series:
    """i.i.d. N(0,1) — represents random-walk RETURNS.  Theoretical H = 0.5."""
    return pd.Series(np.random.default_rng(42).standard_normal(n))


def _random_walk(n: int = N) -> pd.Series:
    """Cumulative sum of white noise — a price level I(1) series.  Theoretical H ≈ 1.0."""
    return pd.Series(np.cumsum(np.random.default_rng(42).standard_normal(n)))


def _ar1(phi: float, n: int = N) -> pd.Series:
    """AR(1): y_t = phi * y_{t-1} + ε_t.

    phi > 0 → persistent (H > 0.5 in R/S).
    phi < 0 → anti-persistent / mean-reverting (H < 0.5 in R/S).
    """
    rng = np.random.default_rng(42)
    eps = rng.standard_normal(n)
    y = np.empty(n)
    y[0] = eps[0]
    for t in range(1, n):
        y[t] = phi * y[t - 1] + eps[t]
    return pd.Series(y)


def _trending(n: int = N) -> pd.Series:
    """Cumulative sum of positive-drift process — I(1) with drift.  H ≈ 1.0."""
    rng = np.random.default_rng(42)
    steps = rng.standard_normal(n) + 0.3  # positive drift
    return pd.Series(np.cumsum(steps))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_hurst_returns_correct_type() -> None:
    result = hurst_exponent(_white_noise())
    assert isinstance(result, HurstResult)


def test_hurst_brownian_motion() -> None:
    """White noise (iid returns) should have Hurst ≈ 0.5 (within ±0.10).

    Note: R/S applied to the *levels* of a random walk gives H ≈ 1.0 (I(1) process).
    This test uses white noise (returns), which is I(0) with H = 0.5.
    """
    result = hurst_exponent(_white_noise())
    h = result.exponent
    assert 0.40 <= h <= 0.60, f"White noise Hurst={h:.4f}, expected [0.40, 0.60]"


def test_hurst_random_walk_levels_high() -> None:
    """R/S on a random walk (level) should return H > 0.5 (I(1) process is persistent)."""
    result = hurst_exponent(_random_walk())
    assert result.exponent > 0.55, (
        f"Random walk level Hurst={result.exponent:.4f}, expected > 0.55"
    )


def test_hurst_trending_series() -> None:
    """Cumulative sum with positive drift should yield Hurst > 0.55."""
    result = hurst_exponent(_trending())
    h = result.exponent
    assert h > 0.55, f"Trending series Hurst={h:.4f}, expected > 0.55"
    assert "TRENDING" in result.interpretation


def test_hurst_mean_reverting_series() -> None:
    """AR(1) φ=-0.7 (strong negative autocorrelation) should yield Hurst < 0.45.

    In financial terms, a VWAP spread that oscillates (positive today → negative
    tomorrow) has negative autocorrelation at the level, producing H < 0.5 via R/S.
    """
    result = hurst_exponent(_ar1(-0.7))
    h = result.exponent
    assert h < 0.45, f"Anti-persistent AR(1) φ=-0.7 Hurst={h:.4f}, expected < 0.45"
    assert "MEAN_REVERTING" in result.interpretation


def test_hurst_ar1_positive_phi_persistent() -> None:
    """AR(1) φ=0.5 has positive autocorrelation → R/S gives H > 0.5 (persistent in levels).

    This confirms the R/S method correctly classifies a positively autocorrelated
    stationary series as 'not mean-reverting' at the level.
    """
    result = hurst_exponent(_ar1(0.5))
    assert result.exponent > 0.50, (
        f"AR(1) φ=0.5 should have H > 0.5 in R/S analysis, got {result.exponent:.4f}"
    )


def test_hurst_r_squared_positive() -> None:
    """R² of the log-log regression should be non-negative."""
    result = hurst_exponent(_white_noise())
    assert result.r_squared >= 0.0


def test_hurst_n_windows_positive() -> None:
    result = hurst_exponent(_random_walk())
    assert result.n_windows >= 2


def test_hurst_insufficient_data() -> None:
    """Series shorter than HURST_MIN_OBS (32) should return NaN."""
    short = pd.Series(np.random.default_rng(42).standard_normal(20))
    result = hurst_exponent(short)
    assert math.isnan(result.exponent)
    assert result.interpretation == "INSUFFICIENT_DATA"


def test_hurst_nan_dropped() -> None:
    """NaNs in input must be dropped without error."""
    rng = np.random.default_rng(42)
    arr = rng.standard_normal(N).copy()
    arr[::20] = float("nan")
    result = hurst_exponent(pd.Series(arr))
    assert isinstance(result.exponent, float)
