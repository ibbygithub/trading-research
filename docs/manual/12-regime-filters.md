# Chapter 12 — Composable Regime Filters

> **Chapter status:** [EXISTS] — the regime filter layer is fully
> implemented. Only one built-in filter type exists (`volatility-regime`);
> the extension mechanism for adding new types is documented in §12.6.

---

## 12.0 What this chapter covers

A regime filter is a fitted gate that blocks entry signals when the
market is in a condition the strategy is not designed for. This chapter
explains what a filter is, how the built-in `volatility-regime` filter
works, how to wire filters into a strategy YAML, the data-leakage
implications of the `fit_filters` lifecycle, and how to add a new filter
type.

After reading this chapter you will:

- Understand the distinction between an entry condition and a regime filter
- Know the `volatility-regime` filter's parameters and behaviour
- Know the difference between inline and `include:` filter syntax
- Know how to call `fit_filters()` correctly in walk-forward mode to
  avoid leakage
- Be able to compose multiple filters with AND semantics
- Know the protocol and decorator required to add a new filter type

---

## 12.1 What a regime filter is

A regime filter is a **fitted, stateful gate** on top of the entry
conditions. It differs from an entry condition in two important ways:

1. **It is fitted on a training window.** An entry condition like
   `adx_14 < 20.0` uses an absolute threshold. A regime filter computes
   its threshold from the *distribution* of a variable over a training
   period — for example, "block entries when today's ATR is in the top
   quartile of the last six months of ATR values." The threshold depends
   on the data and must be re-fitted each time the training window changes.

2. **It operates at a separate layer.** Regime masks are applied after
   the entry conditions are evaluated and before conflict resolution
   (see the `generate_signals_df` source in `template.py:375`). This
   separation means you can combine any entry logic with any set of
   regime filters without modifying the entry conditions.

The practical motivation: mean-reversion strategies systematically fail
during high-volatility regimes. When ATR is in the top quartile of its
recent distribution, directional event flows tend to dominate; a price
that has moved 2σ away from VWAP is more likely to move further than to
revert. The volatility regime filter is the operationalisation of this
market-structure insight.

> *Why a filter rather than an entry condition:* the distinction becomes
> important in walk-forward evaluation. An entry condition with an absolute
> threshold (`adx_14 < 20.0`) can be evaluated on the test window without
> any reference to training data. A regime filter with a percentile
> threshold (`ATR < P75(ATR)`) must be fitted on the training window —
> the threshold is derived from that distribution, not from a
> pre-committed constant. Using a percentile threshold as an entry
> condition with the percentile computed on the full dataset would be
> leakage; the regime filter lifecycle makes the train/test boundary
> explicit.

---

## 12.2 Built-in filters — `volatility-regime`

The only currently registered filter is `volatility-regime`, implemented
in
[`src/trading_research/strategies/regime/volatility_regime.py`](../../src/trading_research/strategies/regime/volatility_regime.py).

**What it does:** on a given bar, the filter returns True (entry
permitted) if the bar's ATR value is at or below the fitted threshold,
and False (entry blocked) otherwise. Bars with non-finite or non-positive
ATR are always blocked.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vol_percentile_threshold` | float | `75.0` | Percentile of training ATR that sets the threshold. Range [50, 95]. |
| `atr_column` | string | `atr_14` | Feature column name for ATR. Must exist in the features DataFrame. |

**Semantics of the threshold:**

After `fit(train_df)` is called, the filter stores
`P<vol_percentile_threshold>(train_df[atr_column])`. A bar is tradeable
when its ATR is at or below this threshold. At P75, the top 25% of ATR
values (the highest-volatility quarter) are blocked.

**The 75th percentile is structural, not sweepable:**

The P75 threshold is pre-committed in the design specification
(`configs/regimes/volatility-p75.yaml`). It is the standard risk-
management partition — "top quartile" — that real FX desks use to
suspend mean-reversion books during high-vol periods. This value should
not be swept across [50, 60, 70, 80, 90, 95] to find the "best" setting
on the test set. Doing so would transform a structural risk control into
a data-mined parameter, which inflates the deflated Sharpe cost and
defeats the purpose of the filter.

The alternative — using the filter type `volatility-regime` with a
different threshold (e.g., P90 for a strategy designed to trade through
moderately elevated volatility) — is valid when the choice is made on
market-structure grounds and the rationale is documented in the strategy
config.

---

## 12.3 Inline vs `include` syntax

A regime filter can be specified two ways:

**Inline spec** — the filter parameters are written directly in the
strategy YAML:

```yaml
regime_filter:
  type: volatility-regime
  vol_percentile_threshold: 75
  atr_column: atr_14
```

Use this form when the filter parameters are specific to this strategy and
are not shared with others.

**`include:` reference** — the filter spec lives in a shared file at
`configs/regimes/<name>.yaml` and is referenced by name:

```yaml
regime_filter:
  include: volatility-p75
```

The `volatility-p75` name resolves to `configs/regimes/volatility-p75.yaml`.
Use this form when the same filter configuration is used by multiple
strategies — the shared file is the single source of truth, and a change
to the threshold requires editing only one file.

**Overriding shared fields inline:** the two forms can be mixed:

```yaml
regime_filter:
  include: volatility-p75
  atr_column: atr_60m   # override: use 60m ATR instead of the file's default
```

Inline keys take precedence over the loaded file's values.

The shared regime configs currently registered:

| File | type | vol_percentile_threshold | atr_column |
|------|------|--------------------------|------------|
| `volatility-p75.yaml` | `volatility-regime` | 75 | `atr_14` |
| `volatility-p90.yaml` | `volatility-regime` | 90 | `atr_14` |

---

## 12.4 The `fit_filters` lifecycle

Regime filters are stateful: they must be fitted before signals can be
generated. The lifecycle differs between single-window backtests and
walk-forward evaluation.

### 12.4.1 Single-window backtests (non-rolling)

In a single-window backtest (`uv run trading-research backtest ...`),
the filter auto-fits on the full evaluation dataset when
`generate_signals_df` is first called:

```python
# From VolatilityRegimeFilter.vectorized_mask():
if self._threshold is None:
    self.fit(features)  # auto-fit on the same data being evaluated
```

This is acceptable for single-window backtests — the result is a
consistent filter applied to the full history — but it is technically
lookahead: the threshold is derived from the same period being evaluated.
The data scientist notes this in the output; it is a known and accepted
trade-off for single-window backtests.

### 12.4.2 Rolling walk-forward (purged)

In `run_rolling_walkforward`, the runner calls `strategy.fit_filters(train_df)`
explicitly on each fold's training window before calling
`generate_signals_df(test_df)` on the test window:

```python
# Simplified from walkforward.py:
for train_window, test_window in folds:
    strategy.fit_filters(train_window)       # fit on train
    signals = strategy.generate_signals_df(test_window)  # eval on test
```

The threshold computed from `train_window` is then applied to
`test_window`. This is the correct walk-forward evaluation: the filter
sees only the training distribution, not the test period's distribution.

**The critical rule:** in walk-forward mode, `fit_filters(train_df)` must
be called *before* `generate_signals_df(test_df)`. If `generate_signals_df`
is called without a prior `fit_filters`, the filter will auto-fit on the
test data (because `self._threshold is None`), which is leakage.

The `VolatilityRegimeFilter.is_tradeable()` method raises `RuntimeError`
if called without a prior `fit()`:

```
VolatilityRegimeFilter: fit() must be called before is_tradeable().
Pass training-window features to fit() first.
```

This error is the safeguard against accidentally evaluating a filter in
walk-forward mode without fitting it on the training window. The
vectorised path (`vectorized_mask`) silently auto-fits instead of raising;
this is a known inconsistency that will be addressed in a future refactor.

---

## 12.5 Composing multiple filters

Multiple regime filters are specified via the `regime_filters:` key (plural):

```yaml
regime_filters:
  - type: volatility-regime
    vol_percentile_threshold: 75
  - include: trend-filter-adx25
```

All filters are combined with AND semantics: a bar is tradeable only when
every filter permits entry. This is implemented by applying each filter's
mask to the accumulated `mask` array in sequence (see
`template.py:_build_regime_mask`).

The `regime_filter:` (singular) and `regime_filters:` (plural) keys can
coexist — both are parsed and their filter lists are merged. In practice,
use one or the other to avoid ambiguity.

**Ordering.** Filters are applied in the order they appear in the list.
The evaluator short-circuits once a False appears in the mask — this is
an optimisation via NumPy array multiplication, not Python-level
short-circuit evaluation. All filters always run, even if the first
filter has already blocked a bar.

**Performance.** The vectorised path (`vectorized_mask`) runs in O(n)
time for the `VolatilityRegimeFilter`. Custom filters that use the
`is_tradeable(df, idx)` Protocol method without a `vectorized_mask`
optimisation run in O(n × Python_overhead) time. For large backtests
(10M+ bars), the vectorised path matters.

---

## 12.6 Adding a new regime filter type

To add a new filter type, implement the `RegimeFilter` Protocol and
register it with the `@register_filter` decorator.

### 12.6.1 The RegimeFilter Protocol

```python
from typing import Protocol, runtime_checkable
import pandas as pd

@runtime_checkable
class RegimeFilter(Protocol):
    @property
    def name(self) -> str: ...
    def fit(self, features: pd.DataFrame) -> None: ...
    def is_tradeable(self, features: pd.DataFrame, idx: int) -> bool: ...
```

Every filter must implement:

- `name` (property) — human-readable identifier used in logging and error
  messages. Convention: `"filter-type(param_summary)"`, e.g.,
  `"volatility-regime(p75)"`.
- `fit(features)` — compute any thresholds from the training-window
  features DataFrame. Called once per fold (in walk-forward) or once
  on the full dataset (in single-window). Must be idempotent — calling
  `fit()` again resets the threshold.
- `is_tradeable(features, idx)` — return True if the bar at integer
  position `idx` is in a tradeable regime. Must raise `RuntimeError` if
  called before `fit()`.

### 12.6.2 Registering the filter

Use the `@register_filter` class decorator from
`src/trading_research/strategies/regime/__init__.py`:

```python
from trading_research.strategies.regime import register_filter

@register_filter("trend-filter")
class TrendFilter:
    def __init__(self, *, adx_threshold: float = 25.0, ...) -> None:
        ...
```

The string passed to `@register_filter` is the `type:` value in the YAML.
After registration, the filter is instantiated via `build_filter("trend-filter", **kwargs)`.

### 12.6.3 The `vectorized_mask` optimisation hook

If the filter's evaluation over all bars can be expressed as a NumPy
operation rather than a Python loop, add a `vectorized_mask` method:

```python
def vectorized_mask(self, features: pd.DataFrame) -> np.ndarray:
    """Return bool ndarray: True where tradeable."""
    if self._threshold is None:
        self.fit(features)
    col = features[self._column].to_numpy(dtype=float)
    return np.isfinite(col) & (col <= self._threshold)
```

The `_build_regime_mask` method in `YAMLStrategy` checks for
`VolatilityRegimeFilter` specifically and uses `vectorized_mask` when
available. To make your filter use this optimisation, add the method and
update the dispatch in `template.py:_build_regime_mask` to include your
filter class. A future refactor will make this check Protocol-based rather
than type-specific.

### 12.6.4 Making the filter accessible by name

The filter must be importable for `@register_filter` to fire. The
`src/trading_research/strategies/regime/__init__.py` module imports
all concrete filter implementations at the bottom:

```python
from trading_research.strategies.regime import volatility_regime as _vol_regime
```

Add a similar import for the new module at the bottom of `__init__.py`.

---

## 12.7 Related references

### Code modules

- [`src/trading_research/strategies/regime/__init__.py`](../../src/trading_research/strategies/regime/__init__.py)
  — `RegimeFilter` Protocol, `@register_filter`, `build_filter`,
  `RegimeFilterChain`. The authoritative Protocol definition.

- [`src/trading_research/strategies/regime/volatility_regime.py`](../../src/trading_research/strategies/regime/volatility_regime.py)
  — `VolatilityRegimeFilter`: the reference implementation and the
  `vectorized_mask` optimisation example.

- [`src/trading_research/strategies/template.py:475`](../../src/trading_research/strategies/template.py)
  — `_build_regime_mask`: where regime masks are assembled per bar in
  `generate_signals_df`.

### Configuration

- [`configs/regimes/volatility-p75.yaml`](../../configs/regimes/volatility-p75.yaml)
  — the structural P75 filter config; reference for new shared configs.

- [`configs/strategies/6a-vwap-reversion-mtf-v1.yaml`](../../configs/strategies/6a-vwap-reversion-mtf-v1.yaml)
  — an example strategy using `regime_filter: { include: volatility-p75 }`.

### Other manual chapters

- **Chapter 9 §9.3** — overfitting smell: why the volatility-regime
  threshold must be structural and not swept.
- **Chapter 10 §10.2** — entry block: how regime masks interact with
  entry conditions and time windows.
- **Chapter 22 §22.3** — rolling walk-forward: the fold structure that
  makes `fit_filters(train_df)` necessary.

---

*End of Chapter 12. Next: Chapter 13 — Strategy Configuration Reference.*
