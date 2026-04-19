# Track D — Circuit Breakers (Sessions D1–D4)

**Agent fit:** either (Gemini-friendly with close spec adherence)
**Total effort:** 4 sessions, M each (2–4h)
**Depends on:** 23-a (for Instrument model in some checks)
**Unblocks:** E1 (paper trading plumbing), Track I (live execution)
**Runs in parallel with:** Track A (sessions 23–28), Track C (29+)

## Why these live in one document

These four sessions are tightly related and share a conceptual model — a "safety envelope" around any strategy running on the platform. They're presented together so an agent can read the full context, but each session has its own branch, commit, PR, and work log.

## The safety envelope

Every running strategy operates inside three nested safety boundaries:

1. **Strategy-level** — a kill switch for a single strategy. Flip it off, that strategy stops taking new trades, optionally flattens open positions.
2. **Instrument-level** — a kill switch for all strategies on a given instrument. Useful when an instrument's market becomes untradeable (halt, extreme volatility, data feed issue).
3. **Account-level** — a master kill switch. All strategies stop, all positions flatten, no new orders accepted.

On top of the switches are automatic triggers:

- **Max daily drawdown** — if the day's P&L exceeds a configured loss, flip the appropriate level's kill switch.
- **Max weekly drawdown** — same, weekly.
- **Inactivity heartbeat** — if the broker API doesn't respond within N seconds, flip account-level and flatten everything.
- **Order idempotency** — if a signal would produce a duplicate order within a debounce window, it is suppressed.

---

## Session D1 — Max Daily/Weekly Drawdown + Loss Limits

**Agent fit:** either
**Depends on:** 23-a

### Goal

Implement configurable daily and weekly loss limits that, when breached, trigger the appropriate kill-switch level and prevent further trade entries for the defined window.

### In scope

- `src/trading_research/risk/loss_limits.py`:
  - `LossLimitConfig` Pydantic model — `max_daily_dd_usd`, `max_weekly_dd_usd`, `max_daily_dd_pct`, `max_weekly_dd_pct`, `scope` ("strategy" | "instrument" | "account"), `action` ("halt" | "halt_and_flatten").
  - `LossLimitMonitor` class — tracks rolling daily and weekly P&L per scope, evaluates against limits, returns a `LimitBreach` event when exceeded.
  - `LimitBreach` dataclass — `scope`, `level`, `current_pnl`, `limit`, `action_required`, `timestamp`.
- `configs/risk/loss-limits.yaml` — default configuration. Example values:
  ```yaml
  account:
    max_daily_dd_usd: 500
    max_weekly_dd_usd: 1500
    action: halt_and_flatten
  per_instrument:
    "*":
      max_daily_dd_usd: 300
      action: halt
  per_strategy:
    "*":
      max_daily_dd_usd: 200
      action: halt
  ```
- Tests in `tests/risk/test_loss_limits.py`:
  - `test_daily_limit_breach_fires_event`
  - `test_limit_resets_at_session_boundary`
  - `test_weekly_limit_independent_of_daily`
  - `test_pnl_recovery_does_not_reset_breach`
  - `test_multiple_scopes_evaluated_independently`

### Out of scope

- Do NOT wire into the backtest engine yet. D1 is pure monitor logic; wiring is D3 and E1.
- Do NOT build the kill-switch action mechanism (flatten orders, halt new orders). That's D3 and D4.

### Acceptance tests

- [ ] `uv run pytest tests/risk/test_loss_limits.py -v` passes.
- [ ] `uv run pytest` — full suite passes.
- [ ] Loss-limit config loads from YAML, parses into Pydantic model.
- [ ] Synthetic P&L feed triggers correct breach events at correct thresholds.

### Persona review

- **Data scientist: optional** — reviews that loss-limit semantics are well-defined (session boundary, rolling window, FIFO P&L).
- **Architect: required** — module boundaries, config shape, how LossLimitMonitor integrates with the rest of the risk package.
- **Mentor: optional** — sanity check on default values.

---

## Session D2 — Inactivity Heartbeat + Auto-Flatten

**Agent fit:** either
**Depends on:** D1

### Goal

Implement a heartbeat monitor that detects TradeStation API silence and triggers account-level halt + flatten. Works in both paper and live modes.

### In scope

- `src/trading_research/risk/heartbeat.py`:
  - `HeartbeatMonitor` class — takes a "last-seen" timestamp from each API call, fires `HeartbeatLost` event if no call in N seconds.
  - Configurable thresholds: `warning_seconds`, `critical_seconds`, `flatten_seconds`.
  - Graceful interaction with broker API downtime (weekend, maintenance windows) — do not trigger during known closed sessions.
- Integration test harness that simulates API silence and verifies events fire at correct intervals.
- `configs/risk/heartbeat.yaml` — defaults.
- Tests:
  - `test_heartbeat_normal_operation` — calls within threshold, no events.
  - `test_heartbeat_warning_fires`
  - `test_heartbeat_critical_fires`
  - `test_heartbeat_skipped_during_closed_session`
  - `test_heartbeat_reset_on_call_received`

### Out of scope

- Actual TradeStation API integration. This session is monitor + event logic only. Wiring to real API calls is D3/E1.

### Acceptance tests

- [ ] Tests pass.
- [ ] Heartbeat can be driven by a synthetic timestamp feed.
- [ ] Events fire at configured intervals.

### Persona review

- **Architect: required** — module boundaries, event dispatching pattern.

---

## Session D3 — Order Idempotency + Reconciliation Scaffold

**Agent fit:** either
**Depends on:** D2

### Goal

Build the order idempotency layer so a signal cannot produce duplicate orders (within a configured debounce window), and the reconciliation scaffold that compares intended orders to broker-reported orders.

### In scope

- `src/trading_research/risk/idempotency.py`:
  - `IdempotencyKey` — deterministic hash of (strategy_name, instrument, signal_timestamp, direction). Same inputs always produce the same key.
  - `IdempotencyStore` — tracks keys seen within the debounce window; rejects duplicates.
  - `OrderIntent` dataclass — what the strategy *wants* to happen.
- `src/trading_research/risk/reconciliation.py`:
  - `OrderReconciler` — compares `OrderIntent` list to broker-reported order list, flags mismatches (intended but not filled, filled but not intended, fill price far from expected).
  - `ReconciliationReport` dataclass.
- Tests:
  - `test_duplicate_order_intent_rejected`
  - `test_same_strategy_different_signal_time_allowed`
  - `test_reconciliation_clean_match`
  - `test_reconciliation_missing_fill_flagged`
  - `test_reconciliation_unexpected_fill_flagged`
  - `test_reconciliation_price_drift_flagged`

### Out of scope

- Real broker integration. Use mocked broker responses.

### Acceptance tests

- [ ] Tests pass.
- [ ] Two identical signals 1ms apart produce one order; 5 minutes apart produce two.

### Persona review

- **Architect: required** — idempotency key design, reconciliation semantics.
- **Data scientist: optional** — reviews that reconciliation mismatches can feed into slippage calibration later.

---

## Session D4 — Kill Switch Hierarchy

**Agent fit:** either
**Depends on:** D1, D2, D3

### Goal

Wire the three kill-switch levels (strategy / instrument / account) into a single `KillSwitchRegistry` that strategies, order submission, and the monitor systems consult before acting. Cascade logic: account-level overrides all; instrument-level overrides per-strategy; per-strategy is local.

### In scope

- `src/trading_research/risk/kill_switch.py`:
  - `KillSwitchLevel` enum.
  - `KillSwitchRegistry` — persisted state, can be flipped programmatically (by breach events from D1/D2) or manually (CLI command).
  - `is_trading_allowed(strategy_name, instrument_symbol) -> bool` — reads cascaded state.
  - `trigger(level, scope_id, reason) -> None` — flips a switch.
  - Integration with D1 `LimitBreach` and D2 `HeartbeatLost` — these events auto-trigger switches.
- CLI: `uv run trading-research kill --level account`, `--level instrument --symbol 6E`, `--level strategy --name vwap-reversion-6e`.
- CLI: `uv run trading-research status kill-switches` — prints current state.
- Tests:
  - `test_account_kill_overrides_all`
  - `test_instrument_kill_overrides_strategy`
  - `test_strategy_kill_local`
  - `test_breach_triggers_kill`
  - `test_heartbeat_loss_triggers_account_kill`
  - `test_cli_kill_and_status`

### Out of scope

- Auto-flatten execution of open positions. Flatten is an *effect* that requires broker integration; it's declared here, executed in E1.
- Persistence across process restarts. In-memory is fine for D4; persistent store is E1.

### Acceptance tests

- [ ] Tests pass.
- [ ] CLI commands work.
- [ ] Cascading rules verified with integration test.

### Persona review

- **Architect: required** — this is the integration point for the whole risk track.
- **Mentor: required** — reviews that the hierarchy matches how a real trader thinks about a trading halt.

---

## Track D success signal

After D4 ships, this scenario works end-to-end in tests:

```
1. Strategy X on instrument 6E takes three losing trades.
2. Daily loss exceeds $500.
3. LossLimitMonitor fires LimitBreach, scope=account, action=halt_and_flatten.
4. KillSwitchRegistry flips account-level kill switch.
5. Strategy Y on instrument ZN tries to submit an order.
6. is_trading_allowed("Y", "ZN") returns False.
7. Order is suppressed.
```

The Track D acceptance gate is this scenario running green in an integration test.
