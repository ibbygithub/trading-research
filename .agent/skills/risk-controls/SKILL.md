---
name: risk-controls
description: Enforces position sizing, loss limits, exposure caps, and the "No Averaging Down" mandate to protect capital.
---

# Goal
Safeguard the $25k personal account by enforcing strict risk-management invariants. The strategy decides direction, but the risk system decides size.

# Instructions
1. **Position Sizing Standards**:
    - **Default Model**: Use Volatility Targeting (0.4% default) for all entries to ensure consistency over heroics.
    - **Consent Gate**: Any request to use Kelly Criterion requires explicit Ibby authorization and a lecture from the Mentor on ruin risk.
    - **Micro Focus**: Prioritize Micro contracts (MYM, MES, MNQ, M2K, MZN) for account-size appropriateness.
2. **Circuit Breakers & Limits**:
    - **Daily Limit**: Hard stop at $250 (1% of account). If hit, flatten positions and require manual reset.
    - **Weekly Limit**: Hard stop at $750 (3% of account) to prevent behavioral spirals.
    - **Drawdown Limit**: Halt strategy if the account drops 10% from its all-time peak.
3. **The Trio Review**:
    - **Mentor**: Enforce the "No Averaging Down" rule—verify that any scale-in entry is triggered by a fresh signal, not just a P&L loss.
    - **Scientist**: Audit risk metrics (Sortino, Calmar, Max Drawdown) and ensure they aren't masked by outlier win streaks.
    - **Architect**: Ensure the "Kill Switch" logic is decoupled from strategy logic so it cannot be bypassed by a strategy-level bug.

# Constraints
- **Margin Awareness**: Must compute actual Retail Broker margin (TradeStation/IBKR) for pairs, NOT theoretical CME intercommodity spread rates.
- **Idempotency**: All risk-check operations must be idempotent and reconcilable against real-time broker fills.
- **Exposure Caps**: Limit per-strategy exposure to 20% of equity and total account exposure to 100% (no leverage by default).

# Examples
- **User**: "Size this ZN trade for 1% risk."
- **Agent**: (Computes sizing) -> "Mentor recommends Vol-Targeting for 3 Micros. Daily limit is active. Architect verified the Kill Switch is wired.".