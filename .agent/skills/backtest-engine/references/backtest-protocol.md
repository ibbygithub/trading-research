# Backtest Technical & Statistical Protocol

This document defines the technical execution and evaluation standards for the `backtest-engine` skill, migrated from the legacy `CLAUDE.md` and `data-scientist.md` standards.

## Implementation Standards

### 1. Fill Logic & Trade Logging
The engine must separate the "trigger bar" from the "entry bar" in the trade logs to ensure the signal wasn't generated using the same data it filled on.

```python
# Logic from src/trading_research/backtest/engine.py
def execute_fill(signal, next_bar):
    # Scientist: Enforce look-ahead bias check
    # Architect: Use the StrategyContext Protocol
    entry_price = next_bar.open
    # ... logic for stop/target monitoring
```

### 2. Mandatory Reporting Metrics
Reports must be generated as JSON-line logs for consumption by the `forensics-app`.

| Metric | Requirement | Logic Source |
|---|---|---|
| Calmar | Primary Metric | Annual Return / Max Drawdown |
| Deflated Sharpe | Multi-Trial | Adjusts for the number of variants tested |
| PSR | Mandatory | Probabilistic Sharpe Ratio for "luck" quantification |
| Drawdown Days | Behavioral | Duration in trading days until recovery |

## Statistical Guardrails
- **Bootstrap CI**: Every primary metric must be reported with a confidence interval obtained via trade-return bootstrapping.
- **Purged Validation**: When using ML or multi-bar exits, a purge gap must be enforced between training and testing data to prevent label leakage.
- **Bonferroni/BH**: Apply Benjamini-Hochberg correction when performing feature selection across large sets.

## Environment
Invoke all backtest runs via `uv run python -m trading_research.cli.backtest`.
