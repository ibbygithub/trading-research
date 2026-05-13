# Chapter 10 — YAML Strategy Authoring

> **Chapter status:** [EXISTS] — all keys and blocks described here are
> implemented and tested. The worked example uses
> `configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml`, which is a
> production backtest config, not a synthetic example.

---

## 10.0 What this chapter covers

This chapter is the practitioner's guide to writing a strategy YAML.
It explains every top-level block, every key, and the exact semantics
of the entry/exit evaluation. It ends with a line-by-line walkthrough
of a real production strategy.

After reading this chapter you will:

- Know the anatomy of a strategy YAML and what each block does
- Be able to write `entry:`, `exits:`, and `backtest:` blocks that
  produce correct signals and fills
- Understand the `all`/`any` combinators, time windows, and how
  conflicts are resolved
- Know how to reference higher-timeframe columns from a joined feature set
- Know when to add a regime filter and how to wire it

Chapter 11 covers expression syntax in depth. Chapter 12 covers regime
filters in depth. Chapter 13 is the alphabetised configuration reference.
This chapter is the authoring guide; those are the reference chapters.

---

## 10.1 Strategy YAML anatomy

A strategy YAML at `configs/strategies/<name>.yaml` has the following
top-level keys:

```yaml
strategy_id:     # string — unique identifier; used in run directory naming
symbol:          # CME root symbol (ZN, 6E, 6A, 6C, 6N, ...)
timeframe:       # bar timeframe (5m, 15m, 60m, 240m)
description:     # human-readable purpose; use YAML block scalar (>)
feature_set:     # feature-set tag (e.g., base-v1); optional if default
higher_timeframes:  # list of additional TF strings to join (optional)

knobs:           # map of name: value; referenced by expressions
  my_knob: 1.5

entry:           # signal conditions (see §10.2)
  long:
    ...
  short:
    ...
  time_window:   # optional; gates entry by UTC hour range
    ...

exits:           # stop and target price levels (see §10.3)
  stop:
    long:  "expression"
    short: "expression"
  target:
    long:  "expression"
    short: "expression"

backtest:        # backtest engine settings (see §10.4)
  fill_model: next_bar_open
  ...

regime_filter:   # single regime filter (optional; see Chapter 12)
  ...
regime_filters:  # list of regime filters (optional; see Chapter 12)
  - ...
```

Keys are optional unless marked required below. The dispatch key
(`entry:`, `template:`, or `signal_module:`) is required and mutually
exclusive — see Chapter 9 §9.4.

---

## 10.2 The `entry` block

The `entry:` block contains the signal conditions for each direction.

### 10.2.1 Direction blocks

```yaml
entry:
  long:
    all:
      - "condition_A"
      - "condition_B"
    any:
      - "condition_C"
      - "condition_D"
  short:
    all:
      - "condition_E"
```

Each direction block (`long:` and `short:`) contains two optional lists:

- **`all:`** — ALL conditions must evaluate to True. The AND of the list.
  If the list is empty or absent, this direction is disabled.
- **`any:`** — AT LEAST ONE condition must evaluate to True. The OR of
  the list. When both `all:` and `any:` are present, both must pass:
  the overall condition is `AND(all) AND OR(any)`.

A direction is disabled (produces no signals) when neither `all:` nor
`any:` has any conditions. This is the correct way to write a long-only
strategy: populate `long:` fully, leave `short:` empty.

### 10.2.2 Conflict resolution

If both `long:` and `short:` conditions evaluate to True on the same bar
— which can happen if the conditions are not symmetric — neither fires.
The conflict is silently resolved in favour of no trade. This matches the
convention used by Python-module strategies.

> *Why this:* conflicting signals are almost always a symptom of a logic
> error in the conditions, not a meaningful ambiguous market state. Firing
> one direction arbitrarily would produce non-deterministic results that
> are hard to reproduce.

### 10.2.3 Time window

```yaml
entry:
  long:
    all:
      - "..."
  time_window:
    start_utc: "12:00"
    end_utc:   "17:00"
```

The `time_window:` key inside `entry:` restricts both directions to bars
within the UTC time range `[start_utc, end_utc)`. Times are in HH:MM
UTC, 24-hour clock. The window is half-open: bars with `timestamp_utc`
on or after `start_utc` AND before `end_utc` are admitted; bars outside
are treated as if no signal fired.

The window is applied after the condition evaluation, before conflict
resolution. A bar outside the window produces `signal=0` regardless of
conditions.

Common patterns:
- London/NY overlap (USD FX): `12:00`–`17:00` UTC
- US bond session (ZN): `13:20`–`20:00` UTC
- All-session (no restriction): omit `time_window:` entirely

> *Why UTC:* timestamps in the features DataFrame are UTC-indexed.
> Expressing the window in UTC avoids DST edge cases; the operator
> converts ETH and RTH windows to UTC at write time, which is a
> one-time calculation. ETH US bonds open at 00:00 UTC (18:00 ET
> previous day); RTH opens at 13:20 UTC (08:20 ET); RTH closes at
> 20:00 UTC (15:00 ET). These do not shift with DST because
> TradeStation reports times in UTC.

---

## 10.3 The `exits` block

The `exits:` block defines price-level expressions for the take-profit
and stop-loss of each direction. These are prices, not distances.

```yaml
exits:
  stop:
    long:  "close - stop_atr_mult * atr_14"
    short: "close + stop_atr_mult * atr_14"
  target:
    long:  "vwap_monthly - target_mult * vwap_monthly_std_1_0"
    short: "vwap_monthly + target_mult * vwap_monthly_std_1_0"
```

Both `stop:` and `target:` are maps of `long:` and `short:` to price
expressions. The expression evaluator computes a price level at the
signal bar. The backtest engine uses these levels as thresholds in the
fill logic on subsequent bars.

**NaN suppression.** If `stop:` evaluates to `NaN` (e.g., because ATR
has not warmed up on early bars), the signal is suppressed: no trade is
opened on that bar. This is the correct behaviour for warm-up periods.
If `target:` evaluates to `NaN`, the target is inactive and the trade is
managed by EOD flat or `max_holding_bars`.

**Both levels are optional.** A strategy with no `stop:` will hold until
either the target is hit, EOD flat fires, or `max_holding_bars` is
exhausted. A strategy with no `target:` will hold until the stop is hit
or the time-based exits fire. A strategy with neither delegates all exit
management to the engine's time-based rules.

> *Why prices, not distances:* prices make the YAML readable and the
> TP/SL logic auditable. "Target is at the VWAP" is a more meaningful
> sentence than "target is 2.3 ATR away," because the actual price level
> is interpretable without knowing the current ATR value.

---

## 10.4 The `backtest` block

The `backtest:` block configures the backtest engine for this specific
strategy. All keys have defaults in the engine's `BacktestConfig`
dataclass
([`src/trading_research/backtest/engine.py:47`](../../src/trading_research/backtest/engine.py)).

```yaml
backtest:
  fill_model: next_bar_open       # default
  same_bar_justification: ""      # required non-empty when fill_model is same_bar
  eod_flat: true                  # default
  max_holding_bars: null          # default (no time-stop)
  use_ofi_resolution: false       # default
  quantity: 1                     # default
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `fill_model` | enum | `next_bar_open` | `next_bar_open` or `same_bar`. See §10.4.1 |
| `same_bar_justification` | string | `""` | Required text when `fill_model: same_bar` |
| `eod_flat` | bool | `true` | Close all positions at the session RTH close |
| `max_holding_bars` | int\|null | `null` | Force-close after N bars; null = disabled |
| `use_ofi_resolution` | bool | `false` | Use order-flow imbalance to break TP/SL ambiguity |
| `quantity` | int | `1` | Fixed contract quantity |

### 10.4.1 Fill models

**`next_bar_open` (default and strongly preferred).** The signal fires at
bar T's close. The fill is executed at bar T+1's open. This is the
honest fill model: the strategy cannot "know" bar T's close price before
it is traded, and the opening price of the next bar is the first
opportunity to execute.

**`same_bar`**: The fill is executed at bar T's close — the same bar
whose conditions generated the signal. This is appropriate only when the
strategy is explicitly designed to trade on a closing cross (e.g., a
market-on-close strategy where the entry condition is confirmed at the
close and the fill is the closing print). It requires a written
justification: `same_bar_justification:` must be non-empty, and the
justification becomes part of the strategy config's audit trail.

Using `same_bar` for a strategy that looks at the close to make an
intraday entry decision is implicit look-ahead. The engine enforces the
non-empty justification to create friction that discourages casual use.

### 10.4.2 EOD flat and time stops

`eod_flat: true` closes any open position at the session's RTH close
time, taken from `configs/instruments.yaml`. For ZN this is 15:00 ET;
for FX (6A, 6C, etc.) this is 17:00 ET. This is the standing default
for single-instrument intraday strategies.

`max_holding_bars: N` is a second time-stop: after N bars, the position
is closed regardless of whether TP or SL has been reached. It is a
backstop, not a primary exit mechanism. Setting it too small relative to
the typical trade duration will clip winning trades. Setting it to `null`
disables the time-stop.

For 15m strategies with a 6-hour RTH session hold budget:
`max_holding_bars: 24` (6 hours × 4 bars/hour) is a reasonable upper
bound. For 60m strategies: `max_holding_bars: 96` (four trading days).

---

## 10.5 Knobs and parameterisation

The `knobs:` block defines scalar values that can be referenced in any
expression — `entry:`, `exits:`, or regime filter parameters.

```yaml
knobs:
  band_mult: 3.0
  stop_atr_mult: 2.0
  adx_max: 20.0
  target_mult: 0.5
```

Knob values are resolved after column names in the evaluator's name
lookup (see §11.2). This means a knob named `close` would shadow the
`close` column — which is never what you want. Use descriptive names
that cannot collide with column names.

**When to use a knob.** A value should be a knob when it is expected
to vary across instruments, strategies, or sweep experiments. Structural
constants (ATR period, Bollinger sigma 2.0, MACD 12/26/9) are
pre-committed and should not appear in `knobs:` — they belong in the
feature-set config.

**Knob sweeping.** The `sweep` CLI command overrides individual knobs
from the command line without modifying the YAML:

```
uv run trading-research sweep \
    --strategy configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml \
    --param target_mult=0.5,1.0,1.5,2.0,2.5
```

Each value runs as a separate trial and is recorded in `runs/.trials.json`
with the `parent_sweep_id` that links all variants in the sweep. See
Chapter 31 for the full sweep reference.

---

## 10.6 Time windows

Time windows restrict entry signals to specific hours within a session.
The syntax is documented in §10.2.3; this section provides the reference
conversion table for common instruments.

| Instrument | Session | UTH hours (UTC) |
|------------|---------|-----------------|
| ZN | Bond globex open → RTH | 00:00–20:00 |
| ZN | RTH only | 13:20–20:00 |
| 6E, 6A, 6C, 6N | London/NY overlap | 12:00–17:00 |
| 6E, 6A, 6C, 6N | Asian session | 22:00–07:00 (next UTC day) |
| 6E, 6A, 6C, 6N | RTH only | 12:00–21:00 |

Note that the Asian session spans the UTC midnight boundary. The evaluator
compares `time_utc ≥ start_utc` and `time_utc < end_utc`; for a window
that crosses midnight (e.g., 22:00–07:00), you would need two windows.
The current evaluator does not support midnight-crossing windows directly;
the workaround is to omit the window and add an explicit `any:` condition
using `shift(hour_utc, 0) >= 22` or similar if an `hour_utc` column is
present. More commonly, simply omit the window for strategies designed to
run all-session.

---

## 10.7 Multi-timeframe references

A strategy can reference indicator columns from a higher timeframe (HTF)
by listing it in `higher_timeframes:` and ensuring the corresponding
feature parquet exists.

```yaml
higher_timeframes:
  - 60m
```

The walk-forward runner and the CLI backtest command load the 60m feature
parquet for the same symbol and tag, join it onto the primary-TF bars via
[`trading_research.backtest.multiframe.join_htf`](../../src/trading_research/backtest/multiframe.py),
and prefix all 60m columns with `tf60m_`. After the join, the primary-TF
DataFrame contains both the 15m columns (unprefixed) and the 60m columns
(prefixed `tf60m_`).

Column naming rule: timeframes that begin with a digit (5m, 15m, 60m)
get a `tf` prefix to produce a valid Python identifier: `5m` → `tf5m_`,
`15m` → `tf15m_`, `60m` → `tf60m_`. The evaluator can then reference
them by the prefixed name:

```yaml
entry:
  long:
    all:
      - "tf60m_ema_20 > tf60m_ema_50"    # 60m trend bias: uptrend
      - "close < vwap_session - entry_atr_mult * atr_14"  # 15m entry
```

> *Why the prefix rather than using the bare 60m column names:* the join
> introduces the 60m bar's values broadcast onto each 15m bar. Without a
> prefix, `ema_20` would be ambiguous — the 15m value or the 60m value?
> The `tf60m_` prefix makes the timeframe of each column explicit in the
> YAML and prevents subtle bugs from silent column shadowing.

The look-ahead rule applies to HTF joins: the 60m value seen at a 15m
bar is the 60m bar that *closed before* the 15m bar began. See §4.6 for
the implementation.

---

## 10.8 A complete worked strategy

This section walks through `configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml`
line by line.

```yaml
# 6A 60m Monthly VWAP Band Fade — v2b (no time window)
#
# Same as v2 but with the time_window gate removed.
# Purpose: isolate the effect of target_mult from the time-of-day effect.
# Session-39: v2 with 08:00–17:00 UTC gate reduced trades from 170 → 52.
# AUD/USD's large mean-reversion moves primarily occur in Asian hours
# (22:00–08:00 UTC), so the gate was filtering the signal, not the noise.
# This variant tests target_mult without the session restriction.
```

The header comment explains *why* this variant exists, not what it is.
This is the right content for a strategy file comment: the decision
context (removing the time window because it was filtering the signal)
and the empirical finding that drove the decision (Asian hours carry the
moves). Without this comment, a future operator reading the YAML cannot
understand why `time_window:` is absent.

```yaml
strategy_id: 6a-monthly-vwap-fade-yaml-v2b
symbol: 6A
timeframe: 60m
description: >
  6A 60m monthly VWAP band fade v2b. No time window — entries at any hour.
  Sweeps target_mult to find the R:R sweet spot. Band_mult, stop_atr_mult,
  and adx_max fixed at session-38 optimal values.
```

`strategy_id` is the run directory prefix: outputs land in
`runs/6a-monthly-vwap-fade-yaml-v2b/<timestamp>/`. The description uses
a YAML block scalar (`>`) for readability. Note that the description
mentions what was swept and what was fixed — this is crucial context for
interpreting old runs.

```yaml
knobs:
  band_mult: 3.0
  stop_atr_mult: 2.0
  adx_max: 20.0
  target_mult: 0.5          # default; sweep 0.5,1.0,1.5,2.0,2.5
```

Four knobs. Three are fixed at their "session-38 optimal values" (which
is a hint that they were chosen from a prior sweep); `target_mult` is the
active sweep variable. The comment documents the sweep range inline — this
matches the sweep invocation in the run history.

`adx_max: 20.0` — ADX values above 20 suppress entry. This is a
structural regime gate built inline as an entry condition rather than
through the `regime_filter:` mechanism; it is simpler and appropriate
because the threshold is expressed as an absolute value that can be
compared directly to the `adx_14` feature column.

```yaml
entry:
  long:
    all:
      - "close < vwap_monthly - band_mult * vwap_monthly_std_1_0"
      - "adx_14 < adx_max"
  short:
    all:
      - "close > vwap_monthly + band_mult * vwap_monthly_std_1_0"
      - "adx_14 < adx_max"
```

Two-condition entry for each direction. The first condition is the
distance-based signal: close is more than `band_mult` standard deviations
outside the monthly VWAP. The second condition is the regime gate: ADX
below the threshold (range-bound market). Both must be True.

Note that `vwap_monthly_std_1_0` is a pre-computed feature column — it is
the 1.0σ band width around the monthly VWAP. This column is defined in
`configs/featuresets/base-v1.yaml` and is available in the 60m feature
parquet. The evaluator resolves `vwap_monthly_std_1_0` as a column, not
a function call.

```yaml
exits:
  stop:
    long:  "close - stop_atr_mult * atr_14"
    short: "close + stop_atr_mult * atr_14"
  target:
    long:  "vwap_monthly - target_mult * vwap_monthly_std_1_0"
    short: "vwap_monthly + target_mult * vwap_monthly_std_1_0"
```

Stop is ATR-scaled from the signal-bar close. Target is inside the VWAP
band at `target_mult` standard deviations. When `target_mult: 0.5`, the
target is halfway between the 1σ band and the VWAP — an early exit
strategy. When `target_mult: 2.0`, the target is at the 2σ band on the
opposite side — a more ambitious exit. This is the sweep parameter.

```yaml
backtest:
  fill_model: next_bar_open
  same_bar_justification: ""
  eod_flat: false
  max_holding_bars: 96
  use_ofi_resolution: false
  quantity: 1
```

`eod_flat: false` is notable. This is a 60m strategy designed to hold
overnight and across sessions. The monthly VWAP mean-reversion thesis
operates on a multi-session timescale; closing at RTH end would cut most
trades before the signal resolves. The strategy is designed to be held
up to 96 bars (four trading days × 24 hours/day / 1 hour/bar = 96 bars)
or until TP/SL, whichever comes first.

> *Why eod_flat: false is correct here:* 6A is an AUD/USD futures contract.
> AUD/USD moves significantly in Asian hours (22:00–08:00 UTC) — the Sydney
> and Tokyo sessions drive much of the instrument's mean-reversion dynamics.
> A strategy that fades a 3σ VWAP extension and then closes at US RTH end
> would never capture the Asian-session resolution. The multi-session hold
> is the hypothesis. Note that this argument does not apply to single-
> instrument equity-index futures or bonds, where overnight gaps and event
> risk are higher.

---

## 10.9 Strategy templates — the Python path

When a strategy's signal logic cannot be expressed in YAML — because it
requires state from prior bars, multi-step computation, or access to
position history — the `template:` dispatch path (Chapter 9 §9.4 Path B)
is the correct choice.

A template is a class decorated with `@register_template` from
[`src/trading_research/core/templates.py`](../../src/trading_research/core/templates.py):

```python
from pydantic import BaseModel, Field
from trading_research.core.templates import register_template

class MyKnobs(BaseModel):
    entry_mult: float = Field(2.0, ge=0.5, le=5.0)
    stop_mult: float = Field(1.5, ge=0.5, le=4.0)

@register_template(
    name="my-strategy",
    human_description="Example ATR-band mean reversion",
    knobs_model=MyKnobs,
    supported_instruments=["ZN", "6A"],
    supported_timeframes=["5m", "15m", "60m"],
)
class MyStrategy:
    def __init__(self, *, knobs: MyKnobs, template_name: str) -> None:
        self._knobs = knobs

    def generate_signals_df(self, df: pd.DataFrame) -> pd.DataFrame:
        # Python signal logic — any complexity is allowed here
        ...
```

The YAML config then references the template by name:

```yaml
strategy_id: my-strategy-v1
symbol: ZN
timeframe: 15m
template: my-strategy
template_module: trading_research.strategies.my_module  # import path
knobs:
  entry_mult: 2.5
  stop_mult: 1.5
```

`template_module:` is optional; when present, the runner imports it
before looking up the template, which triggers the `@register_template`
decorator. If omitted, the template must already be registered (e.g.,
by a prior import in the process).

The template class must implement the Strategy Protocol's
`generate_signals_df(df) → DataFrame` method (or the full Strategy
Protocol). The returned DataFrame must have the same `signal`/`stop`/`target`
columns that `YAMLStrategy` produces, so the backtest engine receives the
same interface regardless of dispatch path.

Knob validation is enforced by Pydantic at template instantiation time:
passing an `entry_mult` outside [0.5, 5.0] raises a `ValidationError`
before any backtest runs. This is stricter than YAML knobs, which are not
type-validated by default.

---

## 10.10 Related references

### Code modules

- [`src/trading_research/strategies/template.py`](../../src/trading_research/strategies/template.py)
  — `YAMLStrategy`, `ExprEvaluator`, and all helpers. Read this when
  debugging why an expression does not evaluate as expected.

- [`src/trading_research/core/templates.py`](../../src/trading_research/core/templates.py)
  — `StrategyTemplate`, `@register_template`, `TemplateRegistry`.

- [`src/trading_research/backtest/multiframe.py`](../../src/trading_research/backtest/multiframe.py)
  — `join_htf`: the function that joins higher-timeframe features onto
  the primary-TF DataFrame.

### Configuration

- [`configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml`](../../configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml)
  — the worked example in §10.8.

- [`configs/strategies/6a-vwap-reversion-mtf-v1.yaml`](../../configs/strategies/6a-vwap-reversion-mtf-v1.yaml)
  — a strategy using `higher_timeframes:` and `regime_filter:`, which
  illustrates §10.7 and Chapter 12.

- [`configs/regimes/volatility-p75.yaml`](../../configs/regimes/volatility-p75.yaml)
  — the shared regime filter config referenced via `include:`.

### Other manual chapters

- **Chapter 9** — design principles: when to use YAML vs template vs
  signal_module.
- **Chapter 11** — expression evaluator: exact syntax rules for `entry:`
  and `exits:` expressions.
- **Chapter 12** — regime filters: the `regime_filter:` and
  `regime_filters:` keys.
- **Chapter 13** — configuration reference: alphabetised key list with
  types and defaults.
- **Chapter 16** — running a single backtest: how the CLI picks up the
  YAML and what it produces.

---

*End of Chapter 10. Next: Chapter 11 — The Expression Evaluator.*
