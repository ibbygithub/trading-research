# Chapter 37 — Capital Allocation

> **Chapter status:** [EXISTS / GAP] — the capital helpers are in
> [`eval/capital.py`](../../src/trading_research/eval/capital.py) and
> [`eval/portfolio.py`](../../src/trading_research/eval/portfolio.py).
> Live capital allocation (§37.3) is **[GAP]** and is out of scope for
> v1.0.

---

## 37.0 What this chapter covers

Capital allocation answers the question: of the total account equity,
how much is assigned to each strategy and what constraints govern the
portfolio as a whole? After reading this chapter you will:

- Know the `capital.py` helpers and what each computes
- Understand per-strategy capital assignment and the portfolio-level
  constraints
- Know which constraints are enforced today and which are live-phase
  specifications

This chapter is roughly 2 pages. It is referenced by Chapters 36
(Position Sizing) and 40 (Portfolio Reports).

---

## 37.1 Per-strategy capital

The `eval/capital.py` module provides capital-performance helpers that
operate on a trade log and a starting capital assumption:

```python
from trading_research.eval.capital import (
    return_on_peak_capital,
    return_on_margin,
    return_on_max_dd,
    margin_penalty_ratio,
)
```

**`return_on_peak_capital(trades, starting_capital)`** — net profit
divided by the largest equity peak. Penalises strategies that grow
capital then give back a large fraction.

**`return_on_margin(trades, broker_margins, broker)`** — net profit
divided by the peak margin used. Requires `configs/broker_margins.yaml`
to be populated for the strategy's instrument. This is the metric
that distinguishes strategies by capital efficiency: two strategies with
the same net P&L but different margin requirements have very different
returns on capital deployed.

**`return_on_max_dd(equity_series)`** — net profit divided by the
maximum dollar drawdown. Equivalent to Calmar for absolute P&L rather
than annualised return; useful for short-window comparisons.

**`margin_penalty_ratio(symbol, theoretical_margin, broker_margins)`** —
actual retail broker margin divided by the theoretical CME exchange
margin. This ratio is greater than 1 for most retail accounts because
the reduced intercommodity spread margins at CBOT/CME do not apply at
TradeStation or IBKR. A ratio of 4× is common for pairs positions. See
Chapter 39.

---

## 37.2 Portfolio-level constraints

The `eval/portfolio.py` module manages the Portfolio object that
aggregates multiple strategy equity curves:

```python
from trading_research.eval.portfolio import Portfolio

# Build a portfolio from strategy equity curves
portfolio = Portfolio()
portfolio.add_strategy("zn-reversion-v1", daily_pnl_series)
portfolio.add_strategy("6a-vwap-fade-v2b", daily_pnl_series)

combined_equity = portfolio.combined_equity
```

Portfolio constraints enforced today:
- **Strategy count:** currently no hard limit; the portfolio will
  aggregate as many strategies as are added
- **Correlation:** `eval/correlation.py` computes inter-strategy
  correlation and the portfolio report surfaces it (Chapter 41);
  enforcement is operator judgment, not automated
- **Capital ceilings:** there is no automated per-strategy capital cap
  in the current implementation; sizing ratios are managed via the
  `apply_sizing` function in Chapter 36

The correct working posture for v1.0 is to run each strategy at 1
contract, review the portfolio-level drawdown (Chapter 42), and scale
only after understanding the joint drawdown behaviour.

---

## 37.3 Capital allocation in live

**[GAP — out of scope for v1.0]** The live capital allocation
specification includes:

- Account-level constraint: total margin in use never exceeds X% of
  account equity (the operator sets X based on risk tolerance)
- Per-strategy capital ceiling: no strategy consumes more than Y% of
  the account regardless of the volatility-targeting formula
- Broker margin reconciliation: the platform queries the broker's
  current margin state before placing any order and refuses entries
  that would breach the account-level constraint
- Rebalancing: when a strategy grows beyond its capital ceiling due to
  P&L, the excess is redistributed to the account buffer

These items are in the live execution phase specification and are
documented here so they are visible during v1.0 design.

---

## Related references

- Code: [`eval/capital.py`](../../src/trading_research/eval/capital.py) —
  `return_on_margin`, `return_on_peak_capital`, `margin_penalty_ratio`
- Code: [`eval/portfolio.py`](../../src/trading_research/eval/portfolio.py) —
  `Portfolio`, `add_strategy`, `combined_equity`
- Config: `configs/broker_margins.yaml` — broker margin schedule
- Chapter 36 — Position Sizing
- Chapter 39 — Pairs and Spread Trading
- Chapter 40 — Portfolio Reports

---

*Chapter 37 of the Trading Research Platform Operator's Manual*
