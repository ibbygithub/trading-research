═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           36a-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  35c (DONE)
Hand off to:       36b-opus
Branch:            session-36-first-paper-trade
═══════════════════════════════════════════════════════════════

# 36a — First-trade scaffolding + reconciliation

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 35a/b/c all DONE; paper loop with failure-mode handling exists.

## What you implement

### Files
- `src/trading_research/execution/daily_reconcile.py` — EOD routine: pair live with shadow trades by `signal_id`; compute per-trade divergence (entry-price diff, exit-price diff, P&L diff).
- `src/trading_research/execution/comparison_report.py` — generates HTML divergence report.
- `runs/paper-trading/<strategy-id>/day-NN/` directory layout: `live-trades.jsonl`, `shadow-backtest-trades.jsonl`, `divergence-report.html`, `equity-curve-day-NN.parquet`.

### Operational requirements
- Fire the paper-trading loop on real-time SIM (or TV) data.
- Capture at least one closed trade.
- Daily P&L reconciles: trade-log sum == broker account-state delta.

## Acceptance
- [ ] At least one closed paper trade with both live and shadow records.
- [ ] Divergence report generates without error.
- [ ] Daily P&L reconciles.
- [ ] Handoff: `docs/execution/handoffs/36a-handoff.md` with first-trade record.
- [ ] current-state.md: 36a → DONE; 36b → READY.

## What you must NOT do
- Skip the daily reconciliation.
- Aggregate-only trade log.

## References
- Original spec §36a.
