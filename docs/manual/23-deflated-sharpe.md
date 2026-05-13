# Chapter 23 — Deflated Sharpe

> **Chapter status:** [EXISTS] — implementation in
> [`eval/stats.py:54`](../../src/trading_research/eval/stats.py). DSR
> surfaces in the §2 headline of the Trader's Desk Report and in the
> `format_with_ci` text output with the trial count, both added in
> session 46. The trial registry that feeds it lives at
> [`eval/trials.py`](../../src/trading_research/eval/trials.py).

---

## 23.0 What this chapter covers

The Deflated Sharpe Ratio (DSR) is the multiple-testing correction
the platform applies to every Sharpe number it reports. It is the
single most-misunderstood metric in retail backtesting and the
single most important one for the operator's promotion decisions.
After reading this chapter you will:

- Understand the multiple-testing problem in concrete terms
- Know what the Lopez de Prado correction does and why
- Know how the trial registry decides what "trial count" to use
- Be able to read a deflated Sharpe — what a raw 1.8 deflating to 0.4
  actually means and when to walk away

This chapter is roughly 4 pages and is the second of Part V's two
teaching chapters. It is referenced by Chapters 17, 19, 22, 32, 46.

---

## 23.1 The multiple-testing problem

The setup. The operator tests 50 variants of a strategy on the same
data. He picks the variant with the highest Sharpe and reports that
Sharpe as the strategy's performance. There is nothing wrong with the
math — that variant really did print that Sharpe on that data. There
is something deeply wrong with the *inference*: the reported number
is the maximum of 50 noisy realisations, not the mean. The expected
maximum of N draws from a distribution is systematically higher than
any single draw's expected value. Reporting the maximum as if it were
a typical draw inflates the apparent edge.

A worked example. Imagine 50 strategies that genuinely have zero edge
— their true Sharpe is 0. Each backtest is one realisation of a
mean-zero distribution with some sample variance. The realised Sharpes
will scatter around 0; some will be positive by chance. The maximum
of 50 such realisations on a 200-trade backtest is typically around
+1.5 to +2.0 — purely from sampling noise. The operator who tests
50 strategies and reports the best one has a 50% probability of
reporting a Sharpe above 1.7, despite testing only edge-free
strategies. This is the cherry-picking problem stated quantitatively.

The fix is not to test fewer strategies. The fix is to *adjust the
reported number to account for how many strategies were tested*. That
adjustment is what DSR computes.

> *Why this matters more for the operator than for institutions:*
> institutional research desks have process discipline — every test
> is logged, the number of variants is tracked, the inference at the
> end is adjusted. A retail trader has no such process by default.
> The platform's trial registry is the process; DSR is the inference
> adjustment.

---

## 23.2 The Lopez de Prado correction

The formula is from Bailey & Lopez de Prado (2012), "The Sharpe Ratio
Efficient Frontier," *Journal of Risk* 15(2). The implementation:

```python
def deflated_sharpe_ratio(sharpe, n_obs, n_trials, skewness, kurtosis_pearson):
    if n_trials == 1:
        sr_bench = 0.0
    else:
        emc = 0.5772156649  # Euler-Mascheroni constant
        sr_bench = ((1 - emc) * st.norm.ppf(1 - 1.0/n_trials)
                    + emc * st.norm.ppf(1 - 1.0/(n_trials*math.e)))
    return probabilistic_sharpe_ratio(sharpe, n_obs, skewness,
                                       kurtosis_pearson, sr_bench)
```

([`eval/stats.py:54`](../../src/trading_research/eval/stats.py))

Two layers stacked. The inner function is the
**Probabilistic Sharpe Ratio (PSR)**, which is "the probability the
true Sharpe exceeds some benchmark, given the observed Sharpe, the
sample size, and the higher moments of the return distribution":

```python
var = (1 - skewness * sharpe
       + ((kurtosis_pearson - 1) / 4) * sharpe**2) / (n_obs - 1)
return st.norm.cdf((sharpe - sr_benchmark) / math.sqrt(var))
```

PSR against `sr_benchmark = 0` answers "how confident am I that this
strategy has *any* positive Sharpe?" PSR against `sr_benchmark = 1`
answers "how confident am I that this strategy's true Sharpe exceeds
1?" PSR is already an honest number — it accounts for skewness,
kurtosis, and sample size — but it does not account for how many
strategies were tested.

The outer **Deflated Sharpe** layer addresses the multiple-testing
problem. It computes the expected maximum Sharpe that would be
observed across `n_trials` strategies *if every one of them had zero
true edge*. That expected max becomes the benchmark for PSR:

```
SR_bench(N) = (1 - γ) · Φ⁻¹(1 - 1/N) + γ · Φ⁻¹(1 - 1/(N·e))
```

where γ is the Euler-Mascheroni constant. DSR is then PSR evaluated
against this elevated benchmark. The intuition: the more trials you
ran, the higher the bar your observed Sharpe must clear to demonstrate
genuine edge.

### 23.2.1 Deflation behaviour as N grows

The benchmark grows roughly with √log(N). The deflation is brutal:

| Raw Sharpe | n_trials = 1 | n_trials = 10 | n_trials = 50 | n_trials = 200 |
|---|---|---|---|---|
| 1.0 | DSR ~ 0.84 | DSR ~ 0.30 | DSR ~ 0.08 | DSR ~ 0.02 |
| 1.5 | DSR ~ 0.96 | DSR ~ 0.70 | DSR ~ 0.32 | DSR ~ 0.10 |
| 2.0 | DSR ~ 0.99 | DSR ~ 0.92 | DSR ~ 0.66 | DSR ~ 0.32 |

(Illustrative — exact values depend on `n_obs`, skewness, and
kurtosis. The PSR computation uses the trade-level distribution's
actual moments.)

The reading: a raw Sharpe of 1.5 from one strategy is strong
evidence. The same Sharpe from the best of 50 variants is barely
evidence at all.

### 23.2.2 The Pearson-vs-Fisher kurtosis trap

The function takes Pearson kurtosis (normal distribution = 3.0), not
Fisher / excess kurtosis (normal = 0.0). `scipy.stats.kurtosis`
defaults to Fisher; passing the default produces nonsense values.
The function defends against this in
[`eval/stats.py:38`](../../src/trading_research/eval/stats.py):

```python
if not math.isnan(kurtosis_pearson) and kurtosis_pearson < 1.0:
    raise ValueError(...)
```

Any value below 1.0 is impossible for a real distribution; getting one
means the caller passed Fisher kurtosis. The correct call is
`scipy.stats.kurtosis(returns, fisher=False)`.

---

## 23.3 The trial registry's role

DSR's `n_trials` parameter is not a guess. It comes from the trial
registry at [`runs/.trials.json`](../../runs/.trials.json), which
records every backtest the platform has ever run.

The registry schema ([`eval/trials.py`](../../src/trading_research/eval/trials.py)):

```python
@dataclass
class Trial:
    strategy_id: str
    trial_group: str
    sharpe: float
    mode: str = "validation"        # or "exploration"
    parent_sweep_id: str | None = None
    # ... plus timestamp, config hash, CI bounds, etc.
```

Two fields drive the trial-count computation:

**`trial_group`** is a tag for "these variants are testing the same
hypothesis." All variants from one sweep share a `trial_group`. When
DSR is computed for a strategy in that group, `n_trials` is the count
of distinct trials in the group, not the count of all trials in the
registry.

**`mode`** distinguishes `exploration` (knob sweeps, parameter
searches) from `validation` (final candidates run on the validation
set). Exploration trials count toward the deflation. Validation
trials are isolated by their own mode tag.

**`parent_sweep_id`** is the sweep run that produced a given trial.
Multiple sweeps testing the same strategy idea can be aggregated into
one trial group for DSR purposes; the parent ID lets the operator
trace which sweep contributed which trials.

### 23.3.1 What the registry corrects for

A walkforward run that records one trial after testing 24 variants in
a parent sweep should use `n_trials = 24` when computing DSR. A
strategy whose first-ever backtest is its only test gets
`n_trials = 1` and the deflation collapses to plain PSR. The
distinction matters: the same raw Sharpe of 1.5 produces a DSR of
~0.96 in the first case and ~0.32 in the second.

The CLI computes DSR after every backtest using `count_trials_for_group`
([`eval/trials.py:256`](../../src/trading_research/eval/trials.py))
and surfaces the result in `format_with_ci`. The operator does not
need to track the trial count manually; the registry does it.

### 23.3.2 Honesty about the trial registry's limits

The registry only counts trials *the platform has run*. It does not
count tests run in notebooks, Excel, eyeballing charts, or in the
operator's head before the first config was written. Those are
real trials and they really do affect the inference, but the
platform cannot see them. The DSR number assumes the operator's
process is at least as disciplined as the registry's record — when
it isn't, the true deflation is worse than reported.

The fix is process, not math. The mentor's standing position: if you
spent two weeks staring at charts before writing the first YAML, count
that as roughly 20 trials whether or not the platform recorded them.

---

## 23.4 Reading a deflated Sharpe

DSR is a probability between 0 and 1. A DSR of 0.95 means "given the
observed Sharpe, the sample size, the distribution shape, and the
number of trials, there is a 95% probability that this strategy's
true Sharpe exceeds the elevated benchmark." Higher is better.

A practical reading scale:

| DSR | Verdict |
|---|---|
| > 0.95 | Strong evidence. Promote on the strength of DSR alone if other gates are clean. |
| 0.85 – 0.95 | Solid evidence. Treat as the threshold for "real edge probably exists." |
| 0.50 – 0.85 | Weak evidence. The strategy is probably better than zero but the data is not yet decisive. |
| 0.10 – 0.50 | Effectively no evidence. The raw Sharpe is mostly the maximum of noise. |
| < 0.10 | The strategy looks worse than random under the deflation. Walk away. |

The vivid case the data-scientist persona invokes: **raw Sharpe of 1.8
deflating to DSR of 0.4**. What that means in plain English: the
operator's strategy printed Sharpe 1.8, which sounds great, but after
accounting for the (let's say) 30 variants tested, the probability
that the *true* edge is positive is only 40%. Coin-flip territory.
Whatever the operator does next, he should not allocate capital on
the strength of that result alone.

The DSR is also unforgiving in the other direction. A strategy with
raw Sharpe of only 0.9 — modest — but DSR of 0.92 is more trustworthy
than the 1.8-deflating-to-0.4 case. The deflation rewards process
discipline: a single hypothesis, tested once, that works modestly,
beats forty hypotheses tested in a sweep that produce one apparent
winner.

> *Why the platform leads with DSR rather than raw Sharpe:* Sharpe
> 1.8 looks impressive in a vacuum. The operator who looks only at
> Sharpe will, eventually, fund a strategy that doesn't work. The
> deflation is the single most useful guardrail against that failure
> mode the platform can provide. Session 46's decision to place DSR
> next to raw Sharpe in the headline rather than buried in the risk-
> officer section was deliberate: *the operator should never see raw
> Sharpe without the deflated version next to it.*

---

## 23.5 Surfacing DSR in reports

DSR appears in three places, all added in session 46:

1. **§2 headline of the Trader's Desk Report** —
   `_compute_headline_metrics` in
   [`eval/report.py`](../../src/trading_research/eval/report.py)
   includes DSR alongside raw Sharpe.
2. **`format_with_ci` text output** — the
   [`bootstrap.py:191`](../../src/trading_research/eval/bootstrap.py)
   block prints `Deflated Sharpe (DSR)  0.42  (n_trials=24)`.
3. **§17 Risk Officer block** — DSR with PSR vs SR=0 and SR=1, plus
   skewness and kurtosis used in the computation.

The trial count is rendered next to the DSR everywhere it appears, so
the operator can sanity-check the deflation against his own memory of
how many variants he tested.

---

## 23.6 Related references

### Code modules

- [`src/trading_research/eval/stats.py`](../../src/trading_research/eval/stats.py)
  — `probabilistic_sharpe_ratio` (line 20), `deflated_sharpe_ratio`
  (line 54).
- [`src/trading_research/eval/trials.py`](../../src/trading_research/eval/trials.py)
  — `Trial`, `record_trial`, `count_trials_for_group`,
  `migrate_trials`.
- [`src/trading_research/eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py)
  — `format_with_ci` (line 111) — the DSR row in the text output.
- [`src/trading_research/eval/report.py`](../../src/trading_research/eval/report.py)
  — `_compute_headline_metrics` — DSR placement in §2.
- [`src/trading_research/cli/main.py`](../../src/trading_research/cli/main.py)
  — the `backtest` subcommand computes DSR after each run.

### References

- Bailey, D. and López de Prado, M. (2012). "The Sharpe Ratio Efficient
  Frontier." *Journal of Risk* 15(2): 3–44.
- López de Prado, M. (2018). *Advances in Financial Machine Learning*.
  Wiley. Chapter 8 covers DSR and the trial-count discipline in full.

### Other manual chapters

- **Chapter 17** — Trader's Desk Report: §2 headline (DSR next to
  Sharpe) and §17 (DSR/PSR detail).
- **Chapter 19** — Headline Metrics: raw Sharpe and its caveats.
- **Chapter 22** — Walk-Forward Validation: the regime test that
  complements DSR's trial-count test.
- **Chapter 31** — The Sweep Tool: sweeps are the most common source
  of inflated trial counts.
- **Chapter 32** — Trial Registry & Leaderboard: the registry's full
  schema and the leaderboard's view onto it.
- **Chapter 46** — Pass/Fail Criteria: DSR > 0.5 as a gate criterion.

---

*End of Chapter 23. Next: Chapter 24 — Stationarity Suite.*
