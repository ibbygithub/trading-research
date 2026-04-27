# Session 31 — Regime filter (TRUE walk-forward begins)

**Status:** Spec — ready to execute after sprint 30
**Effort:** 1 day, two sub-sprints (M+M)
**Depends on:** Sprint 30 (v1 backtest + persona review)
**Unblocks:** Sprint 32 (Mulligan), sprint 33 (gate)
**Personas required:** Mentor (31a market-structure path), Data Scientist (31a leakage rule), Architect (composability)

## Goal

Add a regime filter to `vwap-reversion-v1` that gates entries when the spread
is unlikely to revert. Two non-negotiables, both surfaced by the data scientist:

1. **Filter threshold cannot be selected from sprint 30 fold-by-fold results
   then re-tested on those same folds.** That is leakage.
2. **Evaluation uses TRUE walk-forward** (rolling fit + slide forward), not
   contiguous-test segmentation, because the filter has a fitted threshold.

## In scope

### 31a — Filter design (Opus 4.7, ~2 hr)

**Inputs:** sprint 30 outputs (read but do NOT data-mine), 6E recommendation doc.

**Pre-commitment rule (data scientist's):** the filter threshold must come
from one of two paths. 31a picks one and writes it down before any code:

- **Path A — Market-structure justification (mentor's path).** Examples:
  - Time-of-day gate: no entries during 12:00–13:00 UTC (ECB fixing window).
    Justification: real-desk knowledge that fixing flows distort VWAP.
  - Calendar gate: no entries within ±30 min of US CPI / NFP / ECB rate
    decision. Justification: event-driven moves dominate reversion.
  - Volatility-regime gate: no entries when realised σ over last N bars
    exceeds a percentile of the trailing 90-day distribution. Justification:
    high-vol periods break OU dynamics.
- **Path B — Hold-out calibration.** Threshold selected on data the v2
  evaluation does not touch:
  - Use 2014–2017 (pre-2018 backtest start) to fit the threshold.
  - OR use folds 1–2 of sprint 30 to fit, evaluate on folds 3–10 in sprint 33.

**31a deliverable:** a written `regime-filter-spec.md` covering:
- Filter type (time-gate / calendar-gate / vol-regime / composite).
- Path A justification OR Path B calibration data window.
- Filter API: `def is_tradeable_regime(bars, features, instrument, ts) -> bool`.
- Knob ranges (for walk-forward sensitivity, not for fitting).
- Stub test files under `tests/strategies/test_regime_filter.py`.

### 31b — Implementation + walk-forward (Sonnet 4.6, ~3 hr)

**Outputs:**
- `src/trading_research/strategies/regime/__init__.py` — composable filter
  layer; multiple filters can be chained (AND-of-filters).
- One concrete filter implementation per 31a's chosen filter type.
- `vwap-reversion-v1` template gains a `regime_filters: list[str]` knob;
  `generate_signals` short-circuits when any filter rejects.
- Walk-forward harness updated: rolling-fit window of 18 months, test window
  of 6 months, slide forward, embargo 576 bars. Total: ~10 folds across
  2018–2024.
- Two trial records: with-filter and without-filter (sprint 30's run #4 baseline).

## Acceptance

- [ ] `tests/strategies/test_regime_filter.py` covers filter unit cases.
- [ ] Walk-forward report shows rolling-fit folds, with vs without filter.
- [ ] ≥6/10 folds positive AND binomial p-value < 0.10 against null p=0.5.
- [ ] Bootstrap CI lower bound on aggregated Calmar > 1.0 (strictly above break-even).
- [ ] Filter is reusable (no 6E-specific code in the regime module).
- [ ] Both trials recorded with cohort fingerprint.

## Out of scope

- Mulligan logic (sprint 32).
- Final gate decision (sprint 33).
- Strategy-class change (escape territory).

## Pre-committed escape (if 31b fails the acceptance)

If the filter does not improve folds-positive count, do not iterate filters in
this sprint. Surface the failure in the work log; sprint 32 still runs (Mulligan
is independent); sprint 33 evaluates whatever combination v2 ends up being.
The plan does not allow burning sprints chasing filter variants.

## References

- `outputs/planning/sprints-29-38-plan-v2.md`
- `outputs/planning/peer-reviews/data-scientist-review.md` §1, §3
- `runs/<sprint-30-trial-id>/30b-review.md`
