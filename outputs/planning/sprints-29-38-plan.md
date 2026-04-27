# Plan: Sprints 29–38 — From hardened pipeline to working trader's desk
Date: 2026-04-25
Status: Draft (awaiting Ibby red-line)

## Objective

Land Ibby on a working trader's desk by sprint ~40: a validated 6E rule-based
strategy in paper trading (on-platform or via TradingView), full circuit-breaker
safety envelope in place, polished CLI + HTML reports, and the platform set up
so adding the next strategy or instrument is a config edit, not a rewrite.

## Scope

**In:** sessions 29–38 covering Tracks C (strategy on 6E), D (execution plumbing),
B (timeframe catalog side-quest), F (UX polish), and the start of E (paper bridge).
Multi-model assignment per session with split sub-sprints where mixing models
buys real efficiency.

**Out:** ML capability (Track G — sessions 38–42 in roadmap, deferred), pairs and
second instrument (Track H), live execution (Track I). Sprint 40 is **paper
trading running on a validated strategy**, not live capital.

## Current state (entering sprint 29)

- **Track A: DONE.** End-to-end pipeline runs for any instrument by config. 6E
  CLEAN+FEATURES built, ADF/Hurst/OU computed, vwap_spread strongly stationary.
- **Strategy class decision (6E):** recommended = intraday VWAP mean reversion
  with extended hold (60-bar / 5-hr cap, London/NY overlap entries, 21:00 UTC
  flatten). Doc: `docs/analysis/6e-strategy-class-recommendation.md`.
- **Known data gap:** 6E Q3 2015 – Q1 2017 (TradeStation 404s). Backtest train
  starts 2018-01-01.
- **Outstanding debt:** stationarity suite tradeable bounds are ZN-calibrated;
  classify both 6E half-lives as TOO_SLOW. Recalibration is folded into 29.

## Model strategy

This plan exists because Ibby pays per-token and wants real parallelism across
Opus, Sonnet, and Gemini-3.1-Antigravity. The pattern that emerged from
sessions 25–28: Gemini handles spec-driven mechanical work cleanly (timeframe
expansion, canonical-method ports), Sonnet is the workhorse for implementation
against a written design, Opus earns its keep on synthesis, regime decisions,
and debugging that cuts across personas. Two rules:

1. **Each session is split into sub-sprints when crossing a model boundary.**
   A session that's 50% design + 50% implementation gets `29a (Opus design)`
   and `29b (Sonnet implement)`. Spec hand-off is the boundary; each sub-sprint
   has its own work log and (where appropriate) its own git branch.

2. **Parallel tracks fire on the same calendar day.** Sprints aren't only
   sequential — D1/D2 (Sonnet) can run while 29 (Opus) is being designed, and
   B1 (Gemini) can run in another window. The plan calls out which slots are
   safe to run concurrently.

### Model fit cheatsheet (used throughout)

| Workload | Best fit | Rationale |
|---|---|---|
| Design / regime decisions / persona synthesis | **Opus 4.7** | Three-persona reasoning, weighing tradeoffs |
| Implementation against a written spec | **Sonnet 4.6** | Cheaper per token, strong code quality, fast |
| Mechanical spec-shape ports (canonical methods, resamplers, manifest migrations, HTML tweaks) | **Gemini 3.1 (Antigravity)** | Proven on sessions 11–13 + 25–28 fan-out work |
| Cross-persona debugging / Calmar-vs-Sharpe interpretation calls | **Opus 4.7** | Synthesis quality matters here, not throughput |
| Walk-forward backtest runs and trade-log analysis | **Sonnet 4.6** | High-volume code edits + assertion tests |

---

## Sprint plan (29–38)

For each sprint:
- **Goal** (one sentence)
- **Sub-sprints** (a/b/c when split across models) with model + agent fit
- **Parallel slot** — what else can run that day
- **Acceptance** — observable, not subjective
- **Estimated model spend** (relative T-shirt size: S = small, M = medium, L = large)

### Sprint 29 — 6E strategy template + suite recalibration
Ports the strategy-class recommendation into a backtestable Strategy template.
Writing the design here is high-stakes (template will outlast this strategy).

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 29a | **Opus 4.7** | Strategy template design — ratify VWAP-MR class, write `templates/vwap_reversion_v1.yaml` schema, define knob registry, write the spec for 29b | M |
| 29b | **Sonnet 4.6** | Implement the template module, plug into Strategy Protocol, port the knob YAML, recalibrate stationarity-suite bounds (10–80 bars at 5m for 6E, leave ZN bounds) | M |
| 29c | **Gemini 3.1** | Acceptance tests + canonical-method validation: VWAP computed against a known reference; OU half-life recalibration tested against the existing 6E data | S |

- **Parallel slot:** Sprint D1 (Sonnet) can run on a separate branch the same day.
- **Acceptance:** `uv run trading-research describe-template vwap_reversion_v1` prints knob defaults + ranges; suite reclassifies 6E half-lives as TRADEABLE.
- **Spend:** Opus M, Sonnet M, Gemini S.

### Sprint D1 — Daily/weekly loss limits (parallel-eligible)
Spec already exists in `docs/roadmap/session-specs/track-D-circuit-breakers.md`.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D1 | **Sonnet 4.6** | Implement `LossLimitMonitor`, `LimitBreach`, default YAML, unit tests | M |

- **Parallel slot:** Runs alongside sprint 29 (different files entirely).
- **Acceptance:** new tests pass; backtest engine consumes the monitor; a synthetic trade log that breaches the daily limit produces a `LimitBreach` event and halts further entries.
- **Spend:** Sonnet M.

### Sprint 30 — 6E backtest v1 (walk-forward, full provenance)
The first real strategy run since the refactor. Trial registry must record code+data+featureset+config+seed.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 30a | **Sonnet 4.6** | Wire `vwap_reversion_v1` into the backtest engine, run 4-fold walk-forward 2018–2024, purge=576 bars, write trial registry entry | L |
| 30b | **Opus 4.7** | Three-persona review of the result: mentor on market behaviour (does the equity curve respect London/NY structure?), data scientist on confidence intervals + deflated Sharpe, architect on whether anything new is hardcoded | S |

- **Parallel slot:** D2 (Sonnet) on inactivity heartbeat — different module.
- **Acceptance:** walk-forward complete; HTML report lives under `runs/<trial-id>/`; trial registry entry has `code_hash`, `featureset_hash`, `config_hash`, `data_hash`, `seed`. Persona review committed in the work log.
- **Spend:** Sonnet L, Opus S.

### Sprint D2 — Inactivity heartbeat + auto-flatten
Spec in track-D doc.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D2 | **Sonnet 4.6** | Implement heartbeat monitor against TradeStation API; on silence > N seconds, flip account-level switch; tests with a fake API stub | M |

- **Parallel slot:** Runs alongside 30.
- **Acceptance:** unit test simulates 30-second API silence and asserts the flatten path fires.
- **Spend:** Sonnet M.

### Sprint 31 — Regime filter integration
The 30b persona review will likely flag a regime issue (mentor's catch — strategy probably doesn't survive 2022 ECB rate cycle untouched). 31 adds the gate revealed by 30b.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 31a | **Opus 4.7** | Regime filter design — pick gate (ADX, ATR percentile, time-of-day, or rate-regime split) using session 30 walk-forward by-fold breakdown; write spec | M |
| 31b | **Sonnet 4.6** | Implement filter as a composable signal layer, re-run walk-forward, compare with/without filter | M |

- **Parallel slot:** D3 (Sonnet) on order idempotency — different files.
- **Acceptance:** filter is a reusable component (not 6E-specific code); v1.1 walk-forward produces ≥5/10 positive folds and tighter CI than v1.0.
- **Spend:** Opus M, Sonnet M.

### Sprint D3 — Order idempotency + reconciliation scaffold
Per track-D spec.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D3 | **Sonnet 4.6** | Idempotency token generator, dedupe debounce, broker-fill reconciliation scaffold (no live API yet — works against fixtures) | M |

- **Parallel slot:** Same day as 31 if Ibby has bandwidth.
- **Acceptance:** dedupe test fires duplicate signals within debounce window, exactly one order is recorded; reconciler matches 100% of fixture fills.
- **Spend:** Sonnet M.

### Sprint B1 — Timeframe catalog (Gemini, fully spec-driven)
Spec already written: `docs/roadmap/session-specs/session-B1-timeframe-catalog.md`.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| B1 | **Gemini 3.1** | Add 3m, 10m, 30m, 120m resamplers; build CLEAN+FEATURES for ZN and 6E at new timeframes; tests on OHLCV invariants and session boundaries | M |

- **Parallel slot:** Anytime after sprint 25 (already past). Slot whenever Claude work is queued.
- **Acceptance:** spec's success-signal commands run clean; `uv run pytest` green.
- **Spend:** Gemini M.

### Sprint 32 — Mulligan scale-in logic
Re-entry on a fresh signal with predefined combined risk/reward (per CLAUDE.md
risk rules — this is not averaging down, the trigger must be a fresh signal).

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 32a | **Opus 4.7** | Design the Mulligan rule precisely — what counts as a fresh signal, how combined risk/reward is computed, what the data scientist needs to test for | S |
| 32b | **Sonnet 4.6** | Implement, plug into the strategy template as an optional knob, unit tests on signal-trigger semantics | M |

- **Parallel slot:** D4 (Sonnet) on kill-switch hierarchy.
- **Acceptance:** synthetic test where a mid-trade re-trigger produces a scaled-in second entry with correct combined target and risk; regression test that a price-only "averaging-down" attempt without fresh signal is rejected.
- **Spend:** Opus S, Sonnet M.

### Sprint D4 — Kill-switch hierarchy
Per track-D spec.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| D4 | **Sonnet 4.6** | Strategy / instrument / account kill switches as a composable hierarchy; integrate with LossLimitMonitor and heartbeat from D1/D2 | M |

- **Parallel slot:** Runs with 32.
- **Acceptance:** Track D acceptance — drill test (simulated API outage) flattens at the account level; loss-limit breach on a single strategy halts only that strategy.
- **Spend:** Sonnet M.

### Sprint 33 — 6E backtest v2 + Track C gate decision
Run with regime filter + Mulligan; this is the gate.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 33a | **Sonnet 4.6** | Run v2 walk-forward; produce side-by-side report v1 vs v2 (uses sprint F3 if delivered, else simple two-page diff) | M |
| 33b | **Opus 4.7** | Three-persona gate review: does v2 clear ≥5/10 folds positive, deflated Sharpe CI excluding zero, max consecutive losses < 20, stationarity-passing core feature? Decision: PASS → Track E, FAIL → escape valve options written into the work log | M |

- **Parallel slot:** F1 (Gemini) on HTML report enhancements, only if Ibby wants the side-by-side ready for 33a.
- **Acceptance:** documented PASS/FAIL with rationale signed by all three personas in the work log.
- **Spend:** Sonnet M, Opus M.

### Sprint F1 + F2 — UX polish (Gemini double-header)
Both fully spec-shape, slot anywhere after 27 (already past).

| Sub | Model | Workload | Effort |
|---|---|---|---|
| F1 | **Gemini 3.1** | HTML report enhancements: top-X composite ranking, deflated-Sharpe-with-trader-language explanation, confidence-interval bars on Calmar | M |
| F2 | **Gemini 3.1** | CLI subcommands: `list-templates`, `describe-template <name>`, `backtest --template <name> --knobs k=v,...` | S |

- **Parallel slot:** Run on the same day Claude is busy on 32 or 33.
- **Acceptance:** F1 — sprint 33 report uses the new components; F2 — `uv run trading-research describe-template vwap_reversion_v1` is what the user actually invokes.
- **Spend:** Gemini M+S.

### Sprint 34 — Paper-trading bridge: option pick + E1 begin
At this point Track C has either passed or escaped. Decision time on E-on-platform vs E-via-TradingView.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 34a | **Opus 4.7** | Bridge option decision: factors are TradeStation SIM API maturity, June 30 deadline pressure, port effort to Pine. Recommendation + persona sign-off. | S |
| 34b | **Sonnet 4.6** | Begin E1 (or E1') based on 34a — TradeStation SIM API integration OR Pine port skeleton | L |

- **Parallel slot:** F3 (Gemini) on trial-comparison report.
- **Acceptance:** decision logged; E1/E1' has a working integration test against a recorded fixture (SIM endpoint OR Pine + TV log parser).
- **Spend:** Opus S, Sonnet L.

### Sprint F3 — Trial comparison HTML report (Gemini)
Two trials side-by-side in one HTML file.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| F3 | **Gemini 3.1** | Implement against the existing report module's templates; reuse F1's components | M |

- **Parallel slot:** Same day as 34.
- **Acceptance:** `uv run trading-research compare-trials <id1> <id2>` produces a single HTML file with the two trials.
- **Spend:** Gemini M.

### Sprint 35 — E2 paper-trading loop
End-to-end paper loop: signal → order → fill → trade log → report. The
hardest sprint of the bunch — touches data, strategy, risk, and broker layers
all at once.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 35a | **Sonnet 4.6** | Wire signal generator → order submitter → fill listener → trade log writer → daily report | L |
| 35b | **Opus 4.7** | Failure-mode review: what happens on duplicate fills, partial fills, missing fills, API silence; cross-check against D2/D3/D4 | M |
| 35c | **Sonnet 4.6** | Implement the gaps from 35b | M |

- **Parallel slot:** None — this sprint owns the day.
- **Acceptance:** end-to-end test against fixture: signal at T0 produces an order at T0+slippage, a recorded fill, a trade-log row, and a P&L update. All three failure modes from 35b are covered with tests.
- **Spend:** Sonnet L+M, Opus M. (Heaviest spend day.)

### Sprint 36 — First paper trade + live-vs-backtest comparison report
Fire the loop on real-time SIM (or TV) data and compare actual fills to backtest fills.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 36a | **Sonnet 4.6** | First-trade scaffolding, daily reconciliation, comparison report generator | M |
| 36b | **Opus 4.7** | Live-vs-backtest divergence interpretation: where does slippage land, are trigger-vs-entry separations behaving as designed, mentor's "does the market structure look like the backtest assumed" pass | M |

- **Parallel slot:** None — Ibby is going to want full attention on the first paper trade.
- **Acceptance:** at least one closed paper trade with a comparison report; divergence within tolerance documented in work log.
- **Spend:** Sonnet M, Opus M.

### Sprint 37 — Hardening pass + monitoring polish
After first trade, the cleanup-debt list will be long. This sprint is reserved
for it. Architect-led — exactly the "every session spawns 2–3 cleanup tasks"
slack the roadmap asked for.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 37a | **Opus 4.7** | Architect review of paper-trading day-1 artifacts; produce cleanup punch-list ranked by blast radius | S |
| 37b | **Sonnet 4.6** | Knock out top of punch-list — usually log structure, timestamp tz fixes, manifest fields, retry semantics | M |
| 37c | **Gemini 3.1** | Mechanical fan-out: docstring fills, missing test coverage on touched modules, README updates | S |

- **Parallel slot:** None — focus on cleanup.
- **Acceptance:** punch-list items either closed or moved to backlog with rationale; full test suite green; one-page health-check CLI command runs and prints status of every active component.
- **Spend:** Opus S, Sonnet M, Gemini S.

### Sprint 38 — Trader's-desk polish + readiness review
The "make it a nice app" sprint Ibby explicitly asked for. Daily-status CLI,
HTML cockpit landing page, configuration sanity checker.

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 38a | **Opus 4.7** | UX design pass: what should `trading-research status` show, what one HTML page do you open in the morning, what knobs need a sanity check before a strategy can be promoted | M |
| 38b | **Sonnet 4.6** | Implement `status` command, daily-summary HTML, `validate-strategy` config linter | M |
| 38c | **Gemini 3.1** | Polish and theming for HTML output, copy edits, error message clarity, help text | S |
| 38d | **Opus 4.7** | Three-persona readiness review: is the trader's desk done? what's still missing for live (Track I)? Sign-off recorded. | S |

- **Parallel slot:** None — closing sprint.
- **Acceptance:** Ibby can open one HTML page or run one CLI command and see strategy status, paper-trading P&L, last-N-trades, and current circuit-breaker state. Readiness review committed.
- **Spend:** Opus M+S, Sonnet M, Gemini S.

---

## Daily-throughput patterns

The above 14 sprint slots (29–38 + D1–D4 + B1 + F1–F3) compress into roughly 10
working days because of parallelism. Suggested pairings for one calendar day:

| Day | Claude track | Sonnet parallel | Gemini parallel |
|---|---|---|---|
| 1 | 29a (Opus design) → 29b (Sonnet) | D1 | — |
| 2 | 30a (Sonnet) → 30b (Opus review) | D2 | B1 |
| 3 | 31a (Opus) → 31b (Sonnet) | D3 | — |
| 4 | 32a (Opus) → 32b (Sonnet) | D4 | F2 |
| 5 | 33a (Sonnet) → 33b (Opus gate) | — | F1 |
| 6 | 34a (Opus) → 34b (Sonnet) | — | F3 |
| 7 | 35a–c (Sonnet + Opus mid) | — | — |
| 8 | 36a (Sonnet) → 36b (Opus) | — | — |
| 9 | 37a–c (Opus + Sonnet + Gemini) | — | — |
| 10 | 38a–d | — | — |

This is a target, not a contract. Real days will compress or stretch; the table
just shows the parallelism is real.

## Token-budget intuition (rough, not promises)

- Opus-heavy days (29, 31, 33, 38): higher per-day burn but the synthesis is the
  product. Don't try to substitute Sonnet here.
- Sonnet-heavy days (30, 32, 35, 36): cheap throughput, lots of code.
- Gemini days (B1, F1, F2, F3): essentially free relative to Claude budget; use
  these to absorb mechanical work that would otherwise eat Sonnet hours.
- Parallel-day budget: an Opus design hour + a Sonnet implement hour + a Gemini
  spec hour, all firing on the same day, costs roughly the same as a single
  Opus-only sprint and produces 3× the throughput. That's the trade.

## Dependencies

- Sprint 30 onwards depends on sprint 29 producing a working template registry.
- Sprint 33 (gate) depends on sprints 31 and 32 both landing.
- Sprint 34 depends on sprint 33 PASS or on the documented escape decision.
- Sprint 35 depends on Track D being complete (D1–D4).
- Sprint 36 depends on sprint 35.
- B1, F1–F3 are independent — slot them anywhere after sprint 27 (already past).

## Risks

See `outputs/planning/sprints-29-38-risks.md`.

## Open items

- **Track E option pick (sprint 34):** TradeStation SIM vs TradingView Pine port.
  Cannot decide until sprint 33 result is in, but the discussion can begin
  earlier if Ibby has views on the Pine port effort.
- **Stationarity suite recalibration scope (sprint 29c):** widen ZN+6E shared
  bounds, or per-instrument bounds in the suite config. The architect leans
  per-instrument; the data scientist is fine with either if documented.
- **Whether ML (Track G) starts overlapping at sprint 38 or stays deferred.**
  Recommend: stay deferred until at least 6 weeks of paper trading. Sprint 38
  readiness review will revisit.

## Out of scope (explicit)

- ML strategy work (Track G).
- Second instrument or pairs (Track H).
- Live capital (Track I).
- Web dashboard, mobile, real-time WebSocket cockpit.
- CI/CD beyond local `uv run pytest`.
