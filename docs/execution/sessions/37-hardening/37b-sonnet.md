═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           37b-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  37a (DONE)
Parallel-OK with:  37c
Hand off to:       38a-opus
Branch:            session-37-hardening
═══════════════════════════════════════════════════════════════

# 37b — Critical and High punch-list cleanup

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 37a DONE; punch-list exists.
- [ ] Strategy still RUNNING on paper.

## What you implement

Knock out top of punch-list. Each item gets a small commit referencing the
punch-list line.

**HARD RULE:** No strategy behaviour changes. Cleanup touches infrastructure
only:
- Telemetry, logs, reports, code clarity.
- Manifest migrations.
- Test coverage.
- Operational runbook entries.

If a punch-list item turns out to require a strategy change: ESCALATE — it
becomes a structural bug. Either restart the 30-day window OR move the item
to backlog.

## Acceptance
- [ ] All Critical and High items closed or moved with rationale.
- [ ] No commit changes signal generation, sizing, or exit logic.
- [ ] `uv run pytest` full suite green.
- [ ] One-page health-check CLI: `uv run trading-research health` runs.
- [ ] Handoff: `docs/execution/handoffs/37b-handoff.md`.
- [ ] current-state.md: 37b → DONE.

## What you must NOT do
- Change strategy behaviour.
- Halt the running paper strategy.
- Add new features.

## References
- Original spec §37b.
- 37a punch-list.
