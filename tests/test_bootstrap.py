"""Tests for bootstrap confidence intervals."""

from __future__ import annotations

import math
from datetime import timezone
from datetime import datetime, timedelta

import pandas as pd
import pytest

from trading_research.eval.bootstrap import bootstrap_summary, format_with_ci


def _make_result(net_pnls: list[float]):
    """Build a minimal BacktestResult from a list of net P&Ls."""
    from trading_research.backtest.engine import BacktestResult, BacktestConfig

    rows = []
    for i, net in enumerate(net_pnls):
        entry_ts = pd.Timestamp(datetime(2024, 1, 10, tzinfo=timezone.utc) + timedelta(days=i))
        exit_ts = entry_ts + pd.Timedelta("4h")
        rows.append({
            "trade_id": f"t{i}",
            "strategy_id": "test",
            "symbol": "ZN",
            "direction": "long",
            "quantity": 1,
            "entry_trigger_ts": entry_ts,
            "entry_ts": entry_ts,
            "entry_price": 110.0,
            "exit_trigger_ts": exit_ts,
            "exit_ts": exit_ts,
            "exit_price": 110.25,
            "exit_reason": "target",
            "initial_stop": 109.5,
            "initial_target": 110.5,
            "pnl_points": 0.25,
            "pnl_usd": net + 35.25,
            "slippage_usd": 31.25,
            "commission_usd": 4.0,
            "net_pnl_usd": net,
            "mae_points": -0.05,
            "mfe_points": 0.25,
        })
    trades = pd.DataFrame(rows)
    equity = trades.set_index("exit_ts")["net_pnl_usd"].sort_index().cumsum()
    equity.name = "equity_usd"
    cfg = BacktestConfig(strategy_id="test", symbol="ZN")
    return BacktestResult(trades=trades, equity_curve=equity, config=cfg, symbol_meta={})


class TestBootstrapSummary:
    def test_empty_trades_returns_nan_cis(self):
        from trading_research.backtest.engine import BacktestResult, BacktestConfig
        cfg = BacktestConfig(strategy_id="test", symbol="ZN")
        result = BacktestResult(
            trades=pd.DataFrame(),
            equity_curve=pd.Series(dtype=float),
            config=cfg,
            symbol_meta={},
        )
        cis = bootstrap_summary(result)
        for v in cis.values():
            assert math.isnan(v[0]) and math.isnan(v[1])

    def test_ci_contains_point_estimate(self):
        # 100 trades — CIs should be meaningful and contain the true value.
        pnls = [100.0] * 60 + [-50.0] * 40
        result = _make_result(pnls)

        from trading_research.eval.summary import compute_summary
        point = compute_summary(result)
        cis = bootstrap_summary(result, n_samples=500, seed=0)

        # Win rate 0.6 should be in its CI.
        lo, hi = cis["win_rate_ci"]
        assert lo < point["win_rate"] < hi

        # Expectancy should be in its CI.
        lo, hi = cis["expectancy_usd_ci"]
        assert lo < point["expectancy_usd"] < hi

    def test_ci_keys_present(self):
        result = _make_result([100.0] * 50 + [-50.0] * 50)
        cis = bootstrap_summary(result, n_samples=100)
        expected_keys = {
            "sharpe_ci", "calmar_ci", "win_rate_ci",
            "expectancy_usd_ci", "profit_factor_ci", "sortino_ci",
        }
        assert expected_keys.issubset(set(cis.keys()))

    def test_format_with_ci_runs(self):
        from trading_research.eval.summary import compute_summary
        result = _make_result([100.0] * 60 + [-50.0] * 40)
        point = compute_summary(result)
        cis = bootstrap_summary(result, n_samples=200, seed=1)
        text = format_with_ci(point, cis)
        assert "CI:" in text
        assert "Calmar" in text

    def test_format_with_ci_includes_dsr(self):
        from trading_research.eval.summary import compute_summary
        result = _make_result([100.0] * 60 + [-50.0] * 40)
        point = compute_summary(result)
        cis = bootstrap_summary(result, n_samples=100, seed=1)
        text = format_with_ci(point, cis, dsr=0.72, n_trials=5)
        assert "Deflated Sharpe (DSR)" in text
        assert "0.72" in text
        assert "n_trials=5" in text

    def test_format_with_ci_no_dsr_by_default(self):
        from trading_research.eval.summary import compute_summary
        result = _make_result([100.0] * 60 + [-50.0] * 40)
        point = compute_summary(result)
        cis = bootstrap_summary(result, n_samples=100, seed=1)
        text = format_with_ci(point, cis)
        assert "Deflated Sharpe" not in text

    def test_ci_includes_zero_flag(self):
        from trading_research.eval.summary import compute_summary
        result = _make_result([50.0] * 30 + [-50.0] * 30)
        point = compute_summary(result)
        cis = bootstrap_summary(result, n_samples=500, seed=42)
        text = format_with_ci(point, cis)
        assert "CI includes zero" in text
