# Risk Register — Sprints 29–38
Last updated: 2026-04-25

## Architectural & technical

### Stationarity suite stays ZN-calibrated
- Likelihood: Low (sprint 29c handles it) | Impact: Medium
- Category: Architecture
- Mitigation: 29c recalibrates per-instrument bounds; acceptance test asserts
  6E classifies as TRADEABLE.
- Status: Open (closes at end of sprint 29)

### Strategy template entrenches FX-specific assumptions
- Likelihood: Medium | Impact: High
- Category: Architecture
- Mitigation: Architect reviews 29a output before 29b implementation begins.
  Knob registry is generic; instrument-specific defaults live in instrument
  config, not in template code.
- Status: Open

### Trial registry version-skew breaks v1-vs-v2 comparison (sprint 33)
- Likelihood: Medium | Impact: Medium
- Category: Architecture / Reproducibility
- Mitigation: 30a captures full provenance hashes; 33a comparison report is
  flagged when code_hash differs between trials.
- Status: Open

## Strategy & evidence

### v1 walk-forward fails outright (sprint 30)
- Likelihood: Medium | Impact: Medium
- Category: External (market behaviour)
- Mitigation: Sprint 31 regime filter exists for this case; mentor's escape
  valve options are already on the table.
- Status: Open

### v2 fails to clear Track C gate (sprint 33)
- Likelihood: Medium | Impact: High
- Category: External
- Mitigation: Plan documents three escape paths — pivot to 6A/6C, switch
  strategy class, or port best non-passing candidate to TradingView for
  judgment-driven forward test. Sprint 34 decision branches on this.
- Status: Open

### Deflated Sharpe deflates the v2 result to near-zero
- Likelihood: Medium | Impact: High
- Category: Evidence
- Mitigation: Number of variants tested is logged at every sprint; data
  scientist's deflation is computed alongside raw Sharpe. If deflated CI
  includes zero, gate is FAIL regardless of raw number — escape valves apply.
- Status: Open

### Look-ahead bias in VWAP / regime indicators
- Likelihood: Low (project has discipline here) | Impact: High
- Category: Evidence
- Mitigation: Per-indicator unit tests asserting computability with data
  through bar T-1 are required by data scientist persona. 29b adds the
  missing ones for VWAP-spread variants.
- Status: Open

## Execution & integration

### TradeStation SIM API quirks delay E1 (sprint 34–35)
- Likelihood: Medium | Impact: High (June 30 deadline)
- Category: External
- Mitigation: TradingView option (E1') is the explicit release valve — 1–2
  sessions to a paper trade vs. 3 for TS SIM. Sprint 34a decision factors
  TS SIM maturity directly.
- Status: Open

### Live-vs-backtest divergence is large (sprint 36)
- Likelihood: Medium | Impact: Medium
- Category: Operational
- Mitigation: Trigger-vs-entry separation in trade-log schema is designed for
  exactly this measurement; tolerance defined before sprint 36 begins, not
  after. 36b mentor review interprets the divergence.
- Status: Open

### Circuit breakers don't fire when needed (sprint 35–36)
- Likelihood: Low | Impact: Critical
- Category: Operational / Security
- Mitigation: Drill tests in D1–D4 acceptance; sprint 37 punch-list reviews
  every breaker against day-1 paper trading evidence.
- Status: Open

## Process & multi-model

### Model-handoff context loss between sub-sprints
- Likelihood: Medium | Impact: Medium
- Category: Process
- Mitigation: Each sub-sprint's design document is the contract. Sonnet/Gemini
  do not start without a written spec from the prior sub-sprint. Work logs
  capture handoff state explicitly.
- Status: Open

### Gemini 3.1 misimplements a canonical statistical method
- Likelihood: Low (Gemini-rules require validation against statsmodels/scipy) | Impact: High
- Category: Evidence
- Mitigation: Roadmap's Gemini-session rules are non-negotiable: any claim of
  a published method must be validated against canonical reference in the
  acceptance test. 29c uses this rule explicitly.
- Status: Open

### Parallel-day branch conflicts
- Likelihood: Low | Impact: Low
- Category: Process
- Mitigation: Each sub-sprint owns its own files; the daily pairing table in
  the plan is built around non-overlapping module ownership. Conflicts that
  do appear are resolved at the end of each parallel day before next sprint.
- Status: Open

### June 30 paper-trade deadline slips
- Likelihood: Medium | Impact: High (forcing function fails)
- Category: Schedule
- Mitigation: TradingView path is the structural mitigation. If sprint 34a
  picks TS SIM and sprint 35 overruns, sprint 35-b is the pivot to Pine port
  rather than continuing to push TS SIM. Decision rule pre-committed.
- Status: Open

## Token & budget

### Opus burn higher than expected on design sprints (29, 31, 33, 38)
- Likelihood: Medium | Impact: Low
- Category: Operational
- Mitigation: Each Opus sub-sprint has a written goal cap; if the design
  conversation runs long, the implementation half is moved to next-day
  Sonnet rather than letting Opus also do the implementation.
- Status: Open

### Sonnet runs out of context on the heavy sprint 35
- Likelihood: Medium | Impact: Medium
- Category: Operational
- Mitigation: 35 is split into a/b/c on purpose — three smaller Sonnet
  windows with one Opus review in the middle, rather than one mega-session.
- Status: Open
