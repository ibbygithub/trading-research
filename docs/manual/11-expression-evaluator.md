# Chapter 11 — The Expression Evaluator

> **Chapter status:** [EXISTS]. §11.1–11.6 describe a fully implemented
> evaluator in `src/trading_research/strategies/template.py`. §11.7
> documents the error-reporting behaviour at signal-generation time
> and at lint time via the `validate-strategy` CLI ([Chapter 49.15](49-cli-command-reference.md)).

---

## 11.0 What this chapter covers

The expression evaluator is the core of the YAML strategy path. Every
condition in `entry:` and every price expression in `exits:` is a string
that the evaluator parses, validates, and computes over a pandas DataFrame.
Understanding the evaluator tells you exactly what you can say in a YAML
strategy — and why some things are deliberately unsayable.

After reading this chapter you will:

- Know the complete set of syntax the evaluator permits
- Understand name resolution: when a bare word becomes a column vs a knob
- Understand how NaN propagates through comparisons, and why this matters
  for indicator warm-up
- Know the exact semantics of `shift(col, n)` and why it is the only
  function the evaluator accepts
- Know what the evaluator refuses and the security and correctness reasons
  for each restriction
- Recognise common expression patterns by reading real strategy YAMLs

This chapter is roughly 6 pages. It is a reference chapter; most
practitioners will read it once and then use the common patterns table in
§11.6 as a cookbook.

---

## 11.1 Supported expression syntax

The evaluator accepts a carefully bounded subset of Python expression
syntax. Every supported construct is listed here; anything not listed is
rejected.

### 11.1.1 Bare names

```
close
atr_14
vwap_monthly
adx_max
```

A bare word resolves to either a DataFrame column or a knob value (see
§11.2). Bare names are the primary mechanism for referencing market data
and strategy parameters.

### 11.1.2 Numeric literals

```
2.0
14
0.5
```

Integer and floating-point numeric literals. The evaluator converts all
constants to `float`. Non-numeric literals (strings, booleans) are
rejected.

### 11.1.3 Arithmetic operators

```
atr_14 * 2.0
close - stop_mult * atr_14
(vwap_session + vwap_weekly) / 2
```

Supported: `+`, `-`, `*`, `/`. Standard left-to-right precedence;
parentheses for grouping. Division is always floating-point. Integer
division (`//`) and modulo (`%`) are rejected.

### 11.1.4 Comparison operators

```
close < vwap_session - band_mult * atr_14
adx_14 >= adx_max
macd_hist == 0.0
```

Supported: `<`, `>`, `<=`, `>=`, `==`, `!=`. Comparisons return a
boolean-valued pandas Series when either operand is a Series (i.e., a
DataFrame column). Comparisons between two scalars return a scalar bool.

Chained comparisons (`a < b < c`) are not supported. Write them as two
separate conditions in `all:`.

### 11.1.5 Unary minus

```
-atr_14
-1.5
```

Unary negation. Unary plus (`+atr_14`) is also accepted as a no-op.

### 11.1.6 Parentheses

Parentheses for grouping arithmetic sub-expressions. No limit on nesting
depth.

### 11.1.7 The `shift()` function

```
shift(macd_hist, 1)
shift(close, 2)
```

`shift(col, n)` returns `df[col].shift(n)` — the column shifted by `n`
bars backward in time (positive `n` = look back). This is the only
function the evaluator accepts. See §11.4 for full semantics.

### 11.1.8 Boolean operators in condition lists

Within `all:` and `any:` lists, each condition string is evaluated
independently and the `all`/`any` combinators apply the AND/OR logic.
The evaluator itself also supports `and` and `or` within a single
expression string, though this is rarely needed:

```
"close < vwap_session and adx_14 < 20.0"
```

This is equivalent to two entries in `all:`. The `all:`/`any:` list form
is preferred for readability.

---

## 11.2 Name resolution rules

When the evaluator encounters a bare name, it resolves it in this order:

1. **DataFrame columns.** If the name matches a column in the features
   DataFrame, the evaluator returns that column as a `pd.Series`. This
   covers all indicator columns (e.g., `atr_14`, `vwap_session`),
   OHLCV columns (`open`, `high`, `low`, `close`, `volume`), and HTF
   projection columns (`daily_ema_20`, `tf60m_ema_20`, etc.).

2. **Knobs.** If the name is not a column but matches a key in the
   strategy's `knobs:` block, the evaluator returns the knob's value as
   a Python scalar (`float`). This is resolved at expression evaluation
   time, not at YAML load time, so knob overrides from the sweep CLI
   take effect.

3. **Error.** If the name is neither a column nor a knob, the evaluator
   raises `ValueError` with a message listing the first 8 known column
   names and all known knob names. This error surfaces at signal
   generation time (when `generate_signals_df` is called); the
   `validate-strategy` CLI ([Chapter 49.15](49-cli-command-reference.md))
   surfaces the same error at lint time, before any backtest runs.

**Precedence implication.** Columns always shadow knobs. A knob named
`close` would never be used — the evaluator would always return the
`close` column instead. Use knob names that do not collide with column
names. The naming convention is `<purpose>_<units_or_category>` (e.g.,
`entry_atr_mult`, `adx_max`, `target_mult`) rather than single words
that might match a column.

**Knob values must be numeric.** If a knob's value is a string or other
non-numeric type, the evaluator raises `ValueError` when the name is
resolved. YAML knobs should always be numeric scalars.

---

## 11.3 Comparison NaN handling

When a comparison involves a NaN value — either from a column that has not
yet warmed up or from a computation that produced NaN — the evaluator
applies `fillna(False)` to the result before returning.

```python
# In ExprEvaluator._node for ast.Compare:
result = _CMP_OPS[op_type](left, right)
if isinstance(result, pd.Series):
    return result.fillna(False)
```

The consequence: a comparison against NaN evaluates to `False`, not to
`NaN`. This means a bar in the indicator warm-up period (where ATR,
MACD, RSI, etc. are not yet computable) will never produce an entry
signal, because the comparison conditions will silently be `False`.

This is intentional and correct. The alternative — propagating NaN
through comparisons — would require every YAML condition to explicitly
guard against NaN, which is error-prone. The `fillna(False)` convention
makes warm-up periods safe by default.

> *Why this matters:* ATR(14) requires 14 bars to compute. MACD(12, 26,
> 9) requires 35 bars (26 slow EMA + 9 signal EMA). A 16-year history
> with 35 warm-up bars is negligible — but if the evaluator propagated
> NaN, those 35 bars might fire spurious signals or produce unparseable
> Series. The `fillna(False)` convention eliminates the problem at the
> source.

The stop and target expressions use a separate mechanism: if the stop
expression evaluates to a non-finite value (NaN or inf), the signal is
suppressed by the `np.isfinite` check in `generate_signals_df`. This is
the correct behaviour for warm-up bars where ATR-based stops would
produce nonsensical levels.

---

## 11.4 The `shift()` function

`shift(column_name, n)` returns the values of `column_name` shifted `n`
bars backward in time. It maps directly to `df[column_name].shift(n)`.

**Arguments:**

- `column_name` — must be a bare column name (an `ast.Name` node). It
  cannot be an expression. `shift(close - vwap_session, 1)` is invalid;
  `shift(close, 1)` is valid.
- `n` — must be a constant integer expression. `shift(close, bars_back)`
  where `bars_back` is a knob is invalid. `shift(close, 1)` is valid.

**Semantics:**

| Expression | Meaning |
|------------|---------|
| `shift(macd_hist, 1)` | The MACD histogram value at the previous bar |
| `shift(close, 2)` | The close price two bars ago |
| `shift(macd_hist, 0)` | The current MACD histogram (equivalent to `macd_hist`) |

**Common use case — zero-crossing detection:**

```yaml
entry:
  long:
    all:
      - "macd_hist > 0"                  # current bar: histogram above zero
      - "shift(macd_hist, 1) <= 0"       # previous bar: histogram at or below zero
```

This expresses "MACD histogram crossed above zero on this bar" without
any Python code. The evaluator produces two Series from these two
conditions and combines them in the `all:` AND combinator.

**Why shift() is the only function:**

The evaluator permits `shift()` specifically because "comparison to a
prior bar's value" is a canonical pattern in rule-based technical
strategies, and there is no way to express it without state. Every other
computational need should be satisfied by pre-computing the required
column in the feature set.

Permitting arbitrary function calls (e.g., `min(close, close_shifted)`,
`abs(macd_hist)`) would require the evaluator to either whitelist dozens
of functions or open the door to arbitrary Python evaluation. The
whitelist approach grows without bound as strategies discover new
computational needs. The arbitrary-evaluation approach eliminates the
security posture (see §11.5). `shift()` is the minimal exception to
the "no functions" rule that covers the primary use case — comparing
the current bar to prior bars.

> *Why not `lag()`, `prev()`, or similar?* The name `shift()` is
> deliberately consistent with pandas `Series.shift()`. An operator
> who knows pandas immediately understands `shift(col, 1)` without
> additional explanation.

---

## 11.5 What the evaluator refuses

The evaluator rejects any syntax not listed in §11.1. The specific
rejections, and the reason for each:

**Attribute access.** `df.close`, `obj.method()`. Any `ast.Attribute`
node raises an immediate `ValueError`. Attribute access would allow
`__class__`, `__dict__`, and other Python object internals to be
accessed from an expression string — a trivial attack surface if
strategy YAMLs are ever loaded from untrusted sources.

**Subscripts.** `df["close"]`, `arr[0]`. Any `ast.Subscript` node is
rejected. Subscript access overlaps with attribute access in its
potential for abuse, and the evaluator has no need for it: columns are
referenced by bare names, not by subscripted access.

**Lambda.** `lambda x: x * 2`. Rejected. Lambda would allow arbitrary
computation to be hidden in an expression string, defeating the intent
of the restricted evaluator.

**Imports.** `import os`. YAML conditions are parsed as expressions
(not statements), so `import` cannot syntactically appear in a condition
string. This is belt-and-suspenders: the evaluator uses `ast.parse`
with `mode="eval"`, which prohibits all statements including `import`.

**Function calls (other than `shift`).** Any `ast.Call` node where the
function name is not `shift` raises `ValueError`:

```
Unknown function 'min'. Supported functions: shift(column, n)
```

This includes:
- Standard Python builtins (`min`, `max`, `abs`, `round`, `len`)
- NumPy functions (`np.where`, `np.nan`, `np.percentile`)
- pandas methods (`df.rolling`, `df.fillna`)
- String operations, type conversions, comprehensions

If a computation requires a function that the evaluator does not provide,
the correct answer is to pre-compute the result in the feature builder
as a new indicator column, then reference that column by name in the
YAML. This keeps the evaluator minimal and the feature set comprehensive.

**Non-numeric constants.** String literals (`"long"`), boolean literals
(`True`, `False`), and `None` are all rejected. The evaluator works
exclusively with numeric values.

**Integer division, modulo, power.** `//`, `%`, `**`. These are not in
the supported operator set. Power (`**`) is the most commonly requested;
if a computation requires squaring or square root, add a pre-computed
column to the feature set.

---

## 11.6 Common patterns

The following patterns cover the vast majority of rule-based mean-reversion
entries and exits for this platform's instrument set.

### 11.6.1 VWAP-band fade

```yaml
entry:
  long:
    all:
      - "close < vwap_session - band_mult * atr_14"
  short:
    all:
      - "close > vwap_session + band_mult * atr_14"
```

Entry when close is more than `band_mult` ATRs outside the session VWAP.
Use `vwap_monthly` or `vwap_weekly` for longer-cycle fades.

### 11.6.2 VWAP standard-deviation band fade

```yaml
entry:
  long:
    all:
      - "close < vwap_monthly - band_mult * vwap_monthly_std_1_0"
```

The VWAP standard-deviation bands (`vwap_monthly_std_1_0`,
`vwap_monthly_std_1_5`, etc.) are precomputed feature columns. This
pattern uses a statistically-grounded band width rather than ATR.

### 11.6.3 MACD zero-cross entry

```yaml
entry:
  long:
    all:
      - "macd_hist > 0"
      - "shift(macd_hist, 1) <= 0"
  short:
    all:
      - "macd_hist < 0"
      - "shift(macd_hist, 1) >= 0"
```

Entry on the bar where the histogram crosses zero. Uses `shift()` to
compare the current bar to the prior bar.

### 11.6.4 ATR-scaled stop

```yaml
exits:
  stop:
    long:  "close - stop_mult * atr_14"
    short: "close + stop_mult * atr_14"
```

Stop at `stop_mult` ATRs from the signal-bar close. This is the standard
volatility-scaled stop. The stop is computed at the signal bar and held
fixed (not trailing) until exit.

### 11.6.5 VWAP mean-reversion target

```yaml
exits:
  target:
    long:  "vwap_session"
    short: "vwap_session"
```

Target at the session VWAP. When price has faded below the VWAP, the
target is the return to VWAP — a scalar value that changes bar by bar as
the VWAP accumulates. The engine evaluates the target expression at the
exit check bar, not at the entry bar, so a VWAP target "tracks" the VWAP
as it moves.

### 11.6.6 Bollinger Band reversion

```yaml
entry:
  long:
    all:
      - "close < bb_lower"
      - "rsi_14 < 35.0"
```

Entry below the lower Bollinger Band with an RSI filter. `bb_lower` and
`rsi_14` are standard base-v1 feature columns.

### 11.6.7 ADX trend filter (inline regime gate)

```yaml
entry:
  long:
    all:
      - "adx_14 < adx_max"
```

When `adx_max` is a knob, this gates entry on low-trending markets without
using the `regime_filter:` mechanism. Use the inline condition when the
threshold is expressed in absolute ADX units. Use `regime_filter:` when
the threshold is expressed as a percentile of a training distribution
(see Chapter 12).

### 11.6.8 HTF trend alignment

```yaml
entry:
  long:
    all:
      - "tf60m_ema_20 > tf60m_ema_50"
  short:
    all:
      - "tf60m_ema_20 < tf60m_ema_50"
```

Entry only when the higher-timeframe trend aligns with the direction.
Requires `higher_timeframes: [60m]` and the 60m feature parquet to exist.

---

## 11.7 Common errors and how to read them

The evaluator raises `ValueError` with a diagnostic message for every
failure mode. Two surfaces report these errors: the `backtest` command
when signal generation runs, and the `validate-strategy` CLI
([Chapter 49.15](49-cli-command-reference.md)) at lint time on a
100-bar synthetic dataset. The lint surface is the fast iteration loop
— it catches the same errors without loading real bars or building an
engine.

| Error message pattern | Cause | Fix |
|-----------------------|-------|-----|
| `Name 'x' is not a column (first 8: [...]) or a knob ([...])` | Bare name not in features or knobs | Check column name against feature inventory; check knob spelling |
| `Invalid expression syntax 'expr': ...` | Python syntax error in expression string | Check parentheses, operator spelling, quoting |
| `Only numeric constants allowed; got str: 'x'` | String literal in expression | Remove quotes; reference a column by bare name |
| `Unsupported binary operator FloorDiv. Allowed: + - * /` | Used `//` | Use `/`; or add a pre-computed column |
| `Unknown function 'min'. Supported functions: shift(column, n)` | Function call other than shift | Pre-compute in feature set; or reformulate |
| `shift() requires exactly 2 arguments: shift(column_name, n)` | Wrong argument count | Add the shift count; e.g., `shift(col, 1)` |
| `First argument to shift() must be a bare column name` | Passed an expression as first arg | Use bare column name; no arithmetic inside shift() |
| `Knob 'x' value 'abc' cannot be used as a number` | Non-numeric knob value | Set knob to a numeric value |
| `Chained comparisons (e.g. a < b < c) are not supported` | Chained comparison | Split into two `all:` conditions |

The fastest debugging workflow is `uv run trading-research
validate-strategy <config_path>` — the command resolves the features
parquet, dry-runs signal generation on synthetic bars, and reports any
name-resolution failures with a "did you mean" hint sourced from the
real schema. If a strategy passes the lint but still errors during a
real backtest, the cause is almost always an interaction with the
exact bar data (e.g., a regime filter fitting on a window with no
qualifying bars); re-run with a short `--from`/`--to` window and read
the traceback.

---

## 11.8 Related references

### Code modules

- [`src/trading_research/strategies/template.py`](../../src/trading_research/strategies/template.py)
  — `ExprEvaluator` class: the full implementation. Lines 106–266
  cover the evaluator; the `_node()` method is the recursive descent
  parser. Read the `_call_shift()` method (lines 245–266) for the
  complete `shift()` specification.

### Other manual chapters

- **Chapter 10 §10.2** — entry block syntax: how conditions are composed
  with `all:` and `any:`.
- **Chapter 10 §10.3** — exits block syntax: how stop and target
  expressions are used.
- **Chapter 13** — configuration reference: the complete key list,
  including valid expression positions.
- **Chapter 49.15** — `validate-strategy` CLI: the lint-time error
  surface for expression errors.
- **Chapter 55.2** — strategy-layer common errors: field-level error
  documentation for operators.

---

*End of Chapter 11. Next: Chapter 12 — Composable Regime Filters.*
