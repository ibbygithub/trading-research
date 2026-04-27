---
name: risk-controls
description: Enforces position sizing, loss limits, and the "No Averaging Down" mandate to protect capital.
---

# Goal
Safeguard the $25k personal account by enforcing strict risk-management invariants across all strategies and instruments.

# Instructions
1. **Position Sizing Standards**:
    - **Default Model**: Use Volatility Targeting for all entries.
    - **Consent Gate**: Any request to use Kelly Criterion requires explicit Ibby authorization and a lecture from the Mentor on ruin risk.
    - **Micro Focus**: Recommend Micro contracts (MYM, MES, MNQ, M2K, MZN) by default for account-size appropriateness.
2. **Circuit Breakers (Track D)**:
    - **Daily Limit**: If the strategy hits its defined daily loss limit, it must cease all execution and require manual reset.
    - **Weekly Limit**: Enforce a "Hard Kill" at the weekly loss threshold to prevent behavioral spiral.
3. **The Trio Review**:
    - **Mentor**: Enforce the "No Averaging Down" rule—verify that any scale-in entry is triggered by a fresh signal, not just a p&l loss.
    - **Scientist**: Audit risk metrics (Sortino, Calmar, Max Drawdown) to ensure they aren't masked by outlier win streaks.
    - **Architect**: Ensure the "Kill Switch" logic is decoupled from the strategy logic so it cannot be bypassed by a strategy-level bug.

# Constraints
- **Margin Awareness**: Must compute actual Retail Broker margin (TradeStation/IBKR) for pairs, NOT theoretical CME intercommodity spread rates.
- **Idempotency**: All risk-check operations must be idempotent and reconcilable against real-time broker fills.
- **Configuration**: Loss limits and sizing parameters must be loaded from `configs/strategies/` or `configs/risk_limits.yaml`.

# Examples
- **User**: "Size this ZN trade for 1% risk."
- **Agent**: (Computes sizing) -> "Mentor recommends Vol-Targeting for 3 Micros. Daily limit is active. Architect verified the Kill Switch is wired.".