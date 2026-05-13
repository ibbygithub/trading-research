# Chapter 26 — Monte Carlo Simulation

> **Chapter status:** [EXISTS] — implementation in
> [`eval/monte_carlo.py`](../../src/trading_research/eval/monte_carlo.py).
> Output renders in §23 of the Trader's Desk Report as the 1,000-shuffle
> equity fan plus drawdown and Calmar distributions.

---

## 26.0 What this chapter covers

The bootstrap (Chapter 21) tells you what the trade-return distribution
implies. Monte Carlo tells you what *paths* the same trade set can
produce when the order is shuffled. After reading this chapter you
will:

- Understand path dependence and why bootstrap misses it
- Know what the Monte Carlo percentile of the realised drawdown and
  Calmar tells you
- Be able to read the equity fan in §23

This chapter is roughly 3 pages. It is referenced by Chapters 17, 19,
21, 29.

---

## 26.1 Trade-order Monte Carlo

[`shuffle_trade_order`](../../src/trading_research/eval/monte_carlo.py:7)
shuffles the realised trade sequence and recomputes the equity curve
on each shuffle:

```python
for i in range(n_iter):
    idx = rng.permutation(n)
    shuffled = trades.copy()
    shuffled['net_pnl_usd'] = trades['net_pnl_usd'].values[idx]
    shuffled = shuffled.sort_values('exit_ts')
    eq = shuffled.set_index('exit_ts')['net_pnl_usd'].cumsum()
    # record max drawdown, Calmar, equity curve
```

The default is 1,000 permutations with seed 42. The trade outcomes
(`net_pnl_usd`) are reshuffled; the exit timestamps are kept in
chronological order so the equity curve still spans the original test
window. What changes between simulations is *which* trade landed
*when* — the set is preserved, the sequence is randomised.

Two summary statistics are emitted per simulation: the maximum
drawdown in dollars, and the Calmar ratio. The full distribution of
both, plus the cumulative equity curve from every shuffle, is what
§23 of the Trader's Desk Report renders.

> *Note on terminology:* this is **trade-order Monte Carlo**, not
> **return-distribution Monte Carlo**. The platform does not synthesise
> new trades from a fitted return distribution. Every Monte Carlo
> trial uses only the trades that actually occurred — just in a
> different order.

---

## 26.2 What this catches that bootstrap doesn't

The bootstrap resamples *with replacement* — every sample draws a
fresh combination of trades and may repeat some. It tells you about
the distribution of the trade *set*. Monte Carlo permutes the *order*
of a fixed set. It tells you about the distribution of *paths* a
fixed set can produce.

The metrics that differ between the two:

- **Sharpe, win rate, expectancy, profit factor.** Order-invariant.
  Bootstrap is the right tool; Monte Carlo adds nothing.
- **Max drawdown, drawdown duration, Calmar (via drawdown), max
  consecutive losses.** Path-dependent. Bootstrap cannot reach these;
  Monte Carlo can.

The platform reports the realised value of each path-dependent metric
alongside its Monte Carlo percentile. Concretely, if the realised
max drawdown is $4,200 and the Monte Carlo distribution puts that at
the 35th percentile, the reading is: "in 65% of shuffles, the
drawdown would have been even worse." The strategy got lucky on the
order; the trade set could plausibly have produced a much deeper
drawdown.

The reverse case is also useful: a realised drawdown at the 95th
percentile means the strategy was *unlucky* on order — most
shufflings of the same trades would have produced a milder drawdown.
This is rarely a comforting reading; it usually means the strategy
hit a string of bad trades in close succession that another order
would have spread out.

### 26.2.1 The interpretation lines

[`shuffle_trade_order`](../../src/trading_research/eval/monte_carlo.py:41)
emits an interpretation string based on the Calmar percentile of the
realised result:

| Realised Calmar percentile | Interpretation |
|---|---|
| > 95th | Actual strategy significantly outperforms randomised order (path dependence is favourable) |
| 5th – 95th | Strategy performance is within expectation of random trade order |
| < 5th | Actual strategy significantly underperforms randomised order (path dependence is unfavourable) |

The "favourable path dependence" case is usually a positive signal:
the strategy's trades are clustering in a way that produces a better
equity curve than random ordering would. The "unfavourable" case is a
warning: the trades cluster against the operator. Both extremes
warrant a look at the §19 Drawdown Forensics block (Chapter 29) for
which specific runs of trades drove the result.

---

## 26.3 Reading the equity fan in §23

The §23 visual is the equity fan: 1,000 cumulative-P&L curves on the
same axes, plus the realised curve overlaid. The fan shows the range
of paths the trade set can take; the realised line shows where the
operator actually landed.

What to look for:

- **The realised curve hugging the upper boundary of the fan.** The
  strategy's actual order was a top-quintile path. Most reorderings
  of the same trades would be worse. This is *favourable* path
  dependence and a good sign.
- **The realised curve hugging the lower boundary.** The operator's
  actual order was a bottom-quintile path. Most reorderings would
  have been better. The trade set has edge but the order is currently
  punishing.
- **The fan widening with time.** Normal — uncertainty in cumulative
  P&L grows with the number of trades. The shape of the fan tells
  you about distribution skew: a fan with more mass below the centre
  has negative-skew trade returns.

The fan plus the percentile readout together tell the operator
whether the realised equity curve is typical of the underlying trade
distribution or whether it depends on a particular sequencing of
events. The data-scientist persona's standing position: a strategy
whose backtest looks great *only on its specific realised order* is
not a strategy with edge; it is a strategy that has not yet been
tested under reordering.

---

## 26.4 What this does not test

Path-dependent Monte Carlo holds the trade set fixed. It does not
address:

- **Different trades the strategy would have taken with different
  random seeds in regime fitting.** Walk-forward (Chapter 22) is the
  tool for that.
- **Trades the strategy did not take but should have.** That is a
  signal-quality question; Monte Carlo cannot create signals.
- **What happens under different cost assumptions.** That is the §13
  Cost Sensitivity block in the Trader's Desk Report.
- **Whether the underlying market structure is still mean-reverting.**
  The stationarity suite (Chapter 24) is the right diagnostic.

Monte Carlo is one layer of the validation stack, not the whole
stack. A strategy that passes Monte Carlo and fails walk-forward is
not a working strategy; a strategy that passes both and fails the
gate criteria (Chapter 46) is still not ready for promotion. The
sequence of tests matters as much as each test's verdict.

---

## 26.5 Related references

### Code modules

- [`src/trading_research/eval/monte_carlo.py`](../../src/trading_research/eval/monte_carlo.py)
  — `shuffle_trade_order`. The full equity curves are returned for
  rendering; the summary statistics are computed via
  `compute_summary` on each shuffled `BacktestResult`.
- [`src/trading_research/eval/report.py`](../../src/trading_research/eval/report.py)
  — §23 rendering.

### Other manual chapters

- **Chapter 17** — Trader's Desk Report: §23 (Monte Carlo block).
- **Chapter 19** — Headline Metrics: the path-dependent metrics
  (drawdown, Calmar) that Monte Carlo distributions.
- **Chapter 21** — Bootstrap Confidence Intervals: the orthogonal
  trade-set test.
- **Chapter 22** — Walk-Forward Validation: the regime layer above
  this.
- **Chapter 29** — Drawdown Forensics: per-drawdown decomposition
  for the worst paths.

---

*End of Chapter 26. Next: Chapter 27 — Regime Metrics & Classification.*
