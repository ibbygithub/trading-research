═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           29b-sonnet
Required model:    Sonnet 4.6
Required harness:  Claude Code
Phase:             1 (hardening)
Effort:            M (~3 hr Sonnet time)
Entry blocked by:  29a (DONE)
Parallel-OK with:  D1 (different files entirely)
Hand off to:       29c-sonnet (next on this branch); 29d-gemini (parallel)
Branch:            session-29-strategy-foundation (continue 29a's branch)
═══════════════════════════════════════════════════════════════

# 29b — Walkforward retrofit + `vwap-reversion-v1` template

## Self-check

- [ ] I am Sonnet 4.6. (If not, halt and emit MISROUTE.)
- [ ] 29a is DONE per `docs/execution/handoffs/current-state.md`.
- [ ] `docs/execution/handoffs/29a-handoff.md` exists; I have read it.
- [ ] The four contract test stubs from 29a exist and currently SKIP.
- [ ] I am on branch `session-29-strategy-foundation`.

## What you implement

### 1. New strategy module: `src/trading_research/strategies/vwap_reversion_v1.py`

Implement the Strategy Protocol. Class `VWAPReversionV1`. Pydantic knobs
model `VWAPReversionV1Knobs` exactly as specified in the original session
spec ([`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
sub-sprint 29b section).

Key knob defaults (mentor-corrected):
- `entry_threshold_atr: 2.2` (NOT 1.5)
- `entry_blackout_minutes_after_session_open: 60`
- `flatten_offset_minutes_before_settlement: 0` (use instrument settlement time)
- All other knobs as in the original spec

`generate_signals`:
- Enter when `vwap_spread / atr` exceeds `entry_threshold_atr`.
- Only within entry window AND outside after-open blackout AND outside any
  release blackout.
- Signal direction = sign of vwap_spread overshoot.
- Each Signal carries `metadata={"vwap_spread_z": ..., "regime": "..."}`.

`size_position`:
- Vol-targeting per CLAUDE.md default.
- Use `instrument.contract_multiplier` and `context.account_equity`.
- Return 0 if computed size < 1.

`exit_rules`:
- Take profit at `exit_target_atr` band.
- Stop at `stop_loss_atr`.
- Max hold at `max_hold_bars`.
- Hard flatten at instrument settlement time minus `flatten_offset_minutes_before_settlement`.
- Settlement time read from `instrument.session_schedule`.

Register via `@register_template(...)` decorator with:
- `name="vwap-reversion-v1"`
- `human_description="Intraday VWAP mean reversion with extended hold window."`
- `supported_instruments=["6E"]`
- `supported_timeframes=["5m", "15m"]`

### 2. Walkforward retrofit: `src/trading_research/backtest/walkforward.py`

Add `template:` field handling. If config YAML has a `template:` field:
```python
from trading_research.core.templates import _GLOBAL_REGISTRY
# Make sure strategy modules are imported so templates are registered.
import trading_research.strategies.vwap_reversion_v1  # noqa: F401
strategy = _GLOBAL_REGISTRY.instantiate(cfg["template"], cfg["knobs"])
signals_df = generate_signals_via_strategy(strategy, bars, features, instrument)
```

Otherwise fall back to existing `signal_module:` dynamic-import path. Existing
ZN strategies (which use `signal_module:`) must continue to work unchanged.

### 3. Strategy config: `configs/strategies/6e-vwap-reversion-v1.yaml`

Use exactly the YAML in the original session spec. Verify on save:
- `template: vwap-reversion-v1`
- `symbol: 6E`
- `timeframe: 5m`
- `feature_set: base-v1`
- `backtest.start_date: "2018-01-01"`, `end_date: "2024-12-31"`

### 4. Implement contract test from 29a

`tests/contracts/test_walkforward_uses_registry.py` — replace the
`pytest.skip(...)` body with real assertions. Tests must pass.

### 5. Strategy unit tests: `tests/strategies/test_vwap_reversion_v1.py`

- `test_no_signals_before_entry_window`
- `test_blackout_after_session_open`
- `test_signal_direction_matches_overshoot_sign`
- `test_signal_metadata_present` (vwap_spread_z and regime keys)

## Acceptance checks (must all pass)

- [ ] `tests/contracts/test_walkforward_uses_registry.py` passes (no skip).
- [ ] `tests/strategies/test_vwap_reversion_v1.py` passes.
- [ ] `uv run pytest` full suite green.
- [ ] Existing ZN strategy tests still pass (legacy `signal_module:` path works).
- [ ] No new hardcodings (no symbol strings in `vwap_reversion_v1.py` other
      than as defaults / metadata).
- [ ] Handoff: `docs/execution/handoffs/29b-handoff.md` written.
- [ ] `current-state.md` updated: 29b → DONE.

## What you must NOT do

- Wire `Strategy.size_position` into the BacktestEngine. That is 29c. The
  `vwap-reversion-v1.size_position` method exists, but the engine calling
  it is 29c's job.
- Migrate OU bounds. That is 29d.
- Touch `core/strategies.py` (29a already updated the docstring).
- Add new knobs beyond what the original spec lists.
- Delete the legacy `signal_module:` path. That decommissioning is sprint
  F-track work, not 29b.

## References

- 29a handoff: [`../../handoffs/29a-handoff.md`](../../handoffs/29a-handoff.md)
- Original session 29 spec: [`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
- Mentor's knob-default corrections: [`outputs/planning/peer-reviews/quant-mentor-review.md`](../../../../outputs/planning/peer-reviews/quant-mentor-review.md) §1, §2, §3
- Multi-model handoff protocol: [`../../policies/multi-model-handoff-protocol.md`](../../policies/multi-model-handoff-protocol.md)
