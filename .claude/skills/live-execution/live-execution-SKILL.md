---
name: live-execution
description: Use when implementing or modifying any code that places real or paper orders, manages live positions, reconciles fills against the broker, or operates the kill switches for live trading. This skill defines the broker abstraction (paper and live), the idempotency rules for order submission, the reconciliation pattern for fill verification, the gating between backtest/paper/live modes, and the operational discipline that protects against the most dangerous failure modes in algorithmic trading. Invoke for any task that touches order placement, position management, or the bridge between strategy decisions and real money. This is the most consequential skill in the project — load it carefully and read it fully before writing any code that touches a broker.
---

# Live Execution

This skill owns the line between "the framework thinks it took a trade" and "TradeStation actually filled an order in Ibby's account." Crossing that line is the most consequential thing the framework does, and the rules in this skill exist to make sure it doesn't happen by accident, doesn't happen with the wrong size, doesn't happen at the wrong time, and doesn't happen without verification that the broker actually did what it was told.

The principle: **the broker is the source of truth.** Not the strategy, not the engine's internal state, not the position tracker. When there's any disagreement between what the framework thinks the position is and what the broker says it is, the broker is right. The framework's internal state is reconciled to the broker, not the other way around. This is the discipline that separates real trading systems from toy ones.

The second principle: **gates exist for a reason and the human is the only one allowed to open them.** The path from backtest → paper → live has explicit gates at each step. Each gate requires the human to confirm in conversation, with the framework refusing to advance without that confirmation. No agent can promote a strategy from backtest to paper or from paper to live on its own initiative, ever.

The third principle: **idempotency or it didn't happen.** Network failures, timeouts, retries, double-clicks — the universe is full of ways for an order to be sent twice when you only meant to send it once. Every order operation in this skill is idempotent: sending the same order ID twice produces exactly the same result as sending it once, never two orders. This is non-negotiable and enforced at the broker abstraction layer.

## What this skill covers

- The broker abstraction: BacktestBroker, PaperBroker, LiveBroker
- The order schema and lifecycle (submitted → working → filled / cancelled / rejected)
- Idempotent order submission via client-generated order IDs
- Fill reconciliation: verifying broker state matches engine state
- Position tracking and the broker-as-source-of-truth rule
- Gating between backtest, paper, and live modes
- Kill switches at the strategy, instrument, and account level (integration with `risk-management`)
- Pre-trade checks (margin, exposure, kill switch state)
- The TradeStation order API
- Operational discipline: logs, alerts, manual overrides

## What this skill does NOT cover

- Streaming bar data (see `streaming-bars`)
- Strategy logic that produces signals (see `backtesting`)
- Position sizing and risk limits (see `risk-management`)
- Backtest simulation (see `backtesting` — but the broker abstraction here is consistent with that engine)

## The broker abstraction

Three implementations of one interface, used by the same engine code, controlled by the mode:

**BacktestBroker** — used during backtest. Simulates fills against historical bars per the rules in `backtesting`. Never touches anything external. Accepts all orders (subject to risk checks) and "fills" them according to the configured fill model.

**PaperBroker** — used during paper trading on live data. Simulates fills the same way the BacktestBroker does, but against streaming bars instead of historical. Accepts all orders, fills them according to the same model the backtest used, tracks P&L. Never sends anything to TradeStation. Useful for verifying that the strategy behaves the same way on live data as it did in backtest before any real money is at risk.

**LiveBroker** — used during live trading. Sends real orders to TradeStation via the Order API, tracks fills via the streaming order events, reconciles position state with the broker, and produces the same Fill objects the other brokers produce so the engine code is identical.

```python
# src/trading_research/live/broker.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid

@dataclass(frozen=True)
class Order:
    """An order ready to be sent to a broker."""
    client_order_id: str             # generated locally, used for idempotency
    symbol: str
    side: str                        # "buy" or "sell"
    quantity: float
    order_type: str                  # "market", "limit", "stop", "stop_limit"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"       # "day", "gtc", "ioc", "fok"
    strategy_id: str = ""            # for tagging in the broker's records
    parent_trade_id: Optional[str] = None  # for re-entries
    submitted_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(frozen=True)
class BrokerOrderState:
    """The broker's current view of an order."""
    client_order_id: str
    broker_order_id: str             # the broker's internal ID
    status: str                      # "pending", "working", "filled", "cancelled", "rejected"
    filled_quantity: float
    average_fill_price: Optional[float]
    remaining_quantity: float
    last_update_utc: datetime
    rejection_reason: Optional[str] = None

class Broker(ABC):
    """The broker abstraction. All three implementations satisfy this contract."""

    @abstractmethod
    async def submit_order(self, order: Order) -> BrokerOrderState:
        """Submit an order. Idempotent on client_order_id.

        Returns the broker's initial view of the order's state. The fill
        notification arrives later via the fill stream.
        """
        ...

    @abstractmethod
    async def cancel_order(self, client_order_id: str) -> BrokerOrderState:
        """Cancel a working order. Idempotent (cancelling an already-cancelled
        order is a no-op that returns the current state).
        """
        ...

    @abstractmethod
    async def get_order_state(self, client_order_id: str) -> BrokerOrderState:
        """Query the current state of an order. Used for reconciliation."""
        ...

    @abstractmethod
    async def get_positions(self) -> list["Position"]:
        """Query the current open positions. The authoritative answer."""
        ...

    @abstractmethod
    async def get_account_equity(self) -> float:
        """Query the current account equity in USD."""
        ...

    @abstractmethod
    def fill_stream(self) -> AsyncIterator["Fill"]:
        """Yield Fill objects as they arrive. Used by the engine to update state."""
        ...
```

The same engine code uses any of the three brokers without knowing which is which. The mode is set once, at startup, and the broker is constructed accordingly.

## Idempotent order submission

Every order has a `client_order_id` that's generated locally before the order is sent. The format is `<strategy_id>_<bar_timestamp>_<sequence>`, which is unique by construction within a strategy and recoverable across restarts (you can derive what the next ID should be from the last bar processed).

**The submission contract:**

1. The engine generates a `client_order_id` and constructs an Order.
2. The engine calls `broker.submit_order(order)`.
3. The broker checks whether an order with that `client_order_id` already exists in its records. If yes, it returns the existing state without re-submitting. If no, it submits to the upstream broker (TradeStation in the live case) and records the new order.
4. The broker returns the initial state.

This means: if step 3 succeeds at TradeStation but the network connection drops before step 4 reaches the engine, the engine doesn't know whether the order was placed. The engine retries by calling `submit_order` with the same Order. The broker sees the existing `client_order_id`, recognizes it, and returns the actual state without placing a duplicate order. The retry is safe.

This is the failure mode that destroys algorithmic trading systems that don't think about idempotency. A naive system that retries on network errors will happily double its position size every time the network blips. The framework refuses to be that system.

**For TradeStation specifically:** TradeStation's order API supports a client-supplied identifier on order submission, which it uses to deduplicate. The LiveBroker passes the `client_order_id` as this field. The broker also maintains its own local mapping of `client_order_id` → `broker_order_id` so that even if TradeStation's deduplication fails for some reason, the LiveBroker's own check catches the duplicate.

```python
# src/trading_research/live/live_broker.py
class LiveBroker(Broker):
    def __init__(self, auth_client: "TradeStationAuth", account_id: str):
        self._auth = auth_client
        self._account_id = account_id
        self._submitted_orders: dict[str, BrokerOrderState] = {}
        self._lock = asyncio.Lock()

    async def submit_order(self, order: Order) -> BrokerOrderState:
        async with self._lock:
            # Idempotency check
            if order.client_order_id in self._submitted_orders:
                logger.info("idempotent_resubmission",
                            client_order_id=order.client_order_id,
                            existing_state=self._submitted_orders[order.client_order_id].status)
                return self._submitted_orders[order.client_order_id]

            # Pre-trade checks (kill switch, margin, exposure)
            check = await self._pre_trade_checks(order)
            if not check.passed:
                rejected = BrokerOrderState(
                    client_order_id=order.client_order_id,
                    broker_order_id="",
                    status="rejected",
                    filled_quantity=0.0,
                    average_fill_price=None,
                    remaining_quantity=order.quantity,
                    last_update_utc=datetime.now(timezone.utc),
                    rejection_reason=check.reason,
                )
                self._submitted_orders[order.client_order_id] = rejected
                logger.warning("order_rejected_pretrade", order=order, reason=check.reason)
                return rejected

            # Submit to TradeStation
            try:
                response = await self._submit_to_tradestation(order)
                state = self._parse_order_response(response, order)
                self._submitted_orders[order.client_order_id] = state
                logger.info("order_submitted", order=order, broker_order_id=state.broker_order_id)
                return state
            except Exception as e:
                logger.error("order_submission_failed", order=order, error=str(e))
                # Don't record the order — let the caller retry with the same client_order_id
                raise
```

**Note the failure mode in the exception path:** if submission to TradeStation fails with an exception, the order is NOT recorded in `_submitted_orders`. The caller can safely retry with the same `client_order_id`. If the retry succeeds, no duplicate. If TradeStation actually placed the order before the error and the retry tries to place a second one, TradeStation's own deduplication catches it.

The only failure mode this can't handle is "TradeStation placed the order, returned success, but the response was lost in transit and the engine never recorded it." For this case, the reconciliation step (described below) catches the discrepancy on the next sync.

## Fill reconciliation

The engine's internal state of "what positions do I have" must match the broker's state of "what positions does Ibby have." Reconciliation is the process of comparing them and updating the engine when they differ.

**The reconciliation pattern:**

1. **At a regular interval** (every 30 seconds during live trading, every 5 seconds when an order is in flight), the engine queries the broker for the current state of all open orders and all positions.
2. **It compares the broker's state to its internal state.**
3. **If they match, no action.** Log the successful reconciliation.
4. **If they differ, the broker wins.** The engine updates its internal state to match the broker, logs the discrepancy as a warning, and emits a notification for the human to review.

The discrepancies that can occur, and what they mean:

- **Engine thinks order X is working, broker says it's filled.** The fill notification was missed somehow. Engine updates to filled, generates the Fill record, applies it to internal state.
- **Engine thinks order X is filled, broker says it's still working.** Probably a race condition where the broker hasn't processed the fill yet. Wait one cycle and re-check.
- **Engine thinks position is +2 contracts, broker says +1.** Either an unintended cancel or a partial fill that wasn't recorded. Engine updates to broker's view, logs the discrepancy. The human is notified.
- **Engine thinks no position, broker shows a position.** This is a critical discrepancy. The framework didn't know about a position that exists. Engine immediately halts the affected strategy and notifies the human. Manual review required before resuming.
- **Engine has a position, broker shows none.** Also critical. The engine thinks money is at risk that isn't. Same response: halt and notify.

**The key principle:** the framework is conservative on discrepancies. When in doubt, halt and notify. False alarms are cheap; missed discrepancies can be expensive. The human can always re-enable a halted strategy after confirming the state is correct.

```python
async def reconcile(self) -> ReconciliationResult:
    """Compare engine state to broker state and update engine if they differ."""
    broker_positions = await self._broker.get_positions()
    broker_orders = await self._broker.get_open_orders()

    engine_positions = self._state.positions
    engine_orders = self._state.open_orders

    discrepancies = []

    # Check positions
    for symbol in set(engine_positions.keys()) | set(p.symbol for p in broker_positions):
        engine_qty = engine_positions.get(symbol, Position(symbol, 0.0)).quantity
        broker_qty = next((p.quantity for p in broker_positions if p.symbol == symbol), 0.0)

        if abs(engine_qty - broker_qty) > 1e-6:
            discrepancies.append(PositionDiscrepancy(
                symbol=symbol,
                engine_quantity=engine_qty,
                broker_quantity=broker_qty,
                severity="critical",
            ))

    # Check orders
    for client_id in set(engine_orders.keys()) | set(o.client_order_id for o in broker_orders):
        # ... similar comparison

    if any(d.severity == "critical" for d in discrepancies):
        await self._halt_for_reconciliation(discrepancies)
        await self._notify_human(discrepancies)

    # Update engine state to match broker
    for discrepancy in discrepancies:
        self._state.apply_broker_truth(discrepancy)

    return ReconciliationResult(
        timestamp_utc=datetime.now(timezone.utc),
        discrepancies=discrepancies,
        action_taken="halted" if any(d.severity == "critical" for d in discrepancies) else "synced",
    )
```

## Pre-trade checks

Before any order is sent to a broker (live or paper), the framework runs a pre-trade check. Failure of any check causes the order to be rejected with a logged reason; the order is never sent.

**The checks, in order:**

1. **Account-level kill switch.** If the account kill switch is active, every order is rejected.
2. **Instrument-level kill switch.** If the order's instrument is on the kill list, the order is rejected.
3. **Strategy-level kill switch.** If the order's strategy is halted (daily loss limit, weekly limit, account drawdown), the order is rejected.
4. **Margin check.** Compute the margin required for this order plus the existing positions. If it exceeds the account equity (with a safety buffer, default 10%), reject.
5. **Exposure check.** Compute the new exposure (per-strategy, per-instrument, per-asset-class, total) and verify it's within the configured caps. Reject on cap breach.
6. **Re-entry validation.** If the order is a re-entry (`parent_trade_id` is set), verify the combined target and combined risk are present and valid per the `risk-management` rules.
7. **Sanity checks.** Order quantity is positive. Symbol is in the contract registry. Side is valid. Order type matches the broker's supported types.

These checks live in `risk-management` (which owns the rules) but are *invoked* by the broker abstraction (which owns the integration point). The separation matters: risk rules can be modified without touching broker code, and broker code can't accidentally bypass the checks.

```python
async def _pre_trade_checks(self, order: Order) -> CheckResult:
    """Run all pre-trade checks. Return passed=True only if all pass."""
    from trading_research.risk.checks import (
        check_kill_switches,
        check_margin,
        check_exposure,
        check_reentry_validity,
        check_sanity,
    )

    checks = [
        check_sanity(order),
        check_kill_switches(order),
        check_margin(order, self._state, self._instrument_registry),
        check_exposure(order, self._state, self._instrument_registry),
        check_reentry_validity(order, self._state),
    ]

    failed = [c for c in checks if not c.passed]
    if failed:
        return CheckResult(
            passed=False,
            reason="; ".join(c.reason for c in failed),
            failed_checks=[c.name for c in failed],
        )
    return CheckResult(passed=True, reason="", failed_checks=[])
```

## Mode gating: the path from backtest to paper to live

The framework has explicit, conversational gates between modes. Crossing each gate requires the human to confirm in conversation; agents cannot promote a strategy on their own initiative.

**Backtest → Paper:**

To run a strategy in paper mode, the framework requires:
1. A successful backtest run with a complete report
2. The human's explicit confirmation in conversation: "yes, run this strategy in paper mode"
3. A paper-mode config file at `configs/strategies/<n>.paper.yaml` that's distinct from the backtest config
4. A duration commitment ("run paper for N days") so paper mode has a defined end
5. The data scientist persona's review of the backtest report (the human can override this, but the override must be explicit)

The framework refuses to start paper mode without all five. The human can satisfy them in any order, but all must be present.

**Paper → Live:**

To promote a strategy from paper to live, the framework requires:
1. A successful paper trading period of at least the committed duration
2. A paper-vs-backtest comparison showing the metrics agreed within reasonable bounds (the data scientist defines "reasonable")
3. The human's explicit, unambiguous confirmation: "yes, run this strategy in LIVE mode with REAL MONEY"
4. The mentor persona's review (any concerns get raised)
5. A live-mode config at `configs/strategies/<n>.live.yaml` that explicitly sets `mode: live` and includes the kill switch parameters
6. A starting account balance snapshot for tracking
7. A defined initial capital allocation (less than total account equity, typically much less)

The framework refuses to start live mode without all seven. This is intentional friction. The cost of going live by accident is much higher than the cost of being asked to confirm.

**The conversational gate is enforced in code.** The CLI command to start live mode prompts the human in the terminal:

```
$ uv run trading-research run --strategy zn_macd_rev_v1 --mode live

==========================================================================
LIVE MODE START REQUEST
==========================================================================
Strategy:        zn_macd_rev_v1
Symbol:          ZN
Initial capital: $5,000 (20% of account)
Daily limit:     $250
Weekly limit:    $750

Paper trading history:
  - Period:     2025-01-01 to 2025-01-15 (14 days)
  - Trades:     47
  - Net P&L:    +$310
  - Max DD:     -$120
  - Calmar:     2.1

Backtest comparison:
  - Backtest Calmar:  2.4
  - Paper Calmar:     2.1
  - Difference:       within tolerance

Have the personas reviewed this transition?
  Quant mentor:    [pending]
  Data scientist:  [pending]

To proceed, the human must:
  1. Have the mentor and data scientist review (use Claude Code chat)
  2. Run this command again with --confirm-live-start

This system will NOT start live trading without --confirm-live-start.

==========================================================================
```

Even with `--confirm-live-start`, the framework requires the human to literally type `START LIVE TRADING` (uppercase) into the terminal as a final confirmation. This is the same pattern used by destructive operations in serious infrastructure tools. It's friction by design.

## TradeStation order API

The relevant TradeStation endpoints for live execution:

- **`POST /v3/orderexecution/orders`** — submit a new order
- **`PUT /v3/orderexecution/orders/{order_id}`** — modify a working order
- **`DELETE /v3/orderexecution/orders/{order_id}`** — cancel a working order
- **`GET /v3/brokerage/accounts/{account_id}/orders`** — query open orders
- **`GET /v3/brokerage/accounts/{account_id}/positions`** — query open positions
- **`GET /v3/brokerage/accounts/{account_id}/balances`** — query account balances and margin

**Authentication:** uses the same OAuth flow as `historical-bars` and `streaming-bars`. The `LiveBroker` imports the auth client from those skills.

**Order types:** TradeStation supports market, limit, stop, stop limit, trailing stop, and several variants. The framework wraps the basic four (market, limit, stop, stop limit) and exposes them through the Order schema. Other types can be added per strategy when needed.

**Time in force:** `day` is the default. `gtc` (good till cancelled) is available for swing strategies. `ioc` (immediate or cancel) and `fok` (fill or kill) are supported but rarely used.

**Account ID:** TradeStation accounts have an ID that must be included in every order. The LiveBroker reads it from `.env` as `TRADESTATION_ACCOUNT_ID` and verifies it matches the authenticated account on first connection. A mismatch is a hard error — you do not want to be sending orders to the wrong account.

## Operational discipline

**Logging.** Every action the LiveBroker takes is logged via structlog with full context:

- Order submissions (with the full order body)
- Order acknowledgments from TradeStation
- Fill notifications
- Reconciliation runs and any discrepancies
- Pre-trade check failures
- Connection drops and reconnects
- Kill switch activations

The logs are written to `runs/live/<date>/log.jsonl` and rotated daily. They are the audit trail. Six months from now, "what did the framework do on January 15 at 14:32:11" must be answerable from the logs alone.

**Alerts.** Critical events (reconciliation failures, kill switch activations, repeated connection failures, rejected orders for unexpected reasons) trigger an alert. The alert mechanism is configurable but the default is: log at CRITICAL level, write to a sentinel file at `runs/live/.alerts/`, and (optionally) emit an OS-level notification via `plyer` or similar. The human is responsible for monitoring alerts; the framework doesn't email or text by default because that introduces external dependencies. Future enhancement: integration with a notification service like Pushover or Telegram.

**Manual overrides.** The human can intervene at any time:
- `flatten` — close all positions for a strategy or for the account
- `pause` — halt new orders for a strategy without flattening
- `resume` — re-enable a halted strategy after manual review
- `cancel` — cancel a specific working order

These commands are available via the CLI and via slash commands in Claude Code. They're logged the same way automated actions are.

**Heartbeat to a watchdog.** Optionally, the LiveBroker writes a heartbeat file every 30 seconds. An external watchdog (cron job, systemd timer, whatever) can check the heartbeat file and alert if it's stale. This catches the case where the framework crashes silently and the human has no other way to know.

## The reconciliation-first restart

When the framework starts in live mode (whether for the first time or after a restart), the very first thing it does is reconcile with the broker. It reads the current positions from TradeStation, the current open orders, the current account balance, and initializes its internal state from those values rather than from any saved state file.

This is critical because the framework cannot trust its saved state across restarts. If it crashed mid-trade, the saved state may be inconsistent. The broker is the source of truth, so the broker is what gets read first.

After the initial reconcile, the framework cross-checks against any saved state file. If the saved state exists and matches the broker, it's used for any context the broker doesn't provide (strategy-level metadata, recent decision history). If it conflicts, the broker wins and the human is notified.

```python
async def initialize_live_runner(strategy: Strategy, broker: LiveBroker):
    """Initialize a live runner with reconciliation as the first action."""
    logger.info("live_runner_starting", strategy_id=strategy.id)

    # Step 1: reconcile with broker (the source of truth)
    initial_positions = await broker.get_positions()
    initial_orders = await broker.get_open_orders()
    account_equity = await broker.get_account_equity()

    logger.info("broker_initial_state",
                positions=len(initial_positions),
                open_orders=len(initial_orders),
                equity=account_equity)

    # Step 2: load saved strategy state if it exists
    saved_state = load_saved_state(strategy.id)

    if saved_state:
        # Step 3: cross-check
        discrepancies = compare(saved_state, initial_positions, initial_orders)
        if discrepancies:
            logger.warning("state_discrepancy_on_restart", discrepancies=discrepancies)
            # Broker wins — but notify the human
            await notify_human("Restart found state discrepancies; broker view used")

    # Step 4: build the engine state from broker truth
    state = StrategyState.from_broker_view(initial_positions, initial_orders, account_equity)

    # Step 5: only NOW connect to the streaming feed and start processing
    return state
```

## Standing rules this skill enforces

1. **Idempotent order submission.** Every order has a `client_order_id` and re-submitting it does not create a duplicate.
2. **The broker is the source of truth.** Engine state is reconciled to the broker, not the other way around.
3. **All orders pass pre-trade checks** (kill switches, margin, exposure, sanity, re-entry validity).
4. **Mode promotion requires explicit human confirmation in conversation.** Agents cannot promote backtest → paper → live on their own.
5. **Live mode start requires literal typing of confirmation in the terminal.** Friction by design.
6. **The reconciliation-first restart pattern is mandatory.** The framework cannot trust saved state across restarts.
7. **Critical discrepancies halt the affected strategy and notify the human.** Conservative on discrepancies.
8. **Every action is logged with full context.** The logs are the audit trail.
9. **Manual override commands are always available.** The human can flatten, pause, resume, or cancel at any time.
10. **The LiveBroker uses the same auth client as `historical-bars` and `streaming-bars`.** One auth flow, one set of credentials.

## When to invoke this skill

Load this skill when the task involves:

- Implementing or modifying any code that places orders
- Building or testing the broker abstraction
- Designing or modifying the mode-gating logic
- Investigating live trading discrepancies or failures
- Setting up live trading for a new strategy
- Adding new manual override commands
- Reviewing the audit trail of a live trading session
- Anything that touches real money or the path to it

Don't load this skill for:

- Streaming bar data (use `streaming-bars`)
- Strategy logic (use `backtesting`)
- Risk rule definitions (use `risk-management`)

**Always load this skill fully.** This is not a skill to skim. Every section matters because every section is a failure mode that has destroyed real trading systems. If you're touching this code, you're touching real money, and the rules in this skill exist because the alternatives have cost real people real money.

## Open questions for build time

1. **TradeStation account type and order permissions.** Some account types have restrictions on certain order types or instruments. Verify Ibby's account has the permissions needed for the strategies he wants to run, before any live work starts.
2. **The exact reconciliation interval.** 30 seconds is the proposed default. For strategies with higher trade frequency, more frequent reconciliation is better. For idle strategies, less frequent saves API calls. Tune based on actual behavior.
3. **Whether to integrate with a notification service.** The default is local-only alerts (log + sentinel file + OS notification). A future enhancement could push to Pushover, Telegram, or email. Defer until the default proves insufficient.
4. **Backup broker connectivity.** TradeStation has historically had outages. The framework currently has no fallback broker. If reliability becomes a concern, the broker abstraction could be extended to support failover, but this is a significant complexity addition. Defer until needed.
5. **Whether to implement a "dry run" mode** that goes through the full live order submission pipeline but stops just short of actually submitting. Useful for testing the integration without risk. Probably worth building as a third broker variant (LiveBrokerDryRun) that wraps LiveBroker and intercepts the final submission call.
6. **Position sizing for the very first live trade.** Even after extensive paper testing, the first live trade is meaningfully different. Recommend that the framework supports a "first live trade" mode that further reduces position size for the first N trades, with N configurable. This is psychological scaffolding more than mathematical optimization, but psychological scaffolding is the entire point of going slow into live.
