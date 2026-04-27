═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           39
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  38d (Phase 1 DONE), calendar +5 days from sprint 36
Hand off to:       40 (conditional) OR 41 (skip 40)
Branch:            session-39-week1-review
═══════════════════════════════════════════════════════════════

# 39 — Week-1 paper review

## Self-check
- [ ] I am Opus 4.7.
- [ ] Phase 1 DONE; 30-day window OPEN; ~5 trading days elapsed.
- [ ] Strategy is RUNNING; I will NOT halt it for this review.

## Inputs
- 5 days of paper trade logs.
- 5 daily divergence reports.
- Heartbeat firing log.

## Three-persona pass

**Mentor:**
- Trade cadence and behaviour matching backtest? Surprises in market structure?

**Data Scientist:**
- Per-trade slippage relative to sprint 30 cost-model bounds.
- Stable or trending divergence?

**Architect:**
- New failure modes observed?
- Heartbeat false-positive rate?

## Output
`runs/paper-trading/<strategy>/week-1-review.md`. Verdict:
- "Continue clean" → skip session 40, next is session 41 at +12 days.
- "Cleanup items" → list specific items for session 40.

## Acceptance
- [ ] Three persona observations recorded.
- [ ] Verdict explicit: continue / cleanup needed.
- [ ] Strategy still RUNNING.
- [ ] Handoff: `docs/execution/handoffs/39-handoff.md`.
- [ ] current-state.md: 39 → DONE; 40 → READY (if cleanup) or BLOCKED-skip; 41 → READY at +12 days.

## What you must NOT do
- Halt the strategy.
- Change knobs.
- Recommend ML or pairs work.
