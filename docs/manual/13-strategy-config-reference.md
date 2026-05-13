# Chapter 13 — Strategy Configuration Reference

> **Chapter status:** [EXISTS]. §13.1–13.3 document the complete
> implemented key set. §13.4 covers the `validate-strategy` CLI that
> enforces these constraints at lint time, before a backtest runs; the
> full command reference is in
> [Chapter 49.15](49-cli-command-reference.md).

---

## 13.0 What this chapter covers

This chapter is the alphabetised reference for every legal key in a
strategy YAML. It answers: What is this key? What type does it expect?
What is its default? What happens when it is absent?

Chapter 10 is the authoring guide — it explains how to write strategies
and provides examples. This chapter is the reference — consult it when
you are unsure what a key does, what its type constraint is, or what
happens when you omit it.

---

## 13.1 Complete YAML key reference

Keys are listed alphabetically. Keys marked **[required]** raise an error
if absent; all others are optional.

---

### `backtest`

**Type:** mapping  
**Default:** engine defaults (see individual sub-keys)  
**Purpose:** Configures the backtest engine for this strategy.

Contains: `fill_model`, `same_bar_justification`, `eod_flat`,
`max_holding_bars`, `use_ofi_resolution`, `quantity`. Each is documented
below under its own entry in this table.

---

### `backtest.eod_flat`

**Type:** bool  
**Default:** `true`  
**Purpose:** When `true`, any open position is closed at the session's
RTH close time (taken from `configs/instruments.yaml`). When `false`,
positions may be held overnight and across sessions.

Default `true` is appropriate for all intraday single-instrument
strategies. Set to `false` only for multi-session strategies where the
overnight hold is part of the design — and document the reasoning in the
strategy header comment.

---

### `backtest.fill_model`

**Type:** enum  
**Default:** `next_bar_open`  
**Allowed values:** `next_bar_open`, `same_bar`  
**Purpose:** Determines the fill timing for entries and exits.

`next_bar_open` — the default and the honest choice: signals fire at bar
T's close; fills execute at bar T+1's open.

`same_bar` — fills at bar T's close. Requires a non-empty
`same_bar_justification`.

---

### `backtest.max_holding_bars`

**Type:** int or null  
**Default:** `null` (no time-stop)  
**Purpose:** Force-close a position after this many bars. Acts as a
backstop when TP and SL do not fire.

`null` disables the time-stop. A finite value is recommended for
strategies that may "go stale" — where the trade hypothesis has resolved
but neither TP nor SL has been reached. Common values:
- 15m intraday: 24–32 bars (6–8 hours)
- 60m multi-session: 96 bars (4 days)
- 240m swing: 20–25 bars (4–5 days)

---

### `backtest.quantity`

**Type:** int  
**Default:** `1`  
**Purpose:** Fixed contract quantity for every trade.

The v1.0 platform uses fixed quantity sizing exclusively. Volatility-
targeting sizing is specified in Chapter 36 but is not wired into the
YAML grammar; strategies that need dynamic sizing use the template
(Path B) dispatch path.

---

### `backtest.same_bar_justification`

**Type:** string  
**Default:** `""` (empty)  
**Validation:** Must be non-empty when `fill_model: same_bar`. The engine
raises `ValueError` on construction if this is empty with a `same_bar`
fill model.  
**Purpose:** Documents the justification for using the `same_bar` fill
model.

The non-empty requirement is a friction mechanism: it creates a record
of why the unusual fill model was chosen and forces the author to think
through the justification before proceeding.

---

### `backtest.use_ofi_resolution`

**Type:** bool  
**Default:** `false`  
**Purpose:** When `true`, the engine uses order-flow imbalance
(buy/sell volume ratio on the ambiguous bar) to determine whether the
TP or SL was hit first when both levels are inside the bar's range.

When `false` (default), the pessimistic rule applies: the stop is assumed
to have hit first. This is the more honest default — it does not depend
on the `buy_volume`/`sell_volume` columns, which may be null for older
data.

---

### `description`

**Type:** string or YAML block scalar  
**Default:** `""` (empty, with a warning if missing)  
**Purpose:** Human-readable description of what the strategy is and why
it exists. Used in report headers and leaderboard output.

Use a YAML block scalar (`>` or `|`) for multi-line descriptions:

```yaml
description: >
  Multi-line description here.
  Second line.
```

The description should explain the market hypothesis, not just what the
conditions do.

---

### `entry`

**Type:** mapping  
**Required:** Yes (mutually exclusive with `template:` and `signal_module:`)  
**Purpose:** The YAML entry conditions for the YAML template dispatch path.
Contains `long:`, `short:`, and optionally `time_window:`.

See Chapter 10 §10.2 for the full grammar.

---

### `exits`

**Type:** mapping  
**Default:** No exits (time-based exits only via `eod_flat` and
`max_holding_bars`)  
**Purpose:** Stop-loss and take-profit price level expressions.

Contains `stop:` and `target:`, each of which may contain `long:` and
`short:` expression strings.

See Chapter 10 §10.3 for the full grammar.

---

### `feature_set`

**Type:** string  
**Default:** `"base-v1"`  
**Purpose:** The feature-set tag to use when loading the features
parquet. The runner looks for
`data/features/{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet`.

Must match a tag in `configs/featuresets/`. If the corresponding parquet
does not exist, the runner fails with a file-not-found error before any
backtest runs.

---

### `higher_timeframes`

**Type:** list of strings  
**Default:** `[]` (no higher-timeframe joins)  
**Purpose:** Additional timeframes whose feature parquets are joined onto
the primary-TF DataFrame before signal generation.

Each entry is a timeframe string matching the pattern used in feature
parquet filenames (e.g., `"60m"`, `"240m"`). The runner loads
`{symbol}_backadjusted_{htf}_features_{feature_set}_*.parquet` and joins
it with a prefix of `tf{htf}_` on each column name.

See Chapter 10 §10.7.

---

### `knobs`

**Type:** mapping of string → numeric  
**Default:** `{}` (no knobs)  
**Purpose:** Named scalar values referenced by expressions in `entry:`,
`exits:`, and regime filter parameters.

All knob values must be numeric (int or float). String values raise
`ValueError` at expression evaluation time. Knob names must not collide
with feature column names (columns take precedence in name resolution).

---

### `regime_filter`

**Type:** mapping  
**Default:** absent (no filter)  
**Purpose:** A single regime filter specification, either inline or via
`include:`. See Chapter 12 for the full grammar.

The singular and plural keys (`regime_filter` / `regime_filters`) can
coexist; both are parsed and their filters are merged into a single list.

---

### `regime_filters`

**Type:** list of mappings  
**Default:** `[]` (no filters)  
**Purpose:** A list of regime filter specifications. Filters are applied
with AND semantics: all must permit entry. See Chapter 12 for the full
grammar.

---

### `signal_module`

**Type:** string (importable module path)  
**Required:** Yes (mutually exclusive with `entry:` and `template:`)  
**Purpose:** Legacy dispatch path. Points to a Python module that exposes
a `generate_signals(df)` function. See Chapter 9 §9.4 Path C.

New strategies should not use this path. It exists for compatibility with
strategies written before the YAML evaluator was introduced.

---

### `signal_params`

**Type:** mapping  
**Default:** `{}` (no params)  
**Purpose:** Parameter dict passed to `signal_module` strategies.
Ignored for YAML template and registered template dispatch paths.

---

### `strategy_id`

**Type:** string  
**Required:** Yes  
**Purpose:** The unique identifier for this strategy. Used as the run
directory name prefix: outputs land in `runs/{strategy_id}/{timestamp}/`.
Also appears in the trial registry, the leaderboard, and all report
headers.

Convention: `{instrument}-{signal-class}-{timeframe}-v{N}`. Examples:
`6a-monthly-vwap-fade-yaml-v2b`, `zn-macd-zero-cross-240m-yaml-v1`,
`6e-vwap-reversion-v1`.

Must be unique across all YAMLs in `configs/strategies/`. There is no
automatic dedup check; name collisions produce interleaved output in
`runs/` and confused trial registry entries.

---

### `symbol`

**Type:** string  
**Required:** Yes  
**Purpose:** CME root symbol for the instrument this strategy trades. Must
be registered in `configs/instruments.yaml`.

Registered symbols: `ZN`, `6E`, `6A`, `6C`, `6N`. See Chapter 5 for the
CME-to-TradeStation symbol mapping.

---

### `template`

**Type:** string (registered template name)  
**Required:** Yes (mutually exclusive with `entry:` and `signal_module:`)  
**Purpose:** Registered StrategyTemplate dispatch path. The value must
match a name registered via `@register_template`. See Chapter 9 §9.4
Path B and Chapter 10 §10.9.

---

### `template_module`

**Type:** string (importable module path)  
**Default:** absent  
**Purpose:** Module to import before looking up the `template:` name.
Importing the module triggers the `@register_template` decorator that
populates the registry.

If absent, the template must already be registered (e.g., by a prior
import earlier in the process). Providing `template_module:` makes the
YAML self-contained.

---

### `timeframe`

**Type:** string  
**Default:** `"5m"`  
**Purpose:** Bar timeframe for the primary feature parquet. The runner
looks for `{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet`.

Supported values: `5m`, `15m`, `60m`, `240m`. The `1m` timeframe has
no pre-built features parquet (CLEAN only). Custom timeframes (e.g., `13m`)
require a CLEAN and FEATURES parquet built manually — see Chapter 4 §4.9.

---

### `time_window` (inside `entry`)

**Type:** mapping with `start_utc` and `end_utc` keys  
**Default:** absent (no restriction)  
**Purpose:** Restricts entries to bars within the UTC hour range
`[start_utc, end_utc)`. Specified in HH:MM format.

See Chapter 10 §10.2.3 and §10.6.

---

## 13.2 Cross-key validation

The engine validates certain key combinations at strategy load time and
at `BacktestConfig` construction. Combinations that produce errors:

| Condition | Error |
|-----------|-------|
| More than one dispatch key present | `Config has more than one of 'entry', 'template', 'signal_module'. Use exactly one.` |
| No dispatch key present | `Config must have one of 'entry', 'template', or 'signal_module'.` |
| `fill_model: same_bar` with empty `same_bar_justification` | `same_bar_justification must be non-empty when fill_model is SAME_BAR.` |
| `vol_percentile_threshold` outside [50, 95] in regime filter | `vol_percentile_threshold must be in [50, 95]; got N` |
| `feature_set` tag parquet not found on disk | File-not-found error before backtest starts |
| `symbol` not in `configs/instruments.yaml` | `Unknown instrument: {symbol}` |

Combinations that produce warnings (no hard failure):

| Condition | Warning |
|-----------|---------|
| `eod_flat: false` on a strategy with `timeframe` of `5m` or `15m` | Intraday timeframe with overnight hold is unusual |
| `max_holding_bars: null` with `eod_flat: false` | No time-based exit at all; position could be held indefinitely |
| Empty `description:` | Description missing; report headers will be sparse |

---

## 13.3 The default-filling order

When a key is absent from a strategy YAML, the value comes from one of
three sources in this order:

1. **YAML default** — documented in §13.1 for each key. These are the
   values that make the most common strategy work without explicit config.

2. **Engine default** — `BacktestConfig` field defaults in
   [`src/trading_research/backtest/engine.py:47`](../../src/trading_research/backtest/engine.py):
   - `fill_model: next_bar_open`
   - `eod_flat: true`
   - `max_holding_bars: null`
   - `use_ofi_resolution: false`
   - `quantity: 1`

3. **Error** — required keys (`strategy_id`, `symbol`, dispatch key)
   produce immediate errors when absent; there is no default.

The cost model (slippage and commission) is not configurable per-strategy
in v1.0. Defaults come from `configs/instruments.yaml` under each
instrument's `backtest_defaults:` key. Per-strategy overrides are on the
v2.0 roadmap.

---

## 13.4 Configuration linting — `validate-strategy`

The `validate-strategy` CLI enforces the cross-key constraints from
§13.2 and dry-runs every `entry:` and `exits:` expression against a
synthetic dataset built on the real features-parquet schema. It is the
fast iteration loop: name-resolution and expression errors surface in
under a second, without loading real bars or building a backtest
engine. The full command reference is in
[Chapter 49.15](49-cli-command-reference.md); this section documents
the contract the command implements.

**Specification:**

```
uv run trading-research validate-strategy <config_path> [--verbose]
```

**What it does:**

1. Loads the YAML at `<config_path>`.
2. Validates all cross-key constraints (§13.2).
3. Loads the appropriate features parquet for the configured
   `symbol`, `timeframe`, and `feature_set`.
4. Evaluates all `entry:` and `exits:` expressions on a 100-bar
   synthetic dataset (not the real features data), using the feature
   column set from the real parquet's schema.
5. Reports any name-resolution failures, type errors, or expression
   syntax errors.
6. Reports the expected signal count on the 100 synthetic bars
   (as a sanity check that conditions are not trivially always-True or
   always-False).
7. Reports any structural warnings (§13.2 cross-key validation).

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | No errors; strategy is syntactically valid |
| 1 | One or more validation errors found |
| 2 | Features parquet not found or YAML not parseable |

**Output format (default):**

```
Validating: configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml
  Dispatch:    YAML template (entry:)
  Symbol:      6A / 60m / base-v1
  Feature set: data/features/6A_backadjusted_60m_features_base-v1_*.parquet [OK]
  Entry long:  2 conditions — all resolved [OK]
  Entry short: 2 conditions — all resolved [OK]
  Exits stop:  long + short resolved [OK]
  Exits target: long + short resolved [OK]
  Regime filter: volatility-regime(p75) loaded via include:volatility-p75 [OK]
  Synthetic signal rate: long=12%, short=9% on 100-bar test [OK]
  No errors.
```

**With errors:**

```
Validating: configs/strategies/bad-strategy.yaml
  Entry long condition 2: Name 'atr_15' is not a column or a knob.
    Hint: did you mean 'atr_14'? (available: atr_14, rsi_14, ...)
  Exits stop long: Name 'stop_mult' is not a column or a knob.
    Hint: check the knobs block. Current knobs: band_mult, target_mult
  2 errors found. Fix before running backtest.
```

The `--verbose` flag prints the column list from the features parquet,
all resolved knob values, and the full expression parse tree for each
condition.

---

## 13.5 Related references

### Code modules

- [`src/trading_research/backtest/engine.py:47`](../../src/trading_research/backtest/engine.py)
  — `BacktestConfig` dataclass: the engine-level defaults for all
  `backtest:` sub-keys.

- [`src/trading_research/backtest/walkforward.py:130`](../../src/trading_research/backtest/walkforward.py)
  — config loading and dispatch: where `strategy_id`, `symbol`,
  `timeframe`, `feature_set`, and `higher_timeframes` are extracted.

- [`src/trading_research/strategies/template.py`](../../src/trading_research/strategies/template.py)
  — `YAMLStrategy.from_config()`: validates that the `entry:` block
  is present before constructing the strategy object.

### Configuration

- [`configs/strategies/`](../../configs/strategies/) — the full set of
  registered strategy YAML files; useful for cross-referencing key usage.

### Other manual chapters

- **Chapter 9** — design principles: which keys to use, which to avoid.
- **Chapter 10** — authoring guide: the grammar for `entry:` and `exits:`
  blocks.
- **Chapter 11** — expression evaluator: syntax rules for expression
  strings.
- **Chapter 12** — regime filters: the `regime_filter:` /
  `regime_filters:` grammar.
- **Chapter 49.15** — `validate-strategy` CLI: the full CLI option
  reference (to be written when implemented).

---

*End of Chapter 13. Next: Chapter 14 — The Backtest Engine.*
