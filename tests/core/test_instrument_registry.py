"""Tests for trading_research.core.InstrumentRegistry."""

from decimal import Decimal

import pytest

from trading_research.core.instruments import Instrument, InstrumentRegistry


@pytest.fixture(scope="module")
def registry() -> InstrumentRegistry:
    return InstrumentRegistry()


def test_load_yaml(registry: InstrumentRegistry) -> None:
    instruments = registry.list()
    assert len(instruments) > 0


def test_get_zn(registry: InstrumentRegistry) -> None:
    zn = registry.get("ZN")
    assert isinstance(zn, Instrument)
    assert zn.symbol == "ZN"
    assert zn.tradestation_symbol == "@TY"
    assert zn.exchange == "CBOT"
    assert zn.asset_class == "rates"


def test_get_6e(registry: InstrumentRegistry) -> None:
    e = registry.get("6E")
    assert isinstance(e, Instrument)
    assert e.symbol == "6E"
    assert e.tradestation_symbol == "@EC"  # TS uses EC root, not EU (verified 2026-04-25)
    assert e.exchange == "CME"
    assert e.asset_class == "fx"
    assert e.tick_size == Decimal("0.00005")
    assert e.tick_value_usd == Decimal("6.25")
    assert e.contract_multiplier == Decimal("125000")
    assert e.intraday_initial_margin_usd is not None
    assert e.commission_per_side_usd is not None


def test_unknown_raises(registry: InstrumentRegistry) -> None:
    with pytest.raises(KeyError, match="NONEXISTENT"):
        registry.get("NONEXISTENT")


def test_tick_value_consistency(registry: InstrumentRegistry) -> None:
    zn = registry.get("ZN")
    assert zn.tick_value_usd == zn.tick_size * zn.contract_multiplier


def test_commission_fields_present(registry: InstrumentRegistry) -> None:
    for instrument in registry.list():
        assert instrument.commission_per_side_usd > Decimal("0"), (
            f"{instrument.symbol}: commission_per_side_usd must be positive"
        )


def test_margin_fields_present(registry: InstrumentRegistry) -> None:
    for instrument in registry.list():
        assert instrument.intraday_initial_margin_usd > Decimal("0"), (
            f"{instrument.symbol}: intraday_initial_margin_usd must be positive"
        )
