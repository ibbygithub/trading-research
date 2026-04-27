"""ADF wrapper tests.

All synthetic series use seed=42 and 500 observations per the design doc §8.1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.stattools import adfuller

from trading_research.stats.stationarity import ADFResult, adf_test

RNG = np.random.default_rng(42)
N = 500


def _ar1(phi: float, n: int = N, rng: np.random.Generator = RNG) -> pd.Series:
    """Simulate AR(1): y_t = phi * y_{t-1} + ε_t, ε ~ N(0,1)."""
    eps = rng.standard_normal(n)
    y = np.empty(n)
    y[0] = eps[0]
    for t in range(1, n):
        y[t] = phi * y[t - 1] + eps[t]
    return pd.Series(y)


def _random_walk(n: int = N, rng: np.random.Generator = RNG) -> pd.Series:
    return pd.Series(np.cumsum(rng.standard_normal(n)))


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


def test_adf_returns_correct_type() -> None:
    series = _ar1(0.5)
    result = adf_test(series)
    assert isinstance(result, ADFResult)


def test_adf_stationary_series() -> None:
    """AR(1) φ=0.5 is strongly stationary; ADF should reject the unit-root null."""
    rng = np.random.default_rng(42)
    series = _ar1(0.5, rng=rng)
    result = adf_test(series)
    assert result.p_value < 0.05, f"Expected p < 0.05 for AR(1) φ=0.5, got {result.p_value:.4f}"
    assert result.is_stationary is True


def test_adf_non_stationary_series() -> None:
    """Random walk (φ=1) should fail to reject the unit-root null (p ≥ 0.05)."""
    rng = np.random.default_rng(42)
    series = _random_walk(rng=rng)
    result = adf_test(series)
    assert result.p_value >= 0.05, f"Expected p ≥ 0.05 for random walk, got {result.p_value:.4f}"
    assert result.is_stationary is False


def test_adf_matches_statsmodels() -> None:
    """Wrapper must produce the same p-value as adfuller() directly (within floating point)."""
    rng = np.random.default_rng(42)
    series = _ar1(0.5, rng=rng)
    arr = series.dropna().to_numpy()

    wrapper_result = adf_test(series)
    direct_result = adfuller(arr, autolag="AIC", regression="c")

    assert abs(wrapper_result.p_value - direct_result[1]) < 1e-6, (
        f"p-value mismatch: wrapper={wrapper_result.p_value:.8f}, "
        f"statsmodels={direct_result[1]:.8f}"
    )
    assert abs(wrapper_result.statistic - direct_result[0]) < 1e-6
    assert wrapper_result.lags_used == direct_result[2]
    assert wrapper_result.n_observations == direct_result[3]


def test_adf_critical_values_present() -> None:
    """Critical values dict should have 1%, 5%, 10% keys."""
    series = _ar1(0.5)
    result = adf_test(series)
    for key in ("1%", "5%", "10%"):
        assert key in result.critical_values


def test_adf_regression_ct_for_price_level() -> None:
    """regression='ct' should not raise and returns a valid result."""
    rng = np.random.default_rng(42)
    series = _random_walk(rng=rng)
    result = adf_test(series, regression="ct")
    assert isinstance(result.p_value, float)
    assert 0.0 <= result.p_value <= 1.0


def test_adf_raises_on_too_few_obs() -> None:
    """ADF should raise ValueError when the series is too short."""
    with pytest.raises(ValueError, match="ADF requires"):
        adf_test(pd.Series([1.0, 2.0, 3.0]))


def test_adf_interpretation_strong() -> None:
    """AR(1) φ=0.1 (highly stationary) should produce STATIONARY (strong)."""
    rng = np.random.default_rng(42)
    series = _ar1(0.1, rng=rng)
    result = adf_test(series)
    # p < 0.01 expected for a very mean-reverting series with 500 obs
    assert "STATIONARY" in result.interpretation


def test_adf_nan_dropped() -> None:
    """NaNs in input must be dropped without error."""
    rng = np.random.default_rng(42)
    arr = rng.standard_normal(500)
    arr[::10] = float("nan")
    series = pd.Series(arr)
    result = adf_test(series)
    assert isinstance(result.p_value, float)
