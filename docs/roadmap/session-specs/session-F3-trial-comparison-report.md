# Session F3 — Trial comparison HTML report (Gemini)

**Status:** Spec — slot before sprint 33 if possible
**Effort:** M (~2–3 hr)
**Agent fit:** Gemini 3.1 (Antigravity)
**Depends on:** F1 (HTML report enhancements) helpful but not strict
**Parallel-day candidate:** Day 7 alongside sprint 34

Follows the multi-model handoff protocol and Gemini validation playbook.

## Goal

A single CLI command that produces a side-by-side comparison report for two
trials: `compare-trials <trial-id-1> <trial-id-2>`. Sprint 33's gate review
relies on this for the v1 vs v2 comparison.

## In scope

### Pre-written test fixtures (Sonnet)

- `tests/cli/test_compare_trials.py`:
  - Creates two synthetic trials with known different metrics.
  - Runs the CLI; asserts the produced HTML has both trial IDs, both metric
    values, and a Δ column.
- `tests/eval/test_compare_payload.py`:
  - For two given trials, asserts the comparison payload dict structure:
    `{"left": {...}, "right": {...}, "delta": {...}, "verdict_per_metric": {...}}`.
- `tests/eval/test_compare_significance.py`:
  - Two trials with bootstrap CIs; asserts `verdict_per_metric` correctly
    flags "right strictly improved on left" when right's CI lower bound is
    above left's point estimate (mentor's strict criterion from sprint 33).

### Gemini implementation

- `src/trading_research/eval/compare.py` (new):
  - `build_comparison_payload(left: Trial, right: Trial) -> dict`.
  - Per-metric verdict: "improvement" / "no significant change" / "regression".
  - Uses the same bootstrap CI machinery (no re-implementation).
- `src/trading_research/eval/templates/compare.html.j2` (new) — side-by-side.
- `src/trading_research/cli/compare.py` — `compare-trials` Typer command.

### Layout of the comparison HTML

- Header: both trial IDs, dates, code_versions, cohort_label match check.
  If `cohort_label` differs, render a banner: "WARNING: trials are in
  different cohorts; cross-cohort comparison is informational only."
- Metrics table with columns: Metric / Left / Right / Δ / Significance.
- Equity curves overlaid in a single chart.
- Trade-distribution histograms side-by-side.
- Per-fold breakdown side-by-side (when both trials have walk-forward folds).

## Validation per playbook

- Canonical reference: bootstrap CI comparison logic is reused from
  `eval/bootstrap.py`; no parallel implementation.
- Parity test fixture: pre-written tests assert payload correctness.
- Tolerance: float comparisons rtol=1e-12.
- Escalation: if cross-cohort comparison logic ambiguous, escalate.

## Acceptance

- [ ] All three pre-written tests pass.
- [ ] Cross-cohort warning banner renders when `cohort_label` differs.
- [ ] Significance column is correctly populated by the strict criterion.
- [ ] Equity-curve chart includes both curves with legend.

## Out of scope

- Comparing 3+ trials (use sprint F1's top-X composite for that).
- Comparing trials across instruments (different P&L scales — defer).
- Editing trials.

## References

- `src/trading_research/eval/{trials,bootstrap,report,stats}.py`
- `outputs/planning/gemini-validation-playbook.md`
- `docs/roadmap/session-specs/session-33-track-c-gate.md`
