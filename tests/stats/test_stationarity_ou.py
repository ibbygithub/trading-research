"""OU half-life tests.

Reference: design doc §8.3 — theoretical half-life = ln(2) / ln(1/φ), tolerance ±20%.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trading_research.stats.stationarity import OUResult, ou_half_life

N = 500


def _ar1(phi: float, n: int = N) -> pd.Series:
    """AR(1): y_t = phi * y_{t-1} + ε_t."""
    rng = np.random.default_rng(42)
    eps = rng.standard_normal(n)
    y = np.empty(n)
    y[0] = eps[0]
    for t in range(1, n):
        y[t] = phi * y[t - 1] + eps[t]
    return pd.Series(y)


def _random_walk(n: int = N) -> pd.Series:
    rng = np.random.default_rng(42)
    return pd.Series(np.cumsum(rng.standard_normal(n)))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ou_returns_correct_type() -> None:
    result = ou_half_life(_ar1(0.9))
    assert isinstance(result, OUResult)


def test_ou_half_life_synthetic() -> None:
    """AR(1) φ=0.9: theoretical HL = ln(2)/ln(1/0.9) ≈ 6.58 bars.

    Fitted half-life must be within ±20% of the theoretical value.
    """
    phi = 0.9
    theoretical_hl = math.log(2.0) / math.log(1.0 / phi)  # ≈ 6.58

    result = ou_half_life(_ar1(phi))

    assert not math.isinf(result.half_life_bars), "Expected finite half-life"
    assert not math.isnan(result.half_life_bars), "Expected non-NaN half-life"

    lower = theoretical_hl * 0.80
    upper = theoretical_hl * 1.20
    assert lower <= result.half_life_bars <= upper, (
        f"HL={result.half_life_bars:.2f} outside ±20% of theoretical {theoretical_hl:.2f} "
        f"(range [{lower:.2f}, {upper:.2f}])"
    )


def test_ou_fit_quality_high_for_ou_process() -> None:
    """Mean-reverting AR(1) should yield positive R²."""
    result = ou_half_life(_ar1(0.7))
    assert result.r_squared > 0.0, f"Expected R² > 0 for AR(1) φ=0.7, got {result.r_squared:.4f}"


def test_ou_fit_quality_low_for_random_walk() -> None:
    """Random walk (β ≈ 0) should yield very low R² (near-zero slope)."""
    result = ou_half_life(_random_walk())
    # Random walk has β ≈ 0, so R² of the OLS fit is close to 0 or the HL is infinite.
    is_low_r2 = result.r_squared < 0.10
    is_infinite = math.isinf(result.half_life_bars)
    assert is_low_r2 or is_infinite, (
        f"Expected low R² or infinite HL for random walk; "
        f"got R²={result.r_squared:.4f}, HL={result.half_life_bars}"
    )


def test_ou_trending_large_halflife() -> None:
    """A random walk with strong positive drift should yield a very long half-life.

    The OLS fit on a random walk gives β ≈ 0 (near-zero slope), so the computed
    half-life is extremely large (>> 100 bars) even if β is technically negative.
    A truly trending series is characterised by |β| ≈ 0 and HL >> any tradeable range.
    """
    rng = np.random.default_rng(42)
    trending = pd.Series(np.cumsum(rng.standard_normal(N) + 0.5))
    result = ou_half_life(trending)
    # Either infinite or very long half-life (OLS slope ≈ 0 for unit-root process)
    assert math.isinf(result.half_life_bars) or result.half_life_bars > 100.0, (
        f"Expected large HL for trending series, got {result.half_life_bars:.1f}"
    )


def test_ou_beta_negative_for_mean_reverting() -> None:
    """AR(1) φ=0.5 must have negative beta (required for mean reversion)."""
    result = ou_half_life(_ar1(0.5))
    assert result.beta < 0.0, f"Expected β < 0, got {result.beta:.4f}"


def test_ou_half_life_phi_099() -> None:
    """Near unit-root AR(1) φ=0.999 yields very long half-life (>> 24 bars)."""
    result = ou_half_life(_ar1(0.999, n=2000))
    # Half-life = ln(2)/ln(1/0.999) ≈ 693 bars
    if not math.isinf(result.half_life_bars):
        assert result.half_life_bars > 200.0, (
            f"Expected long HL for φ=0.999, got {result.half_life_bars:.1f}"
        )


def test_ou_insufficient_data() -> None:
    """Series shorter than OU_MIN_OBS (10) should return NaN."""
    short = pd.Series([1.0, 2.0, 1.5, 0.5, 1.0])
    result = ou_half_life(short)
    assert math.isnan(result.half_life_bars)
    assert result.interpretation == "INSUFFICIENT_DATA"


def test_ou_nan_dropped() -> None:
    """NaNs in input must be dropped without error."""
    arr = _ar1(0.8).to_numpy().copy()
    arr[::25] = float("nan")
    result = ou_half_life(pd.Series(arr))
    assert isinstance(result.half_life_bars, float)
