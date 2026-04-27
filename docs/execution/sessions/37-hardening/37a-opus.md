═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           37a-opus
Required model:    Opus 4.7
Effort:            S (~1 hr)
Entry blocked by:  36b (DONE)
Hand off to:       37b-sonnet, 37c-gemini
Branch:            session-37-hardening
═══════════════════════════════════════════════════════════════

# 37a — Punch-list authoring

## Self-check
- [ ] I am Opus 4.7.
- [ ] 36b DONE; 30-day window OPEN.
- [ ] Strategy is currently RUNNING on paper. I will NOT halt it.

## What you produce

`outputs/work-log/2026-XX-XX-37a-punch-list.md` — items ranked by blast radius:

- **Critical:** breaks paper trading or hides risk → fix this sprint.
- **High:** breaks future sprints (29-38 scope) → fix this sprint.
- **Medium:** breaks future sprints (>38) → backlog with rationale.
- **Low:** cosmetic / nice-to-have → fan-out to 37c or backlog.

### Common items expected
- Inconsistent timestamp tz handling.
- Missing structured-log correlation fields.
- Manifest fields added without migration.
- Cost-model drift if 36b found realised slippage outside backtest tolerance.
- Heartbeat false-positive frequency.
- Legacy `signal_module:` path in ZN strategies (decommission queue).
- Test coverage gaps.

## Acceptance
- [ ] Punch-list committed with each item ranked.
- [ ] Critical+High items routed to 37b; Low items routed to 37c or backlog.
- [ ] Handoff: `docs/execution/handoffs/37a-handoff.md`.
- [ ] current-state.md: 37a → DONE; 37b, 37c → READY.

## What you must NOT do
- Touch any code (37b/c's job).
- Recommend strategy changes (would restart window).

## References
- Original spec §37a.
