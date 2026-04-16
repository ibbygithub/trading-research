"""Smoke test for performance summary on a synthetic 10-trade log."""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

from trading_research.eval.summary import compute_summary, format_summary


def _utc(days_offset: int = 0) -> datetime:
    base = datetime(2024, 1, 10, 15, 0, tzinfo=timezone.utc)
    return base + timedelta(days=days_offset)


def _make_trades(net_pnls: list[float]) -> pd.DataFrame:
    """Build a minimal trades DataFrame from a list of net P&Ls."""
    rows = []
    for i, net in enumerate(net_pnls):
        entry_ts = pd.Timestamp(_utc(i))
        exit_ts = pd.Timestamp(_utc(i)) + pd.Timedelta("4h")
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
            "exit_price": 110.25 if net > 0 else 109.75,
            "exit_reason": "target" if net > 0 else "stop",
            "initial_stop": 109.5,
            "initial_target": 110.5,
            "pnl_points": 0.25 if net > 0 else -0.25,
            "pnl_usd": net + 35.25,   # add back costs for gross
            "slippage_usd": 31.25,
            "commission_usd": 4.0,
            "net_pnl_usd": net,
            "mae_points": -0.1 if net < 0 else -0.05,
            "mfe_points": 0.25 if net > 0 else 0.1,
        })
    return pd.DataFrame(rows)


class TestComputeSummary:
    def test_empty_trades(self):
        df = pd.DataFrame()
        s = compute_summary_from_df(df)
        assert s["total_trades"] == 0

    def test_ten_trade_smoke(self):
        # 6 winners (+$200 each), 4 losers (-$100 each) → profit factor > 1
        pnls = [200.0] * 6 + [-100.0] * 4
        trades = _make_trades(pnls)

        from trading_research.backtest.engine import BacktestResult, BacktestConfig
        from trading_research.backtest.fills import FillModel
        import pandas as pd

        cfg = BacktestConfig(strategy_id="test", symbol="ZN")
        equity = trades.set_index("exit_ts")["net_pnl_usd"].sort_index().cumsum()
        equity.name = "equity_usd"

        result = BacktestResult(
            trades=trades, equity_curve=equity, config=cfg,
            symbol_meta={"symbol": "ZN"},
        )
        s = compute_summary(result)

        assert s["total_trades"] == 10
        assert abs(s["win_rate"] - 0.6) < 1e-9
        assert s["profit_factor"] > 1.0
        assert s["expectancy_usd"] > 0
        assert s["max_consec_losses"] == 4
        assert not math.isnan(s["sharpe"])
        # Calmar requires a drawdown — may be nan if no drawdown.
        assert isinstance(s["calmar"], float)

    def test_format_summary_runs(self):
        pnls = [100.0] * 5 + [-50.0] * 5
        trades = _make_trades(pnls)

        from trading_research.backtest.engine import BacktestResult, BacktestConfig
        cfg = BacktestConfig(strategy_id="test", symbol="ZN")
        equity = trades.set_index("exit_ts")["net_pnl_usd"].sort_index().cumsum()
        equity.name = "equity_usd"
        result = BacktestResult(trades=trades, equity_curve=equity, config=cfg, symbol_meta={})
        s = compute_summary(result)
        text = format_summary(s)
        assert "Calmar" in text
        assert "Sharpe" in text


def compute_summary_from_df(df: pd.DataFrame) -> dict:
    """Helper to test empty-trades path without a full BacktestResult."""
    from trading_research.eval.summary import _empty_summary
    if df.empty:
        return _empty_summary()
    from trading_research.backtest.engine import BacktestResult, BacktestConfig
    cfg = BacktestConfig(strategy_id="test", symbol="ZN")
    equity = df.set_index("exit_ts")["net_pnl_usd"].sort_index().cumsum() if not df.empty else pd.Series(dtype=float)
    equity.name = "equity_usd"
    result = BacktestResult(trades=df, equity_curve=equity, config=cfg, symbol_meta={})
    from trading_research.eval.summary import compute_summary
    return compute_summary(result)
