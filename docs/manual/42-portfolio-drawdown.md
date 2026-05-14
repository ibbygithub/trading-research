# Chapter 42 — Portfolio Drawdown

> **Chapter status:** [EXISTS] — portfolio drawdown attribution is in
> [`eval/portfolio_drawdown.py`](../../src/trading_research/eval/portfolio_drawdown.py).
> Per-strategy drawdown forensics (single strategy) are in
> [`eval/drawdowns.py`](../../src/trading_research/eval/drawdowns.py).
> The portfolio report's §5 renders the combined drawdown curve and
> attribution table.

---

## 42.0 What this chapter covers

Aggregated drawdown analysis shows whether the portfolio's worst periods
are produced by correlated failures across strategies or by isolated
single-strategy losses. After reading this chapter you will:

- Know how portfolio drawdown attribution works and what it produces
- Understand recovery characteristics and what they mean for
  psychological runnability
- Know when correlated drawdowns invalidate the case for running two
  strategies together

This chapter is roughly 2 pages. It is referenced by Chapter 40
(Portfolio Reports) and Chapter 41 (Correlation Analysis).

---

## 42.1 Aggregated drawdown analysis

`portfolio_drawdown_attribution` in
[`eval/portfolio_drawdown.py:5`](../../src/trading_research/eval/portfolio_drawdown.py)
identifies each portfolio-level drawdown period (where the combined
equity is below its prior peak) and attributes the loss in that period
to individual strategies.

```python
from trading_research.eval.portfolio_drawdown import portfolio_drawdown_attribution

attr_df = portfolio_drawdown_attribution(portfolio, min_dd_pct=0.01)
```

The output DataFrame has one row per drawdown period and columns:
- `start_date`, `trough_date`, `end_date`
- `max_dd_pct` — the deepest percentage drawdown in this period
- Per-strategy P&L columns showing each strategy's contribution to the
  trough

**Reading the attribution table:**
If Strategy A contributed −$4,000 and Strategy B contributed −$1,000
to a −$5,000 trough, Strategy A was the primary driver. If both
contributed roughly equally (−$2,500 each), the drawdown was correlated
— both strategies failed at the same time. Correlated drawdowns are the
signal that the portfolio is less diversified than it appears.

The `min_dd_pct` parameter (default 1%) filters out noise. For a
portfolio targeting 15% annual return, drawdowns below 1% are not
significant events and would clutter the attribution table.

---

## 42.2 Recovery characteristics

A drawdown's duration is often more brutal than its depth. A −10%
drawdown that recovers in two weeks is operationally manageable. A
−10% drawdown that takes fourteen months to recover is a question of
whether the operator will still be running the strategy at month 12.

Key recovery metrics (computed per drawdown in the attribution table):
- **Duration:** trading days from start to trough
- **Recovery days:** trading days from trough to new equity high (if
  the drawdown has recovered)
- **Ulcer index:** the root-mean-square of all percentage drawdown
  values over the period; penalises both depth and duration
  ([`eval/drawdowns.py`](../../src/trading_research/eval/drawdowns.py)
  computes this for individual strategies)

Multi-strategy recovery curves are plotted in portfolio report §5 as an
overlay: the combined equity curve, each strategy's equity, and the
combined drawdown curve. The visual immediately shows whether recovery
comes from one strategy pulling the other out, or whether both recover
simultaneously (which means the diversification benefit was real).

**When correlated drawdowns invalidate the portfolio:**
If every major drawdown in the attribution table shows roughly equal
losses from both strategies, the portfolio is effectively running the
same bet twice. The capital allocated to the second strategy would be
better deployed in a genuinely uncorrelated instrument or withheld as
a reserve buffer. The mentor persona's test: "if these strategies
fail at the same time, can I hold both through the drawdown, or will I
be forced out of one?"

---

## Related references

- Code: [`eval/portfolio_drawdown.py`](../../src/trading_research/eval/portfolio_drawdown.py) —
  `portfolio_drawdown_attribution`
- Code: [`eval/drawdowns.py`](../../src/trading_research/eval/drawdowns.py) —
  per-strategy drawdown, ulcer index
- Chapter 40 — Portfolio Reports
- Chapter 41 — Correlation Analysis
- Chapter 29 — Drawdown Forensics (single-strategy)

---

*Chapter 42 of the Trading Research Platform Operator's Manual*
