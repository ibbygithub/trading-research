# Session F1 — HTML report enhancements (Gemini)

**Status:** Spec — slot anytime after sprint 27 (already past)
**Effort:** M (~2–3 hr)
**Agent fit:** Gemini 3.1 (Antigravity)
**Depends on:** sprint 27 (BH + composite ranking) — DONE
**Unblocks:** sprint 33's side-by-side report uses these components
**Parallel-day candidate:** Day 6 alongside sprint 33

This sub-sprint follows `outputs/planning/multi-model-handoff-protocol.md` and
`outputs/planning/gemini-validation-playbook.md`. Spec author (Sonnet)
pre-writes the parity tests; Gemini implements only.

## Goal

Three additions to the existing HTML report module:

1. Top-X composite ranking section that surfaces the best trades from a
   trial's trade log by a composite score (R-multiple × hold-quality).
2. Deflated-Sharpe display alongside raw Sharpe with a one-paragraph
   trader-language explanation.
3. Confidence-interval bars on Calmar and Sharpe (visual error bars in the
   metrics summary).

## In scope

### Pre-written test fixtures (Sonnet writes these in spec hand-off)

- `tests/eval/test_composite_ranking.py`:
  - Fixture: synthetic trade log with known R-multiples and hold qualities.
  - Asserts top-X ranking matches expected ordering.
- `tests/eval/test_dsr_display_payload.py`:
  - Fixture: trial with raw Sharpe=1.8, n_trials=8, returns moments specified.
  - Asserts the report context dict contains `dsr_value`, `dsr_ci_lower`,
    `dsr_ci_upper`, `n_trials_in_cohort`, and a non-empty
    `trader_language_explanation` string.
- `tests/eval/test_metric_ci_bars_payload.py`:
  - Fixture: trial with bootstrap CI computed.
  - Asserts the report context provides `calmar_ci_lower`, `calmar_ci_upper`,
    `sharpe_ci_lower`, `sharpe_ci_upper` floats.

### Gemini implementation

- `src/trading_research/eval/report.py` (extend):
  - `_compose_top_x_section(trade_log: pd.DataFrame, x: int) -> dict`
  - `_compose_dsr_section(trial: Trial, cohort: list[Trial]) -> dict`
  - `_compose_metric_ci_bars(metrics: dict, ci: dict) -> dict`
- `src/trading_research/eval/templates/<existing>.html.j2` (extend):
  - New section: top-X composite ranking table.
  - DSR row with side-by-side raw + deflated and the explanation text.
  - SVG/CSS error bars on Calmar and Sharpe rows.

### Trader-language explanation template (mentor's voice)

The DSR explanation lives in `src/trading_research/eval/dsr_explanation.py`
as a function that takes the values and returns a string. Template (literal):

```
Your raw Sharpe is {raw:.2f}. The cohort tested {n_trials} variants. The
deflated Sharpe — what the result would have been if only one variant had
been tested — is {dsr:.2f} (95% CI [{dsr_lo:.2f}, {dsr_hi:.2f}]).

When the deflated Sharpe drops a lot below the raw, much of the apparent edge
came from the noise of testing many variants. {verdict}.
```

Where `{verdict}` is selected by rule:
- DSR CI excludes zero AND DSR > 0.5 → "This still looks like a real edge."
- DSR CI includes zero → "This is statistically indistinguishable from luck
  given how many variants were tried."
- DSR CI excludes zero but DSR < 0.5 → "There's evidence of an edge but it's
  small. Costs and execution quality matter a lot at this scale."

## Validation per playbook

- Canonical reference: `eval/stats.py:deflated_sharpe_ratio` (existing,
  validated against Lopez de Prado 2014 in its own tests).
- Parity test fixture: `tests/eval/test_dsr_display_payload.py`.
- Tolerance: payload dict values are floats; assert with rtol=1e-12 against
  `deflated_sharpe_ratio` direct call.

## Acceptance

- [ ] All three pre-written test files pass.
- [ ] Generated report HTML for sprint 30's trial has the three new sections
      visually rendered (Sonnet visual-checks before merge).
- [ ] No change to the Trial schema or to existing report public API.
- [ ] Existing report tests still pass.

## Out of scope

- New metrics beyond what's already computed.
- Backend changes to bootstrap CI computation (existing module is canonical).
- Changes to Trial dataclass.

## References

- `src/trading_research/eval/{report,stats,bootstrap,trials}.py`
- `outputs/planning/gemini-validation-playbook.md`
