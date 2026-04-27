# Plan v2 — Sprints 29–38: From hardened pipeline to working trader's desk
Date: 2026-04-26
Status: Draft (incorporates persona reviews; awaiting Ibby red-line)
Supersedes: `sprints-29-38-plan.md` v1 (kept on disk as historical record)

This is v2 of the 10-sprint plan. It incorporates every required change from
the data scientist, architect, and quant mentor peer reviews
(`outputs/planning/peer-reviews/`). Substantive differences from v1:

- Sprint 29 spans two days (29a–d), not one. Reasons: registry-engine
  coupling, `Strategy.size_position` wiring, and OU-bounds migration are all
  in scope.
- Walk-forward terminology is now honest. Sprint 30 evaluates with contiguous
  test segmentation; sprints 31 and 33 use rolling-fit walk-forward when any
  parameter is fitted on prior fold results.
- Bootstrap CI is required on every numeric acceptance threshold.
- Cost-sensitivity analysis is in-scope for sprint 30.
- Sprint 36 is the start of a 30-day paper discipline window, not a one-off
  event. Sprint 38 readiness review does not advance to live capital.
- Multi-model handoff and Gemini validation rules are now load-bearing
  documents (`multi-model-handoff-protocol.md`, `gemini-validation-playbook.md`)
  referenced from every cross-model sub-sprint.

## Objective

Land Ibby on a working trader's desk by sprint ~40: a validated 6E rule-based
strategy in paper trading (on-platform or via TradingView), full circuit-breaker
safety envelope in place, polished CLI + HTML reports, and the platform set up
so adding the next strategy or instrument is a config edit, not a rewrite.

Live capital is **not** an objective of this plan. The forcing function is the
June 30, 2026 first-paper-trade deadline.

## Scope

**In:** sessions 29–38 covering Tracks C (strategy on 6E), D (execution
plumbing), B (timeframe catalog side-quest), F (UX polish), and the start of
E (paper bridge). Multi-model assignment per sub-sprint with the spec→test→impl
ordering enforced at every model boundary.

**Out:** ML capability (Track G — sessions 38–42 in roadmap, deferred), pairs
and second instrument (Track H), live execution (Track I).

## Current state (entering sprint 29)

- **Track A: DONE.** Pipeline runs for any instrument by config. 6E
  CLEAN+FEATURES built. ADF/Hurst/OU computed; vwap_spread strongly stationary.
- **6E recommendation:** intraday VWAP mean reversion, London/NY-overlap
  entries, hold cap derived from OU half-life. Doc: `docs/analysis/6e-strategy-class-recommendation.md`.
- **Code state requiring attention in sprint 29 (architect's catch):**
  - `walkforward.py` uses dynamic-import signal-module strings; does NOT
    consume `TemplateRegistry`.
  - `BacktestConfig.quantity` is hardcoded position size; `Strategy.size_position`
    is not on the call path.
  - `stats/stationarity.py:43-47` carries module-level OU bounds (ZN-tuned);
    bounds are not per-instrument.
  - Two free-standing ZN strategy modules predate the Strategy Protocol.
- **Outstanding from session 28:** OU bounds for 6E classify as TOO_SLOW
  under ZN-calibrated thresholds.

## Model strategy

Three rules from `multi-model-handoff-protocol.md`:
1. The spec is the contract.
2. The implementer does not author its own validation.
3. Cohort fingerprinting on every shipped trial.

Model-fit cheatsheet (unchanged from v1):

| Workload | Best fit |
|---|---|
| Design / regime / persona synthesis | **Opus 4.7** |
| Implementation against a written spec | **Sonnet 4.6** |
| Mechanical spec-shape ports + canonical-method parity work | **Gemini 3.1** |
| Cross-persona debugging | **Opus 4.7** |
| Walk-forward runs and trade-log analysis | **Sonnet 4.6** |

---

## Sprint plan v2 (29–38)

### Sprint 29 — Strategy foundation & coupling fixes (TWO DAYS)
Detailed spec: `docs/roadmap/session-specs/session-29-strategy-foundation.md`

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 29a | **Opus 4.7** | Architectural decisions: (1) walkforward↔registry coupling option (recommend Option A staged — see spec), (2) OU bounds → instrument registry, (3) template/instance naming convention, (4) Mulligan freshness invariant promoted to Protocol-level. Output: 29-strategy-foundation.md spec + stub test files for 29b–d. | M |
| 29b | **Sonnet 4.6** | Walkforward retrofit to consume TemplateRegistry; implement `vwap-reversion-v1` template with mentor-approved knob defaults (`entry_threshold_atr=2.2`, `entry_blackout_minutes_after_session_open=60`, flatten time from instrument settlement). | M |
| 29c | **Sonnet 4.6** | Wire `Strategy.size_position` into `BacktestEngine`; `BacktestConfig.quantity` becomes fallback only. Contract test `tests/contracts/test_sizing_path.py`. | M |
| 29d | **Gemini 3.1** | Migrate OU bounds from `stats/stationarity.py` constants to `configs/instruments.yaml` per-instrument. Parity test: existing ZN classifications unchanged under new bounds-from-instrument loader. Per-instrument bounds for 6E (5m: 10–80 bars; 15m: 4–30 bars). Follow `gemini-validation-playbook.md`. | M |

- **Day 1:** 29a (morning Opus) → 29b (afternoon Sonnet).
- **Day 2:** 29c (Sonnet) and 29d (Gemini) in parallel.
- **Parallel slot (Day 1 afternoon):** D1 (Sonnet) on a separate branch.
- **Acceptance:**
  - `uv run trading-research describe-template vwap-reversion-v1` prints knob defaults + ranges.
  - 6E classifies as TRADEABLE under new instrument-level OU bounds.
  - Walkforward runs with `vwap-reversion-v1` registered in TemplateRegistry — no `signal_module` path string in 6E config.
  - `BacktestEngine` calls `strategy.size_position(...)` — verified by contract test.
  - All 4 stub tests from 29a now pass with real implementations.
- **Spend:** Opus M, Sonnet M+M, Gemini M.

### Sprint D1 — Daily/weekly loss limits (parallel-eligible)
Spec: `docs/roadmap/session-specs/track-D-circuit-breakers.md` §D1.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D1 | **Sonnet 4.6** | Implement `LossLimitMonitor`, `LimitBreach`, default YAML, unit tests. Now uses sized P&L from sprint 29c sizing path. | M |

- **Parallel slot:** Day 1 of sprint 29.
- **Acceptance:** synthetic trade log breaching the daily limit produces a `LimitBreach` event and halts further entries.
- **Spend:** Sonnet M.

### Sprint 30 — 6E backtest v1 (contiguous-test, full provenance, cost sensitivity)
Detailed spec: `docs/roadmap/session-specs/session-30-6e-backtest-v1.md`

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 30a | **Sonnet 4.6** | Run `vwap-reversion-v1` on 6E 2018-01-01 to 2024-12-31, 4-fold contiguous-test segmentation with embargo=576 bars (NOT walk-forward — parameters are frozen ex-ante). Cost-sensitivity sweep: slippage ∈ {0.5, 1.0, 2.0, 3.0} ticks × overlap_window∈{quiet, london_ny}. Bootstrap 95% CIs on Calmar, Sharpe, max-consecutive-losses. Per-fold ADF and OU half-life on vwap_spread. `record_trial(...)` with engine_fingerprint, featureset_hash, code_version. | L |
| 30b | **Opus 4.7** | Three-persona review: mentor on market behaviour and cost sensitivity, data scientist on per-fold dispersion + stationarity stability + bootstrap CI interpretation, architect on whether sprint 29's coupling held under load. | S |

- **Parallel slot:** D2 (Sonnet) on inactivity heartbeat.
- **Acceptance:**
  - Trial registry entry has all five hashes + `n_trials` count in current cohort.
  - HTML report includes per-fold stationarity row + cost-sensitivity table.
  - Persona review committed in work log with explicit pass/fail per persona.
  - If cost-sensitivity shows the strategy breaks at <2 ticks slippage, mentor must surface as a finding.
- **Spend:** Sonnet L, Opus S.

### Sprint D2 — Inactivity heartbeat + auto-flatten

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D2 | **Sonnet 4.6** | Heartbeat monitor + tests against fake API stub. | M |

- **Parallel slot:** Sprint 30.
- **Acceptance:** unit test simulates 30-second API silence and asserts the flatten path fires.

### Sprint 31 — Regime filter integration (TRUE walk-forward begins here)

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 31a | **Opus 4.7** | Regime filter design. **Pre-commitment rule:** the filter threshold must be (a) justified by market-structure argument [mentor's path], OR (b) selected on data the v2 evaluation does not touch [hold-out folds]. No threshold-from-30-results-then-test-on-30-folds. Spec includes which path. | M |
| 31b | **Sonnet 4.6** | Implement filter as composable signal layer. Run **rolling-fit walk-forward**: fit the filter on training window, evaluate on next test window, slide forward. Compare with/without filter. `record_trial(...)` for both variants. | M |

- **Parallel slot:** D3 (Sonnet).
- **Acceptance:**
  - Filter is a reusable component (not 6E-specific code).
  - Walk-forward report produces ≥6/10 positive folds AND binomial p-value < 0.10 against null p=0.5.
  - Bootstrap CI on aggregated Calmar excludes 1.0 (i.e., strictly better than break-even on a risk-adjusted basis).
- **Spend:** Opus M, Sonnet M.

### Sprint D3 — Order idempotency + reconciliation scaffold

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D3 | **Sonnet 4.6** | Idempotency token, dedupe debounce, reconciler against fixtures. | M |

- **Parallel slot:** Sprint 31.

### Sprint B1 — Timeframe catalog (Gemini)
Spec: `docs/roadmap/session-specs/session-B1-timeframe-catalog.md` (existing). Add: `gemini-validation-playbook.md` reference; OHLCV resample parity test pattern (Example D in playbook).

| Sub | Model | Workload | Effort |
|---|---|---|---|
| B1 | **Gemini 3.1** | 3m, 10m, 30m, 120m resamplers; build CLEAN+FEATURES on ZN and 6E; tests under playbook pattern. | M |

- **Parallel slot:** Anytime; recommend Day 5 alongside sprint 33.

### Sprint 32 — Mulligan scale-in with directional gate

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 32a | **Opus 4.7** | Mulligan rule precise spec including: (1) freshness invariant (new `Signal` emission required), (2) directional-price-relationship gate (mentor's rule: longs only re-enter at price ≥ original + N×ATR; default N=0.3), (3) combined risk and target pre-defined before second entry. | S |
| 32b | **Sonnet 4.6** | Implement; unit tests covering positive case, both negative cases (adverse-P&L re-trigger; same-signal-second-look), and the directional gate. `record_trial(...)`. | M |

- **Parallel slot:** D4 (Sonnet).
- **Acceptance:**
  - Contract test `tests/contracts/test_mulligan_freshness.py` covers all three semantic cases.
  - Mulligan freshness invariant is documented in `core/strategies.py` Strategy Protocol docstring.
- **Spend:** Opus S, Sonnet M.

### Sprint D4 — Kill-switch hierarchy

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D4 | **Sonnet 4.6** | Strategy / instrument / account kill switches; integrate with D1+D2. | M |

- **Parallel slot:** Sprint 32.
- **Acceptance:** drill test (simulated API outage) flattens at account level; single-strategy loss-limit breach halts only that strategy.

### Sprint 33 — 6E backtest v2 + Track C gate (PRE-COMMITTED)
Detailed spec: `docs/roadmap/session-specs/session-33-track-c-gate.md`

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 33a | **Sonnet 4.6** | Run rolling-fit walk-forward on `vwap-reversion-v1` + regime filter + Mulligan combined. Side-by-side report v1 vs v2 (uses sprint F3 trial-comparison tooling if delivered). Per-fold stationarity + cost sensitivity. `record_trial(...)`. | M |
| 33b | **Opus 4.7** | Pre-committed gate procedure (see spec). Gate criteria — ALL must pass: <br>① ≥6/10 folds positive AND binomial p<0.10. <br>② Bootstrap CI lower bound on Calmar ≥ 1.5. <br>③ Deflated Sharpe CI excluding zero, computed over full cohort with `n_trials` named. <br>④ Max consecutive losses 95th percentile ≤ 8 (mentor's tighter bound). <br>⑤ Per-fold stationarity preserved across all folds (no regime-fitting). <br>⑥ Strategy passes at 2-tick slippage (not just 0.5-tick). <br>⑦ Cohort consistency: all variants in cohort share `engine_fingerprint`. | M |

- **Parallel slot:** F1 (Gemini) on HTML report enhancements.
- **Pre-committed escape paths (mentor's rule):**
  - PASS → Track E (sprint 34a picks E1 or E1').
  - FAIL with positive aggregate equity but failing fold dispersion → pivot to 6A/6C single-instrument (sprint 34 reroutes).
  - FAIL with negative aggregate equity → switch strategy class (sprint 34 picks momentum/breakout from session 28 stationarity follow-up).
  - FAIL with marginal margins after costs and June 30 pressure → TradingView port path (E1').
- **Spend:** Sonnet M, Opus M.

### Sprint F1 + F2 — UX polish (Gemini, follows playbook for any computed metric)

| Sub | Model | Workload | Effort |
|---|---|---|---|
| F1 | **Gemini 3.1** | HTML report: top-X composite ranking, deflated-Sharpe-with-trader-language, CI bars on Calmar. | M |
| F2 | **Gemini 3.1** | CLI subcommands: `list-templates`, `describe-template`, `backtest --template ... --knobs k=v`. | S |

### Sprint 34 — Bridge option pick + E1 begin

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 34a | **Opus 4.7** | Bridge decision (TS SIM vs TV Pine port) using sprint 33 result and pre-committed escape rules. Persona sign-off recorded. | S |
| 34b | **Sonnet 4.6** | Begin E1 (TS SIM API integration) or E1' (Pine port skeleton + TV log parser). Featureset hash check on data-load path is in scope. | L |

- **Parallel slot:** F3 (Gemini) on trial-comparison report.
- **Acceptance:** decision logged; E1/E1' has integration test against recorded fixture.
- **Spend:** Opus S, Sonnet L.

### Sprint F3 — Trial comparison HTML report (Gemini)

| Sub | Model | Workload | Effort |
|---|---|---|---|
| F3 | **Gemini 3.1** | `compare-trials <id1> <id2>` produces single side-by-side HTML. | M |

### Sprint 35 — E2 paper-trading loop

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 35a | **Sonnet 4.6** | Wire signal generator → order submitter → fill listener → trade log writer → daily report. **Featureset hash check on every parquet swap; mismatch is a hard halt.** | L |
| 35b | **Opus 4.7** | Failure-mode review: duplicate fills, partial fills, missing fills, API silence, featureset version drift. Cross-check D2/D3/D4. | M |
| 35c | **Sonnet 4.6** | Implement gaps from 35b. | M |

- **Acceptance:**
  - End-to-end test against fixture: signal at T0 → order at T0+slippage → fill → trade-log row → P&L update.
  - All 35b failure modes covered with tests.
  - Trade-by-trade live-vs-backtest record (not aggregate-only) — required by data scientist for sprint 36 divergence analysis.
- **Spend:** Sonnet L+M, Opus M.

### Sprint 36 — First paper trade + 30-day discipline window opens (mentor reframing)

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 36a | **Sonnet 4.6** | First-trade scaffolding, daily reconciliation, comparison report generator. | M |
| 36b | **Opus 4.7** | Live-vs-backtest divergence interpretation. Mentor's "does the market structure look like the backtest assumed" pass. **Sprint output = beginning of 30-day paper window, not advancement to live.** | M |

- **Acceptance:** at least one closed paper trade with comparison report; trade-by-trade divergence within tolerance documented; **30-day discipline window is now open and tracked**.

### Sprint 37 — Hardening pass + monitoring polish

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 37a | **Opus 4.7** | Architect review of paper-trading day-1 artifacts; punch-list ranked by blast radius. | S |
| 37b | **Sonnet 4.6** | Top-of-list cleanup. | M |
| 37c | **Gemini 3.1** | Mechanical fan-out: docstring fills, missing test coverage, README updates, copy edits. | S |

- **Acceptance:** punch-list closed or moved to backlog; full suite green; one-page health-check CLI runs.

### Sprint 38 — Trader's-desk polish + readiness review (NOT a live-readiness gate)

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 38a | **Opus 4.7** | UX design pass starts with **audit of `gui/` and `replay/`** (architect's catch) — extend / reuse / replace. Then: what should `trading-research status` show, what HTML page do you open in the morning. | M |
| 38b | **Sonnet 4.6** | Implement `status`, daily-summary HTML, `validate-strategy` config linter — integrating with whatever 38a decided about gui/replay. | M |
| 38c | **Gemini 3.1** | Polish, theming, copy. | S |
| 38d | **Opus 4.7** | Three-persona readiness review. **Per mentor: this review does NOT advance to live capital.** It confirms the platform can carry the strategy through the rest of the 30-day discipline window with minimal further changes. ML deferral defended explicitly. | S |

- **Spend:** Opus M+S, Sonnet M, Gemini S.

---

## Daily-throughput patterns v2

11 calendar days for 14 sprint slots (was 10 in v1; +1 because sprint 29 is two days).

| Day | Claude/Opus track | Sonnet parallel | Gemini parallel |
|---|---|---|---|
| 1 | 29a (Opus) → 29b (Sonnet) | D1 | — |
| 2 | 29c (Sonnet) | — | 29d |
| 3 | 30a (Sonnet) → 30b (Opus) | D2 | — |
| 4 | 31a (Opus) → 31b (Sonnet) | D3 | — |
| 5 | 32a (Opus) → 32b (Sonnet) | D4 | F2 |
| 6 | 33a (Sonnet) → 33b (Opus gate) | — | F1, B1 |
| 7 | 34a (Opus) → 34b (Sonnet) | — | F3 |
| 8 | 35a–c (Sonnet + Opus mid) | — | — |
| 9 | 36a (Sonnet) → 36b (Opus) | — | — |
| 10 | 37a–c | — | 37c |
| 11 | 38a–d | — | 38c |

## Token-budget intuition (refined)

- Opus-heavy days (1, 3, 4, 6, 9, 11): synthesis + gate work. Don't substitute Sonnet.
- Sonnet-heavy days (2, 5, 7, 8): cheap throughput.
- Gemini days (B1, F1, F2, F3, 29d, 37c, 38c): essentially free relative to Claude budget.
- Parallel-day budget (e.g. Day 1: Opus 29a + Sonnet 29b + Sonnet D1): roughly equivalent to a single Opus-only sprint, ~3× output. The trade is real but only when the spec→test→impl protocol holds.

## Dependencies (unchanged from v1 except sprint 29 expansion)

- 30 onwards depends on sprint 29 producing working registry coupling AND size_position wiring.
- 33 (gate) depends on 31 and 32.
- 34 depends on 33 PASS or pre-committed escape decision.
- 35 depends on Track D complete.
- 36 depends on 35.
- B1, F1–F3 independent — slot anywhere.

## Risks

See `outputs/planning/sprints-29-38-risks-v2.md`.

## Open items requiring Ibby red-line BEFORE sprint 29

These are plan-level commitments. Sprint 29a operationalises them; Ibby decides
the framing:

1. **Walk-forward terminology fix.** Confirm: sprint 30 is "contiguous-test
   segmentation," not walk-forward. Sprints 31, 33 are walk-forward when fitted.
2. **Sprint 29 spans two days.** Confirm acceptance.
3. **Cost sensitivity in sprint 30.** Confirm slippage sweep {0.5, 1.0, 2.0, 3.0}
   ticks is the right grid. Mentor-specified.
4. **Knob defaults: `entry_threshold_atr=2.2`, `entry_blackout=60min`.** Confirm.
5. **Track C gate criteria (sprint 33b).** Seven-criterion gate. Confirm or
   modify per Ibby's risk tolerance.
6. **Sprint 36 reframed.** First paper trade is start of 30-day window, not
   completion of E. Confirm 38d does not advance to live.
7. **Multi-model handoff protocol & Gemini playbook adopted as policy.** Confirm.

## Out of scope (explicit, unchanged from v1)

- ML strategy work (Track G).
- Second instrument or pairs (Track H).
- Live capital (Track I).
- Web dashboard, mobile, real-time WebSocket cockpit.
- CI/CD beyond local `uv run pytest`.
