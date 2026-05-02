"""Tests for VWAPReversionV1 template strategy.

Verifies signal generation respects entry window, blackout, and direction logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from trading_research.core.instruments import Instrument
from trading_research.core.strategies import PortfolioContext, Signal, Strategy
from trading_research.core.templates import TemplateRegistry, StrategyTemplate
from trading_research.strategies.vwap_reversion_v1 import (
    VWAPReversionV1,
    VWAPReversionV1Knobs,
)


@pytest.fixture()
def instrument_6e() -> Instrument:
    return Instrument(
        symbol="6E",
        tradestation_symbol="@EC",
        name="Euro FX",
        exchange="CME",
        asset_class="fx",
        tick_size=Decimal("0.00005"),
        tick_value_usd=Decimal("6.25"),
        contract_multiplier=Decimal("125000"),
        is_micro=False,
        commission_per_side_usd=Decimal("1.75"),
        intraday_initial_margin_usd=Decimal("500"),
        overnight_initial_margin_usd=None,
        session_open_et=time(18, 0),
        session_close_et=time(17, 0),
        rth_open_et=time(8, 0),
        rth_close_et=time(17, 0),
        calendar_name="CMEGlobex_FX",
        roll_method="panama",
    )


def _make_features(
    start: str = "2024-06-03 12:00",
    periods: int = 60,
    freq: str = "5min",
    close_base: float = 1.085,
    vwap_base: float = 1.085,
    atr: float = 0.001,
    spread_mult: float = 0.0,
) -> pd.DataFrame:
    """Build a synthetic features DataFrame."""
    idx = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    close = np.full(periods, close_base + spread_mult * atr)
    vwap = np.full(periods, vwap_base)
    return pd.DataFrame({
        "open": close,
        "high": close + 0.0005,
        "low": close - 0.0005,
        "close": close,
        "volume": 1000,
        "vwap_session": vwap,
        "atr_14": np.full(periods, atr),
    }, index=idx)


def _make_strategy(**overrides) -> VWAPReversionV1:
    knobs = VWAPReversionV1Knobs(**overrides)
    return VWAPReversionV1(knobs=knobs, template_name="vwap-reversion-v1")


class TestGenerateSignals:
    def test_no_signals_outside_entry_window(self, instrument_6e: Instrument) -> None:
        features = _make_features(
            start="2024-06-03 08:00",
            periods=20,
            spread_mult=-3.0,
        )
        strategy = _make_strategy()
        signals = strategy.generate_signals(features, features, instrument_6e)
        assert len(signals) == 0

    def test_long_signal_when_spread_below_threshold(self, instrument_6e: Instrument) -> None:
        features = _make_features(spread_mult=-3.0)
        strategy = _make_strategy()
        signals = strategy.generate_signals(features, features, instrument_6e)
        assert len(signals) > 0
        assert all(s.direction == "long" for s in signals)

    def test_short_signal_when_spread_above_threshold(self, instrument_6e: Instrument) -> None:
        features = _make_features(spread_mult=3.0)
        strategy = _make_strategy()
        signals = strategy.generate_signals(features, features, instrument_6e)
        assert len(signals) > 0
        assert all(s.direction == "short" for s in signals)

    def test_no_signal_when_within_threshold(self, instrument_6e: Instrument) -> None:
        features = _make_features(spread_mult=1.0)
        strategy = _make_strategy()
        signals = strategy.generate_signals(features, features, instrument_6e)
        assert len(signals) == 0

    def test_signals_carry_metadata(self, instrument_6e: Instrument) -> None:
        features = _make_features(spread_mult=-3.0)
        strategy = _make_strategy()
        signals = strategy.generate_signals(features, features, instrument_6e)
        assert len(signals) > 0
        for s in signals:
            assert "vwap_spread_z" in s.metadata
            assert "stop" in s.metadata
            assert "target" in s.metadata

    def test_signal_direction_matches_spread_sign(self, instrument_6e: Instrument) -> None:
        features = _make_features(spread_mult=-3.0)
        strategy = _make_strategy()
        signals = strategy.generate_signals(features, features, instrument_6e)
        for s in signals:
            assert s.metadata["vwap_spread_z"] < 0
            assert s.direction == "long"


class TestSatisfiesProtocol:
    def test_vwap_reversion_v1_satisfies_strategy_protocol(self) -> None:
        strategy = _make_strategy()
        assert isinstance(strategy, Strategy)

    def test_template_registration(self) -> None:
        from trading_research.core.templates import _GLOBAL_REGISTRY
        template = _GLOBAL_REGISTRY.get("vwap-reversion-v1")
        assert template.name == "vwap-reversion-v1"
        assert "6E" in template.supported_instruments


class TestSizePosition:
    def test_returns_positive_int(self, instrument_6e: Instrument) -> None:
        strategy = _make_strategy()
        signal = Signal(
            timestamp=datetime(2024, 6, 3, 14, 0, tzinfo=UTC),
            direction="long",
            strength=2.5,
            metadata={"vwap_spread_z": -2.5, "stop": 1.083, "target": 1.086},
        )
        ctx = PortfolioContext(
            open_positions=[],
            account_equity=Decimal("25000"),
            daily_pnl=Decimal("0"),
        )
        size = strategy.size_position(signal, ctx, instrument_6e)
        assert isinstance(size, int)
        assert size >= 1

    def test_returns_zero_on_zero_equity(self, instrument_6e: Instrument) -> None:
        strategy = _make_strategy()
        signal = Signal(
            timestamp=datetime(2024, 6, 3, 14, 0, tzinfo=UTC),
            direction="long",
            strength=2.5,
            metadata={"vwap_spread_z": -2.5, "stop": 1.083, "target": 1.086},
        )
        ctx = PortfolioContext(
            open_positions=[],
            account_equity=Decimal("0"),
            daily_pnl=Decimal("0"),
        )
        assert strategy.size_position(signal, ctx, instrument_6e) == 0
