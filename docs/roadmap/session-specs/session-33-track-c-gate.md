# Session 33 — 6E backtest v2 + Track C gate

**Status:** Spec — gate procedure pre-committed
**Effort:** 1 day, two sub-sprints (M+M)
**Depends on:** Sprints 30, 31, 32 complete
**Unblocks:** sprint 34 (paper-trading bridge OR escape path)
**Personas required (33b):** Mentor, Data Scientist, Architect — all three sign off in writing

This is the gate. The procedure is pre-committed so the gate cannot be argued
into a PASS at the moment of decision. If v2 does not clear the gate by the
criteria below, the escape paths fire automatically.

## Goal

Run `vwap-reversion-v1` + regime filter + Mulligan combined as v2; evaluate
under rolling-fit walk-forward; produce a side-by-side v1-vs-v2 report; then
apply the seven gate criteria and route to either Track E or to a pre-committed
escape path.

## In scope

### 33a — v2 walk-forward + side-by-side report

**Model:** Sonnet 4.6 | **Effort:** M (~3 hr)

**Strategy under test:** `vwap-reversion-v1` with:
- Regime filter from sprint 31 (its threshold pre-committed per 31a's rule).
- Mulligan logic from sprint 32 (with mentor's directional gate).

**Evaluation:** rolling-fit walk-forward.
- 10 folds across 2018-01-01 to 2024-12-31.
- Each fold: fit window of 18 months, test window of 6 months, embargo 576 bars.
- Slide forward; refit at each fold.
- This is **true walk-forward**, not contiguous-test segmentation. Required
  because the regime filter has a fitted threshold (per 31a path).

**Cost configuration:**
Run two cost variants (not the full 8-variant sweep — that was sprint 30):
- Realistic: 1.0-tick quiet / 2.0-tick overlap, $4.20/RT (sprint 30 run #4).
- Pessimistic: 2.0-tick quiet / 3.0-tick overlap, $4.20/RT (sprint 30 run #6).

**Metrics + CIs (bootstrap, 2000 resamples, seed=20260427):**
Same metrics as sprint 30. In addition:
- Per-fold stationarity classification (must NOT flip — see gate criterion 5).
- Cohort DSR computed over **all** trials in current cohort (sprint 30 ×8 +
  sprint 31 variants + sprint 32 variants + this v2 trial).

**Side-by-side report:**
v1 (sprint 30 run #4 realistic config) vs v2 (this run, realistic config).
For each metric:
- v1 value + CI
- v2 value + CI
- Δ (v2 − v1)
- "Did v2 improve significantly?" — yes only if v2's CI lower bound > v1's
  point estimate (a strict criterion).

Use sprint F3's `compare-trials` command if delivered; fall back to a manual
two-page diff if F3 is not yet available.

**Provenance:** `record_trial(...)` for both v2 cost variants.

### 33b — Pre-committed gate evaluation

**Model:** Opus 4.7 | **Effort:** M (~2 hr)

Apply the seven gate criteria. **All seven must pass for a PASS verdict.**

#### Gate criteria

**G1 — Fold count.** ≥6 of 10 folds positive AND binomial p-value vs.
p=0.5 < 0.10. (5/10 is exactly the null and does not reject.)

**G2 — Calmar CI.** Bootstrap 95% CI lower bound on aggregated Calmar ≥ 1.5.
A point estimate of 2 with a CI of [0.4, 3.0] does not pass.

**G3 — Deflated Sharpe.** DSR computed over the full cohort (`n_trials = N`,
where N includes every variant tested in sprints 30–32). DSR 95% CI must
exclude zero.

**G4 — Max consecutive losses.** 95th percentile of bootstrapped max-consecutive-
losses distribution ≤ 8. (Realised number alone is one draw; we need the
distribution.) Mentor's tighter behavioural bound — 20 was too loose for a
solo retail trader's psychology.

**G5 — Per-fold stationarity preserved.** vwap_spread classification does not
flip across folds. Mixed classification means the strategy is regime-fitting,
not exploiting a stable spread structure.

**G6 — Cost robustness.** Strategy passes G1–G5 under the **realistic** cost
configuration. Pessimistic cost configuration is reported but does not gate.
However, if pessimistic Calmar CI lower bound < 0.5, that is surfaced as a
mentor concern even if realistic passes.

**G7 — Cohort consistency.** All trials in the current cohort share
`engine_fingerprint`. If the engine changed mid-sprint sequence, the affected
trials are rerun or the cohort is split with explicit justification in the
work log.

#### Verdict procedure

After applying G1–G7, the gate verdict is:

- **All seven pass:** PASS → sprint 34a picks Track E option (E1 vs E1').
- **Any fail:** FAIL → apply escape rule below.

**The personas vote independently and in writing.** Each persona produces a
verdict block:

```
## <Persona> verdict — <PASS / FAIL / FAIL with caveat>
G1: <PASS / FAIL — explanation>
G2: ...
...
Recommendation: <go to Track E / escape via X>
Signed: <persona name>
Date: 2026-...
```

If the three personas disagree, Ibby is the synthesizer — but the procedure is
that the **most conservative** verdict drives the outcome unless Ibby explicitly
overrides in writing. Disagreement is logged, not papered over.

#### Pre-committed escape rules (mentor's procedure)

The escape path is determined by the *shape* of the failure, not by
discussion:

| Failure shape | Escape path | Sprint 34 action |
|---|---|---|
| Positive aggregate equity but failing fold dispersion (e.g., G1 fail with high CI variance) | Pivot to 6A/6C single-instrument; same template, different FX cross | 34a redirects to "build 6A/6C pipeline next sprint cycle" |
| Negative aggregate equity, most folds losing (G2/G3 hard fail) | Switch strategy class | 34a picks momentum or breakout from session 28 stationarity follow-up |
| Marginal margins after costs, June 30 pressure (G6 caveat) | TradingView Pine port path | 34a picks E1' (Pine port + TV reconciliation) |
| Stationarity flipping (G5 fail) | Pivot to 6A/6C OR switch class — mentor + data scientist must agree which | 34a holds a focused decision conversation, then proceeds |
| Cohort consistency fail (G7) | Rerun affected trials in a unified engine version, then re-evaluate | Sprint 33 redo |

These rules are pre-committed *now* (sprint 26 plan v2). Sprint 33b applies
them; it does not invent new rules.

## Out of scope

- Sprint 34 work itself.
- New strategy class design (that is sprint 34a's job after escape, if needed).
- Live trading decisions.

## Acceptance tests

- [ ] v2 trial recorded for both cost configurations.
- [ ] Walk-forward report (10 folds, rolling-fit) committed.
- [ ] Side-by-side v1-vs-v2 report committed.
- [ ] Per-fold stationarity row in report.
- [ ] Cohort DSR computed with `n_trials >= 4` named.
- [ ] All three persona verdict blocks committed in `33b-gate-review.md`.
- [ ] Final verdict (PASS or named escape path) committed and dated.
- [ ] Sprint 34 entry condition unambiguously set.

## Definition of done

- [ ] Gate procedure applied to each criterion.
- [ ] Verdict logged per persona.
- [ ] Escape path (if any) named explicitly.
- [ ] Branch `session-33-track-c-gate`.
- [ ] Work log per CLAUDE.md convention.

## References

- `outputs/planning/sprints-29-38-plan-v2.md`
- `outputs/planning/peer-reviews/`
- `runs/.trials.json` (loaded for cohort DSR)
- `src/trading_research/eval/{trials,bootstrap,stats}.py`
- `docs/roadmap/sessions-23-50.md` Track C section
