"""Mulligan scale-in controller.

Enforces three rules before allowing a second entry into an open position:

Rule M-1 — Fresh signal required.
    The candidate signal's timestamp must be strictly later than the last
    consumed signal timestamp.  Re-evaluating the same emitted signal does
    not satisfy this rule.

Rule M-2 — Directional price gate.
    For longs: new_entry_price >= orig.entry_price - n_atr * atr
    For shorts: new_entry_price <= orig.entry_price + n_atr * atr
    Default n_atr=0.3 (~1.2 pips on 6E at typical 5m ATR).
    Blocks scale-ins that are more than n_atr ATR worse than the original
    entry — prevents chasing a runaway adverse move.

    Note: n_atr=0.3 is intentionally loose at session 32 defaults.
    Session 33 parameter sweep should include n_atr ∈ {0.3, 0.5, 1.0, 1.5, 2.0}.

Rule M-3 — Combined risk pre-defined.
    Before the second entry is placed, combined stop and target are computed
    by combined_risk() and recorded.  Combined dollar risk is logged but not
    a hard block — the size cap (max_scale_ins=1) is the primary limiter.

combined_risk() computes:
    combined_stop   = orig.stop (thesis-invalidation level unchanged)
    combined_target = weighted_avg_entry ± mulligan_target_atr × atr
                      (ATR multiples from average entry; parameterised for
                      backtesting sweep in session 33)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

import structlog

from trading_research.core.strategies import Position, Signal

log = structlog.get_logger(__name__)


class MulliganViolation(Exception):  # noqa: N818 — spec-mandated name
    """Raised when a proposed scale-in violates one of the Mulligan rules."""


@dataclass(frozen=True)
class CombinedRisk:
    """Pre-defined risk envelope for a scaled-in position."""

    combined_stop: Decimal
    combined_target: Decimal
    combined_avg_entry: Decimal
    combined_size: int


class MulliganController:
    """Per-position guard that enforces Rules M-1, M-2, and M-3.

    Instantiated by the engine at position-entry time.  The engine owns the
    instance; strategy code never holds a reference to it, so
    ``last_consumed_ts`` cannot be mutated by strategy logic.

    Parameters
    ----------
    entry_trigger_ts:
        Timestamp of the signal that triggered the original entry.
        Becomes the initial freshness anchor.
    direction:
        Direction of the open position ("long" or "short").
    max_scale_ins:
        Hard cap on total Mulligan re-entries for this position.
    """

    def __init__(
        self,
        entry_trigger_ts: datetime,
        direction: Literal["long", "short"],
        max_scale_ins: int = 1,
    ) -> None:
        self._last_consumed_ts: datetime = entry_trigger_ts
        self._direction: Literal["long", "short"] = direction
        self._max_scale_ins: int = max_scale_ins
        self._scale_in_count: int = 0

    @property
    def last_consumed_ts(self) -> datetime:
        """Freshness anchor.  Read-only — strategy code cannot advance this."""
        return self._last_consumed_ts

    @property
    def scale_in_count(self) -> int:
        return self._scale_in_count

    def check_scale_in(
        self,
        candidate_signal: Signal,
        position: Position,
        new_entry_price: Decimal,
        atr: float,
        n_atr: float,
    ) -> None:
        """Validate all Mulligan rules.

        On success: advances ``last_consumed_ts`` and increments
        ``scale_in_count``.

        Parameters
        ----------
        candidate_signal:
            The signal proposed to justify the scale-in.
        position:
            The currently open position (for gate and direction check).
        new_entry_price:
            Proposed fill price for the second entry.
        atr:
            Current bar's ATR value (used for the directional gate).
        n_atr:
            Gate width in ATR multiples (knob ``mulligan_n_atr``).

        Raises
        ------
        MulliganViolation
            When any of M-1, M-2, or the scale-in cap is exceeded.
        """
        # --- Rule M-1: fresh signal required ---
        if candidate_signal.timestamp <= self._last_consumed_ts:
            raise MulliganViolation(
                f"Rule M-1: signal timestamp {candidate_signal.timestamp!s} "
                f"not strictly later than last consumed {self._last_consumed_ts!s}"
            )

        # M-1b: signal direction must match position direction
        if candidate_signal.direction != self._direction:
            raise MulliganViolation(
                f"Rule M-1: signal direction '{candidate_signal.direction}' "
                f"does not match position direction '{self._direction}'"
            )

        # --- Rule M-2: directional price gate ---
        gate_offset = Decimal(str(n_atr * atr))
        if self._direction == "long":
            floor = position.entry_price - gate_offset
            if new_entry_price < floor:
                raise MulliganViolation(
                    f"Rule M-2: long scale-in at {new_entry_price} is more than "
                    f"{n_atr}×ATR ({atr:.6f}) below original entry "
                    f"{position.entry_price} (floor={floor})"
                )
        else:  # short
            ceiling = position.entry_price + gate_offset
            if new_entry_price > ceiling:
                raise MulliganViolation(
                    f"Rule M-2: short scale-in at {new_entry_price} is more than "
                    f"{n_atr}×ATR ({atr:.6f}) above original entry "
                    f"{position.entry_price} (ceiling={ceiling})"
                )

        # --- Scale-in cap ---
        if self._scale_in_count >= self._max_scale_ins:
            raise MulliganViolation(
                f"Max scale-ins ({self._max_scale_ins}) already reached for "
                f"this position"
            )

        # All rules passed — consume the signal.
        self._last_consumed_ts = candidate_signal.timestamp
        self._scale_in_count += 1

        log.info(
            "mulligan.scale_in_accepted",
            signal_ts=str(candidate_signal.timestamp),
            new_entry_price=str(new_entry_price),
            scale_in_count=self._scale_in_count,
        )


def combined_risk(
    orig: Position,
    new_entry_price: Decimal,
    scale_in_size: int,
    atr: float,
    mulligan_target_atr: float,
) -> CombinedRisk:
    """Compute combined stop and target for a Mulligan-scaled position.

    Rule M-3 contract: this function MUST be called before the second entry
    fill is applied.  The engine records the result before placing the order.

    Strategy
    --------
    combined_stop   = orig.stop (thesis-invalidation level unchanged)
    combined_target = weighted_avg_entry ± mulligan_target_atr × atr

    The target is anchored to the average entry rather than VWAP so it
    remains valid after price has moved away from session VWAP.
    ``mulligan_target_atr`` is a knob to sweep in session 33.

    Combined dollar risk is logged but not enforced as a hard block —
    the ``max_scale_ins=1`` cap is the primary size limiter.

    Parameters
    ----------
    orig:
        The existing open position.
    new_entry_price:
        Proposed fill price for the Mulligan leg.
    scale_in_size:
        Number of contracts in the scale-in leg.
    atr:
        Current bar ATR (same value used in check_scale_in gate).
    mulligan_target_atr:
        ATR multiples from average entry for the combined target.

    Returns
    -------
    CombinedRisk
        Named tuple of (combined_stop, combined_target, combined_avg_entry,
        combined_size).
    """
    combined_size = orig.size + scale_in_size
    # Weighted average entry (Decimal arithmetic throughout)
    combined_avg_entry = (
        orig.entry_price * orig.size + new_entry_price * scale_in_size
    ) / combined_size

    target_offset = Decimal(str(mulligan_target_atr * atr))
    if orig.direction == "long":
        combined_target = combined_avg_entry + target_offset
    else:
        combined_target = combined_avg_entry - target_offset

    combined_stop = orig.stop  # thesis-invalidation level unchanged

    log.info(
        "mulligan.combined_risk",
        orig_entry=str(orig.entry_price),
        new_entry=str(new_entry_price),
        combined_avg_entry=str(combined_avg_entry),
        combined_size=combined_size,
        combined_stop=str(combined_stop),
        combined_target=str(combined_target),
    )

    return CombinedRisk(
        combined_stop=combined_stop,
        combined_target=combined_target,
        combined_avg_entry=combined_avg_entry,
        combined_size=combined_size,
    )
