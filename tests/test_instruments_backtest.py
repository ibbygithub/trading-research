"""Tests for instrument loader backtest cost helpers."""

from __future__ import annotations

from trading_research.data.instruments import get_cost_per_trade, load_instrument


def test_load_instrument_zn():
    spec = load_instrument("ZN")
    assert spec.tick_value_usd == 15.625
    assert spec.tick_size == 0.015625
    assert spec.point_value_usd == 1000.0


def test_get_cost_per_trade_zn():
    slip, comm = get_cost_per_trade("ZN")
    # slippage: 1 tick × $15.625 × 2 sides = $31.25
    assert abs(slip - 31.25) < 1e-9
    # commission: $2.00 × 2 sides = $4.00
    assert abs(comm - 4.00) < 1e-9


def test_get_cost_per_trade_6a():
    slip, comm = get_cost_per_trade("6A")
    # 6A tick_value_usd = $10.00; 1 tick × $10 × 2 = $20
    assert abs(slip - 20.0) < 1e-9
    assert abs(comm - 4.00) < 1e-9


def test_unknown_symbol_raises():
    import pytest
    with pytest.raises(KeyError):
        load_instrument("BOGUS")
