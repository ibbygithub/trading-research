# Risk Management & Circuit Breaker Protocol

This document defines the technical execution for the `risk-controls` skill, migrated from the legacy `risk-management` standards.

## 1. Volatility Targeting Logic
The default sizing model aims for consistent P&L volatility (0.4% target for Ibby's $25k account).

```python
# Logic from src/trading_research/risk/sizing.py
def vol_target_size(account_equity, target_pct, instrument_atr_ticks, tick_value):
    # Scientist: Annualize bar-level volatility to daily estimate
    daily_vol = (instrument_atr_ticks * tick_value) * sqrt(session_bars)
    target_usd = account_equity * target_pct
    return floor(target_usd / daily_vol)
```

## 2. Dual-Margin Model (Pairs)
Retail brokers (TradeStation) do **NOT** honor CME intercommodity offsets. The agent must surface both numbers:

| Pair | Theoretical Offset | Actual Broker Margin |
|---|---|---|
| ZN/ZB | 75% | Naive Sum (No Offset) |
| ZN/ZF | 70% | Naive Sum (No Offset) |
| ZC/ZS | 65% | Naive Sum (No Offset) |

## 3. Combined-Risk (Re-Entries)
Re-entries are only permitted if a fresh signal exists and combined risk is validated.

- **Calculation**: `(Parent Risk + Re-entry Risk)` must **NOT** exceed the remaining daily loss limit.

## 4. Kill Switch Levels
Managed via `runs/.kill_switches.json` to ensure persistence across restarts.

- **Strategy**: Daily/Weekly stop hit.
- **Instrument**: Manual halt for data/event issues.
- **Account**: Nuclear option. Flattens everything and requires manual override.

## 5. Exposure Caps
Enforced at signal validation:

- **Per Strategy**: 20% of equity.
- **Per Asset Class**: 40% of equity.
- **Total Account**: 100% of equity (No Leverage).
