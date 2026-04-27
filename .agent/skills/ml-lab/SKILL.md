---
name: ml-lab
description: Handles the training, hyperparameter tuning, and evaluation of ML models using purged cross-validation to prevent overfitting.
---

# Goal
Train robust, non-overfit machine learning models that provide a measurable edge over simple linear baselines. This skill enforces the "Simpler is Better" rule.

# Instructions
1. **The Simple-Baseline Mandate**:
    - Every complex model (e.g., XGBoost, Meta-labeling) MUST be compared against a linear/logistic regression baseline using the same features.
    - If the complex model does not significantly outperform the baseline, it is rejected.
2. **Purged Training Protocol**:
    - Use **Purged k-fold Cross-Validation** to tune hyperparameters.
    - Enforce **Embargoes** after each test fold to prevent information spill from serial correlation.
3. **The Trio Review**:
    - **Scientist**: Perform a "Leakage Audit" on the feature/label set before training. Verify that the **Deflated Sharpe Ratio** is computed to account for multiple trial overfitting.
    - **Architect**: Ensure the model is saved in `models/` with a unique hash that links it to the specific `data/features/` metadata version.
    - **Mentor**: Perform the "Regime Check"—does the model's performance hold up across different volatility regimes, or is it just a "Bull Market Hero"?.

# Constraints
- **Stationarity**: No model may be trained on non-stationary data (e.g., raw prices). Features must be transformed (Returns, FracDiff) as defined in the `feature-factory`.
- **No Random Splits**: All validation must be temporal. Randomly shuffled cross-validation is a critical failure.
- **Model Registry**: Every trained model must include a `.json` metadata file documenting the training parameters, CV scores, and leakage test results.

# Examples
- **User**: "Train a meta-labeling model for the ZN divergence signals."
- **Agent**: (Loads FEATURES) -> (Trains Linear Baseline) -> (Tunes XGBoost via Purged-CV) -> "Scientist confirms 15% edge over baseline. Model v1-ZN saved.".