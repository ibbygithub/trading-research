# Risk Register v2 — Sprints 29–38
Last updated: 2026-04-26
Supersedes: `sprints-29-38-risks.md` v1

Reflects all three persona reviews. New rows below are tagged [DS], [A], [M] for
the persona who surfaced them.

## Architectural & technical

### [A] Walkforward bypasses TemplateRegistry — coupling drift
- Likelihood: HIGH (current state) | Impact: HIGH
- Mitigation: 29a commits to Option A staged; 29b retrofits walkforward; 30 confirms registry path holds.
- Status: Open (closes end of sprint 29)

### [A] `BacktestEngine` ignores `Strategy.size_position` — sizing is hardcoded
- Likelihood: HIGH (current state) | Impact: HIGH
- Mitigation: 29c wires sizing path; contract test guards the regression.
- Status: Open (closes end of sprint 29)

### [DS, A] OU bounds live in module constants, not instrument registry
- Likelihood: HIGH (current state) | Impact: MEDIUM
- Mitigation: 29d migrates to `configs/instruments.yaml`; ZN-classification-unchanged regression test.
- Status: Open (closes end of sprint 29)

### [A] Strategy template entrenches FX-specific assumptions
- Likelihood: MEDIUM | Impact: HIGH
- Mitigation: 29a architect review before 29b; instrument-specific values in instrument config, generic in template.
- Status: Open

### [A] Trial registry version-skew across the engine refactor in sprint 29
- Likelihood: HIGH (sprint 29 changes the engine) | Impact: HIGH
- Mitigation: 30a is the *first* trial in the new cohort; v1 trials from prior cohorts are explicitly excluded from cross-cohort comparison; cohort consistency check runs at 33b.
- Status: Open

### [A] gui/ and replay/ duplicated by sprint 38 if not audited first
- Likelihood: MEDIUM | Impact: MEDIUM
- Mitigation: 38a starts with audit; extend/reuse/replace decision before any new code.
- Status: Open

## Strategy & evidence

### [DS] "Walk-forward" is misnamed in v1 plan; sprint 30 is contiguous-test, not walk-forward
- Likelihood: HIGH (terminology drift in v1) | Impact: HIGH
- Mitigation: v2 fixes terminology; sprints 31 and 33 use rolling-fit walk-forward when any parameter is fitted.
- Status: Open (closes when v2 plan is approved)

### [DS] Regime filter threshold leakage into sprint 33 gate
- Likelihood: MEDIUM | Impact: HIGH
- Mitigation: 31a pre-commitment rule — threshold is justified by market structure OR selected on data the v2 evaluation does not touch. Spec captures path.
- Status: Open

### [DS] Cohort DSR ignores variants tested earlier in the sprint sequence
- Likelihood: MEDIUM (without procedural fix) | Impact: HIGH
- Mitigation: every variant (v1, v1+regime, v1+Mulligan, v2) calls `record_trial(...)` regardless of result; 33b loads cohort and reports `n_trials` next to DSR.
- Status: Open

### [DS] Per-fold stationarity not checked → strategy may be regime-fitting
- Likelihood: MEDIUM | Impact: HIGH
- Mitigation: 30a and 33a deliverables include per-fold ADF + OU half-life on vwap_spread; report-row visible; 33b gate fails if v2 wins only in stationarity-strong folds.
- Status: Open

### [DS] Point-estimate threshold gates (no CIs) hide statistical uncertainty
- Likelihood: HIGH | Impact: HIGH
- Mitigation: every numeric gate criterion in 33b uses bootstrap CI lower bound; existing `eval/bootstrap.py` is the reference.
- Status: Open

### [M] Cost-modelling optimism — backtest fills look better than real fills
- Likelihood: HIGH (without sensitivity sweep) | Impact: HIGH
- Mitigation: 30a runs slippage sweep {0.5, 1.0, 2.0, 3.0} ticks × {quiet, london_ny}; 33b gate requires PASS at 2-tick slippage.
- Status: Open

### [DS] Look-ahead bias in indicators (VWAP, ATR, regime gate)
- Likelihood: LOW (project discipline good) | Impact: HIGH
- Mitigation: per-indicator unit tests asserting computability with data through bar T-1; 29b adds the missing ones for VWAP-spread variants used by `vwap-reversion-v1`.
- Status: Open

### [M] Default knobs from session-28 doc are FX-naive (1.5σ entry, 21:00 UTC flatten)
- Likelihood: HIGH (without correction) | Impact: HIGH
- Mitigation: 29b uses mentor-corrected defaults: `entry_threshold_atr=2.2`, `entry_blackout=60min`, flatten time from instrument settlement.
- Status: Open

## Execution & integration

### [A] Featureset version drift on live data path
- Likelihood: MEDIUM | Impact: HIGH
- Mitigation: 35a hard-halts on `featureset_hash` mismatch at startup and on every parquet swap.
- Status: Open

### [DS] Live-vs-backtest divergence detection requires per-trade granularity
- Likelihood: MEDIUM | Impact: MEDIUM
- Mitigation: 35a writes trade-by-trade live + backtest log, not aggregate-only; 36b consumes the per-trade record.
- Status: Open

### TradeStation SIM API quirks delay E1 (sprint 34–35)
- Likelihood: MEDIUM | Impact: HIGH (June 30 deadline)
- Mitigation: Pre-committed escape — sprint 34a decision rule includes "TS SIM looks shaky → Pine port path"; no debate at gate time.
- Status: Open

### Circuit breakers don't fire when needed
- Likelihood: LOW | Impact: CRITICAL
- Mitigation: D1–D4 acceptance includes drill tests; 37 punch-list reviews every breaker against day-1 paper trading evidence.
- Status: Open

### [M] Sprint 36 advances to live too quickly
- Likelihood: MEDIUM (psychological pull is strong after first profitable trade) | Impact: HIGH
- Mitigation: sprint 36 reframed as "first paper trade + 30-day discipline window opens"; 38d does not advance to live; mentor signs off on this rule.
- Status: Open

## Strategy logic

### [DS, M] Mulligan freshness + directional gate not enforced
- Likelihood: MEDIUM | Impact: HIGH
- Mitigation: 32a spec enumerates freshness invariant (DS) AND directional-price gate (M); 32b tests cover positive case + both negative cases + directional gate; rule promoted to Strategy Protocol docstring.
- Status: Open

## Process & multi-model

### [DS, A] Gemini self-validates implementation against its own tests
- Likelihood: MEDIUM (without mitigation) | Impact: HIGH
- Mitigation: spec author writes parity tests; Gemini implements only; `gemini-validation-playbook.md` codifies the pattern.
- Status: Open

### Model-handoff context loss between sub-sprints
- Likelihood: MEDIUM | Impact: MEDIUM
- Mitigation: `multi-model-handoff-protocol.md` requires committed spec at every model boundary; implementer does not extrapolate; escalation path defined.
- Status: Open

### Parallel-day branch conflicts
- Likelihood: LOW | Impact: LOW
- Mitigation: daily pairing table built around non-overlapping module ownership; conflicts resolved end-of-day before next sprint.
- Status: Open

### June 30 paper-trade deadline slips
- Likelihood: MEDIUM | Impact: HIGH
- Mitigation: Pine port escape path pre-committed; sprint 34a decision rule allows pivot without debate.
- Status: Open

## Token & budget

### Opus burn higher than expected
- Likelihood: MEDIUM | Impact: LOW
- Mitigation: each Opus sub-sprint has goal cap; if conversation runs long, implementation half moves to next-day Sonnet.
- Status: Open

### Sonnet runs out of context on sprint 35
- Likelihood: MEDIUM | Impact: MEDIUM
- Mitigation: 35 split into a/b/c on purpose; Opus review in middle, not at end.
- Status: Open

### Sprint 29 expanded to two days reduces overall throughput
- Likelihood: HIGH (this is the actual plan) | Impact: LOW
- Mitigation: 11-day plan vs 10-day plan; June 30 deadline still has slack; first-day pairing absorbs D1 in parallel.
- Status: Accepted (architect's correction)
