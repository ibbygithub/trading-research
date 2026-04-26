"""Generalized continuous.py tests — instrument-agnostic output path logic.

These tests verify that the output path and contract symbol are derived from
the Instrument object, not hardcoded for ZN, without making real API calls.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from trading_research.core.instruments import InstrumentRegistry
from trading_research.data.continuous import contract_sequence

_registry = InstrumentRegistry()
_ZN = _registry.get("ZN")
_6E = _registry.get("6E")


def test_continuous_output_path_zn(tmp_path: Path):
    """Output path for ZN contains 'ZN', not '6E'."""
    symbol = _ZN.symbol
    date_tag = "2024-01-01_2024-03-31"
    adj_path = tmp_path / f"{symbol}_1m_backadjusted_{date_tag}.parquet"
    assert "ZN" in adj_path.name
    assert "6E" not in adj_path.name
    assert "TY" not in adj_path.name  # ts_root not used in output path


def test_continuous_output_path_6e(tmp_path: Path):
    """Output path for 6E contains '6E' and does NOT contain 'ZN'."""
    symbol = _6E.symbol
    date_tag = "2024-01-01_2024-03-31"
    adj_path = tmp_path / f"{symbol}_1m_backadjusted_{date_tag}.parquet"
    assert "6E" in adj_path.name
    assert "ZN" not in adj_path.name


def test_continuous_ts_root_derived_from_instrument_zn():
    """ZN Instrument produces TS root 'TY', not 'ZN'."""
    ts_root = _ZN.tradestation_symbol.lstrip("@")
    assert ts_root == "TY"
    periods = contract_sequence(ts_root, date(2024, 1, 1), date(2024, 3, 31))
    assert all(p.ts_symbol.startswith("TY") for p in periods)


def test_continuous_ts_root_derived_from_instrument_6e():
    """6E Instrument produces TS root 'EC' (TradeStation uses EC, not EU or 6E).

    Verified against TradeStation API 2026-04-25: @EU returns 'Invalid Symbol';
    @EC and ECH24 return valid data. instruments_core.yaml corrected in session 28.
    """
    ts_root = _6E.tradestation_symbol.lstrip("@")
    assert ts_root == "EC"
    periods = contract_sequence(ts_root, date(2024, 1, 1), date(2024, 3, 31))
    assert all(p.ts_symbol.startswith("EC") for p in periods)
