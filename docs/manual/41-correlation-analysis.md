# Chapter 41 — Correlation Analysis

> **Chapter status:** [EXISTS] — correlation functions are in
> [`eval/correlation.py`](../../src/trading_research/eval/correlation.py).
> The portfolio report renders both the static matrix and the rolling
> correlation chart. This chapter explains what to look for and what
> the numbers mean in practice.

---

## 41.0 What this chapter covers

Correlation analysis answers: do two strategies make and lose money at
the same time? After reading this chapter you will:

- Know the three correlation functions the platform provides
- Understand the difference between Pearson and Spearman correlation
  and when each is more informative
- Know the "diversification myth" — why low static correlation does not
  guarantee independent behaviour in tail events

This chapter is roughly 2 pages. It is referenced by Chapter 40
(Portfolio Reports) and Chapter 42 (Portfolio Drawdown).

---

## 41.1 Strategy correlation

Three functions in
[`eval/correlation.py`](../../src/trading_research/eval/correlation.py):

**`daily_pnl_correlation(portfolio)`** — computes Pearson and Spearman
correlation matrices over the full daily P&L history of all strategies.
Returns a dict with keys `"pearson"` and `"spearman"`, each a DataFrame
N×N correlation matrix.

**`rolling_correlation(portfolio, window_days=60)`** — computes pairwise
rolling Pearson correlation over a sliding window. Returns a dict keyed
by `"strategy_A vs strategy_B"` with a Series per pair.

**`return_correlation_vs_market(portfolio, benchmark_series)`** — if you
have a benchmark P&L series (e.g., daily S&P P&L as a sentiment proxy),
this computes each strategy's correlation with it. Useful for
understanding how much of a strategy's edge is correlated with
macro-risk-on/risk-off.

Reading the static matrix:
- Values near 0: strategies are trading independently
- Values above +0.5: strategies tend to win and lose together — they
  are effectively the same position held twice
- Values below −0.5: strategies tend to offset each other — useful for
  drawdown smoothing but the portfolio returns less than either strategy
  alone

Pearson measures linear correlation; Spearman measures rank correlation.
For mean-reversion strategy P&L distributions (which are typically
right-skewed with occasional large losers), Spearman is often more
informative because it is less sensitive to outlier trades.

---

## 41.2 The diversification myth

A static Pearson correlation of 0.1 between two strategies in normal
market conditions does not mean they are uncorrelated during tail events.
The canonical example from the mentor persona: two mean-reversion
strategies on 6A and 6C (Australian and Canadian dollars) may have low
correlation during normal ranges because their drivers differ (commodity
prices vs trade flows) — but during a risk-off shock both currencies sell
off against the USD simultaneously. The correlation spikes toward 1 in
exactly the conditions where you least want it.

The rolling correlation chart (60-day window) is more informative than
the static matrix for detecting this. Look for periods where rolling
correlation spikes above 0.7 and check whether those spikes coincide
with notable drawdowns. If they do, the strategies are not providing
genuine diversification during stress; they are two bets on the same
outcome.

The practical implication: two strategies with static correlation of 0.1
may justify a small portfolio diversification benefit, but they should
not be allocated as if they were independent. Run the joint drawdown
analysis from Chapter 42 before deciding on capital weights.

---

## Related references

- Code: [`eval/correlation.py`](../../src/trading_research/eval/correlation.py) —
  `daily_pnl_correlation`, `rolling_correlation`, `return_correlation_vs_market`
- Chapter 40 — Portfolio Reports
- Chapter 42 — Portfolio Drawdown
- Chapter 39 — Pairs and Spread Trading

---

*Chapter 41 of the Trading Research Platform Operator's Manual*
