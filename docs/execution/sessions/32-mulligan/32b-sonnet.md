═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           32b-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  32a (DONE)
Parallel-OK with:  D4, F2
Hand off to:       33a-sonnet
Branch:            session-32-mulligan
═══════════════════════════════════════════════════════════════

# 32b — Mulligan implementation + tests

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 32a DONE; `mulligan-spec.md` and stub tests exist.

## What you implement

### 1. `src/trading_research/strategies/mulligan.py`
- `MulliganController` class. Holds reference to position's last consumed Signal timestamp; rejects scale-in unless strictly-later Signal of same direction is presented.
- `combined_risk(orig: Position, new_entry_price, knobs) -> (stop, target)`.
- `MulliganViolation` exception.

### 2. `src/trading_research/backtest/engine.py`
- When `Strategy.exit_rules` returns `ExitDecision(action="scale_in", ...)`,
  engine consults `MulliganController`. Consult-fail → `MulliganViolation` raised, trade rejected, logged.

### 3. `vwap-reversion-v1` template knobs
Add:
- `mulligan_enabled: bool = False`
- `mulligan_n_atr: float = 0.3` (directional gate)
- `mulligan_max_scale_ins: int = 1`

### 4. Test bodies
Replace `pytest.skip(...)` in `tests/contracts/test_mulligan_freshness.py` with real assertions per 32a's described cases.

### 5. Walk-forward run with mulligan_enabled=True
Single trial recorded with `mulligan_enabled=True` for sprint 33's combined v2 evaluation.

## Acceptance
- [ ] All 6 test cases pass.
- [ ] `MulliganController.last_consumed_ts` is freshness anchor; not mutable from strategy code.
- [ ] Strategy Protocol docstring rule from 29a is enforced by engine.
- [ ] Trial recorded.
- [ ] `uv run pytest` full suite green.
- [ ] Handoff: `docs/execution/handoffs/32b-handoff.md`.
- [ ] current-state.md: 32b → DONE; 33a → READY.

## What you must NOT do
- Allow `mulligan_max_scale_ins > 1` (future sprint).
- Implement scale-out (Mulligan exits — future sprint).
- Modify Mulligan rules from 32a's spec.

## References
- 32a's `mulligan-spec.md`.
- Original session 32 spec.
