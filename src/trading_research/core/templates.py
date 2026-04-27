"""Strategy template registry — parameterised strategy factory.

A ``StrategyTemplate`` pairs a strategy class with a Pydantic knobs model.
Instantiating a template with a knob dict validates the knobs and returns a
ready-to-use ``Strategy`` object.

``TemplateRegistry`` is a named registry of templates.  A module-level
singleton (``_GLOBAL_REGISTRY``) is populated by the ``@register_template``
decorator when a strategy module is imported.

Usage
-----
Define a knobs model and decorate your strategy class::

    class MyKnobs(BaseModel):
        band_sigma: float = Field(2.0, ge=1.0, le=4.0)

    @register_template(
        name="my-strategy",
        human_description="Example mean-reversion strategy",
        knobs_model=MyKnobs,
        supported_instruments=["6E"],
        supported_timeframes=["5m", "15m"],
    )
    class MyStrategy:
        def __init__(self, *, knobs: MyKnobs, template_name: str) -> None:
            self._knobs = knobs
            self._template_name = template_name
        ...

Instantiate via the global registry::

    from trading_research.core.templates import _GLOBAL_REGISTRY
    strategy = _GLOBAL_REGISTRY.instantiate("my-strategy", {"band_sigma": 2.5})
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from trading_research.core.strategies import Strategy


@dataclass
class StrategyTemplate:
    """A strategy blueprint: class + knob schema + metadata.

    ``strategy_class`` is typed as ``type[Any]`` rather than ``type[Strategy]``
    because Protocol classes cannot be used as class-type arguments in mypy
    without false positives.  At runtime, ``instantiate`` verifies the result
    satisfies the Strategy Protocol via ``isinstance``.
    """

    name: str
    human_description: str
    strategy_class: type[Any]
    knobs_model: type[BaseModel]
    supported_instruments: list[str] | Literal["*"]
    supported_timeframes: list[str] = field(default_factory=list)

    def instantiate(self, knobs: dict) -> Strategy:
        """Validate *knobs* against the schema and return a Strategy instance.

        Raises ``pydantic.ValidationError`` on type mismatch or out-of-range
        value.  Raises ``TypeError`` if the strategy class constructor does not
        accept the expected keyword arguments.
        """
        validated = self.knobs_model(**knobs)
        instance = self.strategy_class(knobs=validated, template_name=self.name)
        if not isinstance(instance, Strategy):
            raise TypeError(
                f"strategy_class {self.strategy_class.__name__!r} produced an "
                f"object that does not satisfy the Strategy Protocol."
            )
        return instance  # type: ignore[return-value]


class TemplateRegistry:
    """In-memory registry of ``StrategyTemplate`` objects.

    Instances are independent — the module-level ``_GLOBAL_REGISTRY`` singleton
    is separate from any test-local instances.  Tests should create their own
    ``TemplateRegistry()`` to avoid cross-test contamination.
    """

    def __init__(self) -> None:
        self._registry: dict[str, StrategyTemplate] = {}

    def register(self, template: StrategyTemplate) -> None:
        """Add *template* to the registry.

        Raises ``ValueError`` if a template with the same name is already
        registered.  Duplicate registration is almost always a bug (two modules
        both registering "vwap-reversion") and should be loud.
        """
        if template.name in self._registry:
            raise ValueError(
                f"Template {template.name!r} is already registered. "
                "Use a unique name or deregister the existing entry first."
            )
        self._registry[template.name] = template

    def get(self, name: str) -> StrategyTemplate:
        """Return the template for *name*, raising ``KeyError`` if unknown."""
        try:
            return self._registry[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._registry)) or "(none)"
            raise KeyError(
                f"Unknown template {name!r}. Known templates: {known}"
            ) from exc

    def list(self) -> list[StrategyTemplate]:
        """Return all registered templates in registration order."""
        return list(self._registry.values())

    def instantiate(self, template_name: str, knobs: dict) -> Strategy:
        """Convenience: ``get(template_name).instantiate(knobs)``."""
        return self.get(template_name).instantiate(knobs)


# ---------------------------------------------------------------------------
# Module-level singleton and decorator
# ---------------------------------------------------------------------------

_GLOBAL_REGISTRY: TemplateRegistry = TemplateRegistry()


def register_template(
    *,
    name: str,
    human_description: str,
    knobs_model: type[BaseModel],
    supported_instruments: list[str] | Literal["*"] = "*",
    supported_timeframes: list[str] | None = None,
) -> Callable[[type[Any]], type[Any]]:
    """Class decorator that registers a strategy class in ``_GLOBAL_REGISTRY``.

    The decorated class is returned unchanged — the decorator's only side
    effect is creating and registering a ``StrategyTemplate`` keyed by *name*.

    All kwargs except the decorated class map 1-to-1 to ``StrategyTemplate``
    fields.  ``strategy_class`` is set to the decorated class automatically.
    """

    def decorator(cls: type[Any]) -> type[Any]:
        template = StrategyTemplate(
            name=name,
            human_description=human_description,
            strategy_class=cls,
            knobs_model=knobs_model,
            supported_instruments=supported_instruments,
            supported_timeframes=supported_timeframes or [],
        )
        _GLOBAL_REGISTRY.register(template)
        return cls

    return decorator
