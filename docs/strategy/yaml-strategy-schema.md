# YAML Strategy Schema

A YAML strategy file lets you define entry/exit logic for a strategy without writing any Python.
The file is self-contained: it holds the symbol, timeframe, entry conditions, stop/target formulas,
and backtest defaults. You pass it directly to the backtest CLI or walk-forward harness.

---

## Top-level structure

```yaml
strategy_id: <string>          # unique identifier, used in output filenames
symbol: <string>               # instrument root (e.g. ZN, 6C, 6A)
timeframe: <string>            # bar resolution (5m, 15m, 60m, …)
description: >                 # human-readable summary (optional but encouraged)
  …

knobs:                         # named scalar parameters referenced in expressions
  param_name: <float>

entry:                         # entry conditions (mutually exclusive with template: / signal_module:)
  long:
    all: [ … ]                 # AND conditions
    any: [ … ]                 # OR conditions (any one true fires the direction)
  short:
    all: [ … ]
    any: [ … ]
  time_window:                 # optional — restricts entry to a UTC time range
    start_utc: "HH:MM"
    end_utc:   "HH:MM"

exits:
  stop:
    long:  "<expression>"      # stop price for long trades
    short: "<expression>"
  target:
    long:  "<expression>"      # take-profit price for long trades
    short: "<expression>"

backtest:
  fill_model: next_bar_open    # next_bar_open | same_bar (same_bar requires justification)
  same_bar_justification: ""
  eod_flat: true               # flatten all positions at session end
  max_holding_bars: null       # null = unlimited
  use_ofi_resolution: false    # order-flow pessimism for TP/SL ambiguous bars
  quantity: 1                  # number of contracts per signal
```

---

## Dispatch rule

The backtest engine recognises three mutually exclusive dispatch keys.
Exactly one must be present:

| Key present | Dispatch |
|:---|:---|
| `entry:` | YAML template path (this schema) |
| `template:` | Registered StrategyTemplate (Python template registry) |
| `signal_module:` | Python module import (`generate_signals` function) |

A file with more than one of these keys, or none, is rejected at startup.

---

## Expression language

Every string value under `entry.long.all`, `entry.short.all`, `exits.stop.*`,
and `exits.target.*` is an **expression string**. It is evaluated against the
features DataFrame for each bar.

### What you can write

| Element | Syntax | Example |
|:---|:---|:---|
| Column reference | bare name | `close`, `atr_14`, `vwap_session` |
| Knob reference | bare name | `atr_stop_mult` (must be defined in `knobs:`) |
| Integer / float literal | `1`, `2.5`, `-0.5` | `2.0` |
| Arithmetic | `+  -  *  /` | `close - 2.0 * atr_14` |
| Unary minus | `-` | `-adx_14` |
| Comparison | `<  <=  >  >=  ==  !=` | `close > vwap_session` |
| Boolean (entry only) | `and  or` | `adx_14 < 25 and close > vwap_session` |
| Parentheses | `(…)` | `(close - vwap_session) / atr_14` |
| Shift | `shift(col, n)` | `shift(donchian_upper, 1)` |

`shift(col, n)` returns the value of column `col` from `n` bars ago —
equivalent to `df[col].shift(n)`. Use it anywhere you need a lookback
comparison on a prior bar's value (e.g., Donchian breakout).

### What is rejected

Attribute access, subscripts, imports, lambda, function calls other than
`shift` — anything that looks like arbitrary Python. The evaluator uses an
AST whitelist; an unknown node type raises `ValueError` at load time.

---

## Condition blocks

Each direction (`long:`, `short:`) supports two composition modes:

```yaml
long:
  all:
    - "expr_A"    # all must be True
    - "expr_B"
  any:
    - "expr_C"    # at least one must be True
    - "expr_D"
```

When both `all:` and `any:` are present, both must pass (AND semantics at
the block level). Either key may be omitted. Typical usage is `all:` only
for simple multi-condition entries.

---

## Time window

```yaml
time_window:
  start_utc: "13:20"
  end_utc:   "20:00"
```

Times are UTC HH:MM. Only bars whose UTC time falls within
`[start_utc, end_utc)` can generate entry signals. Stops and targets are
not filtered — they apply to the full bar range once a position is open.
The window is optional; omit it entirely for 24-hour instruments.

---

## Conflict resolution

If both `long` and `short` conditions fire on the same bar, **neither fires**.
This matches the Python-module convention. In practice it is rare on
well-separated entry thresholds (e.g., opposite sides of a VWAP band).

---

## Stop / target formulas

Stop and target are evaluated **at signal time** (the bar that fires the
entry condition). They are fixed prices, not trailing.

```yaml
exits:
  stop:
    long:  "close - atr_stop_mult * atr_14"   # below entry
    short: "close + atr_stop_mult * atr_14"   # above entry
  target:
    long:  "vwap_session"                      # mean-reversion target
    short: "vwap_session"
```

A signal bar whose stop expression evaluates to `NaN` is suppressed (the
signal is not emitted). This handles indicator warm-up periods where ATR or
other look-back indicators are not yet populated.

---

## Knobs

Knobs are named scalar float parameters. They appear in `knobs:` as key/value
pairs and can be referenced by name in any expression string. The parameter
sweep tool uses them as the sweep axis — define knobs for every threshold
you expect to tune.

```yaml
knobs:
  atr_stop_mult: 2.0
  target_atr_mult: 3.0
  adx_max: 25.0
```

Column names and knob names share the same namespace inside an expression.
If a name appears in both `knobs:` and the DataFrame columns, the DataFrame
column takes precedence. Avoid naming knobs after feature columns.

---

## Backtest defaults

| Field | Default | Notes |
|:---|:---|:---|
| `fill_model` | `next_bar_open` | Same-bar fill requires written `same_bar_justification` |
| `eod_flat` | `true` | Recommended for single-instrument intraday strategies |
| `max_holding_bars` | `null` | Use an integer to cap hold duration (e.g., `48` for 2-day cap at 60m) |
| `use_ofi_resolution` | `false` | Opt-in OFI-based TP/SL ambiguity resolution |
| `quantity` | `1` | Contracts per signal |

---

## Full example — 6A VWAP reversion

```yaml
strategy_id: 6a-vwap-reversion-adx-yaml-v1
symbol: 6A
timeframe: 5m

knobs:
  entry_atr_mult: 1.5
  stop_atr_mult: 1.0
  adx_max: 25.0

entry:
  long:
    all:
      - "close < vwap_session - entry_atr_mult * atr_14"
      - "adx_14 < adx_max"
  short:
    all:
      - "close > vwap_session + entry_atr_mult * atr_14"
      - "adx_14 < adx_max"
  time_window:
    start_utc: "13:30"
    end_utc:   "20:00"

exits:
  stop:
    long:  "close - stop_atr_mult * atr_14"
    short: "close + stop_atr_mult * atr_14"
  target:
    long:  "vwap_session"
    short: "vwap_session"

backtest:
  fill_model: next_bar_open
  same_bar_justification: ""
  eod_flat: true
  max_holding_bars: null
  use_ofi_resolution: false
  quantity: 1
```

---

## Adding a new strategy

1. Copy any existing YAML in `configs/strategies/` as a starting point.
2. Change `strategy_id` to a unique slug ending in `-yaml-v1` (or increment the version).
3. Update `symbol`, `timeframe`, and `description`.
4. Write entry conditions referencing columns from the features parquet for that instrument.
   Run `uv run backtest configs/strategies/your-new-strategy.yaml --dry-run` to validate that
   all referenced columns exist in the features file.
5. Set stop and target formulas. Both must produce non-NaN values for valid signal bars.
6. Adjust `backtest:` defaults — in particular `eod_flat` and `max_holding_bars`.
7. Run the full backtest. The trial is written to `runs/trials/`.

---

## Relationship to Python-module strategies

YAML templates and Python-module strategies (under `src/trading_research/strategies/`) are
interchangeable from the backtest engine's perspective — both produce a signals DataFrame
with the same schema (`signal`, `stop`, `target`). Use YAML for new strategies where the
entry/exit logic can be expressed as arithmetic comparisons. Use Python when you need
imperative logic (rolling state, complex exit signals, per-bar callbacks).

The three bundled YAML templates are ports of existing Python modules and have parity tests
that verify identical signal outputs on synthetic fixtures.
