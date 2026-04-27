═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           33b-opus
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  33a (DONE)
Parallel-OK with:  none — gate decision owns the focus
Hand off to:       34a-opus
Branch:            session-33-track-c-gate
═══════════════════════════════════════════════════════════════

# 33b — Track C gate (PRE-COMMITTED procedure)

This sub-sprint applies a procedure that was pre-committed at plan v2.
You DO NOT invent new gate criteria. You DO NOT argue with the criteria.
You apply them and route per the failure-shape table.

## Self-check
- [ ] I am Opus 4.7.
- [ ] 33a DONE; v2 trials and side-by-side report exist.
- [ ] I have read the seven criteria below and the pre-committed escape paths.

## The seven gate criteria (ALL must pass for PASS)

**G1 — Fold count.** ≥6 of 10 folds positive AND binomial p-value vs.
p=0.5 < 0.10.

**G2 — Calmar CI.** Bootstrap 95% CI lower bound on aggregated Calmar ≥ 1.5.

**G3 — Deflated Sharpe.** DSR over full cohort with `n_trials = N`. DSR
95% CI must exclude zero.

**G4 — Max consecutive losses.** 95th percentile of bootstrapped distribution ≤ 8.

**G5 — Per-fold stationarity preserved.** vwap_spread classification does
NOT flip across folds.

**G6 — Cost robustness.** Strategy passes G1–G5 under REALISTIC cost config.
Pessimistic reported but does not gate. If pessimistic Calmar CI lower
bound < 0.5: surface as mentor concern even if realistic passes.

**G7 — Cohort consistency.** All trials in current cohort share
`engine_fingerprint`. If engine changed mid-cohort: rerun affected trials
or split cohort with explicit justification.

## Verdict procedure

You produce three independent verdict blocks and a synthesis.

### Verdict block format (one per persona)

```
## <Persona> verdict — <PASS / FAIL: <reason> / FAIL with caveat>
G1: <PASS / FAIL — explanation with numbers>
G2: <PASS / FAIL — CI bounds>
G3: <PASS / FAIL — DSR + n_trials>
G4: <PASS / FAIL — 95th percentile>
G5: <PASS / FAIL — fold classification list>
G6: <PASS / FAIL — pessimistic vs realistic>
G7: <PASS / FAIL — cohort consistency>
Recommendation: <go to Track E / escape via X>
Signed: <persona>
Date: <today>
```

Mentor: lens is market behaviour and trader survivability.
Data Scientist: lens is evidence honesty and statistical interpretability.
Architect: lens is coupling integrity and system maturity.

### Pre-committed escape rules — apply exactly

| Failure shape | Escape path |
|---|---|
| Positive aggregate equity, failing fold dispersion (G1 fail with high CI variance) | Pivot to 6A/6C single-instrument |
| Negative aggregate equity, most folds losing (G2/G3 hard fail) | Switch strategy class |
| Marginal margins after costs, June 30 pressure (G6 caveat) | TradingView Pine port (E1') |
| Stationarity flipping (G5 fail) | Pivot to 6A/6C OR class change — focused decision |
| Cohort consistency fail (G7) | Sprint 33 redo |

### Synthesis

If three personas all sign PASS: verdict is PASS → 34a routes to E1.
If any FAIL: most-conservative verdict drives outcome unless Ibby
explicitly overrides. Apply escape table per failure shape.

## Acceptance

- [ ] All three persona verdict blocks committed in `runs/.../33b-gate-review.md`.
- [ ] Final verdict (PASS or named escape path) committed.
- [ ] Sprint 34 entry condition unambiguously set.
- [ ] Handoff: `docs/execution/handoffs/33b-handoff.md` with verdict.
- [ ] current-state.md: 33b → DONE; 34a → READY (verdict drives 34a's branch).

## What you must NOT do
- Soften criteria. They are pre-committed.
- Pick an escape path not in the table.
- Skip a persona's verdict.

## References
- Plan v2 commitments: [`../../plan/master-execution-plan.md`](../../plan/master-execution-plan.md)
- Original spec: [`../../../roadmap/session-specs/session-33-track-c-gate.md`](../../../roadmap/session-specs/session-33-track-c-gate.md)
