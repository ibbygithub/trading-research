═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           32a-opus
Required model:    Opus 4.7
Effort:            S (~1 hr)
Entry blocked by:  31b (DONE)
Parallel-OK with:  D4, F2
Hand off to:       32b-sonnet
Branch:            session-32-mulligan
═══════════════════════════════════════════════════════════════

# 32a — Mulligan rule precise spec

## Self-check
- [ ] I am Opus 4.7.
- [ ] 31b DONE.
- [ ] Strategy Protocol Mulligan freshness invariant (29a) is in `core/strategies.py` docstring.

## What you produce

A spec document `mulligan-spec.md` and a stub test file (`tests/contracts/test_mulligan_freshness.py`).
The spec enumerates the three rules:

**M-1 Freshness (DS):** Mulligan re-entry allowed only when `Strategy.generate_signals`
emits a NEW `Signal` for the position's direction at strictly later timestamp
than original entry's trigger Signal. Re-evaluating same emitted Signal
does NOT count.

**M-2 Directional gate (mentor):** Long re-entry only at price ≥ original
entry + N×ATR. Short re-entry only at price ≤ original − N×ATR. Default N=0.3.

**M-3 Combined risk pre-defined:** Before second entry placed, combined
position's stop and target are computed and recorded. Combined risk does
not exceed the original strategy's per-trade risk limit; combined target
is at original target level.

### Stub test file (32b implements bodies)

`tests/contracts/test_mulligan_freshness.py` with these described tests:
- `test_fresh_signal_with_directional_gate_satisfied_accepted` — positive case.
- `test_adverse_pnl_only_re_trigger_rejected` — averaging-down detection.
- `test_same_signal_second_look_rejected` — same Signal.timestamp, no fresh emission.
- `test_directional_gate_long_lower_price_rejected` — fresh emission but worse price.
- `test_directional_gate_short_higher_price_rejected` — fresh emission but worse price.
- `test_combined_risk_computed_correctly` — combined stop/target math.

Each test body is `pytest.skip("Implemented in 32b-sonnet")`.

## Acceptance
- [ ] `mulligan-spec.md` committed with three rules.
- [ ] `tests/contracts/test_mulligan_freshness.py` committed (skipping).
- [ ] Handoff: `docs/execution/handoffs/32a-handoff.md`.
- [ ] current-state.md: 32a → DONE; 32b → READY.

## What you must NOT do
- Implement Mulligan code. 32b's job.
- Modify `core/strategies.py` (29a already updated docstring).

## References
- DS rule: [`outputs/planning/peer-reviews/data-scientist-review.md`](../../../../outputs/planning/peer-reviews/data-scientist-review.md) §7.
- Mentor directional rule: [`outputs/planning/peer-reviews/quant-mentor-review.md`](../../../../outputs/planning/peer-reviews/quant-mentor-review.md) §4.
