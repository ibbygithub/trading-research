# Chapter 25 — Distribution Analysis

> **Chapter status:** [EXISTS] — diagnostics in
> [`eval/distribution.py`](../../src/trading_research/eval/distribution.py),
> tail risk and higher-order metrics in
> [`eval/stats.py`](../../src/trading_research/eval/stats.py).
> Outputs surface in §21 of the Trader's Desk Report.

---

## 25.0 What this chapter covers

The headline metrics (Chapter 19) assume the strategy's return
distribution is well-behaved. When it isn't, Sharpe lies. The
distribution module exists to catch those lies. After reading this
chapter you will:

- Know what skew and kurtosis tell you and which one to read first
- Be able to read a Jarque-Bera p-value as the normality verdict
- Know which tail-risk metrics the platform reports and when each
  one is appropriate

This chapter is roughly 3 pages. It is referenced by Chapters 17, 19,
21.

---

## 25.1 Return distribution diagnostics

[`return_distribution_stats`](../../src/trading_research/eval/distribution.py:5)
returns a dict with seven fields:

| Field | Meaning |
|---|---|
| `skewness` | `scipy.stats.skew` — third standardised moment. Symmetric distributions have skew = 0; left-tail-heavy has negative skew |
| `kurtosis` | Pearson kurtosis. Normal = 3.0; fat-tailed > 3.0 |
| `excess_kurtosis` | Fisher kurtosis. Normal = 0.0; fat-tailed > 0 |
| `jb_stat` | Jarque-Bera test statistic |
| `jb_pvalue` | Jarque-Bera p-value |
| `normality_flag` | True when `jb_pvalue < 0.05` |
| `normality_warning` | Human-readable warning string |

The Jarque-Bera test is the formal normality check. The null hypothesis
is "the distribution is normal." A low p-value (< 0.05) is evidence
against normality. For typical trading return distributions the JB
test almost always rejects normality — fat tails, asymmetry, and
discrete tick effects all contribute. The flag is informational; it
says "don't trust metrics that assume normality" rather than "the
strategy is broken."

### 25.1.1 What each number means for the operator

**Skew.** A mean-reversion strategy that takes small profits and lets
losers run will print negative skew — many small wins, fewer larger
losses. The headline win rate looks great, but the distribution shape
warns that a single loser can eat months of gains. The mentor's
question: "what is the worst single-trade outcome you have planned
for?" Negative skew in the backtest is a hint at the answer.

**Kurtosis.** High kurtosis means the distribution has more mass in
the tails than a normal distribution would. For trading returns this
is normal — markets jump. What matters is *whether the tails are
symmetric*. High kurtosis with negative skew is the worst combination:
fat tails concentrated on the losing side. High kurtosis with neutral
skew is just "this strategy has occasional big moves both ways."

> *Why Pearson kurtosis is the convention here:* the DSR computation
> (Chapter 23) requires Pearson kurtosis as input, and the platform
> uses the same convention throughout for consistency.
> `scipy.stats.kurtosis` defaults to Fisher (normal = 0); the module
> calls it with `fisher=False`. The check at
> [`eval/stats.py:38`](../../src/trading_research/eval/stats.py)
> catches any caller that passes Fisher kurtosis by mistake.

---

## 25.2 Tail-risk metrics

When the distribution is non-normal, the right way to characterise
downside is to look at the tail directly, not via the standard
deviation that Sharpe uses. The platform reports three families:

### 25.2.1 VaR and CVaR

**Value at Risk (VaR)** is the percentile-based downside: the 5% VaR
is the loss the strategy will exceed on 5% of days. It is reported
in dollars or as a return.

**Conditional VaR (CVaR)**, also called *expected shortfall*, is the
average loss *conditional on* exceeding the VaR threshold. CVaR is
the more informative of the two — VaR says "at least this bad on
average 5% of days," CVaR says "this is how bad those 5% of days
typically are."

Both surface in §18 of the Trader's Desk Report (Extended Risk
Metrics) alongside the other risk-officer aggregates.

### 25.2.2 Tail ratio

[`tail_ratio`](../../src/trading_research/eval/stats.py:114) returns
`|p95| / |p5|` of returns. The interpretation:

| Tail ratio | Verdict |
|---|---|
| < 0.8 | Negative-tail-heavy. Losers are larger than equivalent winners. |
| 0.8 – 1.2 | Roughly symmetric. |
| > 1.2 | Positive-tail-heavy. Winners are larger than equivalent losers. |

Tail ratio is the quick visual companion to skew. They usually agree;
when they don't (skew negative, tail ratio above 1.0), the
asymmetry is concentrated in moderate moves rather than in the
extremes, which is a different and usually-better problem.

### 25.2.3 Omega and gain-to-pain

**Omega ratio** ([`eval/stats.py:120`](../../src/trading_research/eval/stats.py))
is the ratio of probability-weighted gains to probability-weighted
losses above and below a threshold (default zero). Omega > 1 means
the gain distribution dominates the loss distribution at that
threshold.

**Gain-to-pain ratio** ([`eval/stats.py:126`](../../src/trading_research/eval/stats.py))
is the sum of positive monthly returns over the absolute sum of
negative monthly returns. Schwager's metric; useful when the
operator wants a "how much pain did I endure to get these gains"
number that aggregates at the month level rather than the trade or
day level.

These two are reported in §18; both are most useful when comparing
two strategies that have similar Sharpe and Calmar — they
differentiate strategies that look identical on the headlines.

---

## 25.3 Q-Q plot and autocorrelation

§21 of the Trader's Desk Report adds two diagnostic plots on top of the
numeric distribution stats.

[`qq_plot_data`](../../src/trading_research/eval/distribution.py:31)
emits the data for a quantile-quantile plot: standardised observed
returns against theoretical normal quantiles. A perfectly normal
distribution lies on the diagonal; deviations at the ends of the line
reveal tail behaviour faster than reading skew and kurtosis numbers.
The data scientist's standard heuristic: if the lower tail of the Q-Q
plot bends down sharply, that's where the strategy will hurt.

[`autocorrelation_data`](../../src/trading_research/eval/distribution.py:44)
computes the autocorrelation function (ACF) of returns for lags 1
through `max_lags` (default 20) and the Ljung-Box test for serial
correlation. The `serial_correlation_flag` is True when the Ljung-Box
p-value is < 0.05.

Serial correlation in trade returns is a problem the operator
should know about. It usually means trades are not independent —
the strategy is firing repeatedly in correlated bursts. The Sharpe
calculation assumes independence; when it is violated, the realised
Sharpe variance is wider than the formula predicts, and the
bootstrap CI is more honest than the point estimate.

---

## 25.4 Related references

### Code modules

- [`src/trading_research/eval/distribution.py`](../../src/trading_research/eval/distribution.py)
  — `return_distribution_stats`, `qq_plot_data`,
  `autocorrelation_data`.
- [`src/trading_research/eval/stats.py`](../../src/trading_research/eval/stats.py)
  — `tail_ratio` (line 114), `omega_ratio` (line 120),
  `gain_to_pain_ratio` (line 126), and the higher-order risk
  metrics (`mar_ratio`, `ulcer_index`, `recovery_factor`,
  `pain_ratio`) used in §18.

### Other manual chapters

- **Chapter 17** — Trader's Desk Report: §18 (Extended Risk Metrics)
  and §21 (Distribution Diagnostics).
- **Chapter 19** — Headline Metrics: where the distribution
  assumptions live in the Sharpe definition.
- **Chapter 21** — Bootstrap Confidence Intervals: the empirical
  fallback when distributional assumptions fail.
- **Chapter 23** — Deflated Sharpe: consumes the Pearson kurtosis
  computed here.

---

*End of Chapter 25. Next: Chapter 26 — Monte Carlo Simulation.*
