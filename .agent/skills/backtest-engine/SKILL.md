---
name: backtest-engine
description: Simulates trading strategies with pessimistic rigor and generates statistically honest performance reports.
---

# Goal
Execute high-fidelity simulations of trading strategies using CLEAN or FEATURES data, ensuring that results are never inflated by leakage or optimistic fill assumptions.

# Instructions
1. **Simulation Rigor**:
    - **Fill Model**: Use the next-bar-open fill model by default. Any deviation requires a written justification in the strategy config.
    - **Ambiguity Resolution**: If both TP and SL are hit in the same bar, assume the stop-loss hit first.
    - **Costs**: Apply pessimistic slippage and commission rates relative to current TradeStation retail rates.
2. **The Trio Review**:
    - **Scientist**: Audit the run for "The I Just Looked At It" trap and verify that any threshold fit on a test set is flagged as a bug.
    - **Architect**: Ensure the backtest result is a function of (code, data, and config versions) and that all five provenance factors are recorded.
    - **Mentor**: Perform the Fed-surprise/stress-test vibe check. If Sharpe is over 2.0, treat it as a bug until proven otherwise.
3. **Reporting Centering**:
    - Every report must lead with **Calmar Ratio**, not Sharpe.
    - Compute **Deflated Sharpe** whenever multiple strategy variants have been tested to account for cherry-picking.

# Constraints
- **Sample Size**: Strategies with fewer than 50 trades over five years must be flagged as statistically indistinguishable from zero.
- **No Averaging Down**: Verify that no strategy implementation adds to a losing position without a fresh, pre-defined signal.
- **Configuration**: All strategy thresholds must be loaded from YAML configs in `configs/strategies/`, never hardcoded in the Python module.

# Examples
- **User**: "Run the ZN mean-reversion backtest for 2024."
- **Agent**: (Runs simulation) -> "Scientist reports Calmar of 1.8 with a tight CI. Mentor notes it survived the July CME outage. Architect has logged the trial hash.".