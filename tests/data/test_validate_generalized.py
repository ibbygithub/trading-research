"""Generalized validate.py tests — instrument-agnostic behavior.

Verifies that last_trading_day() and RTH window logic work correctly for
multiple instruments, not just ZN.
"""

from __future__ import annotations

from datetime import date, time

from trading_research.core.instruments import InstrumentRegistry
from trading_research.data.validate import last_trading_day

_registry = InstrumentRegistry()
_ZN = _registry.get("ZN")
_6E = _registry.get("6E")


def test_last_trading_day_zn():
    """last_trading_day returns a valid weekday date for ZN."""
    result = last_trading_day(_ZN)
    assert isinstance(result, date)
    assert result.weekday() < 5  # Monday–Friday


def test_last_trading_day_6e():
    """last_trading_day returns a valid weekday date for 6E."""
    result = last_trading_day(_6E)
    assert isinstance(result, date)
    assert result.weekday() < 5


def test_last_trading_day_respects_reference_date():
    """last_trading_day result is at or before the given reference_date."""
    ref = date(2024, 6, 14)  # Friday
    result = last_trading_day(_ZN, reference_date=ref)
    assert result <= ref


def test_rth_window_zn():
    """ZN RTH open is 08:20 ET, close is 15:00 ET."""
    assert _ZN.rth_open_et == time(8, 20)
    assert _ZN.rth_close_et == time(15, 0)


def test_rth_window_6e():
    """6E RTH window is defined and open precedes close."""
    assert isinstance(_6E.rth_open_et, time)
    assert isinstance(_6E.rth_close_et, time)
    assert _6E.rth_open_et < _6E.rth_close_et
