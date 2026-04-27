---
name: feature-factory
description: Computes technical indicators and engineers ML features/labels with strict causality and statistical stationarity.
---

# Goal
Transform CLEAN bars into strategy-ready indicators and ML-ready features. This skill enforces the "Honesty requires effort" principle, ensuring no look-ahead bias or leakage enters the pipeline.

# Instructions
1. **The Fundamental As-Of Contract**:
    - Every indicator and feature at bar N MUST be computable using only data through bar N (or N-1 per strategy fill model).
    - This is verified by the `test_asof_correctness` unit test protocol.
2. **Stationarity & Transformation**:
    - Raw prices are non-stationary. The agent must apply returns, log-returns, or **Fractional Differentiation** (d=0.3-0.5) before feeding data to ML models.
3. **Labeling (Supervised Learning)**:
    - **Triple Barrier** is the default labeling method (Profit Target, Stop Loss, Time Barrier).
    - **Meta-labeling** should be used to filter primary signals rather than predicting direction in a single stage.
4. **Validation & Leakage Prevention**:
    - Never use random splits. Use **Temporal Splits** (Train -> Purge -> Val -> Purge -> Test).
    - Use **Purged k-fold Cross-Validation** with embargoes to prevent information spill across folds.
5. **The Trio Review**:
    - **Scientist**: Enforce the "Simple Baseline" rule. No complex model (XGBoost) is accepted without a linear-baseline comparison. Audit for stationarity using ADF tests.
    - **Architect**: Ensure all features are stored in `data/features/` with mandatory JSON metadata documenting the computation hash and `passes_asof_test` status.
    - **Mentor**: Verify indicator physics (Wilder smoothing for RSI/ATR) and confirm order-flow signals (Delta/Absorption) handle nulls.

# Constraints
- **Causality**: Indicators/Features must not look forward. Any violation of the "As-of" rule is a critical failure.
- **No Indicator Storage in CLEAN**: The CLEAN layer remains a pure OHLCV record. Indicators only exist in the FEATURES layer.
- **Leakage Reporting**: High feature-label correlation (>0.9) must be flagged as suspicious future-leakage.

# Examples
- **User**: "Prepare ZN for a meta-labeling model using fractional diff."
- **Agent**: (Loads CLEAN) -> (FracDiff d=0.4) -> (Triple-Barrier labeling) -> (Purged k-fold) -> "Features ready. Scientist verified simple-baseline is outperformed by 12%.".