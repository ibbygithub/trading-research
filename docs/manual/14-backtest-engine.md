# Chapter 14 — The Backtest Engine

> **Chapter status:** [EXISTS] — every section in this chapter documents a
> capability present at the current commit. No code changes are needed to
> make this chapter accurate. Cite paths against
> `src/trading_research/backtest/engine.py`,
> `src/trading_research/backtest/fills.py`, and
> `src/trading_research/strategies/mulligan.py`.

---

## 14.0 What this chapter covers

The backtest engine is the simulation core that converts a strategy's
signals into a trade log. It is the most consequential component in the
platform: every metric, every confidence interval, every deflated Sharpe
reported in the Trader's Desk Report is downstream of what the engine
decides about fills, costs, and exits. Getting the engine right is more
important than getting it fast.

This chapter documents the engine's design decisions, fill models, cost
model, TP/SL resolution logic, the EOD-flat mechanism, the max-holding-bars
time stop, and the Mulligan controller for planned scale-ins. After reading
this chapter you will understand not just what the engine does, but *why*
each choice was made pessimistically.

---

## 14.1 Engine design principles

The engine's design priorities are stated in the module docstring
([`src/trading_research/backtest/engine.py:1`](../../src/trading_research/backtest/engine.py)):
auditability over speed, bar-by-bar walk over vectorisation.

### 14.1.1 Bar-by-bar iteration, not vectorisation

The engine iterates the dataset one bar at a time using a Python `for`
loop:

```python
bar_list = list(bars.itertuples())
for i, bar in enumerate(bar_list):
    # 1. If in position: check exit conditions
    # 2. If not in position: check entry signal
```

This is deliberately slower than a vectorised implementation. The advantage
is that the simulation respects causality without any special-casing:
information at bar *T* is never available at bar *T-1*, because the loop
never looks backwards in the price series, only at the current and next bar.

Vectorised engines are faster but dangerous. It is straightforward to write
vectorised code that accidentally uses bar T's close to compute a signal and
fills at bar T's open — leak in both directions. The bar-by-bar walk
prevents this class of bug structurally, not by programmer discipline.

> *Why this:* mean-reversion futures strategies typically run at 5m or 15m
> bars over a 16-year history. The dataset is large enough that performance
> matters, but even the bar-by-bar implementation runs a full ZN backtest
> in under a minute on a modern laptop. Vectorised speed is not needed.
> Auditability is. When a trade in the replay app looks wrong, being able to
> step through the engine's logic in a debugger — and having confidence that
> the debugger shows exactly what the production simulation did — is worth
> every millisecond of the slow path.

### 14.1.2 The three-phase loop

The engine's inner loop has three sequential phases per bar:

**Phase 1 — Exit check (when in a position).** For each bar while the
engine holds a position, it checks exit conditions in priority order:

1. EOD flat: is this bar at or past the session's RTH close?
2. Time limit: has the position been held for `max_holding_bars` bars?
3. TP/SL: does the bar's range include the stop or target price?
4. Strategy exit rules: does the `Strategy.exit_rules()` Protocol method
   return anything other than "hold"?
5. Signal reversal: is there an opposing signal in `signals_df` at this bar?

The first condition that fires determines the exit. EOD and time-limit
checks happen before TP/SL so that a position is never kept open beyond
session boundaries regardless of where TP/SL are set.

**Phase 2 — Entry check (when not in a position).** After any exit (or when
the engine starts a bar flat), it checks the `signal` column of
`signals_df`. A non-zero signal triggers an entry at the next bar's open
(under `NEXT_BAR_OPEN`, the default fill model).

**Phase 3 — End-of-data sweep.** After the bar loop, if the engine is still
holding a position (which can happen when data ends mid-session), it
force-closes at the last bar's close with exit reason `"eod"`.

### 14.1.3 Public API

```python
engine = BacktestEngine(config, instrument_spec, strategy=None)
result = engine.run(bars_df, signals_df)

result.trades       # pd.DataFrame conforming to TRADE_SCHEMA
result.equity_curve # pd.Series: cumulative net_pnl_usd indexed by exit_ts (UTC)
```

`bars_df` is the FEATURES parquet loaded by the `backtest` CLI — a tz-aware
UTC DatetimeIndex with at minimum `open`, `high`, `low`, `close`.
`signals_df` has the same index and a `signal` column (`+1` long, `-1`
short, `0` flat) plus optional `stop` and `target` columns.

---

## 14.2 Fill models

The engine supports two fill models, controlled by
`BacktestConfig.fill_model`
([`engine.py:48`](../../src/trading_research/backtest/engine.py)).

### 14.2.1 NEXT_BAR_OPEN (default)

Signal fires at bar T. The fill executes at bar T+1's open ± slippage.

```python
# fills.py:64
if model == FillModel.NEXT_BAR_OPEN:
    base = float(next_bar["open"])
```

This is the honest default. The strategy cannot have acted on bar T's
close until bar T has closed. Any latency between signal generation and
order routing means the fill will be somewhere in bar T+1. Using bar
T+1's open is slightly optimistic (in practice you might miss a gap
open), but it is defensible and it is what TradeStation's Strategy
Performance Report uses as its default.

> *Why next-bar-open and not next-bar-close or TWAP:* next-bar-open is
> conservative and simple. It cannot be worse than TWAP on trending bars
> (you get the open, not the end of the move), and it prevents the
> classic backtest optimism of "my strategy triggered at the 9:45 bar but
> the simulator filled me at 9:45:01 at the VWAP for the day." Bar
> T+1 open is the worst fill you'd have expected if you submitted a
> market order immediately.

### 14.2.2 SAME_BAR (requires justification)

Signal fires and fill executes at bar T's close.

```python
# engine.py:62
if self.fill_model == FillModel.SAME_BAR and not self.same_bar_justification.strip():
    raise ValueError(
        "same_bar_justification must be non-empty when fill_model is SAME_BAR."
    )
```

`SAME_BAR` is only permitted when `BacktestConfig.same_bar_justification`
contains a non-empty string. The engine raises `ValueError` at
construction time if this guard is violated — you cannot get to `run()`
with `SAME_BAR` fills without writing down why you need them.

The justification requirement is not bureaucracy. Same-bar fills mean
the strategy is assumed to have observed the signal during the bar and
acted before the bar closed. This is only defensible for strategies
that produce signals based solely on information available at the bar's
open (e.g. a gap-open strategy where the signal fires at 09:31 and the
fill is at the 09:31 bar close). Any strategy that uses the bar's close
to generate the signal and also fills at the bar's close is look-ahead,
and `SAME_BAR` will produce optimistic results.

In the strategy YAML:

```yaml
backtest:
  fill_model: same_bar
  same_bar_justification: "Open-price strategy: signal uses only the bar's open; fill at same-bar close is within the bar's information set."
```

---

## 14.3 Cost model

The cost model applies two charges to every trade: slippage and
commission.

### 14.3.1 Slippage

Slippage is expressed as a number of ticks per side, charged adversely:

```python
# fills.py:62
slip = slippage_ticks * tick_size
return base + direction * slip  # long fills higher, short fills lower
```

The default comes from `instruments.yaml` under each instrument's
`backtest_defaults.slippage_ticks`. For ZN (10-Year Treasury Note),
the default is 1 tick per side (1/64th of a point = $15.625 per
contract). For 6E (Euro FX), it is 1 tick ($12.50 per contract).

These defaults are deliberately pessimistic relative to the fills an
experienced operator would typically achieve — particularly in RTH
liquidity. A 1-tick default assumes you are always the price-taker and
there is always half a bid-ask of adverse selection. In practice your
fills will often be better. Using a worse assumption in the backtest
means the live results beat expectations rather than disappoint them.

### 14.3.2 Commission

Commission is charged as a flat USD amount per side per contract,
sourced from `backtest_defaults.commission_usd` in `instruments.yaml`.
The engine charges it on both entry and exit:

```python
# engine.py:484
comm_usd = self._commission_per_side * 2 * qty
net_pnl_usd = pnl_usd - slip_usd - comm_usd
```

### 14.3.3 Per-config overrides

Both slippage and commission can be overridden in `BacktestConfig`:

```python
BacktestConfig(
    ...
    slippage_ticks=0.5,      # override instrument default
    commission_rt_usd=4.50,  # full round-trip (not per-side)
)
```

Config overrides take precedence over instrument defaults. Use them when
testing a specific broker's rate or when modelling a scenario with worse
fills than the instrument default. Never set them to zero to make a
backtest look better — that is lying to yourself.

---

## 14.4 TP/SL resolution

When the engine holds an open position, each bar is examined for whether
the stop or target price has been hit. The logic lives in
[`src/trading_research/backtest/fills.py:73`](../../src/trading_research/backtest/fills.py)
(`resolve_exit`).

### 14.4.1 Unambiguous bars

If only one level is inside the bar's range, that level triggered:

```python
stop_hit  = bar_low  <= stop   # for longs: low breaches below stop
target_hit = bar_high >= target  # for longs: high reaches the target
```

For shorts the direction reverses: stop hits when `bar_high >= stop`,
target hits when `bar_low <= target`.

### 14.4.2 Pessimistic resolution for ambiguous bars

An ambiguous bar is one where both the stop and the target are inside
the bar's range — meaning both levels were hit at some point during the
bar, and the simulator cannot know which hit first without sub-bar data.

The engine resolves ambiguous bars pessimistically: **the stop wins**.

```python
if stop_hit and target_hit:
    return ("stop", stop)
```

This is the correct default for a strategy that claims to be
risk-controlled. Assuming the target hit first on every ambiguous bar
produces a flattering backtest. Assuming the stop hit first produces an
honest one. The difference compounds over thousands of trades.

> *Why pessimistic resolution is non-negotiable:* a bar where both stop
> and target are inside the range is a volatile bar. Volatile bars are
> exactly the bars where your stop is most likely to have been triggered
> first — either by a sweep of retail stops before the reversal, or
> simply by the market hitting the lower level before the higher one.
> The pessimistic assumption is not just conservative; it is directionally
> correct for mean-reversion strategies where stops are close to entry
> and targets are further away.

### 14.4.3 OFI-based resolution (opt-in)

When `use_ofi_resolution: true` is set in the strategy's `backtest:`
block, the engine uses the bar's `buy_volume` and `sell_volume` to
infer which level hit first:

```python
ofi_ratio = (bv - sv) / (bv + sv)  # -1 = all selling, +1 = all buying

if direction == 1:   # long
    return ("target", target) if ofi_ratio > 0 else ("stop", stop)
```

The logic: a bar dominated by buy volume on a long trade suggests the
upward move (target) happened first; a bar dominated by sell volume
suggests the downward move (stop) happened first. The inference is
imperfect — OFI at the 1-minute bar level is noisy — but it is better
than always assuming the worst on every ambiguous bar, particularly
for strategies that have genuine directional conviction.

OFI resolution falls back to pessimistic if `buy_volume` or
`sell_volume` is null or zero (a real situation for older TradeStation
data). The fallback is logged:

```
ofi_fallback_to_pessimistic  bar_ts=2024-03-15T14:30:00+00:00
```

---

## 14.5 EOD flat

`eod_flat: true` (the default) closes any open position at the last
RTH bar of each trading session.

### 14.5.1 How it fires

At each bar while in a position, the engine checks:

```python
# engine.py:422
def _is_eod(self, bar: pd.Series) -> bool:
    if self._session_close is None:
        return False
    # Prefer timestamp_ny column; fall back to tz_convert on the index.
    bar_time = ts_ny.time()
    return bar_time >= self._session_close
```

`self._session_close` is the instrument's `rth.close` time from
`instruments.yaml`. For ZN it is 15:00 ET; for FX instruments (6E, 6A,
6C, 6N) it is 17:00 ET. If `eod_flat: false`, `_session_close` is
`None` and the check always returns `False`.

The exit price on an EOD close is the current bar's close minus adverse
slippage — the engine does not wait for the next bar, because there is
no trading in the maintenance halt:

```python
# engine.py:448
def _exit_fill(self, bar: pd.Series, direction: int) -> float:
    slip = self._slippage_ticks * self._tick_size
    return float(bar["close"]) - direction * slip
```

### 14.5.2 Why default-on for intraday strategies

Overnight gap risk is asymmetric for single-instrument strategies.
Central bank announcements, geopolitical events, and macro surprises can
move ZN or 6E several full ATRs in a gap open. A 15-tick stop that
would have limited a loss during RTH hours offers no protection against
a 60-tick gap open.

EOD flat is the only structural defence against this risk in a backtest
that uses historical intraday data. Any strategy that does not flatten
by end-of-session is implicitly assuming it can tolerate gap risk —
an assumption that must be explicit, not an accidental omission.

Pairs and spread strategies are different: the two legs partially hedge
each other against headline shocks, and the spread's mean-reversion
thesis operates on a slower timescale that may justify multi-day holds.
The EOD flat override for pairs strategies should be accompanied by a
documented rationale and a review of the spread's overnight gap
behaviour in historical data.

---

## 14.6 Max holding bars

`max_holding_bars` is a time-stop fallback: if a position has been open
for this many bars without hitting a stop, target, EOD flat, or signal
exit, the engine closes it at the current bar's close.

```yaml
backtest:
  max_holding_bars: 26   # ~6.5 RTH hours at 15m bars
```

### 14.6.1 Null vs. a large number

`max_holding_bars: null` (the default) disables the time stop entirely.
This is *not* the same as `max_holding_bars: 9999`. The distinction:

- `null` means the time stop is inactive, and the engine will hold a
  position indefinitely if no other exit fires. This is appropriate for
  strategies with explicit stop/target levels that the engine will
  eventually hit.
- A large integer means the time stop is active but set so loosely it
  almost never fires. This is rarely what you want — it leaves a silent
  parameter lurking in the config.

Use `null` when you have a well-defined stop and target. Use a specific
number when your strategy uses `signal`-driven exits (when a counter-
signal fires rather than a price level) and you want a backstop against
a position that never generates a counter-signal.

### 14.6.2 Sizing max_holding_bars

A useful heuristic is to set `max_holding_bars` to the maximum hold
time you'd accept in live trading, expressed in bars. For a 5m
strategy where you'd never hold a position more than 4 hours:

```
4 hours × 12 bars/hour = 48 bars
```

The time stop should be generous enough not to fire on normal trades
but tight enough to cut positions that are clearly failing.

---

## 14.7 The Mulligan controller

The Mulligan controller enables planned scale-ins into an existing
position on a fresh, pre-defined signal. It enforces the distinction
the platform draws between a legitimate technique and the most dangerous
habit in mean-reversion trading: averaging down.

The controller lives in
[`src/trading_research/strategies/mulligan.py`](../../src/trading_research/strategies/mulligan.py).

### 14.7.1 The distinction the controller enforces

**Averaging down** means adding to a losing position because the price
has moved further against you and you want it to come back. The trigger
is the P&L state, not a signal. The result is maximum exposure at the
worst moment.

**A planned Mulligan scale-in** means adding a second lot when a fresh,
independent signal confirms the original thesis. The trigger is a new
signal bar, not the position's loss. The combined risk (stop and target
for the total position) is computed before the second entry is placed.

The Mulligan controller makes this distinction operational by enforcing
three rules mechanically.

### 14.7.2 Rule M-1 — fresh signal required

The candidate signal's timestamp must be strictly later than the
timestamp of the last signal consumed by this controller:

```python
if candidate_signal.timestamp <= self._last_consumed_ts:
    raise MulliganViolation(
        f"Rule M-1: signal timestamp not strictly later than last consumed"
    )
```

The controller also checks that the new signal is in the same direction
as the open position. An opposing signal at this point is a reversal
cue, not a scale-in signal.

The engine owns the `MulliganController` instance; strategy code never
holds a reference to it. This makes `last_consumed_ts` tamper-resistant
— a strategy module cannot advance the freshness anchor to approve its
own scale-in.

### 14.7.3 Rule M-2 — directional price gate

For a long position, the scale-in price must be no more than `n_atr ×
ATR` below the original entry price:

```python
floor = position.entry_price - gate_offset   # Decimal arithmetic
if new_entry_price < floor:
    raise MulliganViolation(f"Rule M-2: long scale-in too far below entry")
```

For shorts, the ceiling is `original_entry + n_atr × ATR`.

The default `n_atr` knob value is 0.3 — intentionally loose, designed
to allow scale-ins at prices close to the original entry (the signal
confirmed quickly) while blocking scale-ins that are chasing a
deteriorating position. The knob is exposed for sweeping:

```yaml
knobs:
  mulligan_enabled: true
  mulligan_n_atr: 0.3
  mulligan_max_scale_ins: 1
  mulligan_target_atr: 0.3
```

### 14.7.4 Rule M-3 — combined risk pre-defined

Before the scale-in fill is applied, `combined_risk()` computes the
stop and target for the combined position:

```python
combined_size = orig.size + scale_in_size
combined_avg_entry = (
    orig.entry_price * orig.size + new_entry_price * scale_in_size
) / combined_size

# Stop: unchanged from the original thesis-invalidation level.
combined_stop = orig.stop

# Target: anchored to weighted average entry, ATR-multiples away.
combined_target = combined_avg_entry + target_offset  # for longs
```

The combined stop is the original stop — the thesis-invalidation level
does not change just because a second lot was added. The combined target
is set from the average entry price, so it is meaningful even after
price has moved away from session VWAP.

Combined dollar risk is logged but not a hard block at this stage. The
`max_scale_ins=1` cap is the primary size limiter — the default
configuration permits at most one Mulligan scale-in per position.

### 14.7.5 How the engine records scale-in trades

When a scale-in succeeds, the engine emits *two* trade records at close
time: one for the original leg and one for the Mulligan leg. Both carry
the shared exit fields (exit_trigger_ts, exit_ts, exit_price,
exit_reason) because the legs exit together. Each carries its own
entry timestamps and entry price. This design lets the trade log show
the exact economics of each leg separately — the original leg's P&L and
the Mulligan leg's P&L are independently attributed.

### 14.7.6 MulliganViolation

`MulliganViolation` is raised by `check_scale_in()` when any of M-1,
M-2, or the `max_scale_ins` cap is violated. The engine catches it,
logs it, and proceeds without the scale-in — the original position
remains open unmodified. This is the correct behaviour: a rejected
scale-in is not a position exit.

---

## 14.8 What the engine does not do

Staying explicit about the engine's scope prevents scope creep and
false confidence.

**Multi-position sizing and portfolio limits.** The engine simulates
one position at a time, for one strategy, on one instrument. It does
not enforce portfolio-level concentration limits, does not net exposures
across correlated strategies, and does not cap total risk at the account
level. Portfolio-level constraints live in `eval/portfolio.py` and are
applied analytically on the trade log after the fact, not during
simulation.

**Broker reconciliation.** The engine produces a hypothetical trade log.
It has no concept of broker fills, partial fills, order queuing, or
reject-and-retry logic. These belong in the live-execution layer, which
is out of scope for v1.0 (see §3.5 and Chapter 48).

**Daily loss limits in the simulator.** The `BacktestConfig` does not
enforce a daily loss limit that would halt the strategy mid-session.
This is a known gap ([GAP] in §35.2). The limit exists conceptually —
the standing rules require it for any paper or live strategy — but the
backtest engine does not simulate it. A strategy's backtest P&L may
therefore be slightly better than its live P&L when the loss limit would
have halted the strategy on a bad day.

**Fractional contracts.** `quantity` is an integer. Volatility targeting
(Chapter 36) can compute fractional contract sizes, but the engine
rounds to the nearest integer. There is no fractional position.

---

## 14.9 Related references

### Code modules

- [`src/trading_research/backtest/engine.py`](../../src/trading_research/backtest/engine.py)
  — `BacktestConfig`, `BacktestEngine`, `BacktestResult`. The complete
  implementation referenced throughout this chapter.

- [`src/trading_research/backtest/fills.py`](../../src/trading_research/backtest/fills.py)
  — `FillModel`, `apply_fill`, `resolve_exit`, `_resolve_via_ofi`. The
  fill model and TP/SL resolution logic.

- [`src/trading_research/strategies/mulligan.py`](../../src/trading_research/strategies/mulligan.py)
  — `MulliganController`, `combined_risk`, `MulliganViolation`,
  `CombinedRisk`. The scale-in guard.

- [`src/trading_research/data/schema.py`](../../src/trading_research/data/schema.py)
  — `TRADE_SCHEMA` — the schema the engine's output conforms to.
  See Chapter 15.

### Configuration

- [`configs/instruments.yaml`](../../configs/instruments.yaml) — source
  of `backtest_defaults.slippage_ticks` and
  `backtest_defaults.commission_usd` used by the cost model.

### Other chapters

- **Chapter 15** — Trade Schema & Forensics: the `TRADE_SCHEMA` field
  definitions and how to read a trade log.
- **Chapter 16** — Running a Single Backtest: the `backtest` CLI command
  and output artefacts.
- **Chapter 22** — Walk-Forward Validation: how the engine is invoked
  repeatedly over folded data.
- **Chapter 38** — Re-entries vs Averaging Down: the mentor and data
  scientist perspectives on the Mulligan technique.

---

*End of Chapter 14. Next: Chapter 15 — Trade Schema & Forensics.*
