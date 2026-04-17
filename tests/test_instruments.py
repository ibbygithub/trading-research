"""Tests for the instrument registry loader."""

import pytest

from trading_research.data.instruments import (
    InstrumentRegistry,
    load_instruments,
)


def test_default_registry_loads_zn():
    reg = load_instruments()
    assert isinstance(reg, InstrumentRegistry)
    zn = reg.get("ZN")
    assert zn.root_symbol == "ZN"
    assert zn.continuous_symbol == "@TY"
    assert zn.exchange == "CBOT"
    assert zn.tick_size == 0.015625
    assert zn.tick_value_usd == 15.625
    assert zn.point_value_usd == 1000.0
    assert zn.session.timezone == "America/New_York"


def test_unknown_instrument_raises_with_known_list():
    reg = load_instruments()
    with pytest.raises(KeyError, match="Unknown instrument"):
        reg.get("NONEXISTENT")


def test_instrument_spec_is_frozen():
    from pydantic import ValidationError

    reg = load_instruments()
    zn = reg.get("ZN")
    with pytest.raises(ValidationError):
        zn.tick_size = 0.0  # type: ignore[misc]
