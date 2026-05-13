# Chapter 15 — Trade Schema & Forensics

> **Chapter status:** [EXISTS] — every section documents an existing
> capability. The `TRADE_SCHEMA` is authoritative in
> `src/trading_research/data/schema.py:107`.

---

## 15.0 What this chapter covers

Every backtest the engine runs produces a trade log conforming to
`TRADE_SCHEMA`. This chapter defines each field, explains why the schema
records two timestamp pairs per trade, maps the exit reasons to their
exit-trigger logic, and shows how to load and navigate a trade log.
After reading this chapter you will be able to read a raw trades parquet
and know exactly what happened in each trade — which bars the signal
fired on, which bars the fills executed on, and where in the trade's
life the stop or target resided.

---

## 15.1 The TRADE_SCHEMA contract

`TRADE_SCHEMA` is a PyArrow schema defined in
[`src/trading_research/data/schema.py:107`](../../src/trading_research/data/schema.py).
It is the contract between the backtest engine and every downstream
consumer: the eval layer, the bootstrap CI engine, the walk-forward
aggregator, and the replay app.

```python
TRADE_SCHEMA: pa.Schema = pa.schema([
    pa.field("trade_id",         pa.string(),   nullable=False),
    pa.field("strategy_id",      pa.string(),   nullable=False),
    pa.field("symbol",           pa.string(),   nullable=False),
    pa.field("direction",        pa.string(),   nullable=False),  # "long" | "short"
    pa.field("quantity",         pa.int64(),    nullable=False),
    pa.field("entry_trigger_ts", _TS_UTC,       nullable=False),
    pa.field("entry_ts",         _TS_UTC,       nullable=False),
    pa.field("entry_price",      pa.float64(),  nullable=False),
    pa.field("exit_trigger_ts",  _TS_UTC,       nullable=False),
    pa.field("exit_ts",          _TS_UTC,       nullable=False),
    pa.field("exit_price",       pa.float64(),  nullable=False),
    pa.field("exit_reason",      pa.string(),   nullable=False),
    pa.field("initial_stop",     pa.float64(),  nullable=True),
    pa.field("initial_target",   pa.float64(),  nullable=True),
    pa.field("pnl_points",       pa.float64(),  nullable=False),
    pa.field("pnl_usd",          pa.float64(),  nullable=False),
    pa.field("slippage_usd",     pa.float64(),  nullable=False),
    pa.field("commission_usd",   pa.float64(),  nullable=False),
    pa.field("net_pnl_usd",      pa.float64(),  nullable=False),
    pa.field("mae_points",       pa.float64(),  nullable=True),
    pa.field("mfe_points",       pa.float64(),  nullable=True),
], metadata={b"schema_version": b"trade.v1"})
```

All timestamp fields are nanosecond-precision UTC (`_TS_UTC = pa.timestamp("ns", tz="UTC")`).
All monetary values are in USD. `pnl_points` and `mae_points`/`mfe_points`
are in price points for the instrument (not ticks and not USD).

---

## 15.2 Why two pairs of timestamps per trade

The schema records four timestamps: `entry_trigger_ts`, `entry_ts`,
`exit_trigger_ts`, and `exit_ts`. Understanding why requires understanding
what the engine does at each fill.

### 15.2.1 Entry pair

**`entry_trigger_ts`** — the UTC timestamp of bar T: the bar on which
the signal fired. This is the bar the strategy evaluated to produce
signal = +1 or -1. The strategy cannot have acted until after bar T
closed.

**`entry_ts`** — the UTC timestamp of bar T+1: the bar at whose open
the fill was executed (under the default `NEXT_BAR_OPEN` fill model).
This is when the engine considers the position open. `entry_price` is
bar T+1's open ± slippage.

Under `SAME_BAR` fills, `entry_trigger_ts == entry_ts`: both point to
bar T, because the strategy fills at bar T's close.

### 15.2.2 Exit pair

**`exit_trigger_ts`** — the UTC timestamp of the bar on which the exit
condition was detected. For TP/SL exits, this is the bar whose range
contained the stop or target price. For signal exits, it is the bar
where the opposing signal appeared. For EOD exits, it is the RTH-close
bar.

**`exit_ts`** — the UTC timestamp of the bar where the fill executed.
For TP/SL exits, `exit_ts == exit_trigger_ts` (the fill is inside the
bar). For signal-driven exits, `exit_ts` is the next bar's open under
`NEXT_BAR_OPEN`. For EOD and time-limit exits, `exit_ts == exit_trigger_ts`
(fill at the current bar's close).

### 15.2.3 What this enables in replay

The two-pair design means the replay app can show exactly what the
trade log says: the trigger bar marked with the signal arrow, and the
fill bar marked with the actual entry/exit triangle. On the price chart
you see a small gap between the signal caret and the fill marker — that
gap is the slippage bar, and it is the difference between this engine
and a backtest that tells you what you want to hear.

This is particularly important for detecting look-ahead bugs. If
`entry_trigger_ts == entry_ts` on every trade and `SAME_BAR` was not
specified, there is a bug in signal generation — the signal is using
bar T's close to generate the signal and the engine is somehow filling
at the signal bar. The two-pair schema makes this class of error
immediately visible in the trade log.

---

## 15.3 Exit reasons

`exit_reason` is a non-null string taking one of five values. Each maps
to a specific exit path in the engine.

| exit_reason | Trigger | Fill bar | exit_ts |
|-------------|---------|----------|---------|
| `target` | Bar's high ≥ target (long) or bar's low ≤ target (short) | Same bar | = exit_trigger_ts |
| `stop` | Bar's low ≤ stop (long) or bar's high ≥ stop (short) | Same bar | = exit_trigger_ts |
| `signal` | Opposing signal in signals_df | Next bar open | = next bar ts |
| `eod` | Bar's NY time ≥ RTH session close | Same bar close | = exit_trigger_ts |
| `time_limit` | Position age ≥ max_holding_bars | Same bar close | = exit_trigger_ts |

### 15.3.1 `target` and `stop`

Both execute inside the triggering bar. The exit price is the exact
level (stop or target), not the bar's close. The pessimistic resolution
rule (§14.4.2) applies when both levels are inside the bar's range: in
that case `exit_reason = "stop"` and `exit_price = stop`.

### 15.3.2 `signal`

A signal exit fires when an opposing signal appears while a position is
open. The exit is treated symmetrically to a new entry: it fills at the
next bar's open under `NEXT_BAR_OPEN`, or at the current bar's close
under `SAME_BAR`. The engine then immediately checks for a new entry
from the same opposing signal.

### 15.3.3 `eod`

EOD fires at the first bar at or past the RTH session close. The fill
is the current bar's close minus adverse slippage — not the next bar's
open, because RTH is ending. `exit_price` will typically be the 15:00
ET close for ZN or the 17:00 ET close for FX instruments.

If a position is still open at the last bar of the dataset (a scenario
that occurs when data ends mid-session), the engine also uses `"eod"` as
the exit reason and closes at the last bar's close. This is a
belt-and-suspenders close, not a normal session-end exit.

### 15.3.4 `time_limit`

The time stop fires when `bars_held >= max_holding_bars`. The fill
is identical to an EOD exit: current bar's close minus adverse slippage.

---

## 15.4 MAE and MFE — maximum excursion fields

`mae_points` and `mfe_points` measure how far the trade moved against
and in favour of the position from fill to exit.

### 15.4.1 Tracking logic

The engine tracks `mae_low` (the running minimum of `bar.low` since
fill) and `mfe_high` (the running maximum of `bar.high` since fill):

```python
mae_low  = fill_price          # initialised at fill price
mfe_high = fill_price          # initialised at fill price
# each bar:
mae_low  = min(mae_low,  bar.low)
mfe_high = max(mfe_high, bar.high)
```

At close time:

```python
# For a long:
mae_points = mae_low  - entry_price   # negative = moved against us
mfe_points = mfe_high - entry_price   # positive = moved in our favour

# For a short:
mae_points = entry_price - mfe_high   # negative = moved against us (up)
mfe_points = entry_price - mae_low    # positive = moved in our favour (down)
```

The sign convention: `mae_points` is always negative or zero (adverse
excursion is always against you), `mfe_points` is always positive or
zero (favourable excursion is always in your favour).

### 15.4.2 What MAE and MFE tell you

**Average MAE across all trades** tells you how much room the market
typically needs to move against you before reversing. If your stop is at
−2 ATR and the average MAE is −0.3 ATR, your stop is far too wide and
you are giving back edge. If the average MAE is −1.9 ATR, your stop is
barely not getting hit — adjust it slightly further and the win rate
collapses. The distribution matters more than the average; look at the
MFE/MAE scatter in the Trader's Desk Report (Chapter 17).

**Average MFE across all trades** tells you how much profit the market
typically offers. If your target is at +2 ATR and the average MFE is
+0.8 ATR, your target is almost never being reached — you are leaving
money on the table if the trade can get to +0.8 before reversing. A
target at +0.6 ATR would catch more of the available move.

---

## 15.5 Monetary fields

Three fields attribute the monetary outcome of each trade.

| Field | Formula |
|-------|---------|
| `pnl_usd` | `direction × (exit_price − entry_price) × point_value × quantity` |
| `slippage_usd` | `slippage_ticks × tick_value × 2 × quantity` (entry + exit) |
| `commission_usd` | `commission_per_side × 2 × quantity` |
| `net_pnl_usd` | `pnl_usd − slippage_usd − commission_usd` |

`pnl_points` is `direction × (exit_price − entry_price)` before applying
the point value — useful for comparing strategy performance across
instruments with different contract sizes.

The `net_pnl_usd` column is what every downstream metric is built from.
`pnl_usd` without costs is never used in performance reporting — it is
present for attribution analysis only (how much did slippage and
commission cost this strategy, relative to gross P&L?).

---

## 15.6 Reading a trade log

The trade log is a parquet file at
`runs/<strategy_id>/<YYYY-MM-DD-HH-MM>/trades.parquet`. Load it:

```python
import pandas as pd

trades = pd.read_parquet("runs/zn-macd-v1/2026-05-01-14-30/trades.parquet")
trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
trades["exit_ts"]  = pd.to_datetime(trades["exit_ts"],  utc=True)
```

### 15.6.1 First things to check

**Trade count.** Below 50 trades, every metric in the summary is wide-CI
noise. Below 100 trades, walk-forward results will have high fold
variance. The data scientist persona will flag this; the trade log is
where you verify it.

**Exit reason distribution.** A healthy mean-reversion strategy has most
exits from `target` (the trade worked) and some from `stop` (the trade
failed). An excess of `eod` exits suggests the strategy is not resolving
intraday — either the targets and stops are too wide for the timeframe,
or the entry timing is poor.

**MAE distribution relative to stop.** Filter for winning trades and
look at their MAE: if winning trades regularly have MAE approaching the
stop distance, the strategy is surviving by luck, not by edge.

```python
winners = trades[trades["net_pnl_usd"] > 0]
print(winners["mae_points"].describe())
```

**Time-of-day concentration.** If 60% of trades trigger in the first
30 minutes of RTH, the strategy may be responding to the open-auction
noise rather than a durable pattern.

```python
trades["entry_hour_ny"] = trades["entry_ts"].dt.tz_convert("America/New_York").dt.hour
print(trades.groupby("entry_hour_ny").size())
```

---

## 15.7 Related references

### Code modules

- [`src/trading_research/data/schema.py:107`](../../src/trading_research/data/schema.py)
  — `TRADE_SCHEMA`, `Trade` pydantic model, `TRADE_SCHEMA_VERSION`,
  `empty_trade_table()`.

- [`src/trading_research/backtest/engine.py:462`](../../src/trading_research/backtest/engine.py)
  — `_close_trade()`: the method that assembles each trade record.

- [`src/trading_research/eval/summary.py`](../../src/trading_research/eval/summary.py)
  — `compute_summary()`: primary consumer of the trade log for metrics.

- [`src/trading_research/eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py)
  — `bootstrap_summary()`: resamples `net_pnl_usd` column for CIs.

### Appendices

- **Appendix B** — the complete `TRADE_SCHEMA` field list with types
  and nullability.

### Other chapters

- **Chapter 14** — The Backtest Engine: how each field is populated.
- **Chapter 16** — Running a Single Backtest: where the parquet is
  written and what `summary.json` contains.
- **Chapter 17** — The Trader's Desk Report: how MAE/MFE and exit
  reasons are visualised.
- **Chapter 20** — Behavioural Metrics: `max_consec_losses` and other
  derived metrics built from this schema.

---

*End of Chapter 15. Next: Chapter 16 — Running a Single Backtest.*
