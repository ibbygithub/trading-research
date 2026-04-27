═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           34b-sonnet
Required model:    Sonnet 4.6
Effort:            L (~4 hr)
Entry blocked by:  34a (DONE)
Parallel-OK with:  F3
Hand off to:       35a-sonnet
Branch:            session-34-bridge-pick
═══════════════════════════════════════════════════════════════

# 34b — Bridge implementation

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 34a DONE; branch chosen in `34a-bridge-decision.md`.
- [ ] Track D fully complete (D1–D4 all DONE).

## What you implement (depends on 34a branch)

### Branch 1 — TS SIM (E1)
- `src/trading_research/execution/broker.py` — abstract `Broker` Protocol.
- `src/trading_research/execution/tradestation_sim.py` — auth, order submission, fill subscription, account sync.
- `tests/execution/test_tradestation_sim.py` — fixture-based integration test.
- Featureset hash check on data-load path.

### Branch 2 — TV Pine port (E1')
- `external/tradingview/vwap-reversion-v1.pine` — strategy in Pine.
- `tests/external/test_pine_python_parity.py` — Pine vs Python within ±0.5 tick.
- `src/trading_research/execution/tradingview.py` — daily TV trade-log parser.

### Branch 3 — Pivot
Sprint 34 ends here. Sprint 35 reroutes per addendum from 34a.

## Acceptance
- [ ] Branch 1: integration test passes against fixture.
- [ ] Branch 2: parity test passes; TV log parser handles real TV exports.
- [ ] Branch 3: this sprint complete (no implementation).
- [ ] Featureset hash check active (Branch 1/2).
- [ ] Handoff: `docs/execution/handoffs/34b-handoff.md`.
- [ ] current-state.md: 34b → DONE; 35a → READY.

## What you must NOT do
- Place real orders. SIM only or fixture only.
- Build LIVE-mode plumbing (that's session 47).

## References
- 34a decision file.
- Original spec branches.
