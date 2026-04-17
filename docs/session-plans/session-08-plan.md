# Session 08 — Backtest Engine

## Objective

Build a generic, honest backtesting engine. By end of session:
`uv run trading-research backtest --strategy configs/strategies/<name>.yaml`
runs a strategy against the ZN features data, writes a trade log parquet and
equity curve to `runs/<strategy_id>/<timestamp>/`, and prints a performance
summary. The replay cockpit's `--trades` flag can load the output immediately.

**Generic first. No strategy logic lives in the engine. The engine is a
simulation harness; strategies are config-driven signal generators.**

---

## Entry Criteria

- Session 07 complete: cockpit runs and renders all four panes
- `data/features/` has valid ZN 5m and 15m base-v1 parquets
- `configs/instruments.yaml` has ZN tick_size, tick_value_usd, point_value_usd
- `src/trading_research/backtest/__init__.py` is an empty stub

---

## Context

The engine must be honest before it is fast. The two standing rules that
govern every design decision here:

1. **Next-bar-open fills only** (default). The strategy fires a signal on bar T
   close; the fill executes at bar T+1 open. Same-bar fills require an explicit
   override in the strategy config with a written justification.

2. **Pessimistic TP/SL resolution**. When both stop and target are inside a
   bar's high–low range, the stop is assumed to have hit first. Order-flow
   resolution (using buy_volume/sell_volume to infer which hit first) is opt-in.

The trade log schema records the trigger bar and fill bar separately on both
entry and exit. Without that separation the fill model cannot be audited.

---

## Trade Log Schema (extend `src/trading_research/data/schema.py`)

Add a `TRADE_SCHEMA` PyArrow schema and a `Trade` Pydantic model.

Fields — one row per completed trade:

| Field | Type | Notes |
|---|---|---|
| `trade_id` | string | UUID4, unique per trade |
| `strategy_id` | string | From strategy config |
| `symbol` | string | e.g. "ZN" |
| `direction` | string | "long" or "short" |
| `quantity` | int64 | Contracts |
| `entry_trigger_ts` | timestamp UTC | Bar T close — signal fired |
| `entry_ts` | timestamp UTC | Bar T+1 open — fill executed |
| `entry_price` | float64 | Actual fill price (T+1 open + slippage) |
| `exit_trigger_ts` | timestamp UTC | Bar when exit condition first met |
| `exit_ts` | timestamp UTC | Bar when fill executed |
| `exit_price` | float64 | Actual fill price (+ slippage) |
| `exit_reason` | string | "target", "stop", "signal", "eod", "time_limit" |
| `initial_stop` | float64 | Stop level at entry (nullable) |
| `initial_target` | float64 | Target level at entry (nullable) |
| `pnl_points` | float64 | Raw P&L in price points |
| `pnl_usd` | float64 | pnl_points × point_value_usd × quantity |
| `slippage_usd` | float64 | Total slippage both sides |
| `commission_usd` | float64 | Total commission both sides |
| `net_pnl_usd` | float64 | pnl_usd − slippage_usd − commission_usd |
| `mae_points` | float64 | Max adverse excursion in points |
| `mfe_points` | float64 | Max favourable excursion in points |

Schema version string: `"trade.v1"`

---

## Default Cost Assumptions

Read from `configs/instruments.yaml` where present; fall back to these:

**ZN (10-Year T-Note futures):**
- Slippage: 1 tick each way = $15.625/side = **$31.25 round turn**
- Commission: $2.00/side = **$4.00 round turn**
- Total friction per round trip: **$35.25**

Add to `instruments.yaml` under each instrument:

```yaml
backtest_defaults:
  slippage_ticks: 1        # per side
  commission_usd: 2.00     # per side
```

---

## Step 1 — Trade schema (`src/trading_research/data/schema.py`)

Append `TRADE_SCHEMA` (PyArrow), `Trade` (Pydantic), and
`empty_trade_table()` to the existing schema module.

Tests (`tests/test_trade_schema.py`): round-trip a `Trade` → dict → PyArrow
table → parquet → back to `Trade`; assert all fields survive.

---

## Step 2 — Instrument loader (`src/trading_research/data/instruments.py`)

`load_instrument(symbol: str) -> dict` — reads `configs/instruments.yaml`
and returns the instrument dict for `symbol`.

`get_cost_per_trade(symbol: str) -> tuple[float, float]`
→ `(slippage_usd_round_trip, commission_usd_round_trip)`

Uses `backtest_defaults` from the YAML; raises `KeyError` if symbol not found.

Tests: load ZN, assert tick_value_usd == 15.625, assert costs are non-zero.

---

## Step 3 — Signal interface

Strategies communicate with the engine via a signal DataFrame. The engine
does not care how signals are generated — rule-based, ML, anything.

Convention: a strategy returns a `pd.DataFrame` with the same index as the
input features DataFrame and at least these columns:

| Column | Type | Description |
|---|---|---|
| `signal` | int8 | +1 long, −1 short, 0 flat |
| `stop` | float64 | Stop price for this bar's signal (NaN if no signal) |
| `target` | float64 | Target price (NaN if no signal) |
| `signal_strength` | float64 | Optional confidence score, pass-through to trade log |

Define `SignalFrame` as a simple dataclass wrapping the DataFrame with a
`validate()` method. Validation checks: index matches input, `signal` is
in {-1, 0, 1}, no look-ahead (signal at bar T uses only data through T-1's
close, enforced via an optional `check_lookahead` flag that shifts signal
by 1 and diffs).

File: `src/trading_research/backtest/signals.py`

---

## Step 4 — Fill model (`src/trading_research/backtest/fills.py`)

`FillModel` — enum with values `NEXT_BAR_OPEN` (default) and `SAME_BAR`.

`apply_fill(signal_bar: pd.Series, next_bar: pd.Series, model: FillModel,
            direction: int, slippage_ticks: int, tick_size: float) -> float`

Returns the fill price:
- `NEXT_BAR_OPEN`: `next_bar.open ± slippage_ticks × tick_size`
- `SAME_BAR`: `signal_bar.close ± slippage_ticks × tick_size`
  (only reachable with explicit override; engine raises if used without config flag)

Tests: long fill at next-bar-open adds slippage; short subtracts it.

---

## Step 5 — TP/SL resolver (`src/trading_research/backtest/fills.py`)

`resolve_exit(bar: pd.Series, direction: int, stop: float, target: float,
              use_ofi: bool = False) -> tuple[str, float]`

Returns `(exit_reason, exit_price)`.

Rules:
1. If `target` and `stop` are both NaN → `("open", bar.open)` (signal-driven exit)
2. If only one is set → check that level against bar high/low
3. **Both inside range → `("stop", stop)` pessimistically** (the cardinal rule)
4. `use_ofi=True`: when `buy_volume` and `sell_volume` are present, use their
   ratio to infer which level hit first. If OFI data is missing, fall back to
   pessimistic. Log a warning when fallback occurs.

Tests:
- Ambiguous bar → stop wins
- Target only inside range → target hit
- Neither inside range → neither triggered (position carries to next bar)
- OFI fallback when buy_volume is None

---

## Step 6 — Engine (`src/trading_research/backtest/engine.py`)

`BacktestEngine` — the simulation loop.

```python
@dataclass
class BacktestConfig:
    strategy_id: str
    symbol: str
    fill_model: FillModel = FillModel.NEXT_BAR_OPEN
    same_bar_justification: str = ""   # required when fill_model is SAME_BAR
    max_holding_bars: int | None = None
    eod_flat: bool = True              # close all positions at session end
    use_ofi_resolution: bool = False
    quantity: int = 1
```

`BacktestEngine.run(bars: pd.DataFrame, signals: pd.DataFrame) -> BacktestResult`

Walk the bars forward (iterate, not vectorize — clarity over speed at this
stage). For each bar:
1. If in a position: check TP/SL, check EOD, check max_holding_bars
2. If not in a position and signal != 0: queue entry for next bar
3. On entry bar: compute fill price, record entry fields
4. On exit bar: compute fill price, compute P&L, MAE, MFE, record trade

`BacktestResult`:
```python
@dataclass
class BacktestResult:
    trades: pd.DataFrame        # trade log, conforms to TRADE_SCHEMA
    equity_curve: pd.Series     # cumulative net_pnl_usd indexed by exit_ts
    config: BacktestConfig
    symbol_meta: dict           # from instruments.yaml
```

**MAE/MFE computation:** track `min(bar.low)` and `max(bar.high)` over the
holding period (from entry bar to exit bar inclusive). Convert to points
relative to entry price, then apply direction sign.

EOD flat rule: check `bar.timestamp_ny.time() >= session_close` (read from
instruments.yaml). If in a position and it's the last bar before session end,
exit at that bar's close. `exit_reason = "eod"`.

Tests (`tests/test_engine.py`):
- 3-bar synthetic long: enter T+1 open, exit at target, correct net P&L
- Stop hit on ambiguous bar beats target
- EOD close fires when session_close is reached
- No position carried across session boundary
- MAE and MFE computed correctly over holding period

---

## Step 7 — Strategy config (`configs/strategies/`)

Define a minimal strategy config schema so the CLI has something to run:

```yaml
# configs/strategies/example.yaml
strategy_id: example-v1
symbol: ZN
timeframe: 5m
description: "Placeholder — replace signal_module with a real strategy"

signal_module: trading_research.strategies.example   # must expose generate_signals(df)
signal_params: {}

backtest:
  fill_model: next_bar_open
  eod_flat: true
  max_holding_bars: null
  use_ofi_resolution: false
  quantity: 1
```

Also add `src/trading_research/strategies/example.py` — a trivial always-flat
strategy that returns all zeros. Used only to verify the engine runs end-to-end
without a real signal generator.

---

## Step 8 — CLI command

Add `backtest` subcommand to `cli/main.py`:

```
uv run trading-research backtest --strategy configs/strategies/example.yaml
                                 [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                 [--out runs/]
```

Actions:
1. Load strategy config YAML
2. Load features data for the specified symbol and timeframe
3. Import `signal_module` dynamically, call `generate_signals(df)`
4. Wrap in `SignalFrame`, validate
5. Run `BacktestEngine.run()`
6. Write outputs to `runs/<strategy_id>/<YYYY-MM-DD-HH-MM>/`:
   - `trades.parquet` — trade log
   - `equity_curve.parquet` — cumulative P&L series
   - `summary.json` — performance metrics (see Step 9)
7. Print summary table to terminal

---

## Step 9 — Performance summary (`src/trading_research/eval/`)

`compute_summary(result: BacktestResult) -> dict` — returns these metrics:

| Metric | Notes |
|---|---|
| `total_trades` | Count of completed trades |
| `win_rate` | Fraction with net_pnl_usd > 0 |
| `avg_win_usd` | Mean net_pnl of winners |
| `avg_loss_usd` | Mean net_pnl of losers |
| `profit_factor` | gross_wins / gross_losses |
| `expectancy_usd` | Mean net_pnl per trade |
| `trades_per_week` | total_trades / weeks_in_period |
| `max_consec_losses` | Longest losing streak |
| `sharpe` | Annualised, on daily net_pnl |
| `sortino` | Annualised, downside deviation only |
| `calmar` | Annual return / max drawdown |
| `max_drawdown_usd` | Peak-to-trough on equity curve |
| `max_drawdown_pct` | As fraction of peak equity |
| `drawdown_duration_days` | Calendar days of longest drawdown |
| `avg_mae_points` | Avg max adverse excursion |
| `avg_mfe_points` | Avg max favourable excursion |

Calmar is the headline metric per project convention. Sharpe is reported but
not centred. No deflated Sharpe yet — that requires multiple variants and
comes in a later session when strategy optimisation begins.

File: `src/trading_research/eval/summary.py`
Tests: smoke test on a synthetic 10-trade log with known P&L.

---

## Step 10 — Replay integration

The trade log written to `runs/` must be loadable via:

```
uv run trading-research replay --symbol ZN --trades runs/<run>/trades.parquet
```

Update `replay/data.py` to add `load_trades(path: Path) -> pd.DataFrame`.
Update `replay/app.py` to call `build_trade_markers` when `trades_path` is set.
Update `replay/callbacks.py` to redraw trade markers when date range changes.

The trade log's `entry_ts` and `exit_ts` are UTC timestamps — the replay layer
already handles UTC.

---

## Out of Scope for Session 08

- Walk-forward validation / purged k-fold (session 10)
- Deflated Sharpe / multiple-testing correction (session 10)
- Pairs / spread engine (later session)
- Live or paper order routing (much later)
- Any real strategy logic — the `example` strategy fires zero signals

---

## Success Criteria

| Item | Done when |
|---|---|
| Trade schema | `TRADE_SCHEMA` in schema.py; round-trip test passes |
| Instrument costs | `get_cost_per_trade("ZN")` returns ($31.25, $4.00) |
| Signal interface | `SignalFrame.validate()` catches bad signal values |
| Fill model | Next-bar-open adds slippage correctly for long and short |
| TP/SL resolver | Ambiguous bar → stop wins; OFI fallback tested |
| Engine | 3-bar synthetic test produces correct net P&L |
| EOD flat | Position closed at session end, exit_reason == "eod" |
| MAE/MFE | Computed correctly over holding period |
| CLI | `backtest --strategy example.yaml` runs end-to-end, writes outputs |
| Summary | Calmar, Sharpe, win rate, trades/week printed to terminal |
| Replay | `--trades` flag loads trade log and markers appear on charts |
| Tests | All new tests pass; full suite still green |
