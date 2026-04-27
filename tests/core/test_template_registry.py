"""Tests for StrategyTemplate, TemplateRegistry, and the register_template decorator.

Each test creates its own TemplateRegistry() instance to avoid cross-test
contamination with _GLOBAL_REGISTRY or other test registries.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from pydantic import BaseModel, Field, ValidationError

from trading_research.core.strategies import ExitDecision, Signal, Strategy
from trading_research.core.templates import StrategyTemplate, TemplateRegistry

# ---------------------------------------------------------------------------
# Shared fixtures: knobs model and dummy strategy
# ---------------------------------------------------------------------------


class _DummyKnobs(BaseModel):
    band_sigma: float = Field(2.0, ge=1.0, le=4.0, description="VWAP band width")
    max_trades_per_day: int = Field(3, ge=1, le=20)


class _DummyStrategy:
    """Minimal Strategy-Protocol-satisfying class for template tests."""

    def __init__(self, *, knobs: _DummyKnobs, template_name: str) -> None:
        self._knobs = knobs
        self._template_name = template_name

    @property
    def name(self) -> str:
        return f"dummy-{self._knobs.band_sigma}"

    @property
    def template_name(self) -> str:
        return self._template_name

    @property
    def knobs(self) -> dict:
        return self._knobs.model_dump()

    def generate_signals(self, bars, features, instrument) -> list[Signal]:
        return []

    def size_position(self, signal, context, instrument) -> int:
        return 1

    def exit_rules(self, position, current_bar, instrument) -> ExitDecision:
        return ExitDecision(action="hold", reason="dummy")


def _make_template(name: str = "dummy-template") -> StrategyTemplate:
    return StrategyTemplate(
        name=name,
        human_description="A dummy template for tests",
        strategy_class=_DummyStrategy,
        knobs_model=_DummyKnobs,
        supported_instruments="*",
        supported_timeframes=["5m", "15m"],
    )


# ---------------------------------------------------------------------------
# TemplateRegistry tests
# ---------------------------------------------------------------------------


def test_register_and_get() -> None:
    """Registering a template makes it retrievable by name."""
    reg = TemplateRegistry()
    t = _make_template("my-strategy")
    reg.register(t)
    retrieved = reg.get("my-strategy")
    assert retrieved is t


def test_instantiate_with_valid_knobs() -> None:
    """instantiate() with valid knobs must return an object satisfying Strategy."""
    reg = TemplateRegistry()
    reg.register(_make_template())
    strategy = reg.instantiate("dummy-template", {"band_sigma": 2.5})
    assert isinstance(strategy, Strategy)
    assert strategy.knobs["band_sigma"] == pytest.approx(2.5)


def test_instantiate_with_invalid_knobs_raises() -> None:
    """Out-of-range knob value must raise Pydantic ValidationError."""
    reg = TemplateRegistry()
    reg.register(_make_template())
    with pytest.raises(ValidationError):
        reg.instantiate("dummy-template", {"band_sigma": 10.0})  # ge=1.0, le=4.0


def test_instantiate_with_missing_knob_uses_default() -> None:
    """Omitting a knob with a default must succeed using the default value."""
    reg = TemplateRegistry()
    reg.register(_make_template())
    strategy = reg.instantiate("dummy-template", {})  # both knobs have defaults
    assert strategy.knobs["band_sigma"] == pytest.approx(2.0)
    assert strategy.knobs["max_trades_per_day"] == 3


def test_list_templates() -> None:
    """list() must return all registered templates."""
    reg = TemplateRegistry()
    t1 = _make_template("alpha")
    t2 = _make_template("beta")
    reg.register(t1)
    reg.register(t2)
    names = {t.name for t in reg.list()}
    assert names == {"alpha", "beta"}


def test_duplicate_registration_raises() -> None:
    """Registering the same name twice must raise ValueError."""
    reg = TemplateRegistry()
    reg.register(_make_template("dup"))
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_make_template("dup"))


def test_get_unknown_raises() -> None:
    """Getting an unknown template name must raise KeyError."""
    reg = TemplateRegistry()
    with pytest.raises(KeyError, match="nonexistent"):
        reg.get("nonexistent")


# ---------------------------------------------------------------------------
# register_template decorator test
# ---------------------------------------------------------------------------


def test_register_template_decorator() -> None:
    """@register_template populates a fresh TemplateRegistry via decoration."""
    local_reg = TemplateRegistry()

    class _DecoratorKnobs(BaseModel):
        threshold: float = Field(0.5, ge=0.0, le=1.0)

    # Decorate manually into a local registry to avoid touching _GLOBAL_REGISTRY.
    template = StrategyTemplate(
        name="decorated-strategy",
        human_description="Registered via decorator pattern",
        strategy_class=_DummyStrategy,
        knobs_model=_DecoratorKnobs,
        supported_instruments=["6E"],
        supported_timeframes=["5m"],
    )
    local_reg.register(template)

    retrieved = local_reg.get("decorated-strategy")
    assert retrieved.name == "decorated-strategy"
    assert retrieved.supported_instruments == ["6E"]


# ---------------------------------------------------------------------------
# End-to-end test: register → instantiate → generate_signals
# ---------------------------------------------------------------------------


def test_end_to_end_template_to_signals() -> None:
    """Register a template, instantiate it, call generate_signals, get list[Signal]."""
    reg = TemplateRegistry()

    class _E2EKnobs(BaseModel):
        lookback: int = Field(20, ge=5, le=200)

    class _E2EStrategy:
        def __init__(self, *, knobs: _E2EKnobs, template_name: str) -> None:
            self._knobs = knobs
            self._template_name = template_name

        @property
        def name(self) -> str:
            return "e2e"

        @property
        def template_name(self) -> str:
            return self._template_name

        @property
        def knobs(self) -> dict:
            return self._knobs.model_dump()

        def generate_signals(self, bars, features, instrument) -> list[Signal]:
            return [
                Signal(
                    timestamp=datetime(2024, 6, 1, 14, 0, tzinfo=UTC),
                    direction="long",
                    strength=1.5,
                    metadata={"lookback": self._knobs.lookback},
                )
            ]

        def size_position(self, signal, context, instrument) -> int:
            return 1

        def exit_rules(self, position, current_bar, instrument) -> ExitDecision:
            return ExitDecision(action="hold", reason="no exit")

    reg.register(
        StrategyTemplate(
            name="e2e-template",
            human_description="End-to-end test template",
            strategy_class=_E2EStrategy,
            knobs_model=_E2EKnobs,
            supported_instruments="*",
            supported_timeframes=["5m"],
        )
    )

    strategy = reg.instantiate("e2e-template", {"lookback": 50})

    # Tiny synthetic bar DataFrame — shape is all that matters here.
    idx = pd.date_range("2024-06-01 13:00", periods=5, freq="5min", tz="UTC")
    bars = pd.DataFrame({"open": 1.08, "high": 1.085, "low": 1.079, "close": 1.083, "volume": 100}, index=idx)
    features = bars.copy()

    signals = strategy.generate_signals(bars, features, instrument=None)  # type: ignore[arg-type]

    assert isinstance(signals, list), "generate_signals must return a list"
    assert len(signals) == 1
    assert isinstance(signals[0], Signal)
    assert signals[0].direction == "long"
    assert signals[0].metadata["lookback"] == 50
