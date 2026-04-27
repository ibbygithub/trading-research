═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           35c-sonnet
Required model:    Sonnet 4.6
Effort:            M (~2 hr)
Entry blocked by:  35b (DONE)
Hand off to:       36a-sonnet
Branch:            session-35-paper-loop
═══════════════════════════════════════════════════════════════

# 35c — Failure-mode test implementation

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 35b DONE; `35b-failure-modes.md` lists 8 failure modes with test names.

## What you implement

`tests/execution/test_failure_modes.py` — one test per failure mode in 35b.

For each test:
- Construct fixture or mock that reproduces the failure-mode condition.
- Assert detection fires (logs, exception, halt).
- Assert response matches 35b's specified response.

If a test fails initially because the response is missing in 35a's code,
patch the response into the relevant module (`paper_loop.py`,
`reconciler.py`, etc.) and re-run.

## Acceptance
- [ ] All 8 failure-mode tests pass.
- [ ] Each test references the failure-mode number from 35b in its docstring.
- [ ] `uv run pytest` full suite green.
- [ ] Handoff: `docs/execution/handoffs/35c-handoff.md`.
- [ ] current-state.md: 35c → DONE; 36a → READY.

## What you must NOT do
- Add new failure modes not in 35b.
- Modify 35a's failure-mode-response logic without explaining in handoff.

## References
- 35b failure-modes file.
