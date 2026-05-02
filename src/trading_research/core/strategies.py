"""Core Strategy Protocol and associated value types.

All strategy implementations must satisfy the ``Strategy`` Protocol — either by
explicit inheritance (not required) or by structural typing.  The Protocol is
``@runtime_checkable`` so ``isinstance(obj, Strategy)`` works for runtime
guards.

Three-method decomposition rationale
-------------------------------------
- ``generate_signals`` — pure signal generation from bars + features.
  No position state.  Easy to unit-test.
- ``size_position`` — pure sizing from signal + portfolio context.
  Isolated from signal logic; can be swapped without touching entry rules.
- ``exit_rules`` — pure exit decision from an open position + current bar.
  Supports hold / exit / scale_in (Mulligan re-entry) / scale_out.

All methods are side-effect-free.  State lives in the backtest engine and in
the ``PortfolioContext`` passed in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

import pandas as pd

if TYPE_CHECKING:
    from trading_research.core.instruments import Instrument


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    """A single directional signal produced by ``Strategy.generate_signals``.

    ``timestamp`` must be tz-aware (stored in UTC per project convention).
    ``strength`` is strategy-defined — could be z-score, confidence, etc.
    ``metadata`` is an open dict for anything the engine or reporter may want
    (feature values at signal time, regime label, etc.) without schema churn.
    """

    timestamp: datetime
    direction: Literal["long", "short", "flat"]
    strength: float
    metadata: dict = field(default_factory=dict)


@dataclass
class Position:
    """An open position passed into ``Strategy.exit_rules`` and ``PortfolioContext``.

    ``entry_time`` must be tz-aware.
    All price fields are ``Decimal`` to avoid float P&L rounding drift.
    """

    instrument_symbol: str
    entry_time: datetime
    entry_price: Decimal
    size: int
    direction: Literal["long", "short"]
    stop: Decimal
    target: Decimal


@dataclass
class ExitDecision:
    """What the strategy wants to do with an open position this bar.

    ``price`` is optional — used when the strategy wants to specify a limit
    price for scale_in / scale_out.  ``None`` means market / next-bar-open.
    """

    action: Literal["hold", "exit", "scale_in", "scale_out"]
    reason: str
    price: Decimal | None = None


@dataclass
class PortfolioContext:
    """Read-only snapshot of portfolio state passed to ``size_position`` and ``exit_rules``.

    Intentionally narrow for session 23-b.  Extend in a future session
    (with a migration) if strategies need intraday drawdown, per-instrument
    exposure, etc.
    """

    open_positions: list[Position]
    account_equity: Decimal
    daily_pnl: Decimal


# ---------------------------------------------------------------------------
# Strategy Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Strategy(Protocol):
    """Structural interface every strategy implementation must satisfy.

    Use ``isinstance(obj, Strategy)`` for runtime checks.  Concrete classes do
    not need to inherit from this Protocol — structural compatibility is enough.
    """

    @property
    def name(self) -> str:
        """Unique human-readable identifier for this strategy instance."""
        ...

    @property
    def template_name(self) -> str:
        """Name of the ``StrategyTemplate`` that produced this instance."""
        ...

    @property
    def knobs(self) -> dict:
        """Knob values this instance was configured with (serialisable dict)."""
        ...

    def generate_signals(
        self,
        bars: pd.DataFrame,
        features: pd.DataFrame,
        instrument: Instrument,
    ) -> list[Signal]:
        """Return signals for each bar that warrants action.

        Pure function — no side effects, no position state.
        ``bars`` and ``features`` share the same tz-aware UTC DatetimeIndex.
        Return an empty list when there are no signals.
        """
        ...

    def size_position(
        self,
        signal: Signal,
        context: PortfolioContext,
        instrument: Instrument,
    ) -> int:
        """Return integer contract count for ``signal``.

        Default convention per CLAUDE.md is volatility targeting, not Kelly.
        Return 0 to suppress the trade entirely.
        """
        ...

    def exit_rules(
        self,
        position: Position,
        current_bar: pd.Series,
        instrument: Instrument,
    ) -> ExitDecision:
        """Return an ExitDecision for an open position given the current bar.

        ``current_bar`` is a row from the features DataFrame — it includes
        pre-computed ATR, VWAP, and any other indicator the strategy needs
        for trailing stops or dynamic exits.

        Mulligan freshness invariant
        ----------------------------
        When ``exit_rules`` returns ``ExitDecision(action="scale_in", ...)``,
        the engine requires that a *new* ``Signal`` was emitted by
        ``generate_signals`` for the position's direction at a strictly later
        timestamp than the original entry's trigger signal.  Returning
        ``scale_in`` without a fresh emission is a Protocol violation and the
        engine will reject the action with a ``MulliganViolation`` exception.

        This rule exists to prevent adverse-P&L "averaging-down" from being
        implemented as a Mulligan re-entry.  A legitimate scale-in must be
        triggered by new confirming information, not by the position's
        unrealised loss.
        """
        ...
