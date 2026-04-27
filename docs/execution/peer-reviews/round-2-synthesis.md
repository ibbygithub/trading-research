# Round 2 — Synthesis
Date: 2026-04-26
Owner: All three personas
Question set: What product do we have at end of session 38? What can it do?
What can't it do? What's left to make it production-ready for live money trading?

This is the integrated answer to your four questions. The full per-persona
detail is in [`round-2-data-scientist.md`](round-2-data-scientist.md),
[`round-2-architect.md`](round-2-architect.md), and
[`round-2-mentor.md`](round-2-mentor.md).

---

## Q1 — At end of session 38, what product do you have?

**A paper-trading platform with one validated strategy, a 30-day
discipline window just opened, and the architecture in place to add
strategies and instruments by configuration rather than rewrite.**

Three lenses, one product:
- **Methodology (DS):** statistically defensible. Walk-forward, bootstrap
  CIs, deflated Sharpe with cohort awareness, per-fold stationarity. When
  a number gets reported, the platform can defend it.
- **System (Architect):** instrument-agnostic core, single-source-of-truth
  for instrument facts, paper-trading loop with circuit breakers and
  reconciliation, featureset hash drift detection, daily HTML + status
  CLI.
- **Trader (Mentor):** real-desk-shaped guardrails — London/NY only, ECB
  blackout, settlement-aware flatten, Mulligan with directional gate,
  behavioural metrics in plain numbers, replay app for trade-by-trade
  review.

It is what you'd expect a junior PM at a small prop firm to be handed
on day one.

## Q2 — What can it do?

The integrated capability list, deduplicated across personas:

**Research:**
- Add an instrument by editing one YAML file.
- Add a strategy by registering a template (decorator + Pydantic knobs).
- Run a backtest with full provenance (code SHA + engine fingerprint +
  featureset hash + knobs + seed all linked in the trial registry).
- Sweep cost assumptions ({0.5, 1.0, 2.0, 3.0} ticks slippage × commission)
  in one command.
- Walk-forward validate strategies properly (rolling-fit when parameters
  are fitted; contiguous-test when frozen ex-ante).
- Compute deflated Sharpe over a cohort with `n_trials` named.
- Compare two trials side-by-side with cross-cohort warnings.
- Detect Mulligan freshness violations at engine level.
- Run stationarity suite on demand for a candidate instrument.

**Operations:**
- Run a single strategy live on paper with circuit breakers (loss limits,
  heartbeat, kill-switch hierarchy).
- Detect featureset version drift on the live data path; hard halt.
- Trade-by-trade live + shadow-backtest record for divergence analysis.
- Daily reconciliation report.
- One-line CLI status command.
- One-line CLI strategy validation command.

**UX:**
- HTML reports with composite ranking, deflated Sharpe + trader-language
  explanation, CI bars on metrics.
- Replay app for trade-by-trade visual forensics.

## Q3 — What can't it do?

The integrated gap list, prioritized by what blocks live trading:

**Critical for live (must close before session 49):**
1. Place a live (real-money) order — TS LIVE API not implemented.
2. Drill kill switches against real broker silence — only fixtures today.
3. Compute risk-of-ruin tied to actual account size and chosen first-trade
   size — DS L8 criterion not yet computed.
4. Reconcile broker statements against platform state daily — T+1 reality
   not handled.
5. Verify time-sync (NTP) on session start — small but real.
6. Recover from broker outage gracefully — heartbeat detects, but stuck-state
   is not a defined state.
7. Configuration immutability during live session — no lockfile yet.
8. Operational runbook ("what to do when X breaks") — not written.

**High-value but not blocking live (can land in sessions 47–50):**
9. Per-instrument margin headroom check (preflight existence required).
10. Backup + restore for trial registry and configs.
11. Failover behaviour on laptop crash mid-trade — currently undefined.

**Out of scope for live; reasonable to defer:**
12. Multi-strategy portfolio coordination (single strategy live; second
    strategy paper after session 51).
13. Pairs trading framework (Track H, sessions 56+).
14. ML capability in production (Track G, sessions 56+ after 6 weeks live).
15. Tax-lot tracking, year-end 1256 reporting (Track I+).
16. Distributed deployment, cloud, multi-user (intentionally not in scope).
17. Web dashboard, mobile, real-time WebSocket UI (deferred).
18. Automated economic-event blackout calendar (manual today; Track F+).

**Behavioural — software can't help:**
19. Ibby's psychological readiness to sit through a paper drawdown (testable
    only in the 30-day window).
20. Confidence that a strategy will survive a future regime change
    (no software can promise this).

## Q4 — What's left to make it production-ready for live money trading?

This is the question the original 50-session roadmap did not answer in
detail. The Phase 2 plan in [`product-roadmap-to-live.md`](../plan/product-roadmap-to-live.md)
covers it. Summary:

### Phase 2A — 30-day paper window operations (sessions 39–44)
Run the strategy continuously for 30 calendar days. Six review sessions
spaced across that window:
- Sessions 39, 41, 43: weekly Opus reviews with three personas.
- Sessions 40, 42: conditional Sonnet cleanup IF something breaks.
- Session 44: end-of-window comprehensive Opus + Sonnet evaluation.

Hard rule throughout: no knob changes, no new strategies, no behaviour
edits. Cleanup is telemetry only.

### Phase 2B — Live readiness gate (sessions 45–46)
Session 45: nine-criterion gate, all personas sign READY or NOT READY.
Session 46: risk-of-ruin computation; first-live-trade size committed
(default 1 micro M6E).

### Phase 2C — Live execution plumbing (sessions 47–48)
Session 47: TS LIVE API wrapper, preflight checks, manual confirmation
flag, distinct from SIM.
Session 48: drill every D1–D4 circuit breaker against real broker.

### Phase 2D — First live trade + scaling (sessions 49–50)
Session 49: pre-flight checklist read aloud; one micro-contract trade
end-to-end; stop trading for the day.
Session 50: post-trade three-persona review; pre-commit the scaling rule
(5 successful days at 1 contract → 2; 10 days at 2 → recompute size from
larger sample); pre-commit the halt rule (40-trade rolling Calmar lower
CI < 0 → pause).

### Phase 2E — Multi-strategy expansion (sessions 51–55)
Second strategy on 6A or 6C in paper while 6E runs live; promote after
its own 30-day paper window; Track G (ML) / Track H (pairs) decision point
at session 55.

---

## Summary table — readiness for live

| Capability | Status at session 38 | Status at session 50 | Required for live |
|---|---|---|---|
| Strategy validated through gate | ✓ (or escape) | ✓ | ✓ |
| Paper-trading loop running | ✓ | ✓ | ✓ |
| Circuit breakers drilled | fixtures only | real broker | real broker |
| 30-day paper evidence | 0–5 days | 30+ days | 30+ days |
| Live broker integration | — | ✓ (session 47) | ✓ |
| Risk-of-ruin computed for first-trade size | — | ✓ (session 46) | ✓ |
| Pre-flight checklist | — | ✓ (session 49) | ✓ |
| Manual confirmation flag | — | ✓ (session 47) | ✓ |
| Scaling rule pre-committed | — | ✓ (session 50) | ✓ |
| Halt rule pre-committed | — | ✓ (session 50) | ✓ |
| Behavioural readiness | unknown | observed in window | observed |
| Operational runbook | — | ✓ (session 50) | ✓ |
| Daily broker reconciliation | — | ✓ (session 47) | ✓ |
| NTP time-sync check | — | ✓ (session 47) | ✓ |
| Failover behaviour defined | — | ✓ (session 47–48) | ✓ |

By session 50, every "Required for live" cell is ✓. Earlier than that, no.

---

## What we are NOT promising

- That the strategy will be profitable in live trading. The platform makes
  decisions defensible; markets decide outcomes.
- That session 50 is the end of the project. It is the start of live. The
  ongoing operations through session 55+ are the actual job.
- That ML or pairs work happens before session 55. Both are deferred.
- That live capital is a "graduation." It is a state the project enters
  with explicit halt rules, scaling rules, and the discipline to honor
  both.

## What we ARE promising

- A path from end-of-session-38 to first live trade that takes ~38 calendar
  days (30 paper window + ~8 working days for live readiness, plumbing,
  drill, and first trade).
- Every step is gated. Skipping a gate halts the path.
- Three personas have signed off on this path in writing (the round-2
  reviews).
- Each session in the path has a per-model spec ready to dispatch.

The platform you'll have at session 50 is a working live-trading system
on small size with a documented expansion path. That's "production-ready
for live small money trading" in the operational sense Ibby asked about.
It is not "set it and forget it" — no quant trading system is. It is
"runnable as a routine business" — which is what was asked for.
