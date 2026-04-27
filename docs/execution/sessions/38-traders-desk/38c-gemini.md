═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           38c-gemini
Required model:    Gemini 3.1 (Antigravity)
Effort:            S (~1.5 hr)
Entry blocked by:  38a (DONE)
Parallel-OK with:  38b
Hand off to:       38d-opus
Branch:            session-38-traders-desk
═══════════════════════════════════════════════════════════════

# 38c — Polish + theming + copy

Follows [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md).

## Self-check
- [ ] I am Gemini 3.1.
- [ ] 38a DONE.

## What you implement
- HTML/CSS theming consistency with existing replay app aesthetic.
- Copy edits in CLI help text.
- Error messages for the linter (clear "what failed and how to fix").

## What you must NOT do
- Modify strategy, risk, or execution layers.
- Add or remove tests beyond cosmetic copy edits in test names.
- Halt paper strategy.

## Acceptance
- [ ] Theming applied consistently.
- [ ] CLI help text reads cleanly.
- [ ] Linter error messages clear.
- [ ] Handoff: `docs/execution/handoffs/38c-handoff.md`.
- [ ] current-state.md: 38c → DONE.
