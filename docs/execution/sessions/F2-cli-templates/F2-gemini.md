═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           F2-gemini
Required model:    Gemini 3.1 (Antigravity)
Effort:            S (~1.5 hr)
Entry blocked by:  Sprint 29 (DONE)
Parallel-OK with:  32a, 32b, D4
Hand off to:       (none — independent)
Branch:            session-F2-cli
═══════════════════════════════════════════════════════════════

# F2 — CLI subcommands: list-templates, describe-template, backtest --template

Follows [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md). Three pre-written test files from Sonnet.

## Self-check
- [ ] I am Gemini 3.1.
- [ ] Sprint 29 DONE; TemplateRegistry on call path.
- [ ] Pre-written test files exist:
  - `tests/cli/test_list_templates.py`
  - `tests/cli/test_describe_template.py`
  - `tests/cli/test_backtest_with_knobs.py`

## What you implement

Per [`../../../roadmap/session-specs/session-F2-cli-template-subcommands.md`](../../../roadmap/session-specs/session-F2-cli-template-subcommands.md):
- `src/trading_research/cli/templates.py` — Typer commands.
- Extension to `cli/backtest.py` for `--template` mode + `--knobs k=v` parsing via Pydantic.

## Acceptance
- [ ] All three pre-written tests pass.
- [ ] `uv run trading-research list-templates` prints `vwap-reversion-v1`.
- [ ] `uv run trading-research describe-template vwap-reversion-v1` prints knobs with descriptions.
- [ ] No TemplateRegistry public API change.
- [ ] Handoff: `docs/execution/handoffs/F2-handoff.md`.
- [ ] current-state.md: F2 → DONE.

## What you must NOT do
- Mutate templates from CLI.
- Add web UI for templates.
