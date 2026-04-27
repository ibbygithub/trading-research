# Machine Learning Training & Evaluation Protocol

This document defines the technical execution for the `ml-lab` skill, migrated from the legacy `feature-engineering` and `ml-modeling` standards.

## 1. Purged Cross-Validation Pattern
Use the `PurgedKFold` implementation to ensure training sets exclude data within the label's holding period.

```python
# Logic from src/trading_research/features/cross_validation.py
def train_with_purge(features, labels, model_config):
    cv = PurgedKFold(n_splits=5, purge_bars=20, embargo_pct=0.01)
    # Scientist: Perform hyperparameter sweep across folds
    for train_idx, test_idx in cv.split(features):
        model.fit(features[train_idx], labels[train_idx])
        score = model.score(features[test_idx], labels[test_idx])
```

## 2. Meta-Labeling Logic
Use the two-stage training approach to filter signals.

- **Primary Model**: A rule-based or simple model (e.g., MACD Divergence) identifies entry signals.
- **Meta Model**: An ML model (e.g., Random Forest) predicts whether the primary signal will be a win (`+1`) or a loss (`0`).
- **Execution**: The strategy only acts when the Meta Model provides a high-confidence `"1"`.

## 3. Mandatory Evaluation Metrics
The agent must compute these to prevent "The I Just Looked At It" trap:

- **PSR (Probabilistic Sharpe Ratio)**: Corrects for the non-normality of returns.
- **Deflated Sharpe Ratio**: Corrects for "Selection Bias" across multiple model variations.

## 4. Model Storage Schema
Save models to `models/{symbol}/{version}/` with the following:

- `model.joblib`: The serialized model object.
- `metrics.json`: The Purged-CV and Baseline comparison scores.
- `feature_importance.png`: Visual audit of which features drove the decisions.

## 5. Simple Baseline First
If you cannot beat a Logistic Regression with a simple feature set, the complex model is considered overfit.
