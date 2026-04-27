# Trading Research Platform — Roadmap, Sessions 23–50

**Drafted:** 2026-04-19, end of Session 22
**Authors:** Ibby + quant-mentor + data-scientist + platform-architect personas
**Status:** Draft 1, awaiting red-line review

---

## The finish line

**Finish line A ("Trader's desk").** At the end of this roadmap, Ibby can do the following in a morning without writing Python:

1. Open a CLI or HTML report, see the status of every active strategy and its live paper-trading P&L.
2. Pick a strategy template (e.g. VWAP reversion), pick an instrument (e.g. 6E), tweak knob values in a YAML config, run a backtest, read the 24-section HTML report inline.
3. Drill into any trade in the Dash replay cockpit.
4. Promote a validated strategy to paper trading — either on this platform via TradeStation SIM, or by hand-porting to TradingView Pine Script.
5. Know with confidence that every backtest result is honest, reproducible, and statistically interpretable.

**Checkpoint C:** First paper trade (on-platform or via TradingView) by **June 30, 2026**. This is the forcing function. If the calendar drifts past this date, the plan has failed in a way that needs explicit review, not silent slippage.

**What is explicitly NOT in scope for this roadmap:**

- A browser-based full trading desk UI. CLI + HTML reports + Dash replay is the working interface.
- A mobile / tablet experience.
- A plugin architecture for third-party strategies.
- ML-in-production. ML is a framework that will be built (sessions 38–42) and available as a capability, but no ML model is required to live-trade by session 50.
- A Pine Script exporter. Manual port per strategy is the approach.
- CI/CD. Solo project; `uv run pytest` locally is sufficient.

---

## Current state (end of session 22)

See `docs/handoff/status-report-session-22.md` for the full inventory. Summary:

- **Data pipeline, backtest engine, statistical rigor layer, replay cockpit:** WORKING.
- **Instrument generalization:** HAS ISSUES (3 hardcodings: OI-010/011/012).
- **Trial registry:** WORKING but uninterpretable across code versions (the v1 and v2 trials are not directly comparable because the backtest engine has evolved between them).
- **ZN v1 (MACD pullback):** Failed definitively. Hypothesis was flawed (no regime filter, no real exit).
- **ZN v2 (VWAP reversion):** Failed to clear bar. 23.2% win rate, Calmar -0.05. Structural level is real but direction is unresolved.
- **Stationarity suite (ADF, Hurst, OU):** PLANNED, not built.
- **Benjamini-Hochberg correction:** PLANNED, not built.
- **Circuit breakers / kill switches / loss limits:** PLANNED, not built.
- **Paper trading plumbing:** NOT STARTED.

**Strategic pivot effective session 23:** Primary instrument moves from ZN (10-year Treasury) to 6E (EUR/USD futures). ZN is shelved — data pipeline keeps running, no new strategy work. Reasoning: ZN's compressed daily range gives mean reversion insufficient room to pay for commissions and slippage; 6E has wider movement and Ibby has personal trading experience in FX.

**Strategy class is undecided.** Session 29 will use ADF / Hurst / OU results on 6E to pick between mean reversion, momentum, breakout, or event-driven.

---

## The plan: parallel tracks, not a linear list

The session-numbering is **ordering and dependency**, not calendar. At current cadence (1 session/day due to Claude Code token quota), ~10 calendar weeks = ~50 working sessions. This roadmap has 28 numbered sessions. The gap is deliberate slack for the architect's "every session spawns 2–3 cleanup tasks" reality and for the mentor's "build in the idea that a session can be skipped" flexibility.

### Track overview

| Track | Sessions | Can run parallel with | Agent fit |
|---|---|---|---|
| **A — Hardening** | 23–28 | Nothing else (foundational) | Mostly Claude, some Gemini |
| **B — Side-quest: timeframe catalog** | Anytime after 25 | Any | Gemini |
| **C — Strategy iteration on 6E** | 29–34 | E, F after 30 | Claude |
| **D — Execution plumbing** | 30–33 | C, F | Either |
| **E — Paper trading bridge** | 34–36 | C, F | Either |
| **F — Minimal UX (CLI polish + HTML enhancements)** | Anytime after 26 | Any | Either |
| **G — ML capability** | 38–42 | Anything | Claude + Gemini |
| **H — Second instrument + pairs** | 43–48 | G, F | Either |
| **I — Live execution** | 48–50 | Gated on E passing | Claude |

### Dependency summary

- **A is the gate for everything.** 23, 24, 25 must land in order. 26–28 can fan out slightly.
- **C (strategy work) depends on A being done** — no 6E strategy code before the Protocol exists.
- **D (execution plumbing) starts parallel with late A** and continues through C.
- **E (paper trading bridge) depends on C producing a positive result** OR on a decision to port to TradingView manually.
- **G (ML) depends on C producing a positive rule-based strategy.** ML on nothing produces nothing.
- **H, I are downstream of E passing.**

---

## Track A — Hardening sprint (sessions 23–28)

The platform has to be instrument-agnostic, statistically sound, and reproducible before any more strategy iteration happens. Six sessions, time-boxed. If session 28 ships and A isn't done, the mentor overrules and we return to strategy anyway — the hardening sprint cannot become the project.

| # | Title | Agent | Depends on |
|---|---|---|---|
| 23 | Core Protocols — Instrument, Strategy, Template, FeatureSet | Claude | — |
| 24 | Trial registry code-versioning + stationarity suite design | Claude | 23 |
| 25 | Pipeline refactor against Instrument Protocol; fix OI-010/011/012 | Either | 23 |
| 26 | Stationarity suite implementation (ADF, Hurst, OU half-life) | Either | 24 |
| 27 | Benjamini-Hochberg correction + composite top-X ranking in reports | Either | 26 |
| 28 | 6E pipeline end-to-end; ADF run on 6E 5m + VWAP spread | Either | 25, 26 |

**Acceptance gate for Track A:** Running `python -m trading_research.pipeline --symbol 6E --start 2020-01-01 --end 2024-12-31` produces a CLEAN parquet, a FEATURES parquet, and a stationarity report, with zero code changes beyond the initial config entry for 6E in `configs/instruments.yaml`. If this command works, Track A is done. If it doesn't, session 28 rolls over.

## Track B — Timeframe catalog (side-quest, Gemini-eligible)

Current timeframes: 1m, 5m, 15m, 60m, 240m, 1D. Add: **3m, 10m, 30m, 120m**. Apply to every instrument in the registry. Pure resample work, no design judgment. Assign to Gemini.

| # | Title | Agent | Depends on |
|---|---|---|---|
| B1 | Add 3m, 10m, 30m, 120m resamplers; extend CLEAN and FEATURES builders | Gemini | 25 |
| B2 | Acceptance tests — resampled bars round-trip through manifest integrity check | Gemini | B1 |

Runnable any time after session 25 (Instrument Protocol + refactor done). One session, maybe two with tests.

## Track C — Strategy iteration on 6E (sessions 29–34)

All of this depends on Track A passing and on the session 28 ADF results. If 6E tests stationary on the target spread, mean reversion is the path. If not, the mentor and data scientist pick a different strategy class in session 29. The sessions below assume mean reversion; if the class changes, the sequence still applies but the template is different.

| # | Title | Agent | Depends on |
|---|---|---|---|
| 29 | 6E strategy class decision — review stationarity, pick template. Design first 6E template. | Claude | 28 |
| 30 | Backtest v1 of 6E strategy. Walk-forward. Trial registry entry with full provenance. | Claude | 29 |
| 31 | Regime filter integration (ADX gate, or time-of-day, or volatility regime — depending on what 29 reveals). | Claude | 30 |
| 32 | Mulligan scale-in logic — fresh-signal-triggered second entry with pre-defined combined risk/reward. | Claude | 31 |
| 33 | Backtest v2 with regime filter + Mulligan. Walk-forward. If passing, go to Track E. If not, iterate. | Claude | 32 |
| 34 | (Slack session. If session 33 passed, skip. If not, one more strategy design iteration before escalating.) | Claude | 33 |

**Acceptance gate for Track C:** A 6E strategy with positive walk-forward (≥5 folds positive out of 10), deflated Sharpe CI excluding zero, max consecutive losses under 20, and a stationarity-passing core feature. If that gate is met, we go to paper trading plumbing (Track E). If session 34 ends without clearing the gate, escalation decision: shelf 6E mean reversion, try different strategy class, or port the best candidate to TradingView for manual paper trade.

## Track D — Execution plumbing (sessions 30–33, parallel with C)

These can be done by Gemini against a spec while Claude works on C. They have no strategy-design component.

| # | Title | Agent | Depends on |
|---|---|---|---|
| D1 | Max daily drawdown + daily/weekly loss limit implementation | Either | 23 |
| D2 | Inactivity heartbeat + auto-flatten on TradeStation API silence | Either | D1 |
| D3 | Order idempotency + reconciliation scaffold | Either | D2 |
| D4 | Kill switch hierarchy — strategy / instrument / account levels | Either | D3 |

All four run in parallel with Track C. By the time a strategy clears Track C's gate, Track D is done and waiting.

## Track E — Paper trading bridge (sessions 34–36)

Two parallel options; Ibby picks one when a Track C strategy is ready.

**Option E-on-platform:**

| # | Title | Agent | Depends on |
|---|---|---|---|
| E1 | TradeStation SIM API integration — order submission, fill retrieval, account state sync | Claude | Track D done |
| E2 | Paper-trading loop — signal → order → fill → trade log → report | Claude | E1 |
| E3 | First on-platform paper trade. Live-fill vs backtest-fill comparison report. | Claude | E2 |

**Option E-via-TradingView:**

| # | Title | Agent | Depends on |
|---|---|---|---|
| E1' | Hand-port strategy to Pine Script. Validate Pine backtest matches Python backtest within tolerance. | Ibby + Claude | — |
| E2' | TradingView paper trading setup. Daily reconciliation script that pulls TV trade log. | Either | E1' |
| E3' | First TradingView paper trade. Live vs backtest comparison. | Claude | E2' |

E-via-TradingView is strictly faster (1–2 sessions vs 3) but loses the tight integration benefit.

## Track F — Minimal UX polish (anytime after 26)

Small, scoped improvements. Not a dashboard rebuild. Each session is self-contained and Gemini-eligible.

| # | Title | Agent | Depends on |
|---|---|---|---|
| F1 | HTML report enhancements — top-X trades composite ranking, deflated Sharpe side-by-side with trader-language explanation | Either | 27 |
| F2 | CLI `list-templates`, `describe-template <name>`, `backtest --template <name> --knobs k=v,...` subcommands | Either | 23 |
| F3 | Trial comparison report — two runs side-by-side in one HTML file | Either | 27 |

These can slot in wherever throughput allows.

## Track G — ML capability (sessions 38–42)

Deferred until ≥1 rule-based strategy is in paper trading. ML on nothing produces nothing (mentor's rule). When it starts:

| # | Title | Agent | Depends on |
|---|---|---|---|
| 38 | Meta-labeling baseline — logistic regression on best rule-based strategy. Purged walk-forward. | Claude | Track E running |
| 39 | Gradient boosting model. Must beat logistic baseline meaningfully or is discarded. | Claude | 38 |
| 40 | SHAP / feature importance. Fix OI-013 Windows crash or implement CPU-only fallback. | Either | 39 |
| 41 | ML → signal pipeline. Threshold calibration. How a probability becomes a trade. | Claude | 40 |
| 42 | Minimal model registry — versioned, hash-addressable, linked to feature-set version. | Either | 41 |

## Track H — Second instrument / pairs (sessions 43–48)

After the first 6E strategy is stable in paper or live, add 6A or 6C for single-instrument work, then design a first pairs strategy (6A/6C correlation-based).

Content-heavy; will be detailed in a roadmap-revision document once Track C delivers.

## Track I — Live execution (sessions 48–50)

Gated on:
- At least one strategy with ≥6 weeks of profitable paper trading
- All circuit breakers from Track D passing a drill (simulate API outage, verify auto-flatten)
- Sign-off from mentor, data scientist, and architect, in writing in the session log
- Ibby explicit go-ahead

| # | Title | Agent |
|---|---|---|
| 48 | TradeStation live order API wrapper. Micro-lot sizing. | Claude |
| 49 | First live trade. Micro contract. Post-trade review. | Claude |
| 50 | Monitoring, alerting, post-trade review workflow as recurring ritual | Either |

---

## Multi-agent handoff protocol

Every session that is not Claude-only gets a spec in `docs/roadmap/session-specs/session-NN.md` following the template below. The spec is the contract. Any agent (Claude, Gemini, a future one) picks up the spec and runs against it.

### Session spec template

Every spec has these fields:

- **Agent fit:** `claude` | `gemini` | `either`
- **Estimated effort:** S (<2h) | M (2–4h) | L (4h+)
- **Depends on:** list of session numbers
- **Unblocks:** list of session numbers
- **Goal:** one sentence
- **In scope:** file/module list
- **Out of scope:** explicit list
- **Acceptance tests:** specific test functions and CLI invocations that must pass
- **Definition of done:** standard checklist
- **Persona review:** which personas need to sign off (mentor / data-scientist / architect)
- **Reference:** links to relevant prior work

### Gemini-session rules

- Statistical code that claims to implement a published method must be validated against a canonical reference (statsmodels for ADF, scipy for BH, etc.) as part of the acceptance test.
- Strategy code must be validated against a synthetic dataset where the correct signal is known.
- Any new field added to a manifest, trade log, or registry entry requires a migration script and a round-trip test.
- Logging must use `structlog`; no bare `print()` in `src/`.
- Timestamps must be tz-aware; naive datetimes fail acceptance.
- Every session ends with a work log in `outputs/work-log/` per CLAUDE.md convention.

---

## Risks and escape valves

**Risk: Track A overruns.** Mitigation: hard cap at session 28. If not done, mentor overrides and C starts anyway with whatever A has shipped. Accumulated debt becomes a named debt item, not a hidden one.

**Risk: 6E doesn't mean-revert.** Mitigation: session 29 picks strategy class from data. If mean reversion is wrong, momentum or breakout takes over. The template registry makes this cheap.

**Risk: No 6E strategy clears the gate in Track C.** Escape: pivot to 6A/6C, or to a different strategy class, or port the best non-passing candidate to TradingView for forward-test on Ibby's judgment. The platform does not have to invent the strategy; it just has to validate one honestly.

**Risk: Token budget prevents completing a session.** Mitigation: every session is scoped to fit in a single working session. If a session overruns, it splits into NN-a and NN-b, both with their own specs. No sprawling sessions.

**Risk: June 30 paper-trade deadline slips.** Mitigation: TradingView port is a 1–2 session release valve. A strategy that works in backtest can be live-traded on TradingView within a week, even if the on-platform Track E isn't done yet. The deadline is about *paper trading a validated strategy*, not about finishing Track E.

---

## What's explicitly deferred past session 50

- Full web dashboard with real-time P&L
- Mobile view
- Concept drift detection for ML models
- Portfolio-level optimization (beyond simple position sizing)
- Third instrument beyond the 6E + 6A/6C pair
- Automated retraining pipeline
- Any kind of cloud deployment

These may happen in a future roadmap revision. They are not commitments.

---

## Review checkpoints

At the end of each track completing, the three personas do a written review in the session log:

- **Mentor:** is this strategy / capability doing what I expected for this market / instrument?
- **Data scientist:** is the evidence honest, reproducible, and statistically interpretable?
- **Architect:** is this built in a way that will still be maintainable in six months?

A track is "done" when all three sign off. Disagreement is surfaced, not hidden — Ibby is the synthesizer.

---

## This document is a living artifact

Update this file at the end of every track. When a risk materializes or a pivot happens, record it here with a date. Six months from now the commit history of this file is how we reconstruct why the project looks the way it does.
