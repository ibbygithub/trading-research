# Session 35 — End-to-end paper-trading loop

**Status:** Spec — heaviest sprint of the cycle
**Effort:** 1 day, three sub-sprints (L+M+M)
**Depends on:** Sprint 34 (E1 or E1' begun); Track D complete (D1–D4)
**Unblocks:** Sprint 36 (first paper trade)
**Personas required:** Architect (failure-mode review), Data Scientist (per-trade granularity)

## Goal

Wire signal → order → fill → trade-log → daily-report into a single end-to-end
loop that runs against TradeStation SIM (or TV reconciliation, depending on
sprint 34 branch). Every safety mechanism (D1–D4) is on; featureset hash is
verified on every data load; live-vs-backtest divergence is recorded
trade-by-trade.

## In scope

### 35a — End-to-end wiring (Sonnet 4.6, ~4 hr)

**Pipeline:**
```
[Strategy.generate_signals]
       ↓
  [LossLimitMonitor] (D1) — gates new entries
       ↓
  [Strategy.size_position]
       ↓
  [Mulligan check if scale_in]
       ↓
  [Order idempotency layer] (D3) — dedupe
       ↓
  [Broker.submit_order] (E1 = TradeStation SIM, E1' = paper book → TV reconcile)
       ↓
  [Heartbeat monitor] (D2) — kill switch on API silence
       ↓
  [Fill listener] → [Reconciler] (D3) → [Trade-log writer]
       ↓
  [Daily report]
```

**Key requirements (architect S7, S10, T4):**
- **Featureset hash check at startup AND on every parquet swap.** Strategy
  declares its expected `featureset_hash`; loader compares against
  `manifest.featureset_hash`; mismatch → hard halt, no trades.
- **Trade-by-trade live-vs-backtest record.** For every live trade, a parallel
  "what-the-backtest-would-have-done" record is written. This drives sprint
  36's divergence interpretation.
- **Engine fingerprint logged on every paper-trading session start.** Allows
  cohort comparison across paper-trading days.

**Outputs:**
- `src/trading_research/execution/paper_loop.py` — the orchestrator.
- `src/trading_research/execution/trade_log_writer.py` — JSON-line trade log
  with both live and shadow-backtest fields per trade.
- `src/trading_research/execution/daily_report.py` — end-of-day HTML summary.
- `tests/execution/test_paper_loop_integration.py` — end-to-end test against
  fixtures: synthetic signal at T0, mock broker fills at T0+slippage, asserted
  trade-log row, asserted P&L update.

### 35b — Failure-mode review (Opus 4.7, ~2 hr)

**Failure modes to enumerate and design for:**

1. **Duplicate fills.** Broker reports a fill twice (network retry, etc.).
   Reconciler deduplicates by broker fill ID.
2. **Partial fills.** Order for 5 micro contracts fills 3 then later 2.
   Trade-log records both fills; position state is the sum.
3. **Missing fills.** Order submitted, no fill confirmation within T seconds.
   Heartbeat fires; auto-flatten attempts; flag for manual review.
4. **Stale fills (race condition).** Fill arrives after position was already
   flagged exited. Reconciler decides: emergency-flatten the unexpected exposure.
5. **Featureset version drift.** Mid-day parquet rebuild changes the
   `featureset_hash`. Loader's hard-halt fires; trader is alerted; no trades.
6. **Clock drift.** Broker timestamps and local timestamps differ by >1 sec.
   Tradelog writer records both; alerts if drift exceeds 5 sec.
7. **Loss-limit breach during open trade.** D1 fires; D4 kill switch flattens;
   does it conflict with strategy's natural exit? Order: kill switch wins.
8. **Heartbeat false positive.** API silent for 30 sec because nothing
   happened in market. Heartbeat fires unnecessarily; cost is one false-flatten
   per day of low activity. Tradeoff documented.

**Deliverable:** `35b-failure-modes.md` enumerating each failure with:
- Symptom (what does the system see).
- Detection mechanism (which monitor catches it).
- Response (what the loop does).
- Test that exercises it.

### 35c — Implementation of failure-mode tests (Sonnet 4.6, ~2 hr)

**Outputs:**
- `tests/execution/test_failure_modes.py` — one test per failure mode listed
  in 35b.
- Code patches in `paper_loop.py`, `reconciler.py`, etc. to handle any
  failure mode whose test fails initially.

## Acceptance

- [ ] End-to-end fixture test passes (35a).
- [ ] All 8 failure-mode tests pass (35c).
- [ ] Featureset hash mismatch produces hard halt + alert in logs (no trade).
- [ ] Per-trade live + shadow-backtest records exist in trade log.
- [ ] Daily report HTML generates without error on fixture data.
- [ ] Engine fingerprint stamped on session start in logs.

## Out of scope

- Real first paper trade (sprint 36).
- Multi-strategy orchestration (sprint 35 is single-strategy).
- Live capital.
- UI / cockpit (sprint 38).

## References

- `outputs/planning/sprints-29-38-plan-v2.md` sprint 35 row
- `outputs/planning/peer-reviews/architect-review.md` §7
- `docs/roadmap/session-specs/track-D-circuit-breakers.md`
