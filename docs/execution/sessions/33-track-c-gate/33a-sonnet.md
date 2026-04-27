═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           33a-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  31b (DONE), 32b (DONE)
Parallel-OK with:  F1, B1
Hand off to:       33b-opus
Branch:            session-33-track-c-gate
═══════════════════════════════════════════════════════════════

# 33a — v2 walk-forward + side-by-side report

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 31b, 32b DONE.

## What you produce

### 1. v2 strategy combination
`vwap-reversion-v1` with:
- Regime filter from sprint 31 (threshold per 31a's pre-committed Path).
- Mulligan logic from sprint 32 (directional gate enabled).

### 2. True walk-forward
- 10 folds across 2018-01-01 to 2024-12-31.
- Each fold: fit window 18 months, test window 6 months, embargo 576 bars.
- Slide forward; refit at each fold (required because regime filter has a fitted threshold IF Path B).

### 3. Two cost configurations
- Realistic: 1.0-tick quiet / 2.0-tick overlap, $4.20/RT (sprint 30 run #4).
- Pessimistic: 2.0-tick quiet / 3.0-tick overlap, $4.20/RT (sprint 30 run #6).

### 4. Bootstrap CIs
2000 resamples, seed=20260427. All metrics get CIs.

### 5. Cohort DSR
DSR computed over ALL trials in current cohort (sprint 30 ×8 + sprint 31 ×2 + sprint 32 ×1 + this v2 ×2 = ~13 trials).

### 6. Per-fold stationarity (DS rule)
ADF + OU half-life on each fold's vwap_spread. Classification per fold.

### 7. Side-by-side report
v1 (sprint 30 run #4) vs v2 (this run, realistic config). Per metric:
- v1 value + CI
- v2 value + CI
- Δ (v2 − v1)
- "Did v2 improve significantly?" — yes only if v2 CI lower bound > v1 point estimate.

Use `compare-trials` from sprint F3 if delivered; else manual two-page diff.

### 8. Trial records
Two records (realistic, pessimistic) with full provenance.

## Acceptance
- [ ] Both v2 trials recorded.
- [ ] Walk-forward report (10 folds, rolling-fit).
- [ ] Side-by-side v1-vs-v2 report committed.
- [ ] Per-fold stationarity row.
- [ ] Cohort DSR with `n_trials >= 10` named.
- [ ] Handoff: `docs/execution/handoffs/33a-handoff.md`.
- [ ] current-state.md: 33a → DONE; 33b → READY.

## What you must NOT do
- Apply gate criteria yourself. 33b's job.
- Choose escape path. 33b's job per pre-committed rules.

## References
- Original spec: [`../../../roadmap/session-specs/session-33-track-c-gate.md`](../../../roadmap/session-specs/session-33-track-c-gate.md)
