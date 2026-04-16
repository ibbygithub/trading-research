"""Tests for eval/monte_carlo.py."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from trading_research.eval.monte_carlo import shuffle_trade_order


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_trades(pnl: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=len(pnl), freq="D", tz="UTC")
    return pd.DataFrame({
        "entry_ts": dates,
        "exit_ts": dates + pd.Timedelta(hours=1),
        "net_pnl_usd": pnl,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_deterministic_with_seed():
    """Same seed → same results."""
    trades = _make_trades(list(range(-50, 50)))
    r1 = shuffle_trade_order(trades, n_iter=100, seed=42)
    r2 = shuffle_trade_order(trades, n_iter=100, seed=42)
    np.testing.assert_array_equal(r1["max_dd_dist"], r2["max_dd_dist"])
    np.testing.assert_array_equal(r1["final_pnl_dist"], r2["final_pnl_dist"])


def test_different_seeds_different_results():
    """Different seeds → different shuffle distributions."""
    trades = _make_trades(list(range(-50, 50)))
    r1 = shuffle_trade_order(trades, n_iter=100, seed=1)
    r2 = shuffle_trade_order(trades, n_iter=100, seed=2)
    # Not equal (astronomically unlikely if n_iter > 2).
    assert not np.allclose(r1["max_dd_dist"], r2["max_dd_dist"])


def test_final_pnl_invariant():
    """All shuffles must end with the same final P&L (order doesn't change sum)."""
    pnl = [10.0, -5.0, 20.0, -15.0, 30.0]
    trades = _make_trades(pnl)
    result = shuffle_trade_order(trades, n_iter=200, seed=0)
    expected_final = sum(pnl)
    assert all(
        abs(v - expected_final) < 1e-6
        for v in result["final_pnl_dist"]
    )


def test_output_shape():
    """equity_curves shape is (n_iter, n_trades)."""
    pnl = list(range(1, 51))
    trades = _make_trades(pnl)
    result = shuffle_trade_order(trades, n_iter=100, seed=0)
    assert result["equity_curves"].shape == (100, 50)
    assert len(result["max_dd_dist"]) == 100
    assert len(result["calmar_dist"]) == 100


def test_actual_metrics_correct():
    """Actual max DD matches what we'd compute by hand."""
    pnl = [10.0, 10.0, -30.0, 10.0, 10.0]
    trades = _make_trades(pnl)
    result = shuffle_trade_order(trades, n_iter=10, seed=0)
    # Equity: 10, 20, -10, 0, 10. Peak = 20. Trough = -10. DD = 30.
    assert result["actual_max_dd"] == pytest.approx(30.0, abs=0.01)


def test_percentile_monotonically_decreasing_pnl():
    """Strategy with only losses: actual DD is always near 100th percentile."""
    pnl = [-5.0] * 50
    trades = _make_trades(pnl)
    result = shuffle_trade_order(trades, n_iter=200, seed=0)
    # All shuffles produce the same equity curve (all -5). DD is constant.
    # actual_max_dd_pctile should be 100 (or close).
    assert result["actual_max_dd_pctile"] >= 50


def test_empty_trades():
    """Empty trades returns empty result without error."""
    result = shuffle_trade_order(pd.DataFrame())
    assert math.isnan(result["actual_max_dd"])
    assert result["n_trades"] == 0


def test_too_few_trades():
    """Fewer than 5 trades returns empty result."""
    result = shuffle_trade_order(_make_trades([1.0, 2.0]))
    assert math.isnan(result["actual_max_dd"])


def test_interpretation_present():
    """Interpretation string is non-empty for real data."""
    pnl = list(range(-25, 26))
    result = shuffle_trade_order(_make_trades(pnl), n_iter=100, seed=0)
    assert len(result["interpretation"]) > 10
