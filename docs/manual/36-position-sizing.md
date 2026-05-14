# Chapter 36 — Position Sizing

> **Chapter status:** [EXISTS / GAP] — volatility targeting, fixed
> quantity, and Kelly sizing are all implemented. Volatility-targeting
> in a portfolio context lives in
> [`eval/sizing.py`](../../src/trading_research/eval/sizing.py); Kelly
> is in [`eval/kelly.py`](../../src/trading_research/eval/kelly.py).
> Per-trade sizing in the backtest engine is currently fixed quantity
> from the `quantity:` YAML field. The adaptive sizer (§36.5) is
> **[GAP]** and is post-v1.0.

---

## 36.0 What this chapter covers

Position sizing determines how many contracts the engine takes per
entry. Getting this right is at least as important as the entry signal;
a good signal with wrong sizing will blow up. After reading this chapter
you will:

- Know why volatility targeting is the default and how it works
- Know when fixed quantity is appropriate and when it is not
- Understand Kelly sizing, why the platform shows it for reference only,
  and why it is never the default
- Know the `eval/sizing.py` helpers and how to wire a custom sizer

This chapter is roughly 4 pages. It is referenced by Chapters 35 (Risk
Management Standards) and 37 (Capital Allocation).

---

## 36.1 Volatility targeting (default)

Volatility targeting sizes positions to a target dollar volatility per
unit of time. The formula:

```
contracts = target_vol_usd / (ATR_per_contract × point_value)
```

where:
- `target_vol_usd` is the desired daily P&L standard deviation in USD
- `ATR_per_contract` is the current N-bar ATR of the instrument
- `point_value` is the dollar value per tick × ticks per point from
  `configs/instruments.yaml`

At standard vol with `target_vol_usd = $200/day`:
- ZN at ATR $600/contract → 0.33 contracts → round to 1 micro (MZN)
- 6A at ATR $400/contract → 0.5 contracts → round to 1 micro

Volatility targeting has a property that matters in mean reversion: it
auto-reduces size during high-volatility regimes. When the market is
trending hard and ATR is elevated — the regime where mean-reversion
entries are most likely to be wrong — vol targeting naturally sizes
down. This is the opposite of what a fixed-quantity strategy does.

The portfolio-level implementation in
[`eval/sizing.py:21`](../../src/trading_research/eval/sizing.py) uses
rolling historical vol (`shift(1)` to avoid look-ahead) to weight
strategies inversely to their trailing volatility.

> *Why this rather than fixed quantity:* fixed quantity ignores regime.
> A position sized to 1 contract when ATR is $300 is three times the
> risk of the same position when ATR is $100. Volatility targeting
> keeps risk per trade approximately constant as market conditions
> change.

---

## 36.2 Fixed quantity

In the strategy YAML:

```yaml
backtest:
  quantity: 1
```

The engine takes `quantity` contracts at every entry. This is the right
default for initial backtesting: it makes the trade log easy to read
(every trade has the same size) and decouples the sizing question from
the signal question. Fit the signal first; fit the sizer second.

Fixed quantity is not appropriate for:
- Live trading at any serious capital level
- Walk-forward studies where the goal is realistic P&L estimation
- Portfolio studies where strategy weights matter

---

## 36.3 Kelly sizing

Kelly sizing maximises long-run geometric growth by sizing proportional
to the edge divided by the variance of outcomes. The formula for a
simple bet:

```
f* = (mean_return) / (variance_of_returns)
```

The `kelly_fraction` function in
[`eval/kelly.py:5`](../../src/trading_research/eval/kelly.py) computes
full Kelly, half Kelly, quarter Kelly, and a drawdown-constrained
variant:

```python
from trading_research.eval.kelly import kelly_fraction
result = kelly_fraction(returns_series, max_dd_target=0.20)
# result: {"full_kelly": 0.8, "half_kelly": 0.4, "quarter_kelly": 0.2,
#          "dd_constrained_kelly": 0.15, "hist_max_dd": 0.27}
```

Kelly fractions are shown **for reference only**. The module docstring
says it plainly: "Kelly assumes the historical distribution of returns
will repeat; real markets violate this assumption."

The specific failure modes:
- **Kelly is maximally aggressive.** Full Kelly produces the most
  violent drawdowns a system can survive without ruin. In practice,
  traders use fractional Kelly (half or quarter) and the fractions
  still routinely produce drawdowns that cause the trader to abandon
  the strategy.
- **Kelly requires accurate probability estimates.** The win rate and
  win/loss ratio from a backtest are point estimates with wide
  confidence intervals. Kelly amplifies these errors; a Sharpe estimate
  that is 0.3 too optimistic can result in a Kelly fraction that is
  50% too large.
- **Kelly doesn't know about streaks.** The formula assumes independent
  trials. Mean-reversion strategies have correlated entries — if the
  market is trending against you, the next trade is more likely to be
  a loser too.

> *Why not Kelly by default:* the mentor persona's standing rule.
> Volatility targeting degrades gracefully as conditions change; Kelly
> blows up gracefully. For a retired trader sizing a fixed account,
> graceful degradation is the correct risk posture.

---

## 36.4 The `eval/sizing.py` module

Four sizing methods are available for portfolio-level evaluation:

| Method | Implementation | When to use |
|---|---|---|
| `equal_weight` | 1/N across strategies | Baseline; good default |
| `vol_target` | Inverse rolling vol, shifted | The right default for production |
| `risk_parity` | Same as vol_target in this impl | Alias; true risk parity needs covariance |
| `inverse_dd` | Inverse recent drawdown | Use to reduce size during losing streaks |

```python
from trading_research.eval.sizing import apply_sizing, compare_sizing_methods
from trading_research.eval.portfolio import Portfolio

portfolio = Portfolio(...)
pnl_series = apply_sizing(portfolio, method="vol_target", lookback=60)

# Compare all methods side by side
results = compare_sizing_methods(portfolio)
```

The `compare_sizing_methods` function returns Calmar and Sharpe for each
method, which is the practical test for which method fits the strategy's
characteristics.

---

## 36.5 Sizing in walk-forward and live

**[GAP — post-v1.0]** In a walk-forward study, volatility targeting
should adapt each fold's sizing to that fold's historical vol, not the
full-period vol. The current implementation applies sizing
post-hoc to the full equity curve, which means the walk-forward sizing
is retrospective. An adaptive sizer would compute the sizing
function per-fold and only use data available at that fold's start
date. This is specified as a post-v1.0 item because it requires
plumbing the sizer into the fold-level backtest loop.

In live trading, the sizing must adapt in real time to realised intraday
volatility. This is part of the live execution phase specification.

---

## Related references

- Code: [`eval/sizing.py`](../../src/trading_research/eval/sizing.py) —
  `apply_sizing`, `compare_sizing_methods`
- Code: [`eval/kelly.py`](../../src/trading_research/eval/kelly.py) —
  `kelly_fraction`, `portfolio_kelly`
- Config: `configs/instruments.yaml` — tick_value, point_value
- Chapter 35 — Risk Management Standards
- Chapter 37 — Capital Allocation

---

*Chapter 36 of the Trading Research Platform Operator's Manual*
