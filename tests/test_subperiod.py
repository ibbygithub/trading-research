"""Tests for eval/subperiod.py."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from trading_research.eval.subperiod import subperiod_analysis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_trades(n: int, start: str = "2020-01-02", seed: int = 42) -> pd.DataFrame:
    """Generate n synthetic trades across multiple years."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n, freq="D", tz="UTC")
    entry = dates
    exit_ = dates + pd.Timedelta(hours=2)
    pnl = rng.standard_normal(n) * 100
    return pd.DataFrame({
        "entry_ts": entry,
        "exit_ts": exit_,
        "net_pnl_usd": pnl,
        "strategy_id": "test",
        "symbol": "ZN",
    })


def _make_equity(trades: pd.DataFrame) -> pd.Series:
    trades = trades.sort_values("exit_ts")
    cum = trades["net_pnl_usd"].cumsum()
    return cum.set_axis(pd.to_datetime(trades["exit_ts"]).values)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_yearly_splits_correct_count():
    """With 4 years of trades, yearly split produces 4 rows."""
    # 4 years of daily trades.
    trades = _make_trades(365 * 4, start="2020-01-02")
    equity = _make_equity(trades)
    result = subperiod_analysis(trades, equity, splits="yearly")
    table = result["table"]
    # 2020, 2021, 2022, 2023.
    assert len(table) >= 4


def test_halves_split_produces_two_rows():
    trades = _make_trades(200, start="2020-01-02")
    equity = _make_equity(trades)
    result = subperiod_analysis(trades, equity, splits="halves")
    assert len(result["table"]) == 2


def test_thirds_split_produces_three_rows():
    trades = _make_trades(300, start="2020-01-02")
    equity = _make_equity(trades)
    result = subperiod_analysis(trades, equity, splits="thirds")
    assert len(result["table"]) == 3


def test_table_has_expected_columns():
    trades = _make_trades(100, start="2020-01-02")
    equity = _make_equity(trades)
    result = subperiod_analysis(trades, equity)
    cols = result["table"].columns.tolist()
    for c in ["period", "trades", "win_rate", "sharpe", "calmar", "expectancy_usd"]:
        assert c in cols, f"Missing column: {c}"


def test_degradation_detected():
    """Force degradation: first half gains, second half loses."""
    rng = np.random.default_rng(0)
    n = 400
    dates = pd.date_range("2020-01-02", periods=n, freq="D", tz="UTC")
    pnl = np.concatenate([
        rng.exponential(50, n // 2),   # first half: steady gains
        -rng.exponential(50, n // 2),  # second half: steady losses
    ])
    trades = pd.DataFrame({
        "entry_ts": dates,
        "exit_ts": dates + pd.Timedelta(hours=1),
        "net_pnl_usd": pnl,
        "strategy_id": "test",
        "symbol": "ZN",
    })
    equity = _make_equity(trades)
    result = subperiod_analysis(trades, equity, splits="halves")
    # The second half is clearly worse — degradation flag should be set.
    assert result["degradation_flag"] is True
    assert len(result["degradation_message"]) > 0


def test_no_degradation_when_improving():
    """No degradation flag when recent period is better."""
    rng = np.random.default_rng(0)
    n = 400
    dates = pd.date_range("2020-01-02", periods=n, freq="D", tz="UTC")
    pnl = np.concatenate([
        -rng.exponential(30, n // 2),   # first half: losses
        rng.exponential(50, n // 2),    # second half: gains
    ])
    trades = pd.DataFrame({
        "entry_ts": dates,
        "exit_ts": dates + pd.Timedelta(hours=1),
        "net_pnl_usd": pnl,
        "strategy_id": "test",
        "symbol": "ZN",
    })
    equity = _make_equity(trades)
    result = subperiod_analysis(trades, equity, splits="halves")
    assert result["degradation_flag"] is False


def test_empty_trades():
    """Empty trades returns empty table without error."""
    result = subperiod_analysis(pd.DataFrame(), pd.Series(dtype=float))
    assert result["table"].empty
    assert result["degradation_flag"] is False
