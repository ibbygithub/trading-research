---
name: ml-modeling
description: Use when training, evaluating, or deploying machine learning models that produce trading signals or filter rule-based signals. This skill covers classical models (linear/logistic regression as baselines, ARIMA for time series), tree-based models (random forest, XGBoost, LightGBM), model evaluation with proper time-series methodology, hyperparameter tuning, model cards for production, and the integration of trained models into the strategy interface. Invoke when building or modifying any ML model used by a strategy, when investigating poor model performance, when designing the inference path from a saved model to a live signal, or when comparing models against baselines.
---

# ML Modeling

This skill owns the training, evaluation, and serving of machine learning models in the project. Its job is to make sure that any model that ends up influencing a trading decision has been honestly trained, honestly evaluated, and is being used in a way that matches how it was tested. This is a high bar and it's deliberately so — most ML failures in trading come not from bad models but from good models being used in ways their training didn't validate.

The principle: **the model is a feature, not a strategy.** A trained model produces a number — a prediction, a classification, a probability. The strategy decides what to do with that number. Keeping these separate means you can swap models without rewriting strategies, you can verify the model in isolation from the strategy, and you can debug the boundary explicitly. A "strategy that is the model" is harder to reason about and harder to fix when things go wrong.

The second principle: **simpler models, more often than you think.** The data scientist persona will ask "did you try a linear model first?" on every ML task, and the framework will require a simple-baseline comparison before any complex model can be used in production. This isn't anti-ML dogma — it's the empirical observation that on noisy financial data, simple models generalize better than complex ones, and the cases where complex models genuinely help are rare and need to be proven, not assumed.

## What this skill covers

- The model interface and lifecycle (train, evaluate, save, load, predict)
- Classical models: linear regression, logistic regression, ARIMA
- Tree models: random forest, XGBoost, LightGBM
- Hyperparameter tuning with purged cross-validation
- Model evaluation metrics (classification: accuracy, precision, recall, AUC, log loss; regression: MSE, MAE, R²; trading-specific: hit rate, profit factor of model-driven trades)
- Model cards (the documentation that travels with every saved model)
- Saving and loading models in a reproducible way
- The inference path from saved model to live signal
- The simple-baseline rule and how the framework enforces it

## What this skill does NOT cover

- Feature creation and labeling (see `feature-engineering`)
- Strategy logic that consumes model predictions (see `backtesting`)
- Risk and sizing of trades that come from models (see `risk-management`)
- Backtest evaluation of model-driven strategies (see `strategy-evaluation`)

## The model interface

Every model in this project implements a small, consistent interface so that strategies can use models interchangeably and so that the framework can load models without needing to know which library produced them.

```python
# src/trading_research/ml/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import polars as pl

@dataclass(frozen=True)
class ModelMetadata:
    model_id: str                       # unique identifier, e.g. "zn_macd_meta_v3"
    model_type: str                     # "logistic_regression", "xgboost", etc.
    feature_set: str                    # name of the feature set used for training
    label_definition: str               # name of the labeling method
    train_period: tuple[str, str]       # (start_date, end_date) of training data
    train_samples: int                  # number of training samples
    cv_method: str                      # "purged_kfold", "walk_forward", etc.
    cv_n_splits: int
    purge_bars: int
    hyperparameters: dict[str, Any]
    cv_metrics: dict[str, float]        # cross-validated metrics
    holdout_metrics: dict[str, float]   # held-out test metrics (computed once at the end)
    baseline_metrics: dict[str, float]  # the simple baseline's metrics for comparison
    framework: str                      # "scikit-learn", "xgboost", etc.
    framework_version: str
    trained_at_utc: str
    git_commit: str                     # commit hash at training time

class TradingModel(ABC):
    """Base class for all models in the project."""

    def __init__(self, metadata: ModelMetadata):
        self.metadata = metadata

    @abstractmethod
    def fit(self, X: pl.DataFrame, y: pl.Series) -> None:
        """Train the model on the given features and labels."""
        ...

    @abstractmethod
    def predict(self, X: pl.DataFrame) -> pl.Series:
        """Predict for new feature rows. Returns a series of predictions."""
        ...

    @abstractmethod
    def predict_proba(self, X: pl.DataFrame) -> pl.DataFrame:
        """For classifiers: predict class probabilities. Raises for regressors."""
        ...

    @abstractmethod
    def feature_importance(self) -> dict[str, float]:
        """Return feature importance scores. For models without native importance,
        returns coefficients (linear) or computes permutation importance."""
        ...

    @abstractmethod
    def save(self, path: Path) -> None:
        """Save the trained model and its metadata to a directory."""
        ...

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> "TradingModel":
        """Load a trained model from a directory."""
        ...
```

**The contract:** every model takes a polars DataFrame of features (rows are bars, columns are features) and a polars Series of labels, and produces predictions for new feature rows. The framework handles polars↔pandas/numpy conversion at the boundary for libraries that expect pandas (scikit-learn) or numpy (XGBoost native API).

The metadata is stored alongside the model file and travels with it forever. Six months after training, you can answer "what was this model, what data did it see, how did it perform, and what version of the framework produced it" by reading the metadata.

## Classical models

**Linear regression** (for regression labels, like forward returns).

The least glamorous model in ML and one of the most useful in trading. Fast to train, fast to predict, completely interpretable, and the coefficients tell you exactly how each feature contributes to the prediction. If a linear regression on 5 features matches your XGBoost on 200 features, the linear regression is the right answer.

```python
# src/trading_research/ml/linear.py
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from trading_research.ml.base import TradingModel, ModelMetadata
import polars as pl
import numpy as np
import joblib

class LinearRegressionModel(TradingModel):
    def __init__(self, metadata: ModelMetadata, regularization: str = "ridge", alpha: float = 1.0):
        super().__init__(metadata)
        self.regularization = regularization
        self.alpha = alpha
        self._model = self._build_model()

    def _build_model(self):
        if self.regularization == "none":
            return LinearRegression()
        elif self.regularization == "ridge":
            return Ridge(alpha=self.alpha)
        elif self.regularization == "lasso":
            return Lasso(alpha=self.alpha)
        else:
            raise ValueError(f"Unknown regularization: {self.regularization}")

    def fit(self, X, y):
        self._model.fit(X.to_numpy(), y.to_numpy())

    def predict(self, X):
        return pl.Series(self._model.predict(X.to_numpy()))

    def predict_proba(self, X):
        raise NotImplementedError("Regression models don't have predict_proba")

    def feature_importance(self):
        return dict(zip(self._feature_names, self._model.coef_))

    def save(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._model, path / "model.joblib")
        (path / "metadata.json").write_text(json.dumps(asdict(self.metadata), indent=2))

    @classmethod
    def load(cls, path: Path):
        metadata = ModelMetadata(**json.loads((path / "metadata.json").read_text()))
        instance = cls(metadata)
        instance._model = joblib.load(path / "model.joblib")
        return instance
```

**Logistic regression** (for binary classification labels, like direction).

Same simplicity benefits as linear regression. Outputs class probabilities, which is exactly what you want for meta-labeling: a probability that a primary signal will work. Calibrated logistic regression on 5-10 features is often the right answer for the meta-model in a meta-labeling workflow.

**ARIMA** (for time-series forecasting of stationary or differenced series).

Classical time series modeling. Less commonly used in modern ML pipelines but still appropriate for some forecasting tasks. The framework wraps `statsmodels.tsa.arima.model.ARIMA` with the same interface as the other models so it can be plugged in interchangeably. Useful for short-horizon return forecasts when the assumption of linear autocorrelation is approximately right.

## Tree-based models

**Random forest.**

A reasonable middle ground between linear models and gradient-boosted trees. Easier to tune than XGBoost, handles missing values gracefully, and provides reasonable feature importance out of the box. For a first attempt at "is there any non-linear signal here at all," random forest is a sensible choice.

**XGBoost.**

The standard tool for tabular ML competitions and a common choice in trading. More complex than random forest, more powerful, and more prone to overfitting if used carelessly. The framework's XGBoost wrapper has explicit support for:
- Early stopping based on a validation set (prevents overtraining)
- Native handling of class imbalance (common in trading: most bars are not signal-worthy)
- Shapley value computation for model interpretation
- Saved booster files that load identically across machines

```python
# src/trading_research/ml/xgboost.py
import xgboost as xgb
from trading_research.ml.base import TradingModel, ModelMetadata
import polars as pl
import json

class XGBoostClassifier(TradingModel):
    def __init__(
        self,
        metadata: ModelMetadata,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        n_estimators: int = 200,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        early_stopping_rounds: int = 20,
        scale_pos_weight: float = 1.0,
    ):
        super().__init__(metadata)
        self.params = {
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "early_stopping_rounds": early_stopping_rounds,
            "scale_pos_weight": scale_pos_weight,
        }
        self._model = xgb.XGBClassifier(**self.params, eval_metric="logloss")

    def fit(self, X, y, X_val=None, y_val=None):
        eval_set = [(X_val.to_numpy(), y_val.to_numpy())] if X_val is not None else None
        self._model.fit(X.to_numpy(), y.to_numpy(), eval_set=eval_set, verbose=False)

    def predict(self, X):
        return pl.Series(self._model.predict(X.to_numpy()))

    def predict_proba(self, X):
        probs = self._model.predict_proba(X.to_numpy())
        return pl.DataFrame({f"class_{i}": probs[:, i] for i in range(probs.shape[1])})

    def feature_importance(self):
        return dict(zip(self._feature_names, self._model.feature_importances_))
```

**LightGBM.**

Similar to XGBoost but typically faster on large datasets. Worth considering when training speed matters. The framework supports it via the same interface; choose between XGBoost and LightGBM based on dataset size and personal preference.

**The mentor's view on tree models for trading:** they work, they overfit easily, and the cases where they meaningfully beat a well-designed linear model on out-of-sample trading data are rarer than the literature suggests. Use them when you have evidence that the relationship between your features and your labels is non-linear (test this with linear regression first and look at the residuals) and when you have enough data to support the complexity (rule of thumb: at least 1000 trades per parameter being tuned).

## Hyperparameter tuning

Hyperparameter tuning is where most ML pipelines accidentally introduce leakage and overfitting. The framework's approach:

1. **Always use purged k-fold or walk-forward for tuning.** Never random k-fold.
2. **Define the search space tightly.** A grid of 10 hyperparameters with 5 values each is 10 million combinations and the deflated Sharpe will eat any apparent winner. A grid of 3 hyperparameters with 4 values each is 64 combinations and remains tractable.
3. **Use the validation fold's metrics, never the test set's.** The test set is touched once at the end, after the best hyperparameters have been chosen on validation.
4. **Report the deflated metric.** If you tested 64 hyperparameter combinations, the best validation metric is biased upward by ~64 trials worth of cherry-picking. Compute and report the deflated version.

```python
# src/trading_research/ml/tuning.py
from dataclasses import dataclass
from typing import Callable
import polars as pl

@dataclass
class TuningResult:
    best_params: dict
    best_cv_score: float
    deflated_cv_score: float
    n_trials: int
    all_trials: list[dict]   # for each trial: params + cv scores
    cv_method: str

def tune_hyperparameters(
    model_class: type,
    feature_data: pl.DataFrame,
    labels: pl.Series,
    param_grid: dict[str, list],
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
    score_func: Callable,
    metadata_template: ModelMetadata,
) -> TuningResult:
    """Grid search with purged k-fold cross-validation.

    For each hyperparameter combination:
        1. Train a model on each CV fold's training set
        2. Score on the CV fold's test set
        3. Average across folds

    Return the best combination and the deflated score across all trials.
    """
    from itertools import product
    keys = list(param_grid.keys())
    combos = list(product(*param_grid.values()))

    trial_results = []
    for combo in combos:
        params = dict(zip(keys, combo))
        fold_scores = []
        for train_idx, test_idx in cv_splits:
            X_train = feature_data[train_idx]
            y_train = labels[train_idx]
            X_test = feature_data[test_idx]
            y_test = labels[test_idx]

            model = model_class(metadata=metadata_template, **params)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            fold_scores.append(score_func(y_test, preds))

        trial_results.append({
            "params": params,
            "fold_scores": fold_scores,
            "mean_score": np.mean(fold_scores),
            "std_score": np.std(fold_scores),
        })

    best = max(trial_results, key=lambda r: r["mean_score"])
    deflated = compute_deflated_score(
        [r["mean_score"] for r in trial_results],
        best["mean_score"],
    )

    return TuningResult(
        best_params=best["params"],
        best_cv_score=best["mean_score"],
        deflated_cv_score=deflated,
        n_trials=len(trial_results),
        all_trials=trial_results,
        cv_method="purged_kfold",
    )
```

The data scientist persona will demand to see the deflated score whenever a tuned model is presented. If the deflation is large (raw 0.62, deflated 0.55), the apparent improvement from tuning is mostly noise.

## Model evaluation

The standard evaluation metrics for ML models are *separate* from the trading-specific evaluation in `strategy-evaluation`. You evaluate the model first as an ML object (does it predict accurately?) and then evaluate the strategy that uses the model second (does it make money?).

**Classification metrics:**
- **Accuracy** — fraction of correct predictions. Simple but misleading on imbalanced classes.
- **Precision** — of the predicted positives, how many were actually positive. Important when false positives are costly.
- **Recall** — of the actual positives, how many were predicted. Important when missing positives is costly.
- **F1** — harmonic mean of precision and recall.
- **AUC-ROC** — area under the receiver operating characteristic curve. Good summary of classification performance across thresholds.
- **Log loss** — penalizes confident wrong predictions more than uncertain ones. The right metric for probabilistic classifiers.
- **Calibration** — are the predicted probabilities actually accurate? A model that says "70% chance of up move" should be right 70% of the time. Reliability plots show calibration visually.

**Regression metrics:**
- **MSE / RMSE** — mean (root) squared error.
- **MAE** — mean absolute error. More robust to outliers than MSE.
- **R²** — fraction of variance explained. Often misleading on financial data; can be high even when the model is useless.

**Trading-specific metrics that bridge ML and strategy:**
- **Hit rate** — when the model predicts a direction, how often is it right?
- **Information coefficient (IC)** — Spearman correlation between predicted and actual returns. The standard quant metric for return forecasts.
- **Profit factor of model-only trades** — if the model's predictions were used naively (always trade on positive predictions), what's the profit factor?

These trading-specific metrics live at the boundary between this skill and `strategy-evaluation`. They're computed during model evaluation to give an early signal of whether the model is trading-useful, but they don't replace the full backtest of the strategy that uses the model.

## Model cards

Every saved model has a model card — a markdown document that travels with the model and documents what it is, what it was trained on, how it performed, and what its known limitations are.

```markdown
# Model: zn_macd_meta_v3

## Purpose
Meta-labeling model for the ZN MACD divergence strategy. Predicts the
probability that a primary MACD divergence signal will hit its 1.5x ATR
profit target before its 1x ATR stop loss.

## Training data
- Source: data/clean/ZN_1m_2018-01-01_2023-12-31.parquet
- Period: 2018-01-01 to 2022-12-31 (5 years)
- Validation: 2023-01-01 to 2023-06-30
- Holdout test: 2023-07-01 to 2023-12-31
- Number of primary signals: 2,847
- Class balance: 56% positive, 44% negative

## Features
1. RSI(14) at signal bar
2. ATR(14) ratio to 60-bar average ATR
3. Distance from 200-EMA in ATR units
4. Cumulative session delta z-score
5. Hour of day (cyclical encoding)

All features computed at signal bar minus 1 to prevent leakage.

## Model
- Type: XGBoost classifier
- Hyperparameters: max_depth=4, learning_rate=0.05, n_estimators=120 (early stopped)
- Class weight: 1.27 (to balance positive/negative classes)

## Performance
| Metric          | CV (purged 5-fold) | Holdout test | Baseline (logistic) |
|-----------------|---------------------|--------------|---------------------|
| Accuracy        | 0.62                | 0.61         | 0.59                |
| AUC             | 0.66                | 0.64         | 0.63                |
| Log loss        | 0.62                | 0.63         | 0.65                |
| Calibration     | Good                | Good         | Good                |

The XGBoost model beats the logistic baseline by ~2 percentage points
on accuracy and ~1 point on AUC. Marginal improvement; the data scientist
flagged this as borderline whether the complexity is worth it.

## Known limitations
- Trained only on 2018-2022 data; the rate environment shift in 2023 may
  have changed the underlying distribution. Re-train annually.
- Performance degrades during high-volatility regimes (>2x normal ATR).
  Consider a regime filter at the strategy level.
- The class imbalance is mild but the model has slight bias toward predicting
  the majority class. The probability calibration is adjusted for this.

## How to use
- Load with `XGBoostClassifier.load(Path("models/zn_macd_meta_v3/"))`
- Pass features in the same order and format as the training set
- Use `predict_proba()` and threshold at 0.55 for "take this trade"
  (the threshold was tuned on the validation set, not the test set)

## Provenance
- Trained on: 2025-01-15 14:32 UTC
- Framework: scikit-learn 1.4.0, xgboost 2.0.3
- Git commit: a1b2c3d
- Trained by: Claude Code session ID xyz-123
```

**The model card is non-negotiable.** A saved model without a model card is unusable — the framework refuses to load it for production use. The model card is the contract between the training run and every future use of the model.

## The simple-baseline rule (enforcement)

Whenever the framework trains a complex model (anything beyond linear/logistic regression), it automatically also trains a simple baseline on the same features and labels. The baseline's metrics are stored in the model card and surfaced in any evaluation report.

If the complex model doesn't beat the baseline by a meaningful margin, the framework displays a prominent warning. The human can still use the complex model — there are reasons (interpretability, calibration, robustness in some regimes) — but the warning ensures the choice is conscious.

"Meaningful margin" is configurable but defaults to:
- Accuracy: 2 percentage points
- AUC: 0.02
- IC: 0.02
- Log loss: 0.02 absolute reduction

These are calibrated to be larger than typical noise on cross-validated estimates with 1000+ samples. Smaller improvements are usually noise or overfitting.

## Inference: the path from saved model to live signal

When a strategy uses a model, the inference path is:

1. **At strategy initialization:** load the model from `models/<model_id>/`. Verify the model card exists and matches the strategy's expected feature set.
2. **At each bar:** compute the same features that were used during training, in the same order, with the same as-of conventions.
3. **Pass features to the model's `predict()` or `predict_proba()` method.**
4. **Apply the strategy's logic** (e.g., "take the trade if probability > 0.55").

The feature computation step is the one that breaks most often in production. The training pipeline computes features one way (vectorized over a large dataset); the live pipeline computes them another way (one bar at a time, streaming). If these two paths produce different values for the same bar, the model is being used on data it wasn't trained on, and its predictions are unreliable.

**The framework's solution:** the feature computation code is shared between training and inference. There is one function `compute_features(bars, bar_index)` that computes the features for the bar at `bar_index`, and both the training pipeline and the live pipeline call it. This guarantees consistency.

For training, the pipeline calls `compute_features` for every bar in the training set. For inference, the live strategy calls it once per bar. The computational cost is different but the *output* is identical, which is the property that matters.

The framework includes a verification step at inference time: when a strategy first loads a model, it computes features for a small sample of the training data and checks that they match the stored training features bit-for-bit. Any mismatch is a hard error.

## Standing rules this skill enforces

1. **Every model has a model card.** Loading a model without one fails.
2. **The simple-baseline comparison is automatic.** Complex models that don't beat the baseline get a warning.
3. **Hyperparameter tuning uses purged cross-validation, never random.**
4. **Tuned models report deflated metrics alongside raw metrics.**
5. **Feature computation is shared between training and inference.** No parallel implementations.
6. **Inference verifies feature consistency on load.** Mismatches fail loud.
7. **Models are saved with full provenance** (framework version, git commit, training data path, hyperparameters).
8. **The model is a feature, the strategy is the strategy.** Strategies decide what to do with predictions; models don't make trading decisions.

## When to invoke this skill

Load this skill when the task involves:

- Training a new model
- Hyperparameter tuning of an existing model
- Evaluating model performance against baselines
- Saving or loading a model from `models/`
- Designing the inference path for a model in a strategy
- Investigating why a deployed model is underperforming its backtest
- Writing or updating a model card

Don't load this skill for:

- Feature creation (use `feature-engineering`)
- Strategy logic that consumes predictions (use `backtesting`)
- Computing strategy-level metrics like Sharpe and Calmar (use `strategy-evaluation`)

## Open questions for build time

1. **Whether to support neural networks (PyTorch).** They're powerful but rarely the right tool for tabular trading data with thousands of samples. Defer until there's a specific use case that demonstrates value.
2. **Whether to integrate Optuna or another HPO library.** The hand-rolled grid search in this skill is simple and works, but Optuna's Bayesian search is more sample-efficient for large grids. Add when grids get larger than ~100 trials.
3. **Whether to support online learning** (models that update incrementally as new bars arrive). Useful for live trading where the model can adapt to recent regime changes. Defer until the offline pipeline is solid; online learning is hard to get right.
4. **The exact threshold for "meaningful margin" over baseline.** The defaults above are reasonable but should be tuned based on what the project actually sees in practice.
