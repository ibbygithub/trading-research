# Product Roadmap to Live Trading
Date: 2026-04-26
Owner: All three personas
Covers: Sessions 39–55 (Phase 2 of the master execution plan)

This is the plan you (Ibby) asked for: the path from "paper-trading platform
done" (end of session 38) to "first micro-contract live trade and beyond." It
exists because the original sessions-23-50 roadmap stopped at "Track I — live
execution, sessions 48–50" with three rows and no detail. After running the
round-2 peer reviews against that void, the personas concluded the gap was
real and could not be closed at execution time.

---

## Where we are at end of session 38

(See [`../peer-reviews/round-2-synthesis.md`](../peer-reviews/round-2-synthesis.md) for full
detail.)

- One 6E strategy validated (or escaped to a different path) at sprint 33's
  gate.
- Paper-trading loop running on real-time SIM (or TV).
- 30-day paper discipline window OPEN — likely at calendar day +0 to +5
  depending on when sprint 36 fired vs. wall clock.
- Circuit breakers drilled against fixtures, not yet against real broker
  silence.
- No live broker integration yet (TS SIM is a different API surface than TS
  LIVE).
- No risk-of-ruin calculation tied to actual account size.
- No documented scaling rule for adding contracts.

The platform can validate strategies, run them on paper, and surface
divergence between paper and backtest. It cannot place a live order.

---

## Phase 2A — 30-day paper window operations (sessions 39–44)

**Calendar:** ~30 trading days from sprint 36's first paper trade.
**Cadence:** ~6 sessions across 30 calendar days, mostly weekly reviews.

The strategy runs autonomously (or with manual morning starts). Sessions
during this window are FOR REVIEW AND CLEANUP, not for changes.

### Hard rules during this window
1. **No knob changes.** Any change resets the 30-day clock.
2. **No new strategies bolted on.** The window is for *this* strategy's
   discipline.
3. **Cleanup must not change strategy behaviour.** Telemetry, logs, reports —
   yes. Anything that affects signal generation, sizing, or exits — no.
4. **A losing streak is not a bug.** Don't fix what's working as designed.

### Session 39 — Week-1 paper review (Opus, ~2 hr, calendar day +5)

Inputs: 5 days of paper trade logs + divergence reports.

Three-persona pass:
- Mentor: is the trade cadence and behaviour matching the backtest? Any
  surprises in market structure?
- Data scientist: per-trade slippage relative to sprint 30 cost-model bounds.
  Is the divergence stable or trending?
- Architect: any new failure modes observed? Heartbeat false-positive rate?

Output: `runs/paper-trading/<strategy>/week-1-review.md`. Contains either
"continue clean" or a specific list of items to address in session 40.

### Session 40 — Mid-window cleanup IF needed (Sonnet, conditional)

Run only if session 39 surfaced items. Otherwise skip.

Cleanup items must be telemetry, logging, reporting, or polish. **Anything
that touches signal generation triggers a "window restart" decision** —
escalate to Ibby for explicit go/no-go.

### Session 41 — Week-2 paper review (Opus, ~2 hr, calendar day +12)

Same shape as session 39 with two-week dataset. Particular attention:

- DSR computed on observed paper trades (a new cohort of N trades vs. the
  backtest cohort). Is the live cohort's DSR within the bootstrap CI from
  sprint 33?
- Has Ibby personally watched a drawdown without overriding? Mentor explicit
  question.

### Session 42 — Mid-window cost-model recalibration IF needed (Sonnet, conditional)

If session 41 found the realised slippage outside sprint 30's cost-model
bounds, this session updates the cost model in the trial registry's
*evaluation* tooling — NOT in the running strategy. The strategy continues
with original parameters; the *retrospective* analysis uses corrected costs.

Output: updated cost-model fixture; sprint 33 gate-criterion G6 re-evaluated
against new fixture; either confirms the strategy still passes or surfaces a
finding for sprint 44.

### Session 43 — Week-3 paper review (Opus, ~2 hr, calendar day +19)

Same shape as session 41.

### Session 44 — End-of-window evaluation (Opus + Sonnet, ~3 hr, calendar day +30)

The big one. After 30 calendar days (≈22 trading days), the strategy has
run continuously. Now:

**Sonnet:** generate a comprehensive 30-day paper-trading report:
- Equity curve.
- Trade-by-trade live-vs-shadow-backtest divergence statistics.
- Realised Calmar, Sharpe, max consecutive losses, drawdown duration, with
  bootstrap CIs.
- Comparison against sprint 33 backtest CIs: where did paper land?
- Featureset hash drift incidents (should be zero).
- Heartbeat firings (false positives count).

**Opus:** three-persona evaluation:
- Mentor: did Ibby psychologically handle the worst drawdown? Do the
  behavioural metrics support running this with real money?
- Data scientist: is the realised performance inside sprint 33's CI? If not,
  in which direction and is there a structural reason?
- Architect: any operational surprises? Any near-misses with circuit
  breakers? Any data feed gaps?

Output: `30-day-window-evaluation.md`. Verdict: PROCEED / EXTEND / HALT.

---

## Phase 2B — Live readiness gate (sessions 45–46)

### Session 45 — Live readiness gate (Opus, ~3 hr)

This is where 30 days of paper plus the platform readiness meet. The verdict
of session 44 must be PROCEED for this session to start.

**Three-persona verdict required, all three must sign READY.**

Gate criteria (all must pass):

| # | Criterion | Persona |
|---|---|---|
| L1 | 30-day paper window completed without restart | Mentor + DS |
| L2 | Realised Calmar's bootstrap CI lower bound > 1.0 (live, not backtest) | DS |
| L3 | Live-vs-backtest divergence is within tolerance defined at sprint 36 | DS |
| L4 | Realised max consecutive losses ≤ 8 (was the 33b gate) | Mentor |
| L5 | Ibby has personally watched at least one full drawdown to recovery without overriding | Mentor |
| L6 | All circuit breakers fired correctly when triggered (or were never triggered) | Architect |
| L7 | Featureset hash zero-drift over 30 days | Architect |
| L8 | Risk-of-ruin (session 46) explicitly computed and acceptable | DS |
| L9 | First-live-trade size determined and committed (session 46) | Mentor + DS |

If any criterion fails: cycle returns to 39–44 with a documented remediation.
A failed criterion is not a "ship anyway" item.

### Session 46 — Risk-of-ruin + first-live-trade size (Opus + Ibby, ~2 hr)

**Risk-of-ruin (DS):**
Compute, given:
- Account equity (Ibby specifies).
- Strategy expectancy (from session 44 paper data).
- Strategy variance (from session 44 paper data).
- Position size (the question).

The probability of hitting -X% drawdown before reaching +Y% gain. Standard
Kelly-fraction analysis with a sub-Kelly haircut (0.25× Kelly is the
default — full Kelly is for someone with infinite emotional bandwidth).

**First-live-trade size (Mentor):**
- Default: 1 micro contract (M6E), full stop.
- Justification: live execution may surface bugs the paper loop did not
  catch. The first trade is a *system test*, not a *return engine*.
- Scaling rule pre-committed: see session 50.

Outputs:
- `risk-of-ruin-analysis.md` with calculation and committed first-trade size.
- A signed-by-Ibby commitment: "first live trade is 1 micro M6E contract;
  scaling requires session 50's rule."

---

## Phase 2C — Live execution plumbing + drill (sessions 47–48)

### Session 47 — TS LIVE API integration (Sonnet, ~4 hr)

TS LIVE is a different API surface than TS SIM:
- Different auth flow (real credentials, real OAuth scope).
- Real money endpoints.
- Margin checks against real account state.
- Settlement mechanics.

**Outputs:**
- `src/trading_research/execution/tradestation_live.py` — concrete
  implementation of the `Broker` Protocol against TS LIVE.
- `src/trading_research/execution/preflight.py` — checks before any live
  order:
  - Account state matches expected.
  - Available margin > order's required margin × safety factor (2× minimum).
  - Featureset hash matches strategy's expected.
  - All circuit breakers ARMED (not tripped).
  - Time-of-day is within allowed live-trading window.
  - Manual confirmation flag is present in config (see session 49 detail).
- `tests/execution/test_tradestation_live_paper_mode.py` — runs the LIVE
  client in paper-mode against TS to verify auth + endpoints, no real orders.

**What it must NOT do:** place any real orders. Session 47 is plumbing only.

### Session 48 — Kill-switch DRILL against real broker (Sonnet + Opus mid, ~3 hr)

Run every circuit breaker drill from D1–D4 against a real (paper-mode-flagged)
TS LIVE account session:

- **Heartbeat:** simulate API silence; auto-flatten fires; verify the
  flatten order would be the right shape (does NOT actually submit).
- **Loss limit:** simulate trade fills that would breach the daily limit;
  verify halt fires.
- **Idempotency:** submit the same order ID twice; verify second is rejected.
- **Account-level kill switch:** verify it disarms the entire system on
  command.

Outputs:
- `kill-switch-drill-report.md` with per-drill results.
- Opus mid-session review: any surprises in real-broker behaviour vs. SIM
  fixtures?

If any drill fails: session 48 repeats; live trade does NOT happen until
all drills pass.

---

## Phase 2D — First live trade + scaling (sessions 49–50)

### Session 49 — FIRST LIVE MICRO-CONTRACT TRADE (Opus + Ibby together)

This is the first session where real money moves.

**Pre-flight checklist (read aloud, confirmed by Ibby):**

```
[ ] Account equity confirmed: $______________
[ ] First-trade size committed at session 46: 1 micro M6E
[ ] Risk-of-ruin at this size: ______________% (acceptable per session 46)
[ ] All circuit breakers ARMED
[ ] Heartbeat green
[ ] Featureset hash matches
[ ] Strategy unchanged from sprint 33-validated state
[ ] 30-day paper window completed: yes / no — if no, HALT
[ ] Ibby has reviewed the most recent paper trade: yes / no — if no, do that first
[ ] London/NY overlap is open or about to open: ___ UTC
[ ] No major economic release in the next 60 minutes
[ ] Manual confirmation flag set in execution config
[ ] Ibby's emotional readiness self-report: ready / nervous / not today
```

If any checkbox fails: HALT. Do not place the trade. Reschedule.

If all pass: arm the system, wait for the first signal, observe one trade
end-to-end. Whether it wins or loses is irrelevant — the success criterion
is *the trade happened correctly*.

**Outputs:**
- `runs/live/<strategy>/first-trade-record.md`:
  - Pre-flight checklist signed.
  - Signal timestamp, signal strength, expected entry per backtest model.
  - Submitted order ID, fill timestamp, fill price.
  - Slippage observed.
  - Exit timestamp, exit price.
  - Realised P&L (in dollars and ticks).
  - Comparison to what the paper-trading shadow would have shown.
- After-action: Opus three-persona pass. Did anything surprise us? Any
  near-miss with a circuit breaker? Any clock drift?

**Then: stop trading for the day.** Do not place a second live trade
until session 50 evaluates the first.

### Session 50 — Post-first-trade review + scaling rule (Opus, ~2 hr)

Three-persona evaluation of the first live trade. Then:

**The scaling rule (mentor's pre-commitment):**
- After 1 successful trade with no operational issues: continue at 1 contract
  for the next 5 trading days.
- After 5 consecutive trading days at 1 contract with no operational issues:
  scale to 2 contracts.
- After 10 consecutive trading days at 2 contracts: scale to a number
  determined by re-running the risk-of-ruin calc with the larger sample.
- Any operational issue (broker silence, circuit breaker firing, fill
  surprise, account state mismatch): scale RESETS to 1.

This rule is committed before any scaling discussion happens. It is not
revisable mid-stream without a full session-50-style review.

**Outputs:**
- `scaling-rule.md` (this rule, formalised).
- Decision: continue at 1 contract through next 5 trading days; reconvene
  at session 50+5.

---

## Phase 2E — Multi-strategy expansion (sessions 51–55)

By the time session 51 begins, we have 5+ live trading days on 6E with
small size. Now begin work on a second strategy without disrupting the live
one.

### Sessions 51–52 — Second strategy on 6A or 6C in paper (Sonnet)

The instrument decision depends on session 33's escape verdict (if 33 forced
a pivot, this work may have already begun). Otherwise:

- Add 6A or 6C to instrument registry (already free under Track A).
- Re-run sprint 28's stationarity analysis on the new instrument.
- If stationary: register a `vwap-reversion-v2` template tuned for the new
  instrument.
- Run sprint 30-equivalent backtest with cost sensitivity.

The 6E strategy continues live throughout. No interference.

### Session 53 — Second-strategy paper review (Opus, ~2 hr)

Three-persona pass on the second-strategy backtest. Decision: open a
30-day paper window for it, or iterate first.

### Session 54 — Second-strategy live promotion (Sonnet)

After the second strategy clears its own 30-day paper window (so this is
really session "54 + 30 calendar days"), promote it to live with the
session-49-equivalent first-live-trade flow.

The 6E strategy continues at its current scaled size.

### Session 55 — Multi-strategy operations + decision point (Opus, ~3 hr)

We now have two strategies running live. Decision point on what's next:

- **Track G (ML capability):** meta-labeling on 6E rule-based strategy. Now
  defensible because we have ≥6 weeks of live trade data.
- **Track H (pairs):** 6A/6C correlation-based pairs strategy. Defensible
  because both single-instrument strategies are validated.
- **Stay simple:** continue running both strategies, scale gradually,
  defer ML and pairs.

This decision is Ibby's. The plan supports any of the three.

---

## What this roadmap does NOT cover

By design, sessions 56+ are not yet planned at this fidelity. After session
55 the path forks based on actual experience. The current intent:

- Sessions 56–60: depending on session 55 decision, ML capability OR pairs
  framework.
- Sessions 61–65: third instrument; portfolio-level position sizing across
  three strategies.
- Sessions 66+: further expansion and operational maturity.

Live capital + 5 weeks of evidence + a working multi-strategy platform is
the natural plateau for this plan. Anything beyond is gravy.

---

## Risks specific to Phase 2

(Rolls into [`risk-register.md`](risk-register.md) on next update.)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 30-day paper window observed performance diverges from backtest beyond CI | Medium | High | Session 42 cost-model recalibration; session 44 evaluation gates Phase 2B |
| Ibby psychologically can't sit through a drawdown | Medium | Critical | Session 41/43 mentor review; if observed, HALT and reconsider |
| TS LIVE API has features SIM doesn't (or vice versa) | Medium | Medium | Session 47 plumbing + session 48 drill catches these before money moves |
| First live trade has unexpected slippage > paper | High | Medium | Session 50 scaling rule prevents premature size increase; one trade ≠ pattern |
| Account-state reconciliation mismatch on day 1 live | Low | Critical | Pre-flight checklist; preflight.py runs every order |
| Real broker behaviour during outage differs from drilled fixtures | Medium | High | Session 48 drills against real broker silence specifically; if undrillable, escalate |
| Second strategy interferes with first via shared engine state | Low | High | Multi-strategy execution kept out of scope until session 54; until then, single-strategy path |

---

## What "production ready for live small money trading" means in this plan

Operational definition (Ibby's words from the prompt, formalised):

A platform is production-ready for live small money trading when ALL are
true:

1. ≥30 trading days of paper evidence on the strategy in question, with
   realised metrics inside backtest CIs.
2. Live execution plumbing exists (TS LIVE API), tested in paper mode, and
   drilled against real-broker conditions for every circuit breaker.
3. Risk-of-ruin computed for the chosen first-trade size and accepted by
   Ibby in writing.
4. First-trade size is small (1 micro contract default).
5. Pre-flight checklist runs before every live session start.
6. Manual confirmation flag is required to enable live trading; flag is
   off by default.
7. Scaling rule is pre-committed; scaling is not negotiable mid-stream.
8. Behavioural readiness confirmed: Ibby has personally watched at least
   one paper drawdown to recovery without overriding.
9. Recovery and rollback procedures documented (what to do when X breaks).
10. Account-state reconciliation runs daily; any mismatch is a HALT, not
    a "look at it later."

The platform reaches this state at session 49, by design, and not earlier.
Earlier proceeding violates one or more of the above.
