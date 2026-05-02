"""Contract tests: BacktestEngine calls Strategy.size_position for trade sizing.

Written in 29a as stubs. Filled in 29c.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from trading_research.backtest.engine import BacktestConfig, BacktestEngine
from trading_research.core.strategies import (
    ExitDecision,
    PortfolioContext,
    Position,
    Signal,
    Strategy,
)
from trading_research.data.instruments import load_instruments


def _inst():
    return load_instruments().get("ZN")


def _ts(n: int) -> pd.DatetimeIndex:
    base = pd.Timestamp("2024-01-10 14:00:00", tz="UTC")
    return pd.date_range(base, periods=n, freq="5min")


def _make_bars(n: int, close: float = 110.0) -> pd.DataFrame:
    idx = _ts(n)
    prices = [close] * n
    return pd.DataFrame({
        "open": prices,
        "high": [p + 0.25 for p in prices],
        "low": [p - 0.25 for p in prices],
        "close": prices,
        "buy_volume": [500] * n,
        "sell_volume": [500] * n,
        "timestamp_ny": [ts.tz_convert("America/New_York") for ts in idx],
    }, index=idx)


def _make_signals(bars: pd.DataFrame, signal_vals: list[int]) -> pd.DataFrame:
    return pd.DataFrame({
        "signal": signal_vals,
        "stop": [109.0 if s == 1 else 111.0 if s == -1 else np.nan for s in signal_vals],
        "target": [111.0 if s == 1 else 109.0 if s == -1 else np.nan for s in signal_vals],
    }, index=bars.index)


class _FixedSizeStrategy:
    """Strategy that returns a fixed size from size_position."""

    def __init__(self, fixed_size: int) -> None:
        self._fixed_size = fixed_size

    @property
    def name(self) -> str:
        return "fixed-size"

    @property
    def template_name(self) -> str:
        return "test-template"

    @property
    def knobs(self) -> dict:
        return {}

    def generate_signals(self, bars, features, instrument):
        return []

    def size_position(self, signal, context, instrument) -> int:
        return self._fixed_size

    def exit_rules(self, position, current_bar, instrument):
        return ExitDecision(action="hold", reason="test")


class _RaisingStrategy(_FixedSizeStrategy):
    """Strategy whose size_position raises."""

    def size_position(self, signal, context, instrument) -> int:
        raise RuntimeError("sizing error")


def test_engine_uses_strategy_size_position() -> None:
    """Engine must call strategy.size_position() and use the returned integer as trade size."""
    bars = _make_bars(10)
    signals = _make_signals(bars, [0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    strategy = _FixedSizeStrategy(fixed_size=5)

    cfg = BacktestConfig(strategy_id="test", symbol="ZN", quantity=1)
    engine = BacktestEngine(cfg, _inst(), strategy=strategy, core_instrument=None)
    result = engine.run(bars, signals)

    assert not result.trades.empty
    assert result.trades.iloc[0]["quantity"] == 5


def test_engine_suppresses_trade_when_size_is_zero() -> None:
    """When strategy.size_position() returns 0, the engine must suppress the trade."""
    bars = _make_bars(10)
    signals = _make_signals(bars, [0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    strategy = _FixedSizeStrategy(fixed_size=0)

    cfg = BacktestConfig(strategy_id="test", symbol="ZN", quantity=1)
    engine = BacktestEngine(cfg, _inst(), strategy=strategy, core_instrument=None)
    result = engine.run(bars, signals)

    assert result.trades.empty


def test_engine_surfaces_error_from_size_position() -> None:
    """When strategy.size_position() raises, the engine must propagate the error."""
    bars = _make_bars(10)
    signals = _make_signals(bars, [0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    strategy = _RaisingStrategy(fixed_size=1)

    cfg = BacktestConfig(strategy_id="test", symbol="ZN", quantity=1)
    engine = BacktestEngine(cfg, _inst(), strategy=strategy, core_instrument=None)

    with pytest.raises(RuntimeError, match="sizing error"):
        engine.run(bars, signals)


def test_engine_falls_back_to_quantity_without_strategy() -> None:
    """Legacy path: without a Strategy, engine uses BacktestConfig.quantity."""
    bars = _make_bars(10)
    signals = _make_signals(bars, [0, 1, 0, 0, 0, 0, 0, 0, 0, 0])

    cfg = BacktestConfig(strategy_id="test", symbol="ZN", quantity=3)
    engine = BacktestEngine(cfg, _inst())
    result = engine.run(bars, signals)

    assert not result.trades.empty
    assert result.trades.iloc[0]["quantity"] == 3
