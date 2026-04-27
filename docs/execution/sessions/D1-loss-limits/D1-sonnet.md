═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           D1-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  Track A complete (session 28)
Parallel-OK with:  29b, 29c
Hand off to:       D2-sonnet
Branch:            session-D1-loss-limits
═══════════════════════════════════════════════════════════════

# D1 — LossLimitMonitor + LimitBreach

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] Track A complete.

## What you implement

Per [`../../../roadmap/session-specs/track-D-circuit-breakers.md`](../../../roadmap/session-specs/track-D-circuit-breakers.md) §D1 PLUS plan-v2 alignment:

- `src/trading_research/risk/loss_limits.py`:
  - `LossLimitConfig` Pydantic model.
  - `LossLimitMonitor` class.
  - `LimitBreach` dataclass.
- `configs/risk/loss-limits.yaml` — defaults.
- Tests under `tests/risk/`.

**Plan-v2 alignment:** D1 consumes sized P&L from sprint 29c's `Strategy.size_position` path, NOT hardcoded `BacktestConfig.quantity`. If 29c is not yet DONE, the monitor accepts a per-trade P&L parameter and the integration with sized P&L is wired in 29c's branch.

## Acceptance
- [ ] Synthetic trade log breaching daily limit produces `LimitBreach` event.
- [ ] Halt prevents further entries within configured window.
- [ ] Tests pass.
- [ ] Handoff: `docs/execution/handoffs/D1-handoff.md`.
- [ ] current-state.md: D1 → DONE; D2 → READY.

## What you must NOT do
- Implement heartbeat (D2).
- Implement idempotency (D3).
- Implement kill switches (D4).

## References
- Track D spec + alignment doc.
