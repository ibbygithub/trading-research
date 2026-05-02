"""Composable regime filter layer.

A ``RegimeFilter`` is a Protocol with three methods:

- ``name`` — human-readable identifier for logging and reporting.
- ``fit(features)`` — compute any thresholds from a training-window features
  DataFrame.  Must be called before ``is_tradeable()``.
- ``is_tradeable(features, idx)`` — return True if the bar at position *idx*
  is in a regime where entry is permitted.

Multiple filters can be chained via ``RegimeFilterChain`` (AND-of-filters):
a bar is tradeable only when every filter in the chain returns True.

A named filter registry (``_FILTER_REGISTRY``) lets filter names in strategy
YAML knobs be resolved to concrete instances.

Design notes
------------
- Filters are stateful after ``fit()`` (they store the computed threshold).
  Create a fresh instance per walk-forward fold if the training window changes.
- ``is_tradeable()`` raises ``RuntimeError`` if called before ``fit()``.
  This is intentional: the caller must explicitly fit on training data rather
  than relying on silent defaults.
- The Protocol is ``@runtime_checkable`` for ``isinstance`` guards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import pandas as pd

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RegimeFilter(Protocol):
    """Structural interface every regime filter must satisfy."""

    @property
    def name(self) -> str:
        """Human-readable identifier, e.g. ``'volatility-regime(p75)'``."""
        ...

    def fit(self, features: pd.DataFrame) -> None:
        """Compute threshold(s) from *features* (training window).

        Must be called once before ``is_tradeable()``.  Calling ``fit()``
        again with different data resets the threshold.
        """
        ...

    def is_tradeable(self, features: pd.DataFrame, idx: int) -> bool:
        """Return True if the bar at *idx* is in a tradeable regime.

        Raises ``RuntimeError`` if ``fit()`` has not been called.
        """
        ...


# ---------------------------------------------------------------------------
# Named filter registry
# ---------------------------------------------------------------------------


_FILTER_REGISTRY: dict[str, type[Any]] = {}


def register_filter(name: str):  # noqa: ANN201
    """Class decorator: register a filter class under *name*."""

    def decorator(cls: type) -> type:
        _FILTER_REGISTRY[name] = cls
        return cls

    return decorator


def build_filter(name: str, **kwargs: Any) -> RegimeFilter:
    """Instantiate the registered filter class *name* with *kwargs*.

    Raises ``KeyError`` for unknown names.
    """
    if name not in _FILTER_REGISTRY:
        known = ", ".join(sorted(_FILTER_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown regime filter {name!r}. Known filters: {known}"
        )
    return _FILTER_REGISTRY[name](**kwargs)


# ---------------------------------------------------------------------------
# Composable chain
# ---------------------------------------------------------------------------


class RegimeFilterChain:
    """AND-of-filters chain: tradeable only when all filters agree.

    Pass a list of already-constructed ``RegimeFilter`` instances.
    Call ``fit(train_features)`` to fit all filters at once, then call
    ``is_tradeable(test_features, idx)`` per bar.
    """

    def __init__(self, filters: list[RegimeFilter]) -> None:
        self._filters = list(filters)

    def __len__(self) -> int:
        return len(self._filters)

    @property
    def filter_names(self) -> list[str]:
        return [f.name for f in self._filters]

    def fit(self, features: pd.DataFrame) -> None:
        """Fit every filter in the chain on *features* (training window)."""
        for f in self._filters:
            f.fit(features)

    def is_tradeable(self, features: pd.DataFrame, idx: int) -> bool:
        """Return True when ALL filters permit entry at bar *idx*."""
        return all(f.is_tradeable(features, idx) for f in self._filters)


# Import concrete filter implementations so their @register_filter decorators
# fire and populate _FILTER_REGISTRY when this package is imported.
from trading_research.strategies.regime import volatility_regime as _vol_regime  # noqa: F401, E402

__all__ = [
    "RegimeFilter",
    "RegimeFilterChain",
    "build_filter",
    "register_filter",
    "_FILTER_REGISTRY",
]
