---
name: backtesting
description: Use when designing, implementing, running, or debugging strategy backtests. This skill defines the simulation engine architecture, fill models, exit logic, the trade log writer, walk-forward harness, and the pessimistic default behaviors that prevent backtest results from lying. Invoke when building a new strategy, when modifying an existing strategy's backtest, when investigating unexpected backtest results, when implementing fill or slippage models, or when designing the simulation loop for any new market or instrument.
---

# Backtesting

This skill owns the simulation engine that turns strategy logic plus historical bars into trade logs. Its job is to produce backtest results that are honest — meaning that a strategy that looks profitable in backtest has a real chance of being profitable in live trading, and a strategy that looks broken in backtest is actually broken.

Most backtest engines lie. They lie by default. They use unrealistic fill prices, they resolve TP/SL ambiguity optimistically, they ignore slippage, they fail to account for the difference between the bar that triggered a decision and the bar where the fill actually happened, and they let strategies peek at data that wouldn't have been available at the moment of the decision. Every one of these failure modes is documented in the literature, every one of them is preventable, and every one of them is the default in most retail tools.

The principle: **be hostile to the strategy.** Make the simulation pessimistic on every axis. Make ambiguous bars resolve against the strategy. Add slippage and commissions. Use next-bar-open fills. Refuse to let the strategy see future data. If the strategy still looks good after all of that, it has a real chance. If it doesn't, you've saved yourself the cost of finding out the hard way.

## What this skill covers

- The simulation engine architecture (event-driven core)
- Strategy interface and contract
- Fill models (next-bar-open default, with documented overrides)
- Exit logic (TP, SL, timeout, signal-based, end-of-day flat)
- TP/SL ambiguity resolution (pessimistic by default)
- Slippage and commission models
- Walk-forward harness for parameter validation
- Re-entry handling for planned scale-in patterns
- Trade log generation (writes the schema defined in `data-management`)
- Run artifacts and reproducibility

## What this skill does NOT cover

- Indicator math (see `indicators`)
- Position sizing and risk limits (see `risk-management`)
- Metric computation and report generation (see `strategy-evaluation`)
- Visualizing backtest results (see `charting` and `trade-replay`)
- Walk-forward statistical interpretation (see `feature-engineering` and `strategy-evaluation`)

## Architecture

The backtest engine is **event-driven**, not vectorized. This is a deliberate choice with tradeoffs.

**Why event-driven:** because fills, exits, and re-entries depend on the *path* the price takes within a bar, not just the bar's OHLC summary statistics. A vectorized backtest treats each bar as a single event, which makes it impossible to correctly handle TP/SL ambiguity, planned re-entries with combined risk targets, or any logic where the order of events within a bar matters. Event-driven backtests process bars sequentially and let the strategy code reason about state explicitly. This is slower than vectorized (by 10-100x for naive implementations) but it's correct, and correctness wins.

**Why not vectorized:** the failure mode of vectorized backtests is that they're fast and they look right and they lie. Specifically, they tend to handle exits by computing "did this bar hit TP?" and "did this bar hit SL?" as separate boolean masks and then combining them, which loses the temporal information needed to know which one was hit first. They also tend to make scale-in and re-entry logic awkward to express, which leads to subtle bugs.

**The core loop:**

```python
# Pseudocode for the simulation loop
def run_backtest(strategy, bars, config):
    state = StrategyState()
    for bar in bars:
        # 1. Update strategy with new bar (computes any indicators it needs)
        signals = strategy.on_bar(bar, state)

        # 2. Process any pending orders against this bar
        fills = process_pending_orders(state.pending_orders, bar, config.fill_model)
        for fill in fills:
            state.apply_fill(fill)
            log_trade(fill)

        # 3. Process exit conditions for any open positions
        exits = check_exits(state.open_positions, bar, config)
        for exit in exits:
            state.apply_exit(exit)
            log_trade(exit)

        # 4. Submit any new orders the strategy wants
        for signal in signals:
            order = build_order(signal, state, config)
            state.pending_orders.append(order)

    return state.completed_trades
```

The loop is *strict in ordering*: first the strategy sees the new bar, then pending orders from previous bars get filled, then exit conditions are checked, then new orders are queued. The next bar's open is when those new orders fill (under the default fill model). This ordering is the implementation of the as-of rule at the simulation level: the strategy makes decisions based on bar N's close, and those decisions take effect at bar N+1's open.

## The strategy interface

Every strategy implements a small interface:

```python
# src/trading_research/strategies/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import polars as pl

@dataclass
class Signal:
    """A request to enter or exit a position. The engine decides whether
    and when this becomes an actual order based on state and config."""
    side: str                       # "long" or "short"
    action: str                     # "enter", "exit", "reentry"
    parent_trade_id: Optional[str] = None  # for reentry actions
    size: float = 1.0
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    timeout_bars: Optional[int] = None
    notes: str = ""
    indicator_snapshot: dict = None  # as-of indicator values, included in trade log

class Strategy(ABC):
    """Base class for all strategies. Subclasses implement on_bar()."""

    def __init__(self, config: dict, instrument: Instrument):
        self.config = config
        self.instrument = instrument
        self.indicators = {}  # populated by precompute_indicators()

    def precompute_indicators(self, bars: pl.DataFrame) -> None:
        """Compute all indicators the strategy will use, once, at the start.
        Subclasses override to compute their specific indicators.
        Must respect the as-of rule: indicators[name][i] uses bars[:i+1] only.
        """
        pass

    @abstractmethod
    def on_bar(self, bar_index: int, bars: pl.DataFrame, state: "StrategyState") -> list[Signal]:
        """Called once per bar. Returns a list of signals (possibly empty).

        Args:
            bar_index: the index of the current bar in `bars`. The strategy
                may only look at bars[:bar_index + 1].
            bars: the full bar dataset (read-only).
            state: the current strategy state, including open positions and
                recent trade history.

        Returns:
            A list of Signal objects. The engine processes them after the
            current bar's exits are checked.
        """
        ...
```

**The contract:** a strategy reads bars up to and including the current bar, reads its own state, and produces signals for what should happen next. It doesn't directly create orders; it produces signals that the engine turns into orders. This indirection is what lets the engine apply consistent fill models, slippage, and risk checks across all strategies.

**The bar_index discipline:** strategies must look at `bars[:bar_index + 1]`, never `bars[bar_index + 1:]`. This is the as-of rule. The base class doesn't enforce it (Python can't), but the test harness includes a wrapper that checks for accidental future-data access in strategy code by raising on any read past `bar_index`.

## Fill models

The fill model decides what price an order fills at when the engine processes it.

**`next_bar_open` (default).** An order submitted at the close of bar N fills at the open of bar N+1. This is the most realistic model for retail traders because it matches how market orders actually behave: you decide on bar N's close, you submit, the order goes in, and it fills at whatever the next bar opens at. Slippage is added on top of this base price.

**`trigger_bar_close` (override, requires explicit justification).** An order fills at the close of the bar that triggered it. This is faster and produces better backtest results, but it's a lie — you cannot actually submit and fill an order at the close of a bar because the bar's close is only known at the moment the bar ends, and any submission has latency. This model exists only because some research workflows need it for comparison purposes. Using it in any production strategy requires:
1. Explicit `fill_model: trigger_bar_close` in the strategy config
2. A comment in the config explaining why
3. The data scientist persona will flag it loudly in any output

**`limit_at_price` (override).** A limit order is placed and fills only if the limit price is touched within the order's lifetime. Used for limit-order strategies that wouldn't fill at next-bar-open. The fill assumption is *pessimistic*: the limit fills at the limit price exactly, never at a better price (because in real markets, the queue position determines whether you fill at a better price, and we can't simulate queue position from bar data).

**Slippage model.** Slippage is added on top of the base fill price in the direction that hurts the trader: long orders fill higher than the base price, short orders fill lower. The default slippage model is **fixed_ticks**: a configured number of ticks (default 1) added to every fill. More sophisticated models (volume-proportional, volatility-proportional) can be added later but the default is "always 1 tick of slippage" because it's simple and pessimistic and rarely far from reality on liquid CME futures.

**Commission model.** Per-side commission charged at fill. Default $1.50/contract per side, total $3.00 round trip, which is roughly TradeStation's published rate. Configurable per strategy.

```python
# src/trading_research/backtest/fills.py
from dataclasses import dataclass
from typing import Protocol

@dataclass
class Fill:
    timestamp_ny: pd.Timestamp
    price: float
    size: float
    side: str
    commission_usd: float
    slippage_ticks: float
    fill_model: str  # for the trade log

class FillModel(Protocol):
    def fill(self, order: Order, current_bar: Bar, next_bar: Bar | None,
             instrument: Instrument) -> Fill | None:
        """Return a Fill if the order would fill, None otherwise."""
        ...

class NextBarOpenFillModel:
    def __init__(self, slippage_ticks: float = 1.0, commission_per_side_usd: float = 1.50):
        self.slippage_ticks = slippage_ticks
        self.commission_per_side_usd = commission_per_side_usd

    def fill(self, order, current_bar, next_bar, instrument):
        if next_bar is None:
            return None  # no next bar; order does not fill
        base_price = next_bar.open
        slippage_amount = self.slippage_ticks * instrument.tick_size
        if order.side == "long":
            fill_price = base_price + slippage_amount
        else:
            fill_price = base_price - slippage_amount
        return Fill(
            timestamp_ny=next_bar.timestamp_ny,
            price=fill_price,
            size=order.size,
            side=order.side,
            commission_usd=self.commission_per_side_usd * order.size,
            slippage_ticks=self.slippage_ticks,
            fill_model="next_bar_open",
        )
```

## Exit logic

A position can exit for one of several reasons. The engine checks them in priority order on every bar after the position is open:

1. **Stop loss hit** — bar's range touches the stop price
2. **Take profit hit** — bar's range touches the TP price
3. **Both touched (ambiguous)** — handled per the resolution rules below
4. **Timeout** — the position has been open for the configured maximum number of bars
5. **End-of-day flat** — for single-instrument strategies with EOD flat enabled, all positions are closed at a configured time (e.g. 15:00 NY)
6. **Signal exit** — the strategy explicitly returns an "exit" signal

**TP/SL ambiguity resolution.** This is the failure mode that bit the old code Ibby shared and it's worth dwelling on.

When a single bar's range covers both the take-profit price and the stop-loss price, you cannot tell from bar data alone which one was hit first. The bar's OHLC tells you the high and low were both reached, but not in what order.

The resolution methods, in order of pessimism:

1. **`pessimistic` (default).** Always assume the stop was hit first. The exit reason is `tp_sl_ambiguous` and the exit price is the stop price. This is the safest assumption because it means any backtest result that looks profitable is profitable even after accounting for ambiguity in this trader's favor never being assumed.

2. **`delta_inferred`.** If buy/sell volume data is available for the bar, use the delta sign and magnitude to make a probabilistic guess about which level was hit first. A bar with strong negative delta on a long position with both levels touched is more likely to have hit the stop first; strong positive delta suggests TP first. The exit reason is still `tp_sl_ambiguous` but the resolution is `delta_inferred` and the chosen price is recorded.

3. **`tick_verified`.** If sub-bar tick data is available (it usually isn't from TradeStation historical), use the actual sequence to determine the order. Reserved for future enhancement.

4. **`optimistic`.** Always assume TP was hit first. **This is forbidden by default.** It can only be used by setting `tp_sl_ambiguity_resolution: optimistic` in the strategy config, with a comment explaining why, and the data scientist persona will flag it.

The choice is recorded in the trade log's `exit_resolution_method` field so any downstream analysis can filter out ambiguous bars or treat them differently.

**End-of-day flat for single-instrument strategies.** Per `CLAUDE.md`'s standing rules and the mentor's guidance, single-instrument trades are flat by end of day unless the strategy is explicitly a pairs/spread strategy. The engine enforces this with a config-level flag:

```yaml
# In a strategy config
exit_rules:
  end_of_day_flat: true
  flat_time_ny: "15:00"
  daily_loss_limit_usd: 600
  weekly_loss_limit_usd: 2000
```

When `end_of_day_flat: true`, the engine forces a market exit on any open position at the configured time. The exit reason is `eod_flat`. This is non-overridable for any strategy with `category: single_instrument`. Pairs strategies set `category: pairs` and the EOD flat default is off.

## Re-entry handling

Per `CLAUDE.md`, planned re-entries are permitted when triggered by a fresh, pre-defined signal, with combined risk and combined target defined before the second entry. The engine supports this via the `Signal.action == "reentry"` path.

**Contract for re-entries:**

1. The strategy emits a `Signal` with `action="reentry"` and `parent_trade_id` set to the original trade's ID.
2. The signal must include the **combined target** and **combined risk** for the merged position. These are validated by the engine before the re-entry order is placed.
3. The engine merges the re-entry into the existing position. The position's exit conditions are updated to use the new combined target and combined risk.
4. The trade log records the re-entry as a separate row with `is_reentry=true` and `parent_trade_id` populated, but P&L is computed against the merged position.
5. If the re-entry signal lacks combined target/risk, the engine refuses the signal and logs a warning. A re-entry without these fields is averaging-down in disguise and is forbidden.

**The MACD divergence example from the conversation history:**

```python
class MacdDivergenceStrategy(Strategy):
    def on_bar(self, bar_index, bars, state):
        signals = []

        # ... compute current MACD divergence signal

        if has_divergence_signal and not state.has_open_position():
            # Initial entry
            signals.append(Signal(
                side="long",
                action="enter",
                size=1.0,
                take_profit_price=entry_price + 30 * tick_size,
                stop_loss_price=entry_price - 20 * tick_size,
                timeout_bars=20,
                indicator_snapshot=self.snapshot_indicators(bar_index),
            ))

        elif state.has_open_position() and self._histogram_rotated_back(bar_index):
            # Re-entry on histogram rotation back into trade direction
            open_trade = state.open_positions[0]
            combined_target = self._compute_combined_target(open_trade, current_price)
            combined_risk = self._compute_combined_risk(open_trade, current_price)

            signals.append(Signal(
                side="long",
                action="reentry",
                parent_trade_id=open_trade.trade_id,
                size=1.0,
                take_profit_price=combined_target,
                stop_loss_price=open_trade.stop_loss_price,  # keep original stop
                indicator_snapshot=self.snapshot_indicators(bar_index),
                notes="MACD histogram rotation re-entry",
            ))

        return signals
```

The engine validates that `combined_target` and `combined_risk` are present, that the side matches the parent trade, and that the resulting combined position respects the daily loss limit. If any check fails, the signal is rejected with a logged warning.

## Walk-forward harness

A single train/test split is the weakest form of validation. Walk-forward is the standard. The engine supports walk-forward as a wrapper around the basic backtest loop:

```python
# src/trading_research/backtest/walkforward.py
from dataclasses import dataclass
from datetime import date, timedelta

@dataclass
class WalkForwardConfig:
    train_window_days: int       # e.g. 180
    test_window_days: int        # e.g. 30
    step_days: int               # e.g. 30 (overlapping windows = step < test)
    purge_gap_days: int = 0      # gap between train and test to prevent label leakage
    refit_every_step: bool = True  # whether to refit strategy params each step

def run_walk_forward(
    strategy_class: type[Strategy],
    bars: pl.DataFrame,
    instrument: Instrument,
    base_config: dict,
    wf_config: WalkForwardConfig,
) -> WalkForwardResult:
    """Run a walk-forward backtest.

    For each step:
        1. Define train and test windows (with optional purge gap)
        2. Optionally refit the strategy's parameters on the train window
        3. Run the backtest on the test window using those parameters
        4. Collect the test trades and metrics
    Combine all test windows into a single out-of-sample equity curve.
    """
    results = []
    current_start = bars["timestamp_ny"].min()
    end_date = bars["timestamp_ny"].max()

    while current_start + timedelta(days=wf_config.train_window_days + wf_config.purge_gap_days + wf_config.test_window_days) <= end_date:
        train_start = current_start
        train_end = train_start + timedelta(days=wf_config.train_window_days)
        test_start = train_end + timedelta(days=wf_config.purge_gap_days)
        test_end = test_start + timedelta(days=wf_config.test_window_days)

        train_bars = bars.filter(
            (pl.col("timestamp_ny") >= train_start) &
            (pl.col("timestamp_ny") < train_end)
        )
        test_bars = bars.filter(
            (pl.col("timestamp_ny") >= test_start) &
            (pl.col("timestamp_ny") < test_end)
        )

        if wf_config.refit_every_step:
            fitted_config = fit_strategy_params(strategy_class, train_bars, base_config)
        else:
            fitted_config = base_config

        strategy = strategy_class(fitted_config, instrument)
        step_result = run_backtest(strategy, test_bars, fitted_config)
        results.append(step_result)

        current_start += timedelta(days=wf_config.step_days)

    return combine_walk_forward_results(results)
```

**The purge gap matters.** When a strategy uses multi-bar holding periods or any feature that overlaps in time, a label at the end of the train window can be predictive of a label at the start of the test window because they share underlying bars. The purge gap (typically equal to the maximum holding period) prevents this leakage. The default is 0 (no purge), but any strategy with multi-bar exits should set it.

**Refitting per step.** The default is to refit any tunable parameters at each step, which is the realistic simulation of "retrain the model periodically." Strategies with no fitted parameters (pure rule-based) can disable this.

## Run artifacts

Every backtest run produces a directory under `runs/<run_id>/` with the following contents:

```
runs/2025-01-15_zn_macd_rev_v1_walkforward/
├── config.yaml              # the exact config used for this run
├── trades.parquet           # trade log conforming to the trade schema
├── equity.parquet           # equity curve as (timestamp, cum_pnl_usd_net)
├── walkforward_steps.json   # per-step metadata (windows, fitted params, metrics)
├── log.jsonl                # structured log of the entire run
├── charts/                  # generated by the eval module after the run completes
│   ├── equity_curve.png
│   ├── drawdown.png
│   └── ...
├── report.html              # one-page evaluation report
└── data_source.json         # which data file was used (path, hash, version)
```

**Run IDs** are generated as `YYYY-MM-DD_<strategy_id>_<run_type>`. They're sortable by date and self-describing. If multiple runs of the same strategy happen in one day, a numeric suffix is added (`_2`, `_3`, etc.).

**The data_source.json file** records the exact data file used, its hash, and its version. Six months later when reviewing this run, you can verify whether the data has been re-downloaded since.

## Standing rules this skill enforces

1. **Default fill model is `next_bar_open`.** Overrides require explicit config and justification.
2. **TP/SL ambiguity resolves pessimistically.** Optimistic resolution requires explicit override and is flagged loudly.
3. **Slippage is non-zero by default** (1 tick) and added in the direction that hurts the strategy.
4. **Commissions are non-zero by default** ($1.50/side) and slightly higher than TradeStation's actual rate.
5. **Single-instrument strategies enforce end-of-day flat.** This is non-overridable for `category: single_instrument`.
6. **Re-entries require combined target and combined risk.** Without these, the signal is rejected.
7. **No backtest runs against unvalidated data.** The engine refuses to read from `data/raw/` and refuses to read from `data/clean/` if the quality report is missing or `passed: false`.
8. **Every run produces a complete artifact directory.** Trades, equity, config, log, data_source, and charts. Partial outputs are a bug.
9. **The strategy interface is enforced.** Strategies that read past `bar_index` get caught by the test harness.
10. **Walk-forward is the default validation method.** Single train/test splits require explicit justification.

## When to invoke this skill

Load this skill when the task involves:

- Implementing a new strategy
- Modifying an existing strategy's logic
- Building or modifying the simulation engine itself
- Implementing or tuning fill, slippage, or commission models
- Setting up walk-forward parameters for a new strategy
- Debugging unexpected backtest results
- Designing the run artifacts for a new evaluation workflow

Don't load this skill for:

- Indicator implementation (use `indicators`)
- Position sizing (use `risk-management`)
- Computing metrics from a trade log (use `strategy-evaluation`)
- Visualizing backtest results (use `charting` and `trade-replay`)

## Open questions for build time

1. **Vectorized first-pass for parameter sweeps.** A pure event-driven backtest is too slow for 10,000-variant parameter sweeps. One option: do a fast vectorized first pass to identify the top N candidates, then run event-driven backtests only on those. The vectorized pass would be explicitly marked as a screening tool, not a final result. Defer until parameter sweep speed becomes a real bottleneck.
2. **Multi-instrument backtests for pairs.** The current architecture handles a single instrument's bars at a time. Pairs trading needs synchronized bars from two instruments. The right approach is probably a `MultiInstrumentBacktest` wrapper that aligns bars from both instruments by timestamp before feeding the strategy. Build when pairs strategies come online.
3. **Margin enforcement during backtests.** Should the engine refuse trades that would exceed available margin? Probably yes, and it should compute both the theoretical CME margin and the actual broker margin (per the mentor's pairs-margin warning). Defer until risk-management is built; it's the right place for the margin model.
4. **Streaming-mode backtest for live validation.** Running the same strategy code against historical bars (backtest) and live bars (paper or production) should produce identical results bar-for-bar. The engine should be designed so the same `Strategy.on_bar()` method works in both modes. This is a property to verify when streaming-bars and live-execution come online.
