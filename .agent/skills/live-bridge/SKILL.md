---
name: live-bridge
description: The mission-critical bridge between research and the TradeStation API. Manages real-time data ingestion and idempotent order execution.
---

# Goal
Provide an "Enterprise-Hardened" interface for paper and live trading, ensuring that live behavior is bit-for-bit identical to backtest results and that capital is protected by multi-layer gates.

# Instructions
1. **Data Integrity (The Streaming Side)**:
    - **Closed Bar Law**: Strategies ONLY see closed bars. Forming bars (mid-minute) are an internal detail and must NEVER reach the strategy logic.
    - **Backfill Protocol**: On reconnect, use the historical endpoint to backfill missed bars so the strategy's state (EMA, etc.) remains continuous.
    - **Cross-Check**: Every morning, cross-validate live-captured bars against TradeStation's historical truth. Any divergence is a critical platform bug.
2. **Execution Integrity (The Broker Side)**:
    - **Broker as Truth**: The broker is the ONLY source of truth for positions and fills. Reconcile internal state to the broker every 30 seconds.
    - **Idempotency**: Every order MUST carry a unique `client_order_id` to prevent double-fills during network retries.
    - **The Confirmation Gate**: Promotion to LIVE requires the human to literally type `START LIVE TRADING` in uppercase. Agents cannot self-promote.
3. **The Trio Review**:
    - **Mentor**: Enforce the "No Averaging Down" rule and verify that single-instrument trades are flat by EOD.
    - **Scientist**: Monitor for "Stale Bars" (heartbeat miss > 90s) and halt immediately if feed latency exceeds 60 seconds.
    - **Architect**: Ensure the "Kill Switch" is decoupled and that no strategy can bypass the `risk-controls` pre-trade checks.

# Constraints
- **Friction by Design**: The path from Backtest -> Paper -> Live has mandatory conversational gates.
- **Reconciliation-First Restart**: On startup, the agent must read current positions from the broker before initializing any internal state.
- **Symbol Integrity**: Root and month codes must be cross-checked against `docs/Tradestation-trading-symbol-list.md`.

# Examples
- **User**: "Start the live ZN mean-reversion strategy."
- **Agent**: (Runs pre-check) -> "Paper history verified. Mentor and Scientist have signed off. Please type 'START LIVE TRADING' to open the gate.".