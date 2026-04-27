═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           29c-sonnet
Required model:    Sonnet 4.6
Required harness:  Claude Code
Phase:             1 (hardening)
Effort:            M (~3 hr Sonnet time)
Entry blocked by:  29a (DONE), 29b (DONE)
Parallel-OK with:  29d (Gemini, different files entirely)
Hand off to:       30a (after 29d also DONE)
Branch:            session-29-strategy-foundation (continue)
═══════════════════════════════════════════════════════════════

# 29c — Wire `Strategy.size_position` into BacktestEngine

## Self-check

- [ ] I am Sonnet 4.6.
- [ ] 29a, 29b are DONE.
- [ ] `vwap-reversion-v1` is registered and `vwap_reversion_v1.size_position` exists.

## What you implement

### 1. `src/trading_research/backtest/engine.py`

Modify `BacktestEngine` so that for every entry signal:

- If a `Strategy` instance is available (provided in engine construction or
  passed alongside signals), call `strategy.size_position(signal, context, instrument)`
  to determine size.
- Build a `PortfolioContext` from current engine state:
  - `open_positions`: list of currently-open `Position` objects.
  - `account_equity`: current equity (starting equity + realised P&L).
  - `daily_pnl`: today's realised P&L (resets at session boundary).
- If returned size is 0, suppress the trade (log it, do not place an order).
- If `size_position` raises, propagate (do NOT silently fall back to `quantity`).
- If no Strategy instance is provided, fall back to `BacktestConfig.quantity`
  (legacy path; existing ZN tests rely on this).

### 2. `src/trading_research/backtest/walkforward.py`

When `template:` path is used, pass the instantiated Strategy to the
BacktestEngine. Existing legacy path keeps using `quantity`.

### 3. Implement contract test from 29a

`tests/contracts/test_engine_uses_size_position.py` — replace skip body
with real assertions. Required test cases:
- Synthetic Strategy returns deterministic size N → engine uses N.
- Synthetic Strategy returns 0 → trade suppressed.
- Synthetic Strategy raises → exception propagates.
- No Strategy provided + `quantity=3` in config → engine uses 3 (legacy).

### 4. Update existing engine tests

Some existing tests construct `BacktestEngine(bt_config, instrument)` without
a Strategy. These continue to work via the legacy `quantity` fallback. Verify
each is intentional (legacy ZN path); add a comment noting the legacy path
where applicable.

## Acceptance checks

- [ ] `tests/contracts/test_engine_uses_size_position.py` passes (all four cases).
- [ ] `uv run pytest tests/test_engine.py` passes (existing tests still work).
- [ ] `uv run pytest tests/test_strategy_zn_macd_pullback.py` and
      `tests/test_strategy_zn_vwap_reversion.py` pass (legacy path).
- [ ] `uv run pytest` full suite green.
- [ ] Handoff: `docs/execution/handoffs/29c-handoff.md` written.
- [ ] `current-state.md` updated: 29c → DONE.

## What you must NOT do

- Remove `BacktestConfig.quantity`. It remains as fallback.
- Modify the Strategy Protocol.
- Migrate OU bounds (29d).
- Change strategy logic in `vwap_reversion_v1.py`.

## References

- 29a, 29b handoff files in `docs/execution/handoffs/`.
- Architect's review on sizing path: [`outputs/planning/peer-reviews/architect-review.md`](../../../../outputs/planning/peer-reviews/architect-review.md) §2.
- Original session 29 spec sub-sprint 29c: [`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
