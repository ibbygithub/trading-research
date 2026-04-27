# Session 34 — Paper-trading bridge: option pick + E1 begin

**Status:** Spec — branches based on sprint 33 verdict
**Effort:** 1 day, two sub-sprints (S+L)
**Depends on:** Sprint 33 gate (PASS or pre-committed escape path)
**Unblocks:** Sprint 35 (paper-trading loop)
**Personas required:** Mentor (option pick), Architect (interface contract)

## Goal

After sprint 33's verdict, route to one of three execution paths and begin
implementation. The decision rule is pre-committed at sprint 33 (see
`session-33-track-c-gate.md`); 34a applies the rule, does not invent it.

## The three branches

### Branch 1 — Sprint 33 PASS → E1 (TradeStation SIM)

| Sub | Model | Workload |
|---|---|---|
| 34a | Opus 4.7 | Pick E1 vs E1' using **TS SIM API maturity check** + June 30 calendar slack. If TS SIM has known limitations against `vwap-reversion-v1`'s order types (limit + bracket), prefer E1'. Sign-off in writing. |
| 34b | Sonnet 4.6 | TS SIM API integration: order submission, fill retrieval, account state sync. Featureset hash check on data-load path is in scope. Integration test against recorded fixture. |

**E1 deliverables (34b):**
- `src/trading_research/execution/tradestation_sim.py` — auth, order
  submission, fill subscription, account sync.
- `src/trading_research/execution/broker.py` — abstract `Broker` Protocol;
  TS SIM is the first concrete implementation.
- `tests/execution/test_tradestation_sim.py` — fixture-based integration test;
  fixtures captured from a real SIM account session and committed.
- Featureset hash mismatch check on data-load (architect's S10).

### Branch 2 — Sprint 33 FAIL with cost concern → E1' (TradingView Pine port)

| Sub | Model | Workload |
|---|---|---|
| 34a | Opus 4.7 | Confirm Pine path; estimate port effort (Mulligan logic in Pine is non-trivial); commit calendar to E1'+E2'+E3' across sprints 34–36. |
| 34b | Sonnet 4.6 + Ibby pair | Pine port skeleton; validate Pine backtest matches Python backtest within tolerance on a 6-month sample window. |

**E1' deliverables (34b):**
- `external/tradingview/vwap-reversion-v1.pine` — strategy ported to Pine.
- `tests/external/test_pine_python_parity.py` — runs Python backtest on a
  fixed window, parses TV-exported trade log for the same window, asserts
  trade count matches and per-trade P&L matches within ±0.5 tick.
- `src/trading_research/execution/tradingview.py` — daily TV trade-log parser.

### Branch 3 — Sprint 33 FAIL → pivot (6A/6C OR strategy class change)

| Sub | Model | Workload |
|---|---|---|
| 34a | Opus 4.7 | Apply pre-committed pivot rule from sprint 33b verdict. **6A/6C path:** new instrument pipeline (already free under Track A); spec for sprint 35 changes to "6A/6C v1 backtest." **Class change path:** session 28 stationarity follow-up picks momentum or breakout; new strategy template designed in sprint 35. |
| 34b | (varies) | Sprint 34 ends here. Sprint 35 reroutes; 36/37/38 may compress or expand. |

**Pivot deliverables (34a):**
- Updated plan v2 addendum: sprints 35–38 reflowed for the pivot path.
- New session-35 spec (replaces existing).
- Persona sign-off recorded.

## Cross-branch acceptance

- [ ] 34a verdict committed (which branch + reasoning + persona sign-off).
- [ ] If branch 1 or 2: integration test passes against recorded fixture.
- [ ] If branch 3: plan addendum and new sprint-35 spec committed.

## Out of scope

- Live capital (Track I).
- Multi-strategy execution (single strategy on bridge for now).
- Real-time monitoring UI (sprint 38).

## References

- `docs/roadmap/session-specs/session-33-track-c-gate.md` (gate verdict drives this)
- `outputs/planning/sprints-29-38-plan-v2.md`
- TradeStation API docs (when 34b begins, link in work log)
