═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           36b-opus
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  36a (DONE)
Hand off to:       37a-opus
Branch:            session-36-first-paper-trade
═══════════════════════════════════════════════════════════════

# 36b — Divergence interpretation + 30-day window opens

## Self-check
- [ ] I am Opus 4.7.
- [ ] 36a DONE; first paper trade record exists.

## What you produce

`runs/paper-trading/<strategy>/36b-paper-day-1-review.md` containing
three persona observations and an initial divergence verdict.

### Mentor block
- Does actual market behaviour during the trade match backtest's assumed structure?
- Trigger-vs-entry separation behaving as designed (OU inertia from session 28)?
- War-story signals — does equity curve "feel right" for 6E reversion?

### Data Scientist block
- Per-trade entry-price slippage vs sprint 30 cost model.
- If realised slippage is consistently outside sprint 30's pessimistic bound: cost-model update queued for sprint 42.
- Trade count per week within sprint 30 bootstrap CI?
- Featureset hash on every load was expected one (zero drift)?

### Architect block
- Did heartbeat fire? Falsely or correctly?
- Reconciliation mismatches?
- Loss-limit headroom — how close to a circuit breaker?

### Initial divergence verdict
One of: "within tolerance" / "needs cost-model update queued for sprint 42" / "structural problem — pause and investigate."

### Open the 30-day discipline window
Acceptance: strategy is now running continuously; sprints 37+ do not stop it.

## Acceptance
- [ ] All three persona blocks committed.
- [ ] Initial divergence verdict explicit.
- [ ] 30-day window declared open in work log with start date (today).
- [ ] Strategy continues running into sprint 37 — DO NOT halt for cleanup.
- [ ] Handoff: `docs/execution/handoffs/36b-handoff.md`.
- [ ] current-state.md: 36b → DONE; 37a → READY.

## What you must NOT do
- Halt the strategy for cleanup.
- Recommend knob changes (would restart window).
- Advance to live (Phase 2D, far away).

## References
- Mentor §6 reframing.
- Original spec §36b.
