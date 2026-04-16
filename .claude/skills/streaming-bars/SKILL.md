---
name: streaming-bars
description: Use when implementing or debugging real-time bar streaming from TradeStation, when handling WebSocket connections and reconnection logic, when distinguishing forming bars from closed bars, when managing the live state of a bar feed for paper or live trading, or when designing the bridge between live bars and the strategy interface that backtests use. This skill defines how live data flows into the system without diverging from historical data conventions, the heartbeat and reconnection patterns, and the rules for when a bar is considered complete enough for a strategy to act on. Invoke for any task involving the TradeStation streaming API or live market data ingestion.
---

# Streaming Bars

This skill owns the live data path: real-time 1-minute bars flowing in from TradeStation's WebSocket-style streaming API, becoming canonical-schema bars on disk and in memory, and feeding into strategies that are running in paper or live mode. Its job is to make sure the live data path produces bars that are *bit-for-bit identical* to what the historical bars skill would produce for the same market events, so that a strategy that worked in backtest behaves the same way in live.

The principle: **the live bar a strategy sees must equal the historical bar that would have been written for the same time window.** If they differ — even slightly — every backtest in the project becomes a lie about how the live system will behave. The whole point of the framework is that backtests are honest predictions of live behavior, and that property is destroyed at the moment historical and streaming data diverge. This skill exists to prevent that divergence.

The second principle: **a forming bar is not a bar.** This is the most important operational rule in the entire skill, and it's where most live trading systems quietly break. A 1-minute bar that's still in progress (the minute hasn't ended) is *not* the same kind of object as a closed bar. Strategies decide on closed bars, never on forming bars. The streaming layer is responsible for distinguishing the two and only emitting completed bars to the strategy.

## What this skill covers

- TradeStation streaming API connection (WebSocket-style stream over HTTP)
- Authentication reuse from `historical-bars` (same OAuth tokens)
- The forming-bar vs. closed-bar distinction
- Heartbeat and reconnection logic
- Buffer management and state during reconnects
- Live bar persistence (writing live bars to a streaming-mode parquet for replay)
- The bridge to the strategy interface (live bars feed `Strategy.on_bar` the same way historical bars do)
- Gap detection for live bars (e.g., a Trump tweet at 3 AM, you wake up to find a 30-minute gap)
- Clock synchronization and timestamp handling

## What this skill does NOT cover

- Historical bar downloads (see `historical-bars`)
- Order placement or position management (see `live-execution`)
- Strategy logic itself (see `backtesting` for the strategy interface)
- Real-time charting (see `charting`)

## TradeStation streaming API basics

TradeStation's WebAPI v3 supports streaming via long-lived HTTP connections that the server pushes data over. The relevant endpoints:

- **`/marketdata/stream/barcharts/{symbol}`** for streaming bar data
- **`/marketdata/stream/quotes/{symbol}`** for tick-level quotes (not used by this skill, but available)

The streaming endpoint accepts the same parameters as the historical endpoint (symbol, interval, unit, session template, extended) and pushes JSON-encoded bar messages over the connection as bars complete or update.

**Key facts about the streaming API:**

1. **Authentication uses the same OAuth flow as historical.** The `streaming-bars` skill imports the auth client from `historical-bars`. There's only one auth flow to maintain.

2. **Bars are pushed both during formation and at close.** TradeStation sends an updated bar message every time a tick changes the OHLC of the current forming bar. At the end of each interval, a "bar closed" message marks the bar as complete. The skill must distinguish these two message types and only emit closed bars to downstream consumers.

3. **The connection can drop for many reasons.** Network blips, server restarts, account session expiration, idle disconnects. Reconnection must be automatic and transparent to the strategy.

4. **There is no "missed bars" mechanism in the streaming API itself.** If the connection is down for 5 minutes and 5 bars happened during that time, the streaming endpoint won't replay them when the connection comes back. The skill handles this by using the historical endpoint to fetch any missed bars after a reconnect.

5. **Message format matches historical format closely but not exactly.** Streaming messages have additional fields (a status flag indicating forming vs. closed, a high-resolution timestamp, etc.) and may have slightly different field names from the historical batch format. The skill normalizes both into the same canonical bar schema.

6. **Latency from market event to delivered bar varies.** Typically tens to hundreds of milliseconds for a forming-bar update, and the "bar closed" message arrives within a second or two of the actual minute boundary. This is fine for any strategy operating on minute bars or longer; it would be inadequate for sub-second strategies, which the project doesn't pursue.

## The forming-bar vs. closed-bar distinction

This is the operational rule that prevents most live-trading bugs.

A **forming bar** is the bar for the current minute (or whatever timeframe), built up tick by tick as trades happen. Its OHLC changes as the minute progresses. Until the minute ends, the bar's "close" is just "the most recent trade" — it's not actually a close.

A **closed bar** is a bar whose interval has ended. Its OHLC is final and will never change.

**The rule:** strategies only see closed bars. Forming bars are an internal detail of the streaming layer and never reach the strategy interface. This matches the backtest semantics exactly — in a backtest, the strategy sees one bar at a time, and each bar is a completed historical record. Live trading should look identical from the strategy's perspective.

**Why this matters:** if a strategy could act on a forming bar, it could see (for example) RSI dropping below 30 mid-minute, fire a long entry, and then watch the rest of the minute push the close back above 30 — at which point the bar's actual close looks nothing like what the strategy saw when it decided. The strategy would have made decisions based on information that only existed for a moment and then disappeared. In backtest, this can never happen because the strategy only sees completed bars. In live, it can happen unless the streaming layer enforces the same constraint.

```python
# src/trading_research/ingest/streaming.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
import asyncio
import json
import httpx
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

@dataclass(frozen=True)
class StreamingBarMessage:
    """A single message from the streaming endpoint."""
    symbol: str
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    buy_volume: Optional[int]
    sell_volume: Optional[int]
    is_closed: bool                  # True if this is the final message for this bar
    received_at_utc: datetime        # local clock time when message was received

@dataclass
class StreamingBarFeed:
    """Manages a live stream of bars from TradeStation for one symbol."""

    symbol: str
    auth_client: "TradeStationAuth"
    timeframe: str = "1m"
    extended: bool = True
    persist_to: Optional[Path] = None  # parquet file to append closed bars to

    async def stream_closed_bars(self) -> AsyncIterator["Bar"]:
        """Yield closed bars one at a time as they arrive from TradeStation.

        This is the primary interface. The strategy code consumes this iterator
        and never sees forming bars.

        On connection drops, the iterator handles reconnect transparently and
        backfills any missed bars via the historical endpoint before resuming
        the live stream.
        """
        last_emitted_timestamp: Optional[datetime] = None

        while True:
            try:
                async with self._connect() as response:
                    async for raw_message in response.aiter_lines():
                        if not raw_message.strip():
                            continue
                        msg = self._parse_message(raw_message)
                        if msg is None:
                            continue

                        if msg.is_closed:
                            bar = self._normalize_to_canonical_schema(msg)
                            if self.persist_to:
                                self._append_to_parquet(bar)
                            last_emitted_timestamp = bar.timestamp_utc
                            yield bar
                        else:
                            # Forming bar — update internal state but don't emit
                            self._update_forming_bar_state(msg)

            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.warning("streaming_disconnect", symbol=self.symbol, error=str(e))

                # Backfill any bars we missed during the disconnect
                if last_emitted_timestamp is not None:
                    await self._backfill_from_historical(last_emitted_timestamp)

                await self._reconnect_with_backoff()
```

The key insight: the iterator only yields when `is_closed=True`. Everything else is internal state management. The strategy code is identical to a backtest loop — it consumes bars one at a time and acts on each. The live-vs-backtest distinction is invisible at the strategy layer.

## Heartbeat and reconnection

Long-lived HTTP streams die. Reasons include:

- Network interruption on the local machine
- ISP route changes
- TradeStation server-side restarts
- Idle disconnects when no bars have arrived for a while
- OAuth access token expiration mid-stream
- Account session expiration after extended idle periods

The skill handles all of these with the following pattern:

**1. Heartbeat detection.** If no bar message (forming or closed) has arrived for `heartbeat_timeout_seconds` (default 90 seconds for 1-minute bars), the connection is considered dead even if the underlying socket hasn't reported an error. The skill closes it and reconnects.

**2. Exponential backoff with jitter on reconnect.** Initial backoff 1 second, max 60 seconds, jitter ±25%. After 5 consecutive failed reconnects, the skill emits a critical-level log entry and continues trying at the maximum backoff interval. It does not give up — a long outage should not require manual restart.

**3. Token refresh on auth errors.** A 401 response from the streaming endpoint triggers a token refresh via the auth client and an immediate reconnect with the new token.

**4. Backfill via historical on reconnect.** Once the live stream is back, the skill computes the gap between the last successfully emitted closed bar and the current time, and uses the historical endpoint to fetch any bars that closed during the gap. These backfilled bars are emitted to the strategy in order before the live stream resumes. From the strategy's perspective, there's no gap — bars arrive in order, just with a delay during the outage.

```python
async def _reconnect_with_backoff(self):
    """Exponential backoff with jitter."""
    if self._consecutive_failures < 1:
        delay = 1.0
    else:
        delay = min(60.0, 2 ** self._consecutive_failures)

    jitter = random.uniform(-0.25, 0.25) * delay
    await asyncio.sleep(delay + jitter)
    self._consecutive_failures += 1

async def _backfill_from_historical(self, last_emitted: datetime):
    """Fetch any bars that closed between last_emitted and now."""
    now_utc = datetime.now(timezone.utc)
    if (now_utc - last_emitted).total_seconds() < 60:
        return  # nothing to backfill

    logger.info("backfilling_streaming_gap",
                symbol=self.symbol,
                from_time=last_emitted.isoformat(),
                to_time=now_utc.isoformat())

    from trading_research.ingest.tradestation import download_historical_bars
    backfilled = await download_historical_bars(
        symbol=self.symbol,
        start_date=last_emitted.date(),
        end_date=now_utc.date(),
        timeframe=self.timeframe,
        output_dir=Path(".streaming_backfill_temp"),
    )

    # Filter to just the gap window and emit each backfilled bar
    for bar in backfilled.bars_in_range(last_emitted, now_utc):
        if self.persist_to:
            self._append_to_parquet(bar)
        yield bar
```

**Why backfill via historical instead of just resuming live:** because the strategy's state depends on having seen every bar in order. An indicator like EMA depends on the previous EMA value, which depends on every bar before. If the strategy restarts after a 30-minute outage and just sees the next live bar, its EMA will be wrong for hours afterward as the new bars feed in but the historical context is missing. Backfilling the gap means the strategy's state remains consistent with what it would have been if there had been no outage.

## The 3 AM Trump tweet scenario

Ibby explicitly said this is a real concern: he's asleep, a headline hits, the market moves hard, and he wakes up to find his strategy has been making decisions on weird data. The framework's response to this scenario:

**1. Single-instrument strategies are flat by EOD.** This is enforced in `backtesting` and `risk-management`. If Ibby's strategy is single-instrument and was running through the previous session, it's already flat by the time he goes to bed. The 3 AM headline can't hurt a position that doesn't exist.

**2. Pairs strategies hold overnight by design but on micro contracts.** The risk-management defaults restrict overnight positions to micro contracts to keep margin and dollar risk small enough that even a major overnight move is survivable. A 100-point overnight move on M6E (micro euro futures) is $125, not $1,250.

**3. The streaming layer detects gaps and surfaces them on resume.** If the streaming connection drops at 2 AM and reconnects at 6 AM with a backfilled gap, the bars fed to the strategy include the gap period — but the strategy sees them as a sequence, not as live decisions. The strategy doesn't get to react in real time to the 3 AM event because Ibby (and the system) wasn't there to react.

**4. The mentor will surface this scenario in conversation.** Whenever a strategy is being designed for live operation, the mentor asks "what does this strategy do if there's a major headline event during a session you're not watching?" The answer should be either "I'm flat by then" (single-instrument day-trading) or "the position is small enough on micro contracts that the worst case is acceptable" (pairs/swing). Anything else gets pushback.

**5. The framework refuses to run a swing strategy on standard contracts without explicit override.** This is the technical enforcement of the mentor's guidance. A YAML config that specifies `category: swing` and standard contracts on a $25k account triggers a hard error.

## Live bar persistence

Closed bars from the streaming feed are written to disk in real-time. The path:

```
data/streaming/
├── ZN_1m_live.parquet              # appended to as bars arrive
├── ZN_1m_live.metadata.json        # tracking the stream's state
├── 6A_1m_live.parquet
└── 6A_1m_live.metadata.json
```

**Why persist live bars at all:** for replay and validation. After a live trading session, the live bars on disk are the ground truth of what the strategy saw. They can be replayed through the trade-replay app (which currently consumes backtest trade logs but should be extended to consume live session logs the same way). They can also be cross-checked against the historical bars that the historical-bars skill downloads later for the same period — any divergence is a bug in the streaming pipeline that needs to be caught and fixed.

**The cross-check pattern:** every morning (or on demand), the framework runs a job that:
1. Downloads historical bars for the previous day via `historical-bars`
2. Reads the live bars that were captured during the previous day's session from `data/streaming/`
3. Compares the two bar-by-bar
4. Reports any divergences

If divergences are found, that's a critical bug — the live system was making decisions on data that didn't match what TradeStation considers historical truth. The framework treats this as a hard failure and the strategy is halted until the discrepancy is investigated.

**Append semantics:** the live parquet is appended to as bars arrive. Polars supports streaming append to parquet files, but the implementation needs to be careful about partial writes (a crash mid-append must not corrupt the file). The pattern is to write each bar's row to a small buffer parquet first, then merge into the main file periodically (every N bars, or every M minutes), with the merge being atomic.

```python
# src/trading_research/ingest/streaming_persist.py
class StreamingBarWriter:
    """Append closed streaming bars to a parquet file safely."""

    def __init__(self, path: Path, flush_every_n_bars: int = 60):
        self.path = path
        self.flush_every_n_bars = flush_every_n_bars
        self._buffer: list[Bar] = []
        self._lock = asyncio.Lock()

    async def append(self, bar: Bar):
        async with self._lock:
            self._buffer.append(bar)
            if len(self._buffer) >= self.flush_every_n_bars:
                await self._flush()

    async def _flush(self):
        """Atomically merge the buffer into the main parquet file."""
        if not self._buffer:
            return

        new_df = bars_to_polars(self._buffer)
        if self.path.exists():
            existing = pl.read_parquet(self.path)
            combined = pl.concat([existing, new_df])
        else:
            combined = new_df

        # Write to temporary, then atomic rename
        tmp_path = self.path.with_suffix(".parquet.tmp")
        combined.write_parquet(tmp_path)
        tmp_path.replace(self.path)

        self._buffer.clear()
```

## The bridge to the strategy interface

A strategy in this project is implemented once, with one `on_bar` method, and runs in three modes:

1. **Backtest mode.** Bars come from a historical parquet file, fed in order, one at a time. The strategy makes decisions and the engine executes them in simulation.

2. **Paper mode.** Bars come from the live streaming feed (and backfill on reconnect). The strategy makes decisions and the engine executes them against a simulated broker that tracks fills, P&L, and positions but never sends real orders.

3. **Live mode.** Bars come from the live streaming feed. The strategy makes decisions and the engine sends real orders via `live-execution`.

**The contract:** the same `on_bar` method works in all three modes. The strategy doesn't know whether it's in backtest, paper, or live. The bars it receives are all canonical-schema closed bars, in order, one at a time.

This is the fundamental property that makes the framework worth building. If a strategy works in backtest and then misbehaves in live, the bug is almost always in one of two places: (a) the live bars don't match the historical bars (caught by the cross-check), or (b) the engine's order handling differs between backtest and live (caught by the `live-execution` skill's strict simulation matching). The strategy code itself never needs to be different.

The plumbing:

```python
# src/trading_research/runtime/live_runner.py
from trading_research.strategies.base import Strategy
from trading_research.ingest.streaming import StreamingBarFeed
from trading_research.backtest.engine import StrategyState
from trading_research.live.broker import LiveBroker, PaperBroker

async def run_live(
    strategy: Strategy,
    symbol: str,
    mode: str,                    # "paper" or "live"
    auth_client: "TradeStationAuth",
):
    """Run a strategy in paper or live mode against the streaming feed."""
    feed = StreamingBarFeed(
        symbol=symbol,
        auth_client=auth_client,
        persist_to=Path(f"data/streaming/{symbol}_1m_live.parquet"),
    )

    if mode == "paper":
        broker = PaperBroker()
    elif mode == "live":
        broker = LiveBroker(auth_client=auth_client)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    state = StrategyState()

    async for bar in feed.stream_closed_bars():
        # Process pending orders against this bar (same as backtest engine)
        fills = await broker.process_pending_orders(bar)
        for fill in fills:
            state.apply_fill(fill)

        # Check exits
        exits = check_exits(state.open_positions, bar, strategy.config)
        for exit in exits:
            await broker.submit_market_order(exit)

        # Strategy generates new signals
        signals = strategy.on_bar(bar_index=len(state.bars_seen), bars=state.bars_seen, state=state)
        for signal in signals:
            order = build_order(signal, state, strategy.config)
            await broker.submit_order(order)

        state.append_bar(bar)
```

The live runner's loop is structurally identical to the backtest engine's loop. The only differences are: bars come from a streaming iterator instead of a fixed dataset, and the broker is real (or paper) instead of simulated. Everything else is the same code.

## Clock synchronization

The streaming layer trusts TradeStation's timestamps for the bar's open time, not the local clock. This matters because the local clock can drift, and a strategy that uses local time for any decision (like "is it 3pm yet, time to flatten?") will misbehave if the clock is wrong.

**The rule:** all timestamps used for trading decisions come from bar data, never from `datetime.now()`. The local clock is used only for logging and for measuring elapsed time within the streaming layer (heartbeat detection, latency monitoring), never for "what time is it in NY right now."

When the strategy needs to know "is the current bar past 3 PM NY," it asks the bar: `bar.timestamp_ny.time() >= time(15, 0)`. It does not ask the system clock.

**Latency monitoring:** the streaming layer tracks the difference between each bar's timestamp and the local clock at the moment the bar was received. Persistent large latencies (more than ~5 seconds for 1-minute bars) indicate either a slow connection or a slow system, and are logged as warnings. Catastrophic latencies (more than 60 seconds) are logged as errors and may trigger a kill switch via `risk-management`.

## Standing rules this skill enforces

1. **Strategies only see closed bars, never forming bars.** This is the fundamental rule and it's enforced at the iterator boundary.
2. **Live bars are bit-for-bit identical to historical bars for the same time window.** Cross-checked daily; divergences are critical bugs.
3. **Reconnects are automatic and transparent to the strategy.** Strategies do not handle connection management.
4. **Gaps are backfilled via the historical endpoint before live streaming resumes.** No gaps in the strategy's bar sequence.
5. **All timestamps used for trading decisions come from bar data, never from the local clock.**
6. **Closed bars are persisted to `data/streaming/` for replay and cross-validation.**
7. **The strategy interface is identical across backtest, paper, and live modes.** Same `on_bar` method, same bar schema, same state management.
8. **The streaming layer never sends orders.** Orders are the responsibility of `live-execution`. The streaming layer only delivers bars.
9. **The framework refuses to start live mode without a passing data integrity cross-check** from the previous session (or with an explicit acknowledgment of the missing check from the human).

## When to invoke this skill

Load this skill when the task involves:

- Implementing or modifying the streaming bar feed
- Debugging connection drops, reconnects, or gaps in live data
- Designing the bridge between live data and strategies
- Investigating divergences between live and historical bars
- Setting up paper or live mode for a strategy
- Adding a new symbol to the streaming feed
- Performance tuning the streaming pipeline

Don't load this skill for:

- Historical data downloads (use `historical-bars`)
- Order placement and broker interaction (use `live-execution`)
- Strategy logic itself (use `backtesting` for the interface)
- Charting live data (use `charting`)

## Open questions for build time

1. **Whether to support multi-symbol streaming over a single connection** or use one connection per symbol. TradeStation may have account-tier limits on concurrent connections. Verify at build time and choose based on the actual limits.
2. **The exact heartbeat timeout for different timeframes.** 90 seconds is a reasonable default for 1-minute bars. For 5-minute bars (which the framework doesn't currently stream but might in the future), the heartbeat would need to be longer.
3. **Whether the cross-check job runs automatically or on demand.** Automatic is safer but adds operational complexity. Default to automatic, with an opt-out flag for cases where the historical endpoint is unavailable.
4. **How to handle the brief overlap between streaming bars and the historical fetch on reconnect.** Bars near the boundary may appear in both sources. The deduplication logic should prefer the historical version because it's authoritative; streaming is best-effort by nature.
5. **Latency thresholds for different account tiers.** TradeStation's professional tier may have lower latency than retail; the warning thresholds should be tuned to what's actually achievable on Ibby's account.
