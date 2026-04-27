═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           35a-sonnet
Required model:    Sonnet 4.6
Effort:            L (~4 hr)
Entry blocked by:  34b (DONE), D1, D2, D3, D4 (all DONE)
Hand off to:       35b-opus
Branch:            session-35-paper-loop
═══════════════════════════════════════════════════════════════

# 35a — End-to-end paper-trading loop wiring

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 34b DONE (Branch 1 or 2).
- [ ] D1–D4 all DONE.

## What you implement

The pipeline:
```
generate_signals → LossLimitMonitor (D1) → size_position → Mulligan check
  → Order idempotency (D3) → Broker.submit_order → Heartbeat (D2)
  → Fill listener → Reconciler (D3) → Trade-log writer → Daily report
```

### Files
- `src/trading_research/execution/paper_loop.py` — orchestrator.
- `src/trading_research/execution/trade_log_writer.py` — JSON-line trade log with both live and shadow-backtest fields per trade.
- `src/trading_research/execution/daily_report.py` — EOD HTML summary.
- `tests/execution/test_paper_loop_integration.py` — fixture-based end-to-end test.

### Critical requirements
- **Featureset hash check at startup AND on every parquet swap.** Mismatch = HARD HALT.
- **Trade-by-trade live + shadow-backtest record.** Per architect S10, DS divergence requirement.
- **Engine fingerprint logged on session start.** Cohort consistency across paper days.

## Acceptance
- [ ] End-to-end fixture test passes.
- [ ] Featureset hash mismatch produces hard halt + alert.
- [ ] Per-trade live + shadow records exist.
- [ ] Daily report HTML generates without error on fixture.
- [ ] Engine fingerprint stamped at session start.
- [ ] Handoff: `docs/execution/handoffs/35a-handoff.md`.
- [ ] current-state.md: 35a → DONE; 35b → READY.

## What you must NOT do
- Place real orders. SIM only.
- Skip featureset hash check.
- Aggregate-only trade log (must be per-trade).

## References
- Architect §7 featureset hash.
- DS per-trade granularity requirement.
- Original spec §35a.
