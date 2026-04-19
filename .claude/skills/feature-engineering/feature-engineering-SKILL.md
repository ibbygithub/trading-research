---
name: feature-engineering
description: Use when creating features for machine learning models from bar data and indicators, when designing labels (targets) for supervised learning on trading strategies, when implementing train/validation/test splits that respect time ordering, when handling stationarity and fractional differentiation, when computing purged k-fold cross-validation, or when investigating leakage in any ML pipeline. This skill defines the labeling methodologies (triple barrier, meta-labeling), the leakage-prevention rules, and the feature store layout. Invoke whenever data is being transformed for ML consumption rather than for direct strategy use.
---

# Feature Engineering

This skill owns the transformation of raw bars and indicators into the inputs and outputs of machine learning models. Its job is to make sure that when an ML model is trained on this data, the data is honest — meaning the features available at training time would actually have been available at the moment of decision in production, and the labels being predicted are well-defined and don't leak information from the future.

The principle: **leakage is the default; honesty requires effort.** Almost every ML pipeline for trading has subtle leakage somewhere. The features include the close of the bar being predicted. The training set includes data that overlaps in time with the test set. The labels are computed using future information that the model uses to look ahead. The cross-validation folds don't account for the holding period of the predicted positions. Each of these is a bug, each is invisible without explicit checks, and each will produce a model that backtests beautifully and fails in production.

The second principle: **simpler is almost always better.** A linear regression on five thoughtful features will beat a 200-feature XGBoost in production more often than the reverse, because the simpler model is easier to debug, easier to validate, and harder to overfit. The framework supports complex models, but the data scientist persona will always ask "did you try the simple version first?" and the framework will refuse to evaluate a complex model without a simple-baseline comparison.

## What this skill covers

- Feature creation from bars and indicators
- Stationarity transforms (returns, log returns, fractional differentiation)
- Labeling methods (binary, multi-class, regression, triple-barrier, meta-labeling)
- Train/validation/test splits that respect time
- Purged k-fold and combinatorially-purged cross-validation
- The feature store layout in `data/features/`
- Leakage detection rules and tests
- The "simple baseline first" rule

## What this skill does NOT cover

- The actual ML model training (see `ml-modeling`)
- Indicator math (see `indicators`)
- Backtest execution (see `backtesting`)
- Strategy logic that consumes ML predictions (see `backtesting` for the strategy interface)

## The fundamental contract

Every feature in this project conforms to the same as-of rule that indicators do:

> **A feature value at bar N must be computable using only data through bar N (or bar N-1, depending on the strategy's fill model).**

This is non-negotiable. A feature that uses bar N's close to predict something that the strategy decides at bar N's close is leakage. A feature that uses any data from bar N+1 or later is leakage. The features module enforces this with explicit tests, the same as-of correctness tests the indicators module uses.

The trickier version: a feature that uses bar N-1 looks safe but isn't if the strategy's fill model is "trigger bar close" — because at bar N-1's close, the bar N data isn't yet available, so a feature that uses bar N is using future data from the strategy's perspective. The safest convention is **all features at bar N use only data through bar N-1**, and the strategy's decision at bar N takes effect at bar N+1's open. This adds a one-bar delay but eliminates an entire class of subtle bugs.

## Stationarity and the differencing problem

Most ML models assume the data is *stationary* — that its statistical properties (mean, variance, autocorrelation) don't drift over time. Raw price series are not stationary; they trend, they have changing volatility, they have regime shifts. Training a model on raw prices teaches it the wrong things.

The standard fixes:

**Returns.** First difference of price: `p[t] - p[t-1]`. Or equivalently for percentage returns: `(p[t] - p[t-1]) / p[t-1]`. Returns are typically stationary even when prices aren't. This is the standard transform and works for most cases.

**Log returns.** `log(p[t]) - log(p[t-1]) = log(p[t] / p[t-1])`. Equivalent to percentage returns for small changes, but additive across time (the log return of a 5-bar window equals the sum of the 5 individual log returns, which is convenient for some computations).

**Fractional differentiation (Lopez de Prado).** A more sophisticated approach that finds the *minimum amount of differencing* needed to make a series stationary while preserving as much memory as possible. Standard differencing (which produces returns) is `d=1`; fractional differencing uses `d` between 0 and 1, often around 0.3-0.5 for financial series. The result is a series that's stationary AND retains some of the level information that returns throw away.

The case for fractional differencing is strongest when you're using ML models that benefit from the level information in addition to the change information — for example, when you want the model to know "we're in a high-volatility regime" not just "the most recent change was large." For simpler models on intraday data, standard returns are usually fine.

```python
# src/trading_research/features/stationarity.py
import polars as pl
import numpy as np

def percentage_returns(series: pl.Series, periods: int = 1) -> pl.Series:
    """Simple percentage returns over `periods` bars."""
    return series.pct_change(n=periods)

def log_returns(series: pl.Series, periods: int = 1) -> pl.Series:
    """Log returns over `periods` bars."""
    log_prices = series.log()
    return log_prices - log_prices.shift(periods)

def fractional_difference(
    series: pl.Series,
    d: float = 0.4,
    threshold: float = 0.01,
) -> pl.Series:
    """Fractionally differenced series per Lopez de Prado.

    Args:
        d: the differencing order, typically 0.3-0.5 for financial series
        threshold: weight cutoff for truncating the infinite weight series

    Returns a series with NaNs at the start (warmup period) and stationary
    differenced values afterward.
    """
    # Compute weights for the fractional difference
    weights = [1.0]
    k = 1
    while True:
        w = -weights[-1] * (d - k + 1) / k
        if abs(w) < threshold:
            break
        weights.append(w)
        k += 1
    weights = np.array(weights)

    values = series.to_numpy()
    result = np.full(len(values), np.nan)
    skip = len(weights)

    for i in range(skip, len(values)):
        result[i] = np.dot(weights, values[i - skip + 1:i + 1][::-1])

    return pl.Series(result)
```

The data scientist persona will check that any series fed into an ML model has been tested for stationarity (via ADF, from `indicators`) and transformed if needed. A model trained on non-stationary data is a model that's learning the wrong things.

## Labeling methods

Labels are the things ML models predict. For trading strategies, the label is typically "what should the strategy have done at this bar?" or "what happened to the price after this bar?" The choice of labeling method matters enormously because different labels teach the model different things and have different leakage profiles.

**Binary classification: direction.** The label is 1 if the price went up by some amount within some horizon, 0 otherwise. Simple but coarse — it throws away magnitude information.

**Regression: forward return.** The label is the actual return over some horizon. More information than binary but harder to learn because the target has a wide distribution and a lot of noise.

**Triple barrier (Lopez de Prado).** The label is determined by whichever of three barriers the price hits first, within a time window:
- Upper barrier: a profit target (defined in absolute, percentage, or volatility terms)
- Lower barrier: a stop loss
- Vertical barrier: a time limit

The label is +1 if the upper barrier is hit first, -1 if the lower barrier, 0 if the vertical (timeout). This is the standard quant labeling method for trading strategies because it directly corresponds to the structure of an actual trade with TP/SL/timeout exits.

```python
# src/trading_research/features/labeling.py
from dataclasses import dataclass
import polars as pl
import numpy as np

@dataclass(frozen=True)
class TripleBarrierConfig:
    profit_target_pct: float        # e.g. 0.005 for 0.5%
    stop_loss_pct: float            # e.g. 0.005 for 0.5%
    max_holding_bars: int           # e.g. 20 for 20-bar timeout
    use_volatility_scaling: bool = True   # scale barriers by recent ATR
    atr_period: int = 20
    atr_multiplier: float = 1.0     # if vol scaling, multiply ATR by this for barriers

def triple_barrier_labels(
    bars: pl.DataFrame,
    config: TripleBarrierConfig,
) -> pl.DataFrame:
    """Generate triple-barrier labels for every bar in the dataset.

    For each bar i, look forward up to max_holding_bars and determine
    whether the price hit the upper barrier, lower barrier, or timed out.

    Returns a DataFrame with columns:
        bar_index: the source bar
        label: -1, 0, or +1
        exit_bar_index: which forward bar the label was determined by
        exit_reason: "upper", "lower", or "timeout"
        forward_return_at_exit: the return from bar i to the exit bar

    NOTE: this function uses future bars (i+1 through i+max_holding_bars)
    to compute labels for bar i. This is leakage WITH RESPECT TO bar i's
    features but NOT leakage with respect to the model's purpose, because
    the labels are what the model is trying to predict. The leakage rule
    applies to features, not labels.

    However, when training, you must:
        1. Ensure features at bar i use only data through bar i-1
        2. Apply purge gaps in cross-validation equal to max_holding_bars
        3. Never include the label of bar i in any feature for any other bar
    """
```

**Meta-labeling.** A two-stage approach: first, a primary model produces a binary direction signal (or a rule-based signal). Second, a meta-model predicts whether to *act* on the primary signal — essentially a "confidence" model that filters the primary signals. The meta-model is trained on the outcomes of the primary model's signals, with the label being "did this primary signal work?"

Meta-labeling is a powerful technique because it lets you keep a simple, interpretable primary model and add a thin layer of ML on top to filter false positives. It's also less prone to overfitting than a single complex model that tries to predict everything at once. For Ibby's mean-reversion-with-MACD-divergence pattern, meta-labeling could mean: the rule-based MACD divergence signal is the primary model, and a meta-model trained on past divergence trades predicts which ones are worth taking.

The data scientist persona prefers meta-labeling over single-stage classification for most trading problems because it preserves the interpretability of the underlying signal while adding ML's value where ML actually helps (filtering noise).

## Train/validation/test splits

For time-series data, **never use random train/test splits.** A random split puts test data scattered through the same time range as training data, which means the model can effectively memorize the training context and apply it to "test" points that are temporally adjacent to training points. This is a form of leakage and produces wildly optimistic results.

The correct approach: **temporal splits.** The training set is some early time window. The validation set is a later time window. The test set is the most recent time window. The model sees training data, gets tuned on validation data, and is evaluated once on test data.

```python
# src/trading_research/features/splits.py
from dataclasses import dataclass
from datetime import date, timedelta
import polars as pl

@dataclass(frozen=True)
class TimeSplitConfig:
    train_start: date
    train_end: date
    purge_days_before_val: int      # gap between train end and val start
    val_end: date                   # val_start = train_end + purge_days
    purge_days_before_test: int
    test_end: date

def temporal_split(
    bars_with_labels: pl.DataFrame,
    config: TimeSplitConfig,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Split a labeled dataset into train, validation, and test by time.

    Returns three DataFrames with no temporal overlap. Purge gaps are
    enforced between train and val, and between val and test, to prevent
    label leakage from overlapping holding periods.
    """
    train = bars_with_labels.filter(
        (pl.col("timestamp_ny").dt.date() >= config.train_start) &
        (pl.col("timestamp_ny").dt.date() <= config.train_end)
    )

    val_start = config.train_end + timedelta(days=config.purge_days_before_val)
    val = bars_with_labels.filter(
        (pl.col("timestamp_ny").dt.date() >= val_start) &
        (pl.col("timestamp_ny").dt.date() <= config.val_end)
    )

    test_start = config.val_end + timedelta(days=config.purge_days_before_test)
    test = bars_with_labels.filter(
        (pl.col("timestamp_ny").dt.date() >= test_start) &
        (pl.col("timestamp_ny").dt.date() <= config.test_end)
    )

    return train, val, test
```

**The purge gap.** Between the end of training and the start of validation, leave a gap equal to (or larger than) the maximum label horizon. If your triple-barrier labeling looks 20 bars forward, your purge gap should be at least 20 bars (or one day, to be safe). This prevents the situation where the last training bar's label was determined by a forward window that overlaps with the first validation bar — which would mean the validation set contains information the model already saw in training.

The same purge applies between validation and test.

## Purged k-fold cross-validation

For walk-forward backtests and for hyperparameter tuning, k-fold cross-validation is more powerful than a single train/val split. But standard k-fold doesn't work for time series because the folds aren't temporally ordered.

**Purged k-fold (Lopez de Prado)** adapts k-fold to time series by:

1. Sorting the data by time
2. Splitting it into k contiguous folds
3. For each fold-as-test:
   - Training on all other folds
   - **Purging** training points whose labels were determined by forward windows that overlap with the test fold
   - **Embargoing** training points immediately after the test fold (to prevent the test fold's information from leaking into training via correlated features)

The result is k models trained on different temporal subsets, each evaluated on a held-out window with no leakage from the test window into training.

```python
# src/trading_research/features/cross_validation.py
from dataclasses import dataclass

@dataclass(frozen=True)
class PurgedKFoldConfig:
    n_splits: int = 5
    purge_bars: int = 20            # bars to purge around test fold
    embargo_pct: float = 0.01       # fraction of dataset size to embargo after test fold

def purged_k_fold_splits(
    n_samples: int,
    config: PurgedKFoldConfig,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Generate purged k-fold splits.

    Returns a list of (train_indices, test_indices) tuples. Each train set
    excludes any sample within `purge_bars` of the test fold's start, and
    excludes any sample within the embargo region after the test fold.
    """
```

**When to use purged k-fold vs. walk-forward:**

- **Walk-forward** (in `backtesting`): for evaluating strategy performance over time. Each step is a separate train+test cycle, and the test windows accumulate into an out-of-sample equity curve.
- **Purged k-fold** (here): for hyperparameter tuning and feature selection. You want multiple validation folds to get a stable estimate of model performance, and you want them all to be honest.

The two are complementary: tune hyperparameters with purged k-fold on a training period, then evaluate the tuned model with walk-forward on the held-out period.

## Combinatorially-purged cross-validation

For hyperparameter sweeps that test many configurations, even purged k-fold can be too generous because the same test folds get reused across configurations. **Combinatorially-purged CV** (CPCV) is a more aggressive variant that uses many different splits of the data into training and test groups, so that any given configuration is tested against many different out-of-sample periods.

CPCV is computationally expensive (you train many more models) but produces statistically more robust performance estimates and feeds directly into the **Probability of Backtest Overfitting (PBO)** metric. Defer to build time on whether this is worth the cost for any specific use case.

## The feature store

Computed features are stored in `data/features/`. The convention:

```
data/features/
├── ZN_1m_2020-01-01_2024-12-31_indicators.parquet         # bars + indicator columns
├── ZN_1m_2020-01-01_2024-12-31_indicators.metadata.json   # what was computed and how
├── ZN_1m_2020-01-01_2024-12-31_features_v1.parquet        # ML features for model v1
├── ZN_1m_2020-01-01_2024-12-31_features_v1.metadata.json
├── ZN_1m_2020-01-01_2024-12-31_labels_triple_barrier.parquet  # triple-barrier labels
└── ZN_1m_2020-01-01_2024-12-31_labels_triple_barrier.metadata.json
```

Features and labels are stored separately because they have different lifecycles. A given feature set might be reused with multiple labeling schemes (predict 5-bar return, predict 20-bar triple barrier, etc.) and a given labeling scheme might be reused with multiple feature sets. Storing them in separate files makes the cross-product manageable.

The metadata JSON files document exactly what was computed:

```json
{
  "source_parquet": "data/clean/ZN_1m_2020-01-01_2024-12-31.parquet",
  "feature_set_name": "v1_basic_ml",
  "features": [
    {"name": "return_1", "func": "percentage_returns", "params": {"periods": 1}},
    {"name": "return_5", "func": "percentage_returns", "params": {"periods": 5}},
    {"name": "rsi_14_normalized", "func": "rsi_normalized", "params": {"period": 14}},
    {"name": "bb_pct_b_20_2", "func": "bollinger_pct_b", "params": {"period": 20, "n_std": 2}},
    {"name": "atr_14_log", "func": "log_atr", "params": {"period": 14}},
    {"name": "frac_diff_close_04", "func": "fractional_difference", "params": {"d": 0.4}}
  ],
  "as_of_rule": "features at bar i use only data through bar i-1",
  "computation_timestamp_utc": "2025-01-15T16:32:33Z",
  "passes_asof_test": true
}
```

The `passes_asof_test` field is critical. Every features file is generated by code that's been verified against the as-of correctness test (same test pattern as indicators). A features file with `passes_asof_test: false` is unusable and the framework refuses to feed it to a model.

## Leakage detection

Beyond the as-of test for features, there are several other leakage patterns the framework actively checks for:

**Temporal overlap between train and test.** Any sample in the test set whose timestamp is within `[train_end, train_end + label_horizon]` is leaked. The split functions enforce purge gaps to prevent this.

**Feature-label correlation that's too high to be true.** If a feature has correlation > 0.95 with the label across the training set, it's almost certainly using future data. The framework warns whenever a feature's correlation with the label exceeds 0.7, because anything that high in trading data is suspicious.

**Same-bar features and labels.** A feature computed at bar N using data through bar N, paired with a label that's a forward return starting at bar N, can be subtly leaky depending on how the feature is implemented. The safe rule: features at bar N use data through bar N-1, labels at bar N use data from bar N forward.

**Group leakage.** If labels are computed via a process that includes information from bars adjacent to bar N (like the triple-barrier method, which looks forward), then training and validation samples whose label-determining windows overlap are leaked even if the bar timestamps don't directly overlap. The purge gap in cross-validation handles this.

The data scientist persona will run a leakage report on any new feature/label combination before allowing it to be used for model training. The report is short — it's a checklist of the patterns above with pass/fail for each — and lives in the features metadata.

## The simple-baseline rule

Before any complex model is trained, a simple baseline must be trained and evaluated. The baseline is typically:

- **For classification:** logistic regression with the same features
- **For regression:** linear regression with the same features
- **For trading specifically:** a rule-based version of the same idea, with no ML at all

The complex model's performance is reported *relative to the baseline*, not in absolute terms. If a 200-feature XGBoost has 0.62 accuracy and the linear baseline has 0.61, the XGBoost is not adding meaningful value. If a meta-labeling XGBoost has 0.68 accuracy and the rule-based primary signal has 0.55, the ML layer is adding 13 percentage points and is worth its complexity cost.

The data scientist persona enforces this. The mentor reinforces it. Together they'll refuse to celebrate a complex model until the comparison has been done.

## Standing rules this skill enforces

1. **All features pass the as-of correctness test.** Same test pattern as indicators.
2. **All splits are temporal, never random.** Random splits on time series are leakage.
3. **All cross-validation uses purge gaps.** The gap is at least the label horizon.
4. **Features at bar N use data through bar N-1.** This is the safe convention that eliminates an entire class of subtle bugs.
5. **Triple-barrier labeling is the default for trading-strategy ML.** Other methods are available but require justification.
6. **Stationarity is checked before training.** Non-stationary features get transformed (returns, log returns, fractional difference).
7. **A simple baseline is required before any complex model is evaluated.** The framework refuses to report complex-model performance without the baseline comparison.
8. **Feature/label sets are stored separately** so they can be combined orthogonally.
9. **Feature/label metadata documents the exact computation.** Reproducibility is non-negotiable.

## When to invoke this skill

Load this skill when the task involves:

- Creating features from bars and indicators for ML use
- Designing labels (binary, regression, triple-barrier, meta)
- Splitting datasets into train/validation/test for ML
- Implementing or running purged k-fold cross-validation
- Investigating leakage in an existing pipeline
- Computing stationarity transforms (returns, log returns, fractional difference)
- Storing or reading feature/label files in `data/features/`

Don't load this skill for:

- Indicator math (use `indicators`)
- Actual model training and evaluation (use `ml-modeling`)
- Backtest execution (use `backtesting`)

## Open questions for build time

1. **Whether to use polars or pandas for feature pipelines.** Polars is faster and the project's default. Some scikit-learn integrations expect pandas; convert at the boundary.
2. **How to handle missing features for some bars.** Forward-fill, drop, or impute? Default to drop (rows with any NaN feature are excluded from training); imputation can be added per-feature when needed.
3. **Whether to support online (incremental) feature computation.** Useful for streaming/live use; not needed for backtest. The same feature definitions should work in both modes — implement once, expose two interfaces.
4. **Whether the feature store should be versioned with content hashes** so that "the features file from yesterday's training run" is reproducible from its hash. Probably yes for production; defer for now.
