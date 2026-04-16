"""Tests for eval/distribution.py."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from trading_research.eval.distribution import (
    autocorrelation_data,
    daily_acf_data,
    qq_plot_data,
    return_distribution_stats,
)


# ---------------------------------------------------------------------------
# return_distribution_stats
# ---------------------------------------------------------------------------


def test_stats_normal_distribution():
    """Normal distribution should not reject JB at low n."""
    rng = np.random.default_rng(42)
    r = rng.standard_normal(500)
    stats = return_distribution_stats(r)
    assert stats["count"] == 500
    assert math.isfinite(stats["skewness"])
    assert math.isfinite(stats["kurtosis"])
    assert math.isfinite(stats["jb_stat"])
    assert math.isfinite(stats["jb_pvalue"])
    # Normal data should not reject normality strongly.
    assert stats["jb_pvalue"] > 0.001  # not zero


def test_stats_fat_tailed_distribution():
    """Very fat-tailed data should reject normality (JB p ≈ 0)."""
    rng = np.random.default_rng(0)
    # Generate Cauchy-like returns (very heavy tails).
    r = rng.standard_cauchy(2000)
    # Clip to avoid extreme values causing numerical issues.
    r = np.clip(r, -100, 100)
    stats = return_distribution_stats(r)
    assert stats["normality_flag"] is True
    assert "non-normal" in stats["normality_warning"]


def test_stats_too_few_obs():
    """Fewer than 4 observations returns nan stats."""
    stats = return_distribution_stats(np.array([1.0, 2.0]))
    assert math.isnan(stats["jb_stat"])
    assert stats["count"] == 2


def test_stats_keys():
    """All expected keys are present."""
    stats = return_distribution_stats(np.random.default_rng(0).standard_normal(100))
    expected = [
        "count", "mean", "std", "min", "max", "median",
        "skewness", "kurtosis", "excess_kurtosis",
        "jb_stat", "jb_pvalue", "normality_flag", "normality_warning",
    ]
    for key in expected:
        assert key in stats, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# qq_plot_data
# ---------------------------------------------------------------------------


def test_qq_same_length():
    """Theoretical and sample quantile arrays must have the same length."""
    r = np.random.default_rng(0).standard_normal(200)
    qq = qq_plot_data(r)
    assert len(qq["theoretical_quantiles"]) == len(qq["sample_quantiles"])
    assert len(qq["theoretical_quantiles"]) == 200


def test_qq_sorted():
    """Sample quantiles must be sorted ascending."""
    r = np.random.default_rng(0).standard_normal(100)
    qq = qq_plot_data(r)
    sq = qq["sample_quantiles"]
    assert np.all(np.diff(sq) >= 0)


def test_qq_too_few():
    """Too few observations returns empty arrays."""
    qq = qq_plot_data(np.array([1.0, 2.0]))
    assert len(qq["theoretical_quantiles"]) == 0


# ---------------------------------------------------------------------------
# autocorrelation_data
# ---------------------------------------------------------------------------


def test_acf_white_noise_near_zero():
    """ACF of white noise should be near zero at all lags."""
    rng = np.random.default_rng(99)
    r = rng.standard_normal(500)
    acf_data = autocorrelation_data(r, max_lags=10)
    acf = acf_data["acf"]
    # Most lags should be within 2 * confidence bounds.
    bounds = acf_data["confidence_bounds"]
    n_outside = np.sum(np.abs(acf) > 2 * bounds)
    # With 10 lags, expect < 3 outside at 95% CI.
    assert n_outside <= 3


def test_acf_ar1_detects_correlation():
    """AR(1) with high autocorrelation should have non-zero lag-1 ACF."""
    rng = np.random.default_rng(7)
    n = 500
    r = np.zeros(n)
    phi = 0.8
    r[0] = rng.standard_normal()
    for i in range(1, n):
        r[i] = phi * r[i - 1] + rng.standard_normal() * 0.2
    acf_data = autocorrelation_data(r, max_lags=5)
    assert abs(acf_data["acf"][0]) > 0.5  # lag-1 should be high


def test_acf_structure():
    """Output has the expected keys."""
    acf_data = autocorrelation_data(np.random.default_rng(0).standard_normal(100))
    assert "lags" in acf_data
    assert "acf" in acf_data
    assert "ljung_box_stat" in acf_data
    assert "ljung_box_pvalue" in acf_data
    assert "serial_correlation_flag" in acf_data
    assert "confidence_bounds" in acf_data


def test_acf_too_few():
    """Fewer observations than lags returns nan array."""
    acf_data = autocorrelation_data(np.array([1.0, 2.0, 3.0]), max_lags=20)
    assert all(math.isnan(v) for v in acf_data["acf"])


# ---------------------------------------------------------------------------
# daily_acf_data
# ---------------------------------------------------------------------------


def test_daily_acf_from_trades():
    """daily_acf_data correctly aggregates and computes ACF."""
    rng = np.random.default_rng(0)
    n = 200
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    trades = pd.DataFrame({
        "exit_ts": dates,
        "net_pnl_usd": rng.standard_normal(n) * 100,
    })
    result = daily_acf_data(trades, max_lags=10)
    assert "acf" in result
    assert len(result["acf"]) == 10


def test_daily_acf_empty_trades():
    """Empty trades returns empty-ish result without error."""
    result = daily_acf_data(pd.DataFrame(), max_lags=10)
    assert "acf" in result
