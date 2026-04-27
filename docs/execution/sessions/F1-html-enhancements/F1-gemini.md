═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           F1-gemini
Required model:    Gemini 3.1 (Antigravity)
Effort:            M (~3 hr)
Entry blocked by:  Sprint 27 (DONE — composite ranking + BH)
Parallel-OK with:  33a
Hand off to:       (none — independent)
Branch:            session-F1-html
═══════════════════════════════════════════════════════════════

# F1 — HTML report: top-X composite + DSR display + CI bars

Follows [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md). Three pre-written test fixtures from Sonnet — you fill implementations only.

## Self-check
- [ ] I am Gemini 3.1.
- [ ] Three pre-written test files exist:
  - `tests/eval/test_composite_ranking.py`
  - `tests/eval/test_dsr_display_payload.py`
  - `tests/eval/test_metric_ci_bars_payload.py`

## What you implement

Per [`../../../roadmap/session-specs/session-F1-html-report-enhancements.md`](../../../roadmap/session-specs/session-F1-html-report-enhancements.md):
- `_compose_top_x_section`, `_compose_dsr_section`, `_compose_metric_ci_bars` in `eval/report.py`.
- Mentor-voice DSR explanation template in `eval/dsr_explanation.py`.
- HTML template extensions for new sections.

## Validation contract
- Canonical reference: existing `eval/stats.py:deflated_sharpe_ratio`.
- Tolerance: rtol=1e-12 on payload values vs direct DSR call.

## Acceptance
- [ ] All three pre-written tests pass.
- [ ] Sprint 30's trial report renders new sections.
- [ ] No Trial schema or report public API change.
- [ ] Handoff: `docs/execution/handoffs/F1-handoff.md`.
- [ ] current-state.md: F1 → DONE.

## What you must NOT do
- Author your own validation tests.
- Modify Trial schema.
- Loosen tolerance.
