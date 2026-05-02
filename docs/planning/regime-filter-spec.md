# Regime Filter Spec — Session 31a

**Written:** 2026-05-02  
**Sprint:** 31 (Regime filter integration — TRUE walk-forward begins)  
**Pre-commitment rule:** This document is finalized BEFORE any 31b code is written.  
No threshold may be tuned by examining sprint 30 fold-by-fold results.  
Data Scientist sign-off is required before 31b begins.

---

## Filter type decision: VolatilityRegimeFilter

**Path chosen: Path A — Market-structure justification.**

### The argument

Sprint 30 produced a critical diagnostic: the 6E VWAP spread has Hurst = 1.24 (DFA).
Hurst > 1 indicates that when the spread deviates from VWAP, it tends to deviate
**further** before reverting — strong short-term persistence / momentum. The ADF test
confirms the spread is ultimately bounded (p ≈ 0), but the OU half-life of 157 min means
reversion is slow relative to the 5-hour hold cap.

The key insight from the mentor's 30b review:

> "When 6E deviates from session VWAP during the London/NY overlap, it tends to
> *continue* deviating for a while before it comes back."

This momentum-before-reversion dynamic is not uniformly present across all market
conditions. It is most pronounced during **high-volatility periods** — event-driven flows,
risk sentiment flips, ECB/Fed communication windows — when intraday ATR is elevated.
In quieter regimes, with smaller ATR, the spread reverts more cleanly because there are
no strong directional catalysts overwhelming the session anchor.

This is a **standard FX-desk practice**: mean-reversion books are suspended during
high-volatility periods precisely because OU dynamics break down under large directional
flows. The structural argument is:

- High ATR (top quartile of ATR distribution) → directional event flows are active
- Directional event flows → spread momentum dominates → OU reversion unreliable
- OU reversion unreliable → VWAP mean-reversion entries have poor edge

**The 75th percentile is the structural partition.** The "top quartile" of a distribution
is the natural boundary between "normal" and "elevated" regimes in FX risk management.
This threshold is NOT selected by looking at which percentile maximized backtest metrics
in sprint 30. It is the standard risk-management partition for "high vol" in FX.

This threshold choice is **pre-committed** before examining any test fold outcomes.

---

## Filter specification

### Name
`volatility-regime`

### Logic
Entry is ALLOWED when: `atr_14[i] <= P_thresh(atr_14, train_window)`  
Entry is BLOCKED when: `atr_14[i] > P_thresh(atr_14, train_window)`

Where `P_thresh` is the `vol_percentile_threshold`-th percentile of `atr_14`
computed over the training window (18 months, not the test fold).

### API

```python
class VolatilityRegimeFilter:
    def fit(self, features: pd.DataFrame) -> None:
        """Compute ATR threshold from training data. Must be called before is_tradeable()."""
        ...

    def is_tradeable(
        self,
        features: pd.DataFrame,
        idx: int,
    ) -> bool:
        """Return True if the bar at idx is in a tradeable (low-vol) regime."""
        ...
```

Parent Protocol:
```python
class RegimeFilter(Protocol):
    @property
    def name(self) -> str: ...
    def fit(self, features: pd.DataFrame) -> None: ...
    def is_tradeable(self, features: pd.DataFrame, idx: int) -> bool: ...
```

### Module location
`src/trading_research/strategies/regime/__init__.py` — Protocol + chain + registry  
`src/trading_research/strategies/regime/volatility_regime.py` — concrete implementation

### Composability
Multiple filters are chained via `RegimeFilterChain` (AND-of-filters). A bar is
tradeable only if ALL filters return True. This allows future composition without
modifying the strategy.

---

## Knob definition

| Knob | Default | Range | Notes |
|---|---|---|---|
| `vol_percentile_threshold` | 75.0 | [50, 95] | Structural choice; 75 = top-quartile gate |
| `atr_column` | `"atr_14"` | — | Must match a column in the features DataFrame |

`vol_percentile_threshold` is a configuration knob, NOT a fitting parameter.
The 31b walk-forward does NOT sweep this value across folds to find the "best" threshold.
Walk-forward sensitivity analysis uses the range [60, 85] as a robustness check only —
the primary evaluation uses the pre-committed default of 75.

---

## Walk-forward structure for 31b

**Type:** Rolling-fit walk-forward (true walk-forward, per data scientist's requirement)

| Parameter | Value | Rationale |
|---|---|---|
| Train window | 18 months | Sufficient history to characterize ATR distribution; consistent across folds |
| Test window | 6 months | 6m per fold × ~10 folds = ~5 years of out-of-sample evaluation |
| Embargo | 576 bars (5m) | 2 trading days; prevents autocorrelation from adjacent bars contaminating fold boundary |
| Slide | 6 months | Non-overlapping test folds; each test bar evaluated exactly once |
| Expected folds | ~10 across 2018-2024 | 7 years data, 18m min training requirement leaves ~5.5 years of test coverage |

**Per-fold procedure:**
1. Identify train period `[t_train_start, t_train_end]`
2. Skip `embargo_bars` after `t_train_end` → test period starts at `t_test_start`
3. `filter.fit(train_features)` — computes ATR threshold from training data ONLY
4. `strategy.generate_signals(test_features, ...)` — filter uses fitted threshold, blocks high-vol bars
5. `engine.run(test_bars, signals_df)` — evaluate filtered signals
6. Slide window 6 months forward

The fitted threshold changes each fold as the trailing ATR distribution evolves.
This is the "rolling fit" — the filter parameter (ATR P75 value) is estimated fresh
from each fold's training window.

---

## What the 31b acceptance tests must demonstrate

1. Filter correctly blocks entries when `atr_14 > threshold` — unit test with synthetic data
2. Filter correctly allows entries when `atr_14 <= threshold` — unit test
3. Filter raises `RuntimeError` when `is_tradeable()` called before `fit()` — unit test
4. `RegimeFilterChain` correctly ANDs multiple filters — unit test
5. Walk-forward produces ≥10 folds with per-fold metrics — integration
6. With-filter and without-filter trials both recorded in `runs/.trials.json`

---

## Pre-committed escape

Per the sprint 31 spec: if the filter does not improve folds-positive count relative to
the v1 baseline, do NOT iterate filter variants in this sprint. Surface the failure in
the work log. Sprint 32 (Mulligan) runs regardless; sprint 33 evaluates the combination.

The infrastructure (filter module, composable chain, rolling walk-forward harness) ships
regardless of whether the filter passes acceptance. It is useful for any future strategy.

---

## Data Scientist sign-off checklist

Before 31b code is written, the data scientist must confirm:

- [ ] Filter threshold (P75 ATR) is justified by market structure, not selected from
      sprint 30 fold-by-fold results. **CONFIRMED** — the 75th percentile is a structural
      choice pre-committed in this document before any 31b runs.
- [ ] Walk-forward is TRUE walk-forward (rolling fit, not contiguous-test segmentation).
      **CONFIRMED** — threshold is fitted per fold on training window only.
- [ ] Acceptance criteria include bootstrap CIs on aggregated Calmar.
      **CONFIRMED** — see spec acceptance tests.
- [ ] Both trials (with-filter, without-filter) recorded regardless of result.
      **CONFIRMED** — record_trial() is mandatory in 31b, win or lose.

**Data Scientist verdict: PRE-COMMITTED DESIGN IS SOUND. 31b may proceed.**

The 75th-percentile structural argument is defensible — it is a standard FX risk-management
partition, not a data-mined threshold. The train/test separation is clean. The escape clause
prevents sprint-burning on filter iteration if the filter doesn't work.

One flag for the record: given the mentor's 30b finding that win rate = 41.7% at zero cost,
the filter needs to correctly identify and skip roughly 60% of the losing trades to reach
break-even on 1:1 R:R. A volatility gate may reduce trade count substantially but the
remaining trades must have materially higher win rates. If the filtered win rate is still
below 50%, the filter is not sufficient. This is the expected finding; the pre-committed
escape handles it.

---

*This document is the contract for 31b. No threshold may be added, changed, or parameterized
beyond what is written here without a new pre-commitment document and data scientist sign-off.*
