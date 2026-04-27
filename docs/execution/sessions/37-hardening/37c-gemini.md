═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           37c-gemini
Required model:    Gemini 3.1 (Antigravity)
Effort:            S (~2 hr)
Entry blocked by:  37a (DONE)
Parallel-OK with:  37b
Hand off to:       38a-opus
Branch:            session-37-hardening
═══════════════════════════════════════════════════════════════

# 37c — Mechanical fan-out

Follows [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md).

## Self-check
- [ ] I am Gemini 3.1 in Antigravity.
- [ ] 37a DONE; punch-list "Low" items + docstring/test-coverage spec exist.

## What you implement

- Docstring fills on touched modules (37b's modified files).
- Test coverage on functions newly touched in 37b. **Sonnet pre-writes test fixtures (in 37b's spec); you fill implementation/assertions.**
- README updates if any.
- Copy edits in error messages.

## What you must NOT do

- Modify production strategy/risk/execution logic.
- Author your own tests against canonical references without spec-author pre-writing fixtures.
- Halt the paper strategy.

## Acceptance
- [ ] Docstrings filled where 37a punch-list flagged.
- [ ] Test coverage gaps closed.
- [ ] Copy edits applied.
- [ ] Handoff: `docs/execution/handoffs/37c-handoff.md`.
- [ ] current-state.md: 37c → DONE.

## References
- Gemini playbook.
- 37a punch-list.
