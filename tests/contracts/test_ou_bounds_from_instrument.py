"""Contract tests: OU tradeable bounds read from Instrument registry.

Written in 29a as stubs. Filled in 29d.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trading_research.core.instruments import Instrument
from trading_research.stats.stationarity import _interpret_ou, _composite_classification, ADFResult, HurstResult, OUResult


def _make_instrument(
    symbol: str = "6E",
    ou_bounds: dict[str, tuple[float, float]] | None = None,
) -> Instrument:
    """Build a minimal Instrument with configurable OU bounds."""
    return Instrument(
        symbol=symbol,
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
        tradeable_ou_bounds_bars=ou_bounds,
    )


def test_6e_tradeable_under_new_bounds() -> None:
    """6E vwap_spread_5m with OU half-life ~33 bars must classify TRADEABLE
    under per-instrument bounds (10, 80) at 5m."""
    inst = _make_instrument(
        ou_bounds={"5m": (10.0, 80.0), "15m": (4.0, 30.0)},
    )

    result = _interpret_ou(33.0, "5m", instrument=inst)
    assert result == "TRADEABLE"

    result_15m = _interpret_ou(11.8, "15m", instrument=inst)
    assert result_15m == "TRADEABLE"


def test_zn_classifications_unchanged_after_migration() -> None:
    """ZN classifications must be identical before and after migrating OU bounds
    from module constants to instrument registry."""
    # ZN bounds match the original module constants exactly.
    zn_inst = _make_instrument(
        symbol="ZN",
        ou_bounds={"1m": (5.0, 60.0), "5m": (3.0, 24.0), "15m": (2.0, 8.0)},
    )

    # Test values that fall in different classification buckets.
    assert _interpret_ou(10.0, "5m", instrument=zn_inst) == "TRADEABLE"
    assert _interpret_ou(2.0, "5m", instrument=zn_inst) == "TOO_FAST"
    assert _interpret_ou(30.0, "5m", instrument=zn_inst) == "TOO_SLOW"
    assert _interpret_ou(5.0, "15m", instrument=zn_inst) == "TRADEABLE"
    assert _interpret_ou(1.0, "15m", instrument=zn_inst) == "TOO_FAST"
    assert _interpret_ou(10.0, "15m", instrument=zn_inst) == "TOO_SLOW"

    # Without instrument, should get the same results from module constants.
    assert _interpret_ou(10.0, "5m") == "TRADEABLE"
    assert _interpret_ou(2.0, "5m") == "TOO_FAST"
    assert _interpret_ou(30.0, "5m") == "TOO_SLOW"


def test_stationarity_reads_bounds_from_instrument() -> None:
    """_interpret_ou must prefer bounds from the Instrument over module constants."""
    # Create an instrument with very different bounds than the default.
    custom_inst = _make_instrument(
        ou_bounds={"5m": (100.0, 200.0)},
    )

    # Half-life 33 would be TRADEABLE with default ZN bounds (3-24),
    # but should be TOO_FAST with these custom bounds (100-200).
    assert _interpret_ou(33.0, "5m", instrument=custom_inst) == "TOO_FAST"
    assert _interpret_ou(150.0, "5m", instrument=custom_inst) == "TRADEABLE"

    # Without instrument, falls back to module constants.
    assert _interpret_ou(33.0, "5m") == "TOO_SLOW"


def test_composite_uses_instrument_bounds() -> None:
    """_composite_classification must pass instrument through to OU interpretation."""
    inst_6e = _make_instrument(
        ou_bounds={"5m": (10.0, 80.0)},
    )

    adf = ADFResult(
        statistic=-20.0, p_value=0.001, lags_used=5,
        n_observations=1000, critical_values={"1%": -3.5, "5%": -2.9, "10%": -2.6},
        is_stationary=True, interpretation="STATIONARY (strong)",
    )
    hurst = HurstResult(exponent=0.45, n_windows=5, r_squared=0.95, interpretation="MEAN_REVERTING (weak)")
    ou = OUResult(half_life_bars=33.0, beta=-0.021, r_squared=0.05, interpretation="MEAN_REVERTING")

    # With 6E bounds (10, 80), half-life 33 is TRADEABLE.
    result = _composite_classification(adf, hurst, ou, "5m", instrument=inst_6e)
    assert result == "TRADEABLE_MR"

    # Without instrument, uses module defaults (3, 24) — half-life 33 is TOO_SLOW.
    result_no_inst = _composite_classification(adf, hurst, ou, "5m")
    assert result_no_inst == "TOO_SLOW"
