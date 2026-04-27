# Broker Abstraction & Execution Protocol

This document defines the technical enforcement for order placement and reconciliation, migrated from the `live-execution-SKILL.md` manual.

## 1. Idempotent Order Submission
The engine must generate a `client_order_id` in the format `<strategy_id>_<timestamp>_<seq>` before submission.

```python
# Logic from src/trading_research/live/broker.py
async def submit_order(self, order: Order):
    # Architect: Check local registry first to prevent re-submission
    if order.client_order_id in self._submitted_orders:
        return self._submitted_orders[order.client_order_id]

    # Pre-trade: Verify Daily/Weekly loss limits via risk-controls
    # TradeStation: Pass client_order_id as the deduplication token
    response = await self.ts_client.post_order(order)
    return response
```

## 2. Reconciliation Matrix
Perform a full "Broker vs. Engine" audit every 30 seconds.

| Discrepancy | Severity | Action |
|---|---|---|
| Engine shows +2, Broker shows +1 | Critical | Halt strategy, notify human, update to Broker Truth |
| Engine shows filled, Broker shows working | High | Log race condition, retry in 5s |
| Account P&L < Daily Loss Limit | Critical | Activate Kill Switch, refuse new opening orders |

## 3. The Live Promotion Gate
The agent must verify all seven requirements before live trading begins:

1. Passing backtest report.
2. Successful paper period (metrics within tolerance).
3. Explicit human conversation confirmation.
4. Mentor and Scientist qualitative reviews.
5. Live-specific YAML config in `configs/strategies/`.
6. Account balance snapshot.
7. Initial capital allocation cap.

---

## 4. The Streaming Reference (L3)
**Path:** `/.agent/skills/live-bridge/references/streaming-protocol.md`

````markdown
# Real-Time Data & Streaming Protocol

This document defines the technical enforcement for bar ingestion, migrated from the `streaming-bars-SKILL.md` manual.

## 1. The Closed Bar Boundary
The streaming feed yields both forming (live ticks) and closed (completed) bars. The `live-bridge` MUST filter for `is_closed=True`.

```python
# Logic from src/trading_research/ingest/streaming.py
async def stream_bars(self):
    async for msg in self.ws_client:
        if not msg['is_closed']:
            continue # Scientist: Forming bars are NOT for trading

        # Architect: Normalize to canonical schema
        bar = normalize(msg)
        self.persist_to_parquet(bar)
        yield bar
```

## 2. Heartbeat & Reconnect Patterns
- **Heartbeat Timeout**: 90 seconds. If missed, force disconnect and retry.
- **Exponential Backoff**: 1s -> 2s -> 4s -> ... Max 60s with 25% jitter.
- **Historical Backfill**: Upon reconnection, fetch the gap from the historical endpoint to maintain EMA/Indicator continuity.

## 3. Data Integrity Cross-Check
Every session must end with `uv run python -m trading_research.tools.validate_stream`.

- **Goal**: Compare `data/streaming/{symbol}_live.parquet` against the historical fetch.
- **Tolerance**: 0 bits. Live and historical bars must be identical.
````
