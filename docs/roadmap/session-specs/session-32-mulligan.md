# Session 32 — Mulligan scale-in with directional gate

**Status:** Spec — ready to execute after sprint 31
**Effort:** 1 day, two sub-sprints (S+M)
**Depends on:** Sprint 29 (Strategy Protocol, freshness invariant docstring)
**Unblocks:** Sprint 33 (Track C gate)
**Personas required:** Data Scientist (freshness rule), Mentor (directional gate)

## Goal

Implement Mulligan re-entry on a fresh signal with a defined combined risk and
target. CLAUDE.md permits this; averaging-down (no fresh signal, just adverse
P&L) is forbidden. The implementation enforces both rules mechanically.

## The three rules

**Rule M-1 — Fresh signal required (data scientist).** A Mulligan re-entry
is allowed only when `Strategy.generate_signals` emits a *new* `Signal`
object for the position's direction at a strictly later timestamp than the
original entry's trigger signal. Re-evaluating the same emitted signal does
not count.

**Rule M-2 — Directional price gate (mentor).** For longs: the new entry
price must be ≥ original entry price + N×ATR. For shorts: ≤ original − N×ATR.
Default N=0.3. This blocks "fresh-looking" same-direction signals that fire
because the market is trending against the original entry.

**Rule M-3 — Combined risk pre-defined.** Before the second entry is placed,
the combined position's stop and target are computed and recorded. The
combined risk per CLAUDE.md does not exceed the original strategy's per-trade
risk limit; the combined target is at the original target's level.

## In scope

### 32a — Spec (Opus 4.7, ~1 hr)

**Outputs:**
- This document amended with the precise spec for `MulliganDecision`.
- Stub test file `tests/contracts/test_mulligan_freshness.py` covering:
  - Positive: fresh `Signal` emission for the same direction with directional
    gate satisfied → `scale_in` is accepted.
  - Negative 1 (averaging-down): adverse-P&L-only re-trigger without fresh
    `Signal` → `MulliganViolation` raised.
  - Negative 2 (same-signal-second-look): same `Signal.timestamp` re-evaluated
    → rejected.
  - Negative 3 (directional gate): fresh `Signal` but entry price worse than
    original (long re-entry at lower price than original) → rejected.
  - Combined-risk test: combined stop and target computed correctly given
    two entries.
- Strategy Protocol docstring already updated in 29a — no further change there.

### 32b — Implementation (Sonnet 4.6, ~3 hr)

**Outputs:**
- `src/trading_research/strategies/mulligan.py`:
  - `MulliganController` class. Holds reference to the position's last consumed
    Signal timestamp; rejects scale-in unless a strictly-later Signal of the
    same direction is presented.
  - `combined_risk(orig: Position, new_entry_price, knobs) -> (stop, target)`.
  - `MulliganViolation` exception.
- `src/trading_research/backtest/engine.py`:
  - When `Strategy.exit_rules` returns `ExitDecision(action="scale_in", ...)`,
    engine consults `MulliganController`. If consult fails → `MulliganViolation`
    raised, trade rejected, logged.
- `vwap-reversion-v1` template gains:
  - `mulligan_enabled: bool = False`
  - `mulligan_n_atr: float = 0.3` (the directional-gate parameter).
  - `mulligan_max_scale_ins: int = 1` (cap; default one Mulligan per trade).

## Acceptance

- [ ] All four `test_mulligan_freshness.py` cases pass (positive + 3 negatives).
- [ ] `combined_risk` test passes.
- [ ] Walk-forward run with `mulligan_enabled=True` produces a trial record.
- [ ] `MulliganController.last_consumed_ts` is the freshness anchor; not
      reachable for mutation by strategy code.
- [ ] Strategy Protocol docstring rule (sprint 29) is enforced by the engine.

## Out of scope

- More than one Mulligan per trade (`mulligan_max_scale_ins > 1`). Future sprint.
- Symmetric scale-out (Mulligan exits). Future sprint.

## References

- CLAUDE.md "Re-entries into existing positions" rule
- `outputs/planning/peer-reviews/data-scientist-review.md` §7
- `outputs/planning/peer-reviews/quant-mentor-review.md` §4
- `src/trading_research/core/strategies.py` Strategy Protocol
