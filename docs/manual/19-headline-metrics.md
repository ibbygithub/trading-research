# Chapter 19 — Headline Metrics

> **Chapter status:** [EXISTS] — every metric below is produced by
> [`compute_summary`](../../src/trading_research/eval/summary.py)
> ([`summary.py:29`](../../src/trading_research/eval/summary.py))
> and surfaced in the §2 headline block of the Trader's Desk Report
> (Chapter 17). The primitives live in
> [`utils/stats.py`](../../src/trading_research/utils/stats.py); this
> chapter is the operator's reference for what each number means.

---

## 19.0 What this chapter covers

The summary dict that every backtest writes carries roughly fifteen
performance numbers. Six of them appear in the report's headline block.
After reading this chapter you will:

- Know which metric is the platform's headline and why
- Understand what Sharpe assumes and where it misleads
- Know when Sortino adds information over Sharpe
- Be able to read profit factor, expectancy, and the breakeven win rate
  as a coherent triplet
- Know how drawdown depth and duration are computed and which of the two
  is usually the more brutal number

This chapter is roughly 4 pages. It is referenced by Chapters 17
(Trader's Desk Report), 21 (Bootstrap Confidence Intervals), 23
(Deflated Sharpe), 46 (Pass/Fail Criteria).

> *A note on annualisation:* every rate-based metric in this chapter uses
> a 252-trading-day annualisation constant
> ([`utils/stats.py:17`](../../src/trading_research/utils/stats.py)).
> Calmar and the per-trade aggregate metrics are computed over the span
> `[first entry_ts, last exit_ts]` of the trade log; trades_per_week
> uses a calendar-day span. These conventions are
> [`compute_summary`](../../src/trading_research/eval/summary.py)'s
> single source of truth.

---

## 19.1 Why Calmar is the headline

Calmar is **annualised return / |max drawdown|**. The implementation is
in [`utils/stats.py:51`](../../src/trading_research/utils/stats.py):

```python
equity = np.cumsum(pnl)
running_max = np.maximum.accumulate(equity)
drawdown = equity - running_max
max_dd = float(np.min(drawdown))
annual_return = float(np.sum(pnl)) / span_days * trading_days
return annual_return / abs(max_dd)
```

The headline placement is deliberate. The mentor persona's standing
position: Sharpe is a portfolio metric optimised for institutions that
can ride out double-digit drawdowns on a diversified book; Calmar is a
discretionary-trader metric that ties the reward number directly to the
worst losing run.

A Calmar of 1 means the worst observed drawdown ate one full year of
returns. A Calmar of 3 means the worst drawdown ate roughly four months
of returns. In retail mean-reversion specifically — where the operator
is sizing a single account and cannot replace lost capital — the zone
that is *actually runnable* is Calmar 2 to 3. Below 2, the drawdowns are
deep enough relative to returns that the operator will second-guess the
strategy at exactly the wrong moments.

> *Why this rather than Sharpe:* Sharpe rewards smoothness in both
> directions and penalises upside volatility; Calmar penalises only the
> losing path. For a strategy designed to make money in chunky bursts
> with occasional drawdowns, Sharpe systematically understates the
> result that the operator actually experiences. Calmar tells the
> truth about pain-to-gain.

### 19.1.1 Calmar caveats

Calmar depends on a single observation — the worst drawdown — so the
point estimate is noisy. A 200-trade backtest's Calmar can move by a
factor of two if one losing run gets reordered. This is why the
bootstrap CI on Calmar (Chapter 21) is the number the operator should
actually weigh, not the point estimate.

The other caveat is Calmar's sensitivity to the test window. A backtest
whose window happens to avoid the strategy's worst regime will print a
flattering Calmar that does not survive walk-forward. The walk-forward
fold variance table (Chapter 22) is the antidote.

---

## 19.2 Sharpe and what it misses

Sharpe is **mean daily P&L / standard deviation of daily P&L**, scaled
by √252:

```python
mu = np.mean(daily_pnl)
sigma = np.std(daily_pnl, ddof=1)
return mu / sigma * math.sqrt(252)
```

([`utils/stats.py:20`](../../src/trading_research/utils/stats.py))

The platform reports Sharpe but does not centre it. Three reasons:

1. **It penalises upside volatility.** A strategy with one $5,000 winning
   day among a string of $200 winning days is rewarded by Calmar (which
   only cares about the losing path) and penalised by Sharpe (which
   counts the upside surprise as variance). For mean-reversion intraday
   work the upside fat tails are precisely where the edge often lives.

2. **It assumes normal returns.** Mean-reversion P&L distributions are
   skewed — high win rate, occasional large losers, fat left tail. On a
   non-normal distribution Sharpe loses its statistical meaning; the
   number is still computable but its interpretation as "risk-adjusted
   return" requires assumptions the data violates. Chapter 25 covers
   the distribution diagnostics that catch this.

3. **It is sensitive to sample size.** The standard error on a Sharpe
   estimate scales with 1/√N. At 50 trades the CI is so wide that
   Sharpe 0 and Sharpe 2 are statistically indistinguishable; at 200
   trades the CI is defensible; at 1000 it is robust. Chapter 21 makes
   this concrete.

> *Why we keep reporting Sharpe at all:* it remains the most-cited
> performance metric in the literature and on every comparable platform.
> Suppressing it would force the operator to compute it manually whenever
> he wants to compare a result to an outside benchmark. The platform's
> position: report Sharpe, but never make a promotion decision on it
> alone. The deflated version (Chapter 23) is the number that survives
> multiple-testing.

---

## 19.3 Sortino — the downside-only Sharpe

Sortino is identical to Sharpe except the denominator uses only
downside deviation:

```python
downside = arr[arr < 0]
sigma_d = np.std(downside, ddof=1)
return mu / sigma_d * math.sqrt(252)
```

([`utils/stats.py:36`](../../src/trading_research/utils/stats.py))

Sortino sidesteps Sharpe's upside-penalty problem. A strategy with
strong winners and contained losers will print a Sortino noticeably
higher than its Sharpe, and the gap between the two numbers is itself
informative: a wide Sortino / Sharpe ratio means the upside is the
asymmetric part of the distribution.

Sortino is not the headline because Calmar already addresses the same
concern through the maximum-drawdown channel, and Calmar is more direct
about the operator's actual experience. Sortino is useful as a
cross-check: when Calmar and Sortino agree the verdict is robust; when
they disagree (Sortino strong, Calmar weak), the strategy has good
daily P&L behaviour but is losing the gains through one bad run.

> *Edge case:* Sortino requires at least two negative-return days to
> compute a downside deviation. Strategies with very high win rates
> (>90%) and small samples may return NaN. The headline drops the row;
> the bootstrap CI surfaces the instability.

---

## 19.4 Profit factor and expectancy

These are the per-trade aggregates that describe *how* the strategy
makes its money, not just how much.

**Profit factor** = gross wins / |gross losses|. Reported by
[`compute_summary`](../../src/trading_research/eval/summary.py:51)
and by [`utils/stats.py:79`](../../src/trading_research/utils/stats.py).
A profit factor of 1.0 is breakeven before costs; 1.3 is a typical
threshold for "this might survive realistic costs"; above 2.0 is
exceptional and usually warrants a hard look for leakage. Profit factor
hides direction (a high-win-rate scalper and a low-win-rate trend
follower can have identical profit factors with very different
character) which is why it must be read together with win rate.

**Expectancy** is the simple average net P&L per trade — `np.mean(net)`
in [`summary.py:54`](../../src/trading_research/eval/summary.py). It
is denominated in USD per round trip and answers the question "what is
this strategy worth in cash terms per trade?" When converted to
R-multiples (expectancy / avg loss) it becomes scale-free and is the
right number to compare across strategies with different per-trade
risk.

> *Reading them together:* profit factor tells you the ratio; expectancy
> tells you the absolute size; win rate tells you the trade-by-trade
> rhythm. None of the three alone is sufficient — and the bootstrap CIs
> on both profit factor and expectancy (Chapter 21) are wider than the
> point estimates suggest, because both are dominated by a handful of
> large trades in any short sample.

---

## 19.5 Win rate and the breakeven threshold

Win rate is the fraction of trades with positive net P&L
([`utils/stats.py:71`](../../src/trading_research/utils/stats.py)). On
its own it is uninterpretable — a 90% win rate on $5 winners and $500
losers is a losing strategy.

The number that makes win rate meaningful is the **breakeven win rate**:

```
WR_be = avg_loss / (avg_win + avg_loss)
```

A strategy is profitable when its observed win rate exceeds WR_be. The
margin between the two is the *edge*. A strategy with WR = 65% and
WR_be = 60% has a 5-point edge; a strategy with WR = 80% and
WR_be = 79% has a 1-point edge — and the second is far more fragile,
because a small cost increase or a small slippage shift moves WR_be by
more than 1 point.

The platform surfaces both numbers in the §2 headline (`win_rate`,
`avg_win_usd`, `avg_loss_usd`) and the breakeven calculation is
performed by the report renderer rather than carried in the summary
dict directly. The data scientist persona is the right voice to invoke
when this margin is thin: a 1-point margin on 100 trades has a
confidence interval that includes zero.

---

## 19.6 Drawdown depth and duration

The drawdown block in
[`compute_summary`](../../src/trading_research/eval/summary.py:71)
emits three numbers from the equity curve:

| Field | Meaning |
|---|---|
| `max_drawdown_usd` | Worst peak-to-trough dollar loss observed in the run |
| `max_drawdown_pct` | The same as a percentage of the peak at that point |
| `drawdown_duration_days` | Longest peak-to-recovery interval in calendar days |

Depth is computed via `equity.cummax() - equity` and then the minimum.
Duration is computed by [`_longest_drawdown_duration`](../../src/trading_research/eval/summary.py:175):
walks every drawdown episode and returns the longest start-to-recovery
gap in calendar days. A drawdown that the equity curve never recovers
from before the end of the test window is counted to the final bar.

The headline number most operators read is depth. The number that
actually breaks traders psychologically is duration. A 12% drawdown
that recovers in two weeks is uncomfortable; a 12% drawdown that takes
nine months to recover is the one that gets a strategy turned off at
the bottom. Chapter 20 picks up duration as a behavioural metric in
its own right; Chapter 29 decomposes every individual drawdown for
forensic work.

> *Why depth and duration are both required:* a strategy with shallow
> but long drawdowns (think: slow grinder that goes nowhere for months)
> has the same depth metric as a strategy that drops fast and snaps
> back. Without duration the operator cannot tell which one he is
> looking at, and the two demand very different psychological
> responses.

---

## 19.7 Related references

### Code modules

- [`src/trading_research/eval/summary.py`](../../src/trading_research/eval/summary.py)
  — `compute_summary` (the dict every metric flows through),
  `_drawdown_stats`, `_longest_drawdown_duration`, `format_summary`.
- [`src/trading_research/utils/stats.py`](../../src/trading_research/utils/stats.py)
  — single source of truth for `annualised_sharpe`, `annualised_sortino`,
  `calmar`, `win_rate`, `profit_factor`. Used by both the summary
  computation and the bootstrap.
- [`src/trading_research/eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py)
  — `format_with_ci` is the report's headline renderer.

### Other manual chapters

- **Chapter 17** — The Trader's Desk Report: §2 headline block and §16
  CI block.
- **Chapter 20** — Behavioural Metrics: trades/week, max consecutive
  losses, drawdown duration in trading days, MAE/MFE.
- **Chapter 21** — Bootstrap Confidence Intervals: the CIs that flank
  every metric in this chapter.
- **Chapter 23** — Deflated Sharpe: the multiple-testing-corrected
  version of §19.2.
- **Chapter 46** — Pass/Fail Criteria: how these metrics are combined
  into a gate decision.

---

*End of Chapter 19. Next: Chapter 20 — Behavioural Metrics.*
