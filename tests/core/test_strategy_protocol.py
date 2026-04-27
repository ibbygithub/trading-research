"""Tests for the Strategy Protocol and its companion value types.

These tests verify that:
- A minimal concrete class satisfies the Protocol (structural typing works).
- Signal and ExitDecision dataclasses construct and round-trip correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trading_research.core.strategies import (
    ExitDecision,
    PortfolioContext,
    Position,
    Signal,
    Strategy,
)

# ---------------------------------------------------------------------------
# Minimal concrete strategy used across multiple tests
# ---------------------------------------------------------------------------


class _MinimalStrategy:
    """Bare-minimum class that satisfies the Strategy Protocol structurally."""

    def __init__(self) -> None:
        self._name = "minimal"
        self._template_name = "test-template"
        self._knobs: dict = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def template_name(self) -> str:
        return self._template_name

    @property
    def knobs(self) -> dict:
        return self._knobs

    def generate_signals(self, bars, features, instrument):
        return []

    def size_position(self, signal, context, instrument):
        return 1

    def exit_rules(self, position, current_bar, instrument):
        return ExitDecision(action="hold", reason="no condition met")


# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


def test_dummy_strategy_satisfies_protocol() -> None:
    """A concrete class with the right shape must satisfy the Strategy Protocol."""
    s = _MinimalStrategy()
    assert isinstance(s, Strategy), (
        "Expected _MinimalStrategy to satisfy Strategy Protocol via isinstance()."
    )


def test_strategy_protocol_rejects_incomplete_class() -> None:
    """A class missing required methods must NOT satisfy the Protocol."""

    class _Incomplete:
        @property
        def name(self) -> str:
            return "incomplete"

        # missing template_name, knobs, generate_signals, size_position, exit_rules

    assert not isinstance(_Incomplete(), Strategy)


# ---------------------------------------------------------------------------
# Signal dataclass
# ---------------------------------------------------------------------------


def test_signal_dataclass() -> None:
    """Signal constructs correctly and fields are accessible."""
    ts = datetime(2024, 3, 15, 14, 30, tzinfo=UTC)
    sig = Signal(timestamp=ts, direction="long", strength=1.8)

    assert sig.timestamp == ts
    assert sig.direction == "long"
    assert sig.strength == pytest.approx(1.8)
    assert sig.metadata == {}


def test_signal_metadata_is_independent() -> None:
    """Default metadata dict must not be shared between Signal instances."""
    s1 = Signal(timestamp=datetime(2024, 1, 1, tzinfo=UTC), direction="flat", strength=0.0)
    s2 = Signal(timestamp=datetime(2024, 1, 2, tzinfo=UTC), direction="flat", strength=0.0)
    s1.metadata["key"] = "value"
    assert "key" not in s2.metadata, "Mutable default must be per-instance."


# ---------------------------------------------------------------------------
# ExitDecision dataclass
# ---------------------------------------------------------------------------


def test_exit_decision_actions() -> None:
    """All four action literals must round-trip through ExitDecision."""
    for action in ("hold", "exit", "scale_in", "scale_out"):
        ed = ExitDecision(action=action, reason=f"test {action}")  # type: ignore[arg-type]
        assert ed.action == action
        assert ed.reason == f"test {action}"
        assert ed.price is None


def test_exit_decision_with_price() -> None:
    """ExitDecision.price accepts Decimal and is returned correctly."""
    ed = ExitDecision(action="exit", reason="limit hit", price=Decimal("4512.75"))
    assert ed.price == Decimal("4512.75")


# ---------------------------------------------------------------------------
# Position and PortfolioContext dataclasses
# ---------------------------------------------------------------------------


def test_position_dataclass() -> None:
    """Position constructs correctly and Decimal fields do not lose precision."""
    pos = Position(
        instrument_symbol="6E",
        entry_time=datetime(2024, 6, 1, 13, 0, tzinfo=UTC),
        entry_price=Decimal("1.08500"),
        size=1,
        direction="long",
        stop=Decimal("1.08300"),
        target=Decimal("1.08750"),
    )
    assert pos.instrument_symbol == "6E"
    assert pos.entry_price == Decimal("1.08500")
    assert pos.direction == "long"


def test_portfolio_context_dataclass() -> None:
    """PortfolioContext constructs and open_positions list is mutable."""
    ctx = PortfolioContext(
        open_positions=[],
        account_equity=Decimal("25000"),
        daily_pnl=Decimal("0"),
    )
    assert ctx.account_equity == Decimal("25000")
    assert ctx.open_positions == []
