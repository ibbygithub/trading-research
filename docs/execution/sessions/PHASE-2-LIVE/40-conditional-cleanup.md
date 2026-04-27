═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           40
Required model:    Sonnet 4.6
Effort:            M (~2-3 hr) — CONDITIONAL: only run if 39 surfaced items
Entry blocked by:  39 (DONE) with verdict "cleanup items"
Hand off to:       41
Branch:            session-40-conditional-cleanup
═══════════════════════════════════════════════════════════════

# 40 — Mid-window cleanup IF needed

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 39 verdict is "cleanup items" (not "continue clean" — if continue, skip this session).
- [ ] Strategy is RUNNING. I will NOT halt it.

## Hard rule
**Cleanup items must be telemetry / logging / reporting / polish.** Anything
that touches signal generation, sizing, or exits triggers ESCALATION.

## What you do
- Read 39's cleanup-item list.
- For each, evaluate: is this telemetry-only? If yes, fix. If no, escalate.

If escalated: STOP, write `40-escalation.md`, mark session IN_PROGRESS, notify human. Window restart is Ibby's call, not yours.

## Acceptance
- [ ] All cleanup items are either fixed (telemetry-only) or escalated.
- [ ] Strategy still RUNNING.
- [ ] No commits change signal/sizing/exit code.
- [ ] Handoff: `docs/execution/handoffs/40-handoff.md`.
- [ ] current-state.md: 40 → DONE.

## What you must NOT do
- Halt the strategy.
- Modify strategy behaviour.
