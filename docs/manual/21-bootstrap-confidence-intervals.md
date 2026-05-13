# Chapter 21 — Bootstrap Confidence Intervals

> **Chapter status:** [EXISTS] — implementation in
> [`eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py).
> CIs surface in §2 and §16 of the Trader's Desk Report, in the
> `format_with_ci` text output, and in the leaderboard's `Calmar CI`
> and `Sharpe CI` columns (closed in session 46).

---

## 21.0 What this chapter covers

A point estimate from a backtest is one number. A confidence interval
is the range the true value could plausibly take, given that the
backtest is a single realisation of a random process. After reading
this chapter you will:

- Know what the platform resamples and at what level
- Know which six metrics carry CIs
- Be able to read a CI as a kill criterion, not decoration
- Understand the sample-size implications and the trade-count line on
  the headline

This chapter is roughly 3 pages. It is referenced by Chapters 17, 19,
22, 23, 32, 46.

---

## 21.1 What bootstrapping does

[`bootstrap_summary`](../../src/trading_research/eval/bootstrap.py:46)
resamples trade-level `net_pnl_usd` with replacement and recomputes
each metric on each sample. The default is 1,000 samples with seed 42.

```python
for _ in range(n_samples):
    idx = rng.integers(0, n_trades, size=n_trades)
    sample_pnl = net_pnl[idx]
    # recompute each metric on sample_pnl
```

The 5th and 95th percentiles of the resulting distribution are reported
as a 90% confidence interval. The math is simple; the discipline is in
*resampling at the right level*. The platform resamples trades, not
days, not bars. Each bootstrap sample preserves trade-level cost
structure (slippage and commission are baked into `net_pnl_usd`) while
shuffling which trades are drawn.

> *Why trade-level rather than bar-level:* the unit of risk in a
> backtest is the trade, not the bar. A daily-P&L bootstrap would mix
> together bars from inside trades with bars from flat periods,
> producing a sampling distribution that does not describe the
> strategy's actual decision rhythm. Trade-level resampling preserves
> the inferential question — "what is the distribution of outcomes
> across realisations of this trade-generating process?"

### 21.1.1 What is preserved and what is broken

- **Preserved:** the marginal distribution of trade outcomes. Costs,
  slippage, win-rate, expectancy.
- **Broken:** trade order, and therefore drawdown path. A bootstrap
  Calmar is not the Calmar of the realised equity curve — it is the
  Calmar of a hypothetical curve produced by shuffling the trade
  outcomes.

The path-dependence issue is the gap that Monte Carlo (Chapter 26)
fills. Bootstrap tells you *what* the trade distribution implies;
Monte Carlo tells you *what paths* the same distribution can produce.

---

## 21.2 The metrics bootstrapped

`_METRICS_TO_BOOTSTRAP` in
[`bootstrap.py:36`](../../src/trading_research/eval/bootstrap.py)
lists six metrics:

```python
[
    "sharpe",
    "calmar",
    "win_rate",
    "expectancy_usd",
    "profit_factor",
    "sortino",
]
```

These six all reduce to a function of a 1-D P&L array, so trade-level
resampling has a clean interpretation. Metrics that depend on path or
on timing (max drawdown, drawdown duration, max consecutive losses,
trades per week) are *not* bootstrapped at this layer — they would
require resampling at a different level. Drawdown distribution comes
from Monte Carlo instead.

Each metric is computed via the same primitives the headline uses
([`utils/stats.py`](../../src/trading_research/utils/stats.py)) so the
point estimate sits on the resampled distribution rather than next to
it.

### 21.2.1 Threshold for emitting CIs

The bootstrap returns all-NaN CIs when the trade count is below 10
([`bootstrap.py:67`](../../src/trading_research/eval/bootstrap.py)).
At fewer than 10 trades the resampling is uninformative — every sample
draws roughly the same handful of outcomes. The report renders these
NaN bounds as "N/A" rather than fabricating a range.

---

## 21.3 Reading a CI

The CI is a kill criterion before it is anything else. The
[`_ci_flag`](../../src/trading_research/eval/bootstrap.py:149) helper
returns the warning marker `⚠ CI includes zero` whenever the lower
bound is non-positive — this is what shows up in red in the report's §2
headline block. The rule, codified in session 46:

> **If the 90% CI on a metric includes zero, that metric is statistically
> indistinguishable from "no edge". Treat it as a fail until the sample
> grows.**

Three reading-of-CIs heuristics that follow:

1. **Width beats centre.** A Calmar of 1.8 with CI [0.9, 2.7] is
   evidence of an edge. A Calmar of 1.8 with CI [-0.1, 3.6] is noise
   that happens to have a positive point estimate.
2. **Asymmetry tells you about the tail.** When the CI extends much
   farther on one side than the other, the metric is dominated by a
   small number of extreme trades. Profit factor is the classic
   example.
3. **A tight CI on a small sample is suspicious.** Bootstrap CIs from
   fewer than 50 trades that look tight are usually an artefact of
   the resampling drawing the same outcomes repeatedly. Read the
   trade count first.

> *Why 90% rather than 95%:* the 5/95 cutoffs match the report's
> visual emphasis on a *kill* test rather than a *publication* test.
> Tightening to 99% would push every retail-scale backtest into the
> "indistinguishable from zero" bucket regardless of edge; loosening
> to 50% would let through results no operator should trust. 90% is
> the band where the warning markers actually fire on the strategies
> that deserve them and stay quiet on the ones that don't.

---

## 21.4 Sample size implications

The bootstrap exposes the sample-size question that point estimates
hide. The trade-count line in the report's headline is the operator's
single most important sanity check.

| Trade count | Typical CI behaviour |
|---|---|
| < 30 | CIs span multiple signs; statistically uninformative; bootstrap returns N/A below 10 |
| 30 – 100 | CIs roughly ± 50% of the point estimate; most metrics will include zero |
| 100 – 200 | CIs tightening to ± 25–30%; minimum for a defensible promotion case |
| 200 – 500 | CIs around ± 15–20%; strong evidence territory |
| > 500 | CIs below ± 15%; the result is robust if the strategy is genuinely stationary |

These ranges are typical for retail-scale futures mean reversion at
the project's typical timeframes. They are not guarantees. A strategy
with skewed outcomes (rare large winners or losers) will have wider
CIs at every sample size; a strategy with low autocorrelation between
trades will have tighter ones. The 100-trade minimum the gate
criterion enforces (Chapter 46) is the floor, not the target.

The data-scientist persona's standing position: at 50 trades, Sharpe
of 0 and Sharpe of 2 are statistically indistinguishable. At 200 the
two are clearly distinct. The CI is how the platform makes that fact
visible at every level of the report.

---

## 21.5 Related references

### Code modules

- [`src/trading_research/eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py)
  — `bootstrap_summary`, `format_with_ci`, `_ci_flag`, the six metric
  wrappers.
- [`src/trading_research/eval/stats.py`](../../src/trading_research/eval/stats.py)
  — `bootstrap_metric` (the generic helper, used by drawdown CIs in
  §16) and the higher-order risk metrics.
- [`src/trading_research/eval/leaderboard.py`](../../src/trading_research/eval/leaderboard.py)
  — `_format_ci_range` (the helper that surfaces `[lo, hi]` columns in
  leaderboard text and HTML output).

### Other manual chapters

- **Chapter 17** — Trader's Desk Report: §2 (headline + CI flags),
  §16 (full CI block).
- **Chapter 19** — Headline Metrics: the point estimates each CI
  flanks.
- **Chapter 23** — Deflated Sharpe: the multiple-testing layer over
  the per-strategy CI here.
- **Chapter 26** — Monte Carlo: path-dependent metrics that bootstrap
  cannot reach.
- **Chapter 32** — Trial Registry & Leaderboard: `Calmar CI` and
  `Sharpe CI` leaderboard columns.
- **Chapter 46** — Pass/Fail Criteria: CI-includes-zero as a gate
  fail.

---

*End of Chapter 21. Next: Chapter 22 — Walk-Forward Validation.*
