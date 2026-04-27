═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           F3-gemini
Required model:    Gemini 3.1 (Antigravity)
Effort:            M (~3 hr)
Entry blocked by:  F1 (helpful but not strict)
Parallel-OK with:  34b
Hand off to:       (none — independent)
Branch:            session-F3-comparison
═══════════════════════════════════════════════════════════════

# F3 — Trial comparison: compare-trials CLI + side-by-side HTML

Follows [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md). Three pre-written test fixtures.

## Self-check
- [ ] I am Gemini 3.1.
- [ ] Pre-written test files exist:
  - `tests/cli/test_compare_trials.py`
  - `tests/eval/test_compare_payload.py`
  - `tests/eval/test_compare_significance.py`

## What you implement

Per [`../../../roadmap/session-specs/session-F3-trial-comparison-report.md`](../../../roadmap/session-specs/session-F3-trial-comparison-report.md):
- `src/trading_research/eval/compare.py` — `build_comparison_payload`.
- `src/trading_research/eval/templates/compare.html.j2`.
- `src/trading_research/cli/compare.py` — `compare-trials` Typer command.

## Validation contract
- Canonical reference: existing `eval/bootstrap.py` (no parallel impl).
- Tolerance: rtol=1e-12.
- Cross-cohort warning banner required when `cohort_label` differs.

## Acceptance
- [ ] All three pre-written tests pass.
- [ ] Cross-cohort banner renders.
- [ ] Significance column uses strict criterion (right CI lower bound > left point).
- [ ] Equity-curve overlay chart with legend.
- [ ] Handoff: `docs/execution/handoffs/F3-handoff.md`.
- [ ] current-state.md: F3 → DONE.

## What you must NOT do
- Compare 3+ trials.
- Compare across instruments.
- Author your own validation tests.
