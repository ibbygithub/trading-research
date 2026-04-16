"""Known-answer tests for eval/stats.py.

Every function gets at least one test with a hand-computable or
LdP-published expected value.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from trading_research.eval.stats import (
    bootstrap_metric,
    deflated_sharpe_ratio,
    gain_to_pain_ratio,
    mar_ratio,
    omega_ratio,
    pain_ratio,
    probabilistic_sharpe_ratio,
    recovery_factor,
    tail_ratio,
    ulcer_index,
    ulcer_performance_index,
)


# ---------------------------------------------------------------------------
# bootstrap_metric
# ---------------------------------------------------------------------------


def test_bootstrap_metric_mean_converges():
    """Bootstrap mean of a constant array equals that constant."""
    values = np.ones(100) * 5.0
    pt, lo, hi = bootstrap_metric(values, np.mean, n_iter=500, seed=0)
    assert pt == pytest.approx(5.0)
    assert lo == pytest.approx(5.0, abs=0.01)
    assert hi == pytest.approx(5.0, abs=0.01)


def test_bootstrap_metric_ci_width_reasonable():
    """CI width is positive for noisy data."""
    rng = np.random.default_rng(42)
    values = rng.standard_normal(200)
    pt, lo, hi = bootstrap_metric(values, np.mean, n_iter=1000, seed=0)
    assert lo < pt < hi


def test_bootstrap_metric_too_few_obs():
    """Too few observations returns nan CI."""
    _, lo, hi = bootstrap_metric(np.array([1.0]), np.mean, n_iter=100)
    assert math.isnan(lo)
    assert math.isnan(hi)


# ---------------------------------------------------------------------------
# deflated_sharpe_ratio
# ---------------------------------------------------------------------------


def test_dsr_single_trial_equals_psr():
    """With n_trials=1, DSR numerically matches PSR at benchmark=0."""
    sharpe = 1.0
    n_obs = 500
    skew = -0.5
    kurt = 1.0
    dsr = deflated_sharpe_ratio(sharpe, n_obs, n_trials=1, skewness=skew, kurtosis=kurt)
    psr = probabilistic_sharpe_ratio(sharpe, n_obs, skew, kurt, sr_benchmark=0.0)
    assert dsr == pytest.approx(psr, abs=0.001)


def test_dsr_decreases_with_more_trials():
    """More trials → lower DSR (more skeptical)."""
    dsr_1 = deflated_sharpe_ratio(1.5, 500, n_trials=1, skewness=0.0, kurtosis=0.0)
    dsr_30 = deflated_sharpe_ratio(1.5, 500, n_trials=30, skewness=0.0, kurtosis=0.0)
    assert dsr_30 < dsr_1


def test_dsr_negative_sharpe_returns_low_probability():
    """A negative Sharpe yields a DSR close to zero."""
    dsr = deflated_sharpe_ratio(-0.5, 252, n_trials=10, skewness=0.0, kurtosis=0.0)
    assert dsr < 0.2


def test_dsr_high_sharpe_few_trials():
    """Very high Sharpe with 1 trial gives near-1 DSR."""
    dsr = deflated_sharpe_ratio(3.0, 2000, n_trials=1, skewness=0.0, kurtosis=0.0)
    assert dsr > 0.99


def test_dsr_invalid_inputs():
    """Degenerate inputs return nan."""
    assert math.isnan(deflated_sharpe_ratio(1.0, 3, 5, 0.0, 0.0))  # n_obs too low
    assert math.isnan(deflated_sharpe_ratio(1.0, 100, 0, 0.0, 0.0))  # n_trials=0


# ---------------------------------------------------------------------------
# probabilistic_sharpe_ratio
# ---------------------------------------------------------------------------


def test_psr_normal_distribution_sharpe_1():
    """PSR(SR=1, n=500, normal dist) should be high (> 0.99)."""
    psr = probabilistic_sharpe_ratio(1.0, 500, skewness=0.0, kurtosis=0.0, sr_benchmark=0.0)
    assert psr > 0.99


def test_psr_benchmark_above_sharpe():
    """When benchmark > SR, PSR < 0.5."""
    psr = probabilistic_sharpe_ratio(0.5, 100, 0.0, 0.0, sr_benchmark=1.0)
    assert psr < 0.5


def test_psr_too_few_obs():
    """< 4 obs returns nan."""
    assert math.isnan(probabilistic_sharpe_ratio(1.0, 3, 0.0, 0.0))


# ---------------------------------------------------------------------------
# mar_ratio
# ---------------------------------------------------------------------------


def _make_equity(returns: list[float]) -> pd.Series:
    idx = pd.date_range("2020-01-01", periods=len(returns), freq="D")
    return pd.Series(np.cumsum(returns), index=idx)


def test_mar_ratio_known_values():
    """Monotonically rising equity has infinite MAR (no drawdown)."""
    eq = _make_equity([1.0] * 365)
    # With no drawdown, MAR is nan.
    assert math.isnan(mar_ratio(eq))


def test_mar_ratio_with_drawdown():
    """Equity that falls then recovers gives a finite positive MAR."""
    returns = [10.0] * 100 + [-5.0] * 50 + [10.0] * 200
    eq = _make_equity(returns)
    m = mar_ratio(eq)
    assert math.isfinite(m)
    assert m > 0


def test_mar_ratio_empty():
    """Empty equity returns nan."""
    assert math.isnan(mar_ratio(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# ulcer_index
# ---------------------------------------------------------------------------


def test_ulcer_index_flat():
    """Flat (no drawdown) equity yields UI = 0."""
    idx = pd.date_range("2020-01-01", periods=100, freq="D")
    eq = pd.Series([100.0] * 100, index=idx)
    ui = ulcer_index(eq)
    assert ui == pytest.approx(0.0, abs=1e-9)


def test_ulcer_index_positive_for_volatile():
    """Equity with a drawdown has positive UI."""
    returns = [10.0] * 50 + [-5.0] * 20 + [10.0] * 50
    eq = _make_equity(returns)
    assert ulcer_index(eq) > 0


def test_ulcer_index_empty():
    assert math.isnan(ulcer_index(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# ulcer_performance_index
# ---------------------------------------------------------------------------


def test_upi_positive_for_good_strategy():
    """Equity with steady gains and shallow drawdown gives positive UPI."""
    returns = [5.0] * 100 + [-1.0] * 10 + [5.0] * 100
    eq = _make_equity(returns)
    upi = ulcer_performance_index(eq)
    assert math.isfinite(upi)
    assert upi > 0


# ---------------------------------------------------------------------------
# recovery_factor
# ---------------------------------------------------------------------------


def test_recovery_factor_known():
    """Recovery factor = net profit / |max DD|."""
    # Build equity: gains 100, then loses 20, then gains 50.
    eq = _make_equity([1.0] * 100 + [-0.2] * 100 + [0.5] * 100)
    rf = recovery_factor(eq)
    assert math.isfinite(rf)
    net_profit = float(eq.iloc[-1])
    mdd = float((eq - eq.cummax()).min())
    expected = net_profit / abs(mdd)
    assert rf == pytest.approx(expected, rel=1e-6)


def test_recovery_factor_empty():
    assert math.isnan(recovery_factor(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# pain_ratio
# ---------------------------------------------------------------------------


def test_pain_ratio_positive():
    returns = [5.0] * 100 + [-2.0] * 30 + [5.0] * 100
    eq = _make_equity(returns)
    pr = pain_ratio(eq)
    assert math.isfinite(pr)
    assert pr > 0


def test_pain_ratio_empty():
    assert math.isnan(pain_ratio(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# tail_ratio
# ---------------------------------------------------------------------------


def test_tail_ratio_symmetric_normal():
    """Symmetric normal should give tail ratio close to 1."""
    rng = np.random.default_rng(0)
    r = rng.standard_normal(10_000)
    tr = tail_ratio(r)
    assert tr == pytest.approx(1.0, abs=0.1)


def test_tail_ratio_right_skewed():
    """Right-skewed distribution: right tail > left tail → ratio > 1."""
    rng = np.random.default_rng(0)
    # Positive skew: many small losses, occasional large gains.
    r = np.concatenate([rng.standard_normal(9000), rng.exponential(3, 1000)])
    tr = tail_ratio(r)
    assert tr > 1.0


def test_tail_ratio_too_few():
    assert math.isnan(tail_ratio(np.array([1.0, 2.0])))


# ---------------------------------------------------------------------------
# omega_ratio
# ---------------------------------------------------------------------------


def test_omega_ratio_all_gains():
    """All gains above threshold → inf."""
    r = np.array([1.0, 2.0, 3.0, 4.0])
    assert omega_ratio(r, threshold=0.0) == float("inf")


def test_omega_ratio_mixed():
    """Known-answer: gains=[2,3], losses=[1] → ratio = 5/1 = 5."""
    r = np.array([2.0, 3.0, -1.0])
    assert omega_ratio(r, threshold=0.0) == pytest.approx(5.0, rel=1e-6)


def test_omega_ratio_empty():
    assert math.isnan(omega_ratio(np.array([1.0])))


# ---------------------------------------------------------------------------
# gain_to_pain_ratio
# ---------------------------------------------------------------------------


def test_gtp_all_positive():
    """All positive months → inf."""
    r = np.array([1.0, 2.0, 3.0])
    assert gain_to_pain_ratio(r) == float("inf")


def test_gtp_known():
    """Known: gains=[3,4], losses=[1,2] → GPR = 7/3."""
    r = np.array([3.0, 4.0, -1.0, -2.0])
    assert gain_to_pain_ratio(r) == pytest.approx(7.0 / 3.0, rel=1e-6)


def test_gtp_too_few():
    assert math.isnan(gain_to_pain_ratio(np.array([1.0])))
