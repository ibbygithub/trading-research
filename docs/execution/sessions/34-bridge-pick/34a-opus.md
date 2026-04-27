═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           34a-opus
Required model:    Opus 4.7
Effort:            S (~1.5 hr)
Entry blocked by:  33b (DONE) with explicit verdict
Hand off to:       34b-sonnet (path depends on 33b verdict)
Branch:            session-34-bridge-pick
═══════════════════════════════════════════════════════════════

# 34a — Bridge option pick

## Self-check
- [ ] I am Opus 4.7.
- [ ] 33b DONE; verdict is committed in `33b-gate-review.md`.
- [ ] I am applying pre-committed escape rules, not inventing them.

## What you produce

A decision document `34a-bridge-decision.md` selecting one of three branches per the 33b verdict:

**Branch 1 (33b PASS) — TS SIM (E1) vs TV Pine (E1') decision.**
Decision factors: TS SIM API maturity for limit + bracket orders, June 30 calendar slack, port effort to Pine. Recommend E1 unless TS SIM has known limitations.

**Branch 2 (33b FAIL with cost concern) — TV Pine port (E1').**
Confirm Pine path; estimate port effort (Mulligan logic in Pine is non-trivial); commit calendar to E1'+E2'+E3' across sprints 34–36.

**Branch 3 (33b FAIL → pivot) — pivot to 6A/6C OR class change.**
Apply pre-committed pivot rule from 33b verdict. Update plan v2 with sprints 35–38 reflowed for pivot path. Write new sprint-35 spec replacing original.

### Persona sign-off
All three personas sign the decision in writing.

## Acceptance
- [ ] `34a-bridge-decision.md` committed with branch chosen + reasoning.
- [ ] Persona sign-offs (3 blocks).
- [ ] If Branch 3: addendum to plan v2 + new sprint-35 spec committed.
- [ ] Handoff: `docs/execution/handoffs/34a-handoff.md`.
- [ ] current-state.md: 34a → DONE; 34b → READY with branch label.

## What you must NOT do
- Override the pre-committed escape rules.
- Implement bridge code (34b's job).

## References
- 33b verdict file.
- Original spec: [`../../../roadmap/session-specs/session-34-bridge-pick.md`](../../../roadmap/session-specs/session-34-bridge-pick.md).
