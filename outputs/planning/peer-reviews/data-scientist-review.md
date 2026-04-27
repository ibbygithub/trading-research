# Peer Review — Sprints 29–38 Plan
## Reviewer: Data Scientist persona
Date: 2026-04-26
Reviewing: `outputs/planning/sprints-29-38-plan.md` v1, `sprints-29-38-risks.md` v1, `docs/analysis/6e-strategy-class-recommendation.md`, `docs/roadmap/sessions-23-50.md`, code under `src/trading_research/{stats,backtest,eval}/`

I read the plan and the supporting documents twice. There is good thinking here. There are also several places where the plan claims rigor it does not yet have, and a couple where it would let a less-capable agent ship code that I cannot defend statistically. This review names every one of those before they hit a sprint.

---

## 1. Walk-forward plumbing is not what the plan claims it is

The plan repeatedly says "4-fold walk-forward, purge=576 bars" and counts on this for the Track C gate. I read `src/trading_research/backtest/walkforward.py` — it does not implement walk-forward in the sense the plan needs.

What the code does today:
- It splits the **test** set into N contiguous folds with `gap_bars` and `embargo_bars` between adjacent folds.
- There is **no training window**. There is no fit/refit. The strategy is parameter-only — `signals_df = mod.generate_signals(bars, **signal_params)` runs **once across the entire dataset before splitting**.
- The "folds" are evaluation windows, not walk-forward windows.

For a parameter-fixed rule-based strategy where the parameters were not selected by looking at the test data, this is acceptable as evaluation segmentation — it gives you per-fold variance estimates. **It is not walk-forward validation.** Calling it walk-forward is the kind of language drift that, six months from now, makes me unable to tell whether a result was honest.

**Required corrections to the plan:**

1. **Sprint 30 deliverable language must change** from "4-fold walk-forward" to one of:
   - "4-fold contiguous-test segmentation with embargo, parameters frozen ex-ante" — for the v1 run, since we have no parameters being tuned.
   - True walk-forward (rolling fit-on-window, evaluate-on-next, slide forward) — needed when sprint 31 introduces a regime filter that has a fitted threshold.

2. **Sprint 31 has a leakage trap.** A regime filter selected by examining sprint 30 fold-by-fold breakdowns *is* parameter selection on the test set. If 31a picks "ADX > 25 because the failing folds were trending," that threshold is leakage. The fix:
   - Rotate the data: pick the regime threshold using only data **before 2018** OR using the first 2 of 4 folds and then evaluating on the remaining 2.
   - Or: declare the regime gate before looking at any fold-level results, justified by a market-structure argument (mentor) rather than a data-driven argument (me).
   - Whichever path, write the rule in 31a's spec and have me sign it before 31b implements.

3. **Sprint 33's "v2 walk-forward" must be true walk-forward** if either the regime filter or the Mulligan logic has a fitted parameter. The plan should add a gate: "if any parameter in v2 was selected by examining v1 results, the v2 evaluation must be on a rolling refit window, not on contiguous-test folds." Without this, the 33b PASS/FAIL decision is built on sand.

This is the single biggest correctness issue in the plan and it cannot be hand-waved.

---

## 2. The OU half-life recalibration is bigger than "29c, S effort"

The plan estimates 29c at S effort: "recalibrate stationarity-suite bounds." I read `src/trading_research/stats/stationarity.py:43-47`:

```python
_OU_TRADEABLE: dict[str, tuple[float, float]] = {
    "1m": (5.0, 60.0),
    "5m": (3.0, 24.0),
    "15m": (2.0, 8.0),
}
```

These are module-level constants. They are not parameterised by instrument. Recalibrating means:
- Changing the data structure to be `(instrument, timeframe) -> (lower, upper)` or moving the bounds into `configs/instruments.yaml`.
- Updating every call site that consumes them (need to confirm count — likely the suite's `compute_stationarity` and the report writer).
- Migrating any persisted reports that quoted the old bounds — every existing stationarity JSON in `outputs/` needs a flag noting it used pre-recalibration bounds, or it gets rerun.
- Adding a per-instrument default plus an override mechanism in instrument YAML.
- A regression test on the existing ZN report that the recalibration did not silently change ZN classifications.

That is M effort, not S, and it has migration semantics — the architect needs to weigh in on where bounds live before code is written. I would expect 29c to *follow* an architect ruling on bounds-location, not lead it.

**Required correction:**
- Promote 29c from S to M.
- Add architect persona to 29a's review for bounds-location decision.
- Add a backward-compatibility test: ZN's existing classifications must not change unless the change is explicitly justified.
- Add migration line item: existing 6E stationarity report from session 28 must be rerun under new bounds and the prior classification annotated as "computed under ZN-calibrated bounds."

---

## 3. Confidence intervals are missing from every numeric acceptance criterion

The plan says things like "max consecutive losses < 20" and "≥5/10 folds positive." Both are point estimates being compared to thresholds. I do not consume point estimates — I consume confidence intervals.

**Required additions to every acceptance criterion that names a numeric threshold:**
- `Calmar >= 2`: must be `Calmar's bootstrap 95% CI lower bound >= 1.5`. A point estimate of 2 with a CI of [0.3, 3.7] does not pass.
- `≥5/10 folds positive`: must be augmented with `binomial p-value vs. p=0.5 < 0.10` — five out of ten folds positive is exactly the null. To reject the null at any reasonable level we need at least 7/10 or 6/10 with strong individual fold evidence.
- `max consecutive losses < 20`: must be `5th percentile of bootstrapped max-consecutive-losses distribution < 20`, not the realised number from a single trade log. The realised number is one draw.
- `deflated Sharpe CI excluding zero`: this one I wrote. Keep it.

The bootstrap module already exists at `src/trading_research/eval/bootstrap.py`. Sprint 30a must use it. Sprint 33's gate review (33b) does not pass without bootstrap CIs reported on every metric in the gate.

---

## 4. Number of trials being tracked is hidden from the deflation calculation

`eval/trials.py` computes Deflated Sharpe within a cohort keyed on `code_version`. The plan adds new sprints (30, 31, 33) that all produce trials. Each variant Ibby tries — v1, v1+regime-A, v1+regime-B, v1+Mulligan, v2 — is a trial. By sprint 33 we will have 5–10 trials in the cohort, and the deflation will bite hard.

The plan does not surface this. The Track C gate in 33b says "deflated Sharpe CI excluding zero" but does not say how many trials the deflation accounts for. If 33b reports DSR computed against only the v2 trial in isolation, that is wrong — the cohort includes every variant we tested to get to v2.

**Required:**
- Sprint 33b must explicitly load the trial registry, count trials in the current cohort, report `n_trials = N` next to the DSR, and recompute if any prior trial in the cohort was excluded "for being a different strategy."
- Sprint 30a, 31b, 32b must each `record_trial()` regardless of result. Do not let an agent skip recording a failed variant — that is the silent multiple-testing bug.
- Add a check to the gate: if `n_trials < 3`, DSR is not yet meaningful and we lean harder on per-fold evidence; if `n_trials > 10`, pre-register the gate threshold *before* running the next variant.

---

## 5. Stationarity recheck is missing from the strategy iteration loop

Sprint 28 confirmed 6E vwap_spread is stationary on 2024 data. Sprint 30 backtests 2018–2024. The stationarity assumption could fail on the older data — the 2014–2016 negative-rate ECB regime, the 2020 COVID intervention, the 2022 ECB rate cycle pivot all could destroy stationarity within a sub-window.

The plan does not require a per-fold or rolling-window stationarity check. Without it, a "passing" sprint 33 could be passing because half the data window is stationary and the other half is mean-reverting at a totally different speed, with the average looking fine.

**Required:**
- Sprint 30a deliverable: per-fold ADF and OU half-life on the test fold's vwap_spread, plotted alongside the equity curve. If stationarity classification flips between folds, that is a finding 30b must flag.
- Sprint 33a side-by-side report: stationarity row per fold per variant. If v2 looks better than v1 only in folds where stationarity is strong, the gate is FAIL — the strategy is fitting to a regime, not the spread.

---

## 6. Gemini validation rules in the roadmap are not load-bearing enough

The roadmap says:

> Statistical code that claims to implement a published method must be validated against a canonical reference (statsmodels for ADF, scipy for BH, etc.) as part of the acceptance test.

This is correct in spirit but underspecified for someone who is going to ship the code. "Validated against" means what, exactly? Same answer? Same answer to within tolerance? Same answer on what input distribution? The BH implementation in `stats/multiple_testing.py` does claim validation against `scipy.stats.false_discovery_control` in its docstring — but I do not see a test file that runs both and compares. (Test file is `tests/stats/`, I would need to confirm.)

For sprint B1 (timeframe catalog, Gemini), F1/F2/F3 (UX, Gemini), and 29c (suite recalibration, Gemini), I want the validation rules tightened. Specifically:

**Canonical-method parity test pattern (must be a fixture pattern, not prose):**
```python
def test_method_matches_canonical():
    rng = np.random.default_rng(SEED)
    inputs = rng.<distribution>(size=N)
    ours = our_method(inputs)
    canonical = canonical_library.method(inputs)
    np.testing.assert_allclose(ours, canonical, rtol=1e-9, atol=1e-12)
```

**The plan must require this fixture form for every Gemini-shipped statistical computation.** Spec writers, not Gemini, write the fixture; Gemini fills in `our_method`. That way a wrong implementation produces a failing test, not a passing test against itself.

I want a `gemini-validation-playbook.md` document accompanying the plan that codifies this with worked examples (BH, ADF, OU half-life, OHLCV resampling). Without it, the roadmap rule is aspirational.

---

## 7. The Mulligan logic spec has a hidden risk

CLAUDE.md is clear that scale-in on a fresh signal is permitted, scale-in on adverse P&L is averaging-down. The plan correctly distinguishes these in 32a.

What the plan does not say: how do we *test* that the Mulligan code is enforcing the distinction, given that the trigger is semantic ("fresh signal") rather than mechanical?

If a less-capable agent implements `if signal_strength_now > original_signal_strength: scale_in()`, that is *not* a fresh signal — it is the same signal viewed through a fresh threshold, which is exactly the rationalization CLAUDE.md forbids.

**Required:**
- 32a's spec must enumerate what counts as a fresh signal. My recommendation: a fresh signal is a new `Signal` object emitted by `generate_signals()` for the same direction at a later timestamp where the prior signal at the previous emission has already been *consumed* (entered or rejected by sizing). Anything that re-evaluates the same emitted signal is not fresh.
- 32b's tests must include both negative cases:
  - Test that an adverse-P&L re-trigger without a fresh `Signal` emission is rejected.
  - Test that a "stronger version of the same signal" without a new emission is rejected.
  - Test that a fresh emission for the same direction with a defined combined target/stop is accepted.

This is not a sprint-32 concern only — it is a regression risk for every future strategy. Add it as a Strategy Protocol invariant in `core/strategies.py` docstring, not just in the template.

---

## 8. The Track C gate threshold for "max consecutive losses < 20" is wrong for 6E

Twenty consecutive losers on a 165-minute-half-life mean reversion strategy with a 5-hour hold cap and London/NY-only entries means roughly 10 trading days of pure losers. That is a brutal psychological window for someone trading their own retirement money.

I would set this tighter, justified by what is actually runnable rather than what is statistically tolerable:
- `max consecutive losses <= 8` for any strategy that goes to paper (not 20).
- Track this as a *behavioural* metric, not a P&L one. Mentor will agree — he says behavioural metrics matter as much as Sharpe.

The current threshold of 20 was a default. The plan should set it to 8 explicitly with the justification.

---

## 9. Things the plan got right that I want kept

- DSR + n_trials reporting baseline.
- Stationarity-passing core feature as part of the gate. Keep this. It is the difference between fitting to a real spread and fitting to noise.
- Per-fold breakdown in reports. Single aggregated metrics hide the heterogeneity that matters.
- The escape valves at sprint 33 — pivot to 6A/6C or to TradingView is the right structural mitigation.
- Honest split between Opus design and Sonnet implementation. The handoff protocol is correct.

---

## 10. Required updates I want to see in v2 of the plan

1. Walk-forward terminology fixed; sprint 31/33 require true walk-forward if any parameter is fitted on previous fold results.
2. 29c promoted to M; OU bounds migration noted; architect signoff on bounds location.
3. Every acceptance threshold gets a CI requirement, computed via the existing bootstrap module.
4. Sprint 33b gate explicitly counts cohort trials and recomputes DSR over the full cohort.
5. Sprint 30a, 31b, 32b all `record_trial()` regardless of result.
6. Per-fold and per-variant stationarity check baked into 30 and 33.
7. Canonical-method parity test pattern codified into a separate playbook document; sprint specs reference the pattern.
8. Mulligan freshness invariant documented as a Protocol-level rule and tested with both positive and negative cases.
9. Max-consecutive-losses gate tightened to 8, justified behaviourally.
10. Sprint 35 paper-trading loop must record live-vs-backtest trade-by-trade, not aggregate-only — the divergence detection in 36b depends on per-trade granularity.

---

## What I will not sign off on

I will not sign off the Track C gate at sprint 33b unless:
- Walk-forward terminology is honest.
- DSR is computed over the full cohort with `n_trials` named.
- Bootstrap CIs are reported on Calmar, Sharpe, and max consecutive losses.
- Per-fold stationarity is in the report.
- Either the regime filter has a market-structure justification or its threshold was selected on data the v2 evaluation does not touch.

If these conditions are met, I will defend the result publicly. If they are not, I will not, and the gate fails by my vote.

The plan is good. With these changes it becomes defensible.
