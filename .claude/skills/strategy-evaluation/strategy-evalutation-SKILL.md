---
name: strategy-evaluation
description: Use when computing performance metrics from a trade log, generating evaluation reports, comparing strategies or strategy variants, computing deflated Sharpe ratios for multiple-tested strategies, calculating drawdown and recovery metrics, or producing the one-page report that accompanies every backtest run. This skill defines the four metric categories (return-quality, drawdown, robustness, behavioral), the headline metric choice (Calmar over Sharpe), the bootstrap confidence interval methodology, and the report format used to summarize a run for human review. Invoke when adding metrics to the framework, when interpreting backtest results, or when designing comparisons between strategy variants.
---

# Strategy Evaluation

This skill owns the question "is this strategy actually any good?" Its job is to take a trade log produced by the backtest engine and turn it into honest, comprehensive, decision-ready answers about the strategy's behavior. Its job is also to refuse to flatter strategies that don't deserve flattering, even when the headline number looks great.

The principle: **report the numbers a trader needs to make a real decision, not the numbers that sell.** Most backtest tools report a Sharpe ratio and call it a day. Sharpe ratio is a useful number but it's the wrong headline for someone seeking consistent returns, it's misleading on non-normal return distributions, and it's almost always presented without the deflation that would tell you whether the result is real or noise. This skill computes Sharpe but doesn't lead with it. The headline is Calmar. The robustness numbers (deflated Sharpe, bootstrap CIs) are mandatory. The behavioral numbers (max consecutive losses, drawdown duration) are prominent.

The second principle: **every metric reports its uncertainty.** A Sharpe of 1.4 from 47 trades is statistically indistinguishable from a Sharpe of 0. The framework refuses to report point estimates without confidence intervals, because the point estimate alone misleads about how much you actually know.

## What this skill covers

- The four metric categories (return-quality, drawdown, robustness, behavioral)
- Calmar as the headline risk-adjusted metric
- Sharpe and Sortino as supporting metrics
- Deflated Sharpe ratio for multiple-tested strategies
- Bootstrap confidence intervals on every reported metric
- Drawdown depth, duration, and recovery time
- Max consecutive losses and the longest losing streak
- Trades-per-week and average holding period
- Monthly and quarterly return breakdowns
- The one-page evaluation report format
- Strategy comparison reports for multiple variants

## What this skill does NOT cover

- Generating the trade log (see `backtesting`)
- Visualizing equity curves and drawdowns (see `charting`)
- Position sizing or risk limits (see `risk-management`)
- Walk-forward orchestration (see `backtesting`)

## The four metric categories

Every evaluation report computes metrics in four categories. They answer different questions and a strategy that looks good on one but bad on another is a strategy that warrants the conversation rather than the green light.

**Category 1: Return quality.** "Given the risk I took, was the return worth it?"

- **Calmar ratio** — annualized return divided by max drawdown. This is the headline. It directly answers "how much pain did I endure for the return?" which is the question that matters when you're trading your own retirement money.
- **Sortino ratio** — like Sharpe but only penalizes downside deviation. Better than Sharpe for non-normal distributions.
- **Sharpe ratio** — the lingua franca. Reported because comparisons require it, not because it's the right number.
- **MAR ratio** — like Calmar but uses average drawdown instead of max. A complement to Calmar that smooths out the dependence on a single worst case.
- **Profit factor** — gross winning P&L divided by gross losing P&L. A clean number that traders intuitively understand.
- **Expectancy per trade in dollars** — net P&L divided by number of trades. The most direct answer to "how much do I make per trade on average."

**Category 2: Drawdown.** "How bad does it get on the way to the return?"

- **Max drawdown in dollars** and **max drawdown as a percentage of equity**.
- **Max drawdown duration** — the longest time the equity curve was below a prior peak, in calendar days and trading days. Often more painful than the depth.
- **Average drawdown duration** across all drawdowns above a minimum threshold.
- **Time underwater percentage** — what fraction of the backtest period was the strategy in any drawdown at all.
- **Ulcer Index** — root mean square of drawdown depths. A single number that captures both depth and frequency.
- **Recovery time from max drawdown** — how long it took to get back to the prior peak after the worst drawdown.

**Category 3: Robustness.** "Is the result real or did I torture the data into producing it?"

- **Deflated Sharpe ratio** (Lopez de Prado) — adjusts the raw Sharpe for the multiple-testing bias that comes from trying many strategy variants. Required for any reported result that came from a parameter sweep or strategy variation.
- **Probability of backtest overfitting (PBO)** — the probability that the best strategy in your sample is overfit. Computed via the combinatorially symmetric cross-validation method when multiple variants are available.
- **Bootstrap confidence intervals** on every reported metric. The CI tells you how much the metric would vary if the trades happened in a different order or if the sample were slightly different. Wide CIs mean you don't actually know the metric's true value.
- **Out-of-sample degradation** — for walk-forward backtests, the difference between in-sample and out-of-sample performance. Large degradation means the strategy was fitting to noise.
- **Trade count** — reported prominently because everything in this category depends on having enough trades to compute meaningful statistics. Below 100 trades, treat all metrics as suggestive at best. Below 30 trades, treat them as decorative.

**Category 4: Behavioral.** "Can I actually run this strategy?"

- **Trades per week** — frequency of trading. A strategy that fires 40 times per week is a different beast than one that fires twice per week, and the human's ability to monitor differs accordingly.
- **Average holding period** in bars and in wall-clock hours.
- **Max consecutive losses** — the longest streak of losing trades. More painful than max drawdown for many traders because it tests conviction directly.
- **Longest losing streak in days** — distinct from max consecutive losses; this measures the elapsed time during the worst losing run.
- **Win rate** — percentage of trades that were profitable. Reported but not centered, because high win rates often come with bad expectancy (mean reversion strategies are notorious for this).
- **Profit-to-loss ratio (average win / average loss)** — the asymmetry between winners and losers in dollar terms.
- **Largest single-trade loss** — the worst trade in the backtest. Often more informative than averages.
- **Recovery factor** — net profit divided by max drawdown. Different from Calmar because it's not annualized; it answers "how many times the worst pain did I make in total profit."

## The headline: why Calmar, not Sharpe

The standard headline metric in quant trading is Sharpe ratio. This skill defaults to **Calmar** as the headline, with Sharpe shown but not centered. The reasoning, in detail because the question will come up:

**Sharpe assumes returns are normally distributed.** Mean reversion strategies have notoriously non-normal distributions: high win rates, occasional large losers, fat left tails. On those distributions, Sharpe flatters the strategy by treating downside variance the same as upside variance. A strategy that grinds out small wins and occasionally takes a 5x loser will show a respectable Sharpe right up until you look at how much that 5x loser ruined your year.

**Sharpe penalizes upside volatility.** This is mathematically true and almost always a mistake. Nobody loses sleep over a big winner. Sortino is the immediate fix — it penalizes only downside variance — but Calmar goes further by tying the metric to drawdown directly.

**Calmar matches how traders actually feel.** The number that determines whether you abandon a strategy at the worst possible moment is the max drawdown, not the Sharpe ratio. Calmar is `annual return / max drawdown`. A Calmar of 1 means "in the worst year, the drawdown ate the entire annual return." A Calmar of 2 means "the worst drawdown was half a year of returns." A Calmar of 3+ is the zone where retail traders can realistically stay in their seats through the bad times. This maps cleanly to the question "can I actually trade this?"

**Sharpe is reported, not centered.** Every report shows Sharpe so you can compare to other strategies and to industry benchmarks. But the headline number, the one in the largest font on the report, is Calmar. The data scientist persona will direct attention to Calmar in conversation. Sharpe gets a footnote.

**One important caveat:** Calmar depends on the worst single drawdown, which is a single observation. With a small sample, a different period might have produced a much better or worse worst drawdown. The skill always reports Calmar with a bootstrap confidence interval, and a wide CI on Calmar is the signal that the metric is dominated by one event.

## Deflated Sharpe ratio

This is the most important metric in the robustness category and it deserves its own section because the math matters and the framework treats it as mandatory whenever multiple variants have been tested.

**The problem:** if you try 30 variants of a strategy and pick the one with the best Sharpe, the reported Sharpe is biased upward. You're not measuring "the strategy's Sharpe"; you're measuring "the maximum of 30 noisy Sharpe estimates," and the maximum of N noisy estimates is systematically larger than any individual estimate. The more variants you try, the larger the bias.

**The fix:** Lopez de Prado's deflated Sharpe ratio (DSR) adjusts the reported Sharpe to account for the number of trials. The formula involves the variance of the trial Sharpes, the skew and kurtosis of the strategy's returns, and the number of trials. The output is the probability that the true Sharpe is greater than zero, given the sample.

**The interpretation:** if the deflated Sharpe says there's a 90% probability that the true Sharpe is positive, that's a strong result. If it says 55%, the strategy is statistically indistinguishable from noise even though the raw Sharpe might be 1.5.

**When it's required:** any backtest result that came from selecting the best of multiple variants. This includes parameter sweeps, A/B tests, walk-forward steps that select different parameters at each step, and any optimization process. The framework refuses to report a "best Sharpe" without also reporting the deflated version.

```python
# src/trading_research/eval/robustness.py
from scipy import stats
import numpy as np

def deflated_sharpe_ratio(
    trial_sharpes: list[float],
    selected_sharpe: float,
    num_trades: int,
    skew: float,
    kurtosis: float,
) -> dict:
    """Compute the deflated Sharpe ratio per Lopez de Prado (2014).

    Args:
        trial_sharpes: the Sharpe ratios of all variants tested
        selected_sharpe: the Sharpe of the chosen variant
        num_trades: the number of trades in the chosen variant's backtest
        skew: skewness of the chosen variant's per-trade returns
        kurtosis: excess kurtosis of the chosen variant's per-trade returns

    Returns:
        dict with keys:
            - dsr: deflated Sharpe value
            - psr: probabilistic Sharpe (probability the true Sharpe > 0)
            - expected_max_sharpe: the Sharpe you'd expect from N trials of a
                strategy with true Sharpe = 0 (the bias)
            - is_significant: True if PSR > 0.95
    """
    n_trials = len(trial_sharpes)
    sharpe_var = np.var(trial_sharpes, ddof=1) if n_trials > 1 else 0.0

    # Expected maximum Sharpe under null hypothesis (true Sharpe = 0)
    euler_mascheroni = 0.5772156649
    expected_max = (
        np.sqrt(sharpe_var) *
        ((1 - euler_mascheroni) * stats.norm.ppf(1 - 1/n_trials) +
         euler_mascheroni * stats.norm.ppf(1 - 1/(n_trials * np.e)))
    )

    # Deflate the selected Sharpe
    dsr = selected_sharpe - expected_max

    # Probabilistic Sharpe Ratio: probability that true Sharpe > 0
    sharpe_std = np.sqrt(
        (1 - skew * dsr + (kurtosis - 1) / 4 * dsr ** 2) / (num_trades - 1)
    )
    psr = stats.norm.cdf(dsr / sharpe_std) if sharpe_std > 0 else 0.5

    return {
        "dsr": float(dsr),
        "psr": float(psr),
        "expected_max_sharpe": float(expected_max),
        "is_significant": bool(psr > 0.95),
    }
```

The data scientist persona invokes this whenever multiple variants are present. The mentor doesn't compute it but knows what it means and uses it in the "is this strategy real" conversations.

## Bootstrap confidence intervals

Every metric reported by this skill comes with a confidence interval, computed via bootstrap resampling of the trades. The default is 95% CI from 1000 bootstrap samples.

```python
def bootstrap_metric(
    trades: pl.DataFrame,
    metric_func: callable,
    n_samples: int = 1000,
    ci_pct: float = 0.95,
    random_seed: int | None = 42,
) -> dict:
    """Compute a metric with bootstrap confidence interval.

    Resamples the trades with replacement n_samples times, computes the
    metric on each resample, and returns the point estimate, lower bound,
    and upper bound at the requested confidence level.
    """
    rng = np.random.default_rng(random_seed)
    n = len(trades)
    samples = []
    for _ in range(n_samples):
        idx = rng.integers(0, n, size=n)
        sample = trades[idx]
        samples.append(metric_func(sample))

    point = metric_func(trades)
    alpha = (1 - ci_pct) / 2
    lower = np.quantile(samples, alpha)
    upper = np.quantile(samples, 1 - alpha)

    return {
        "point": float(point),
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "ci_pct": ci_pct,
        "n_samples": n_samples,
    }
```

**The interpretation:** a Sharpe reported as `1.4 (95% CI: 0.6–2.1)` is honest about how much you know. The point estimate is 1.4, but the true value could plausibly be anywhere from 0.6 to 2.1 given the sample. If the lower bound includes zero, the metric is not significantly different from zero. If the upper bound is much larger than the lower bound, you have high uncertainty.

**Why bootstrap and not analytical CIs:** analytical confidence intervals require distributional assumptions (typically that returns are normal) that don't hold for trading strategy returns. Bootstrap is distribution-free and works on any sample. It's slower but for the sizes we deal with (hundreds to thousands of trades), the speed difference is irrelevant.

**The fixed seed:** the default seed is 42 so that running the same evaluation twice produces identical CIs. Reproducibility matters for the data scientist persona's claims.

## Drawdown analysis

Drawdown is computed from the equity curve, not from the trade log directly. The equity curve is the running cumulative net P&L, indexed by trade exit time (or by bar time, if a bar-level equity curve is available).

```python
def drawdown_analysis(equity_curve: pl.DataFrame) -> dict:
    """Compute drawdown statistics from an equity curve.

    Returns:
        max_dd_usd, max_dd_pct: depth of the worst drawdown
        max_dd_duration_days: longest time underwater
        max_dd_start, max_dd_end: when the worst drawdown happened
        ulcer_index: RMS of drawdown depths
        time_underwater_pct: fraction of time the strategy was in any drawdown
        recovery_time_days: time from max drawdown to next equity peak
        all_drawdowns: list of all drawdowns above a minimum threshold
    """
    eq = equity_curve["cum_pnl_usd_net"].to_numpy()
    times = equity_curve["timestamp"].to_numpy()

    running_max = np.maximum.accumulate(eq)
    dd = eq - running_max  # always <= 0

    max_dd_idx = np.argmin(dd)
    max_dd_usd = float(dd[max_dd_idx])
    max_dd_start_idx = np.argmax(eq[:max_dd_idx + 1])
    max_dd_start = times[max_dd_start_idx]
    max_dd_end = times[max_dd_idx]

    # Find recovery point: first time eq returns to running_max[max_dd_idx]
    target = running_max[max_dd_idx]
    after_max_dd = eq[max_dd_idx:]
    recovery_offsets = np.where(after_max_dd >= target)[0]
    if len(recovery_offsets) > 0:
        recovery_time_days = float((times[max_dd_idx + recovery_offsets[0]] - max_dd_end) / np.timedelta64(1, 'D'))
    else:
        recovery_time_days = None  # never recovered

    # Ulcer index
    ulcer_index = float(np.sqrt(np.mean(dd ** 2)))

    # Time underwater
    underwater_pct = float(np.mean(dd < 0) * 100)

    return {
        "max_dd_usd": max_dd_usd,
        "max_dd_pct": float(max_dd_usd / running_max[max_dd_idx] * 100) if running_max[max_dd_idx] > 0 else 0.0,
        "max_dd_duration_days": float((max_dd_end - max_dd_start) / np.timedelta64(1, 'D')),
        "max_dd_start": max_dd_start,
        "max_dd_end": max_dd_end,
        "ulcer_index": ulcer_index,
        "time_underwater_pct": underwater_pct,
        "recovery_time_days": recovery_time_days,
    }
```

## The one-page evaluation report

Every backtest run produces a `report.html` in `runs/<run_id>/`. The report is self-contained — embedded charts, no external dependencies — so it can be opened in a browser without the rest of the project being available.

**The layout:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Strategy: zn_macd_rev_v1                  Run: 2025-01-15           │
│  Period: 2020-01-01 to 2024-12-31          Symbol: ZN                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│           CALMAR: 2.8  (95% CI: 1.9 – 3.7)                           │
│                                                                      │
│   Total return: $47,320     Max drawdown: $4,200 (2.1% of equity)    │
│   Trades: 1,240             Time underwater: 31%                     │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│              [equity curve chart]                                    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│              [drawdown chart]                                        │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Return quality                                                      │
│    Calmar          2.8       (CI: 1.9 – 3.7)                         │
│    Sortino         2.1       (CI: 1.6 – 2.7)                         │
│    Sharpe          1.4       (CI: 0.9 – 1.9)                         │
│    Profit factor   1.7                                               │
│    Expectancy      $38.16    (CI: $24 – $52)                         │
│                                                                      │
│  Drawdown                                                            │
│    Max DD          $4,200 (2.1%)                                     │
│    Max DD duration 47 days                                           │
│    Recovery time   62 days                                           │
│    Ulcer index     0.84                                              │
│                                                                      │
│  Robustness                                                          │
│    Deflated Sharpe 0.9       (PSR: 87%)         ⚠ borderline         │
│    Trade count     1,240     (sufficient for inference)              │
│    OOS degradation -18%      (in-sample Sharpe 1.7 vs OOS 1.4)       │
│                                                                      │
│  Behavioral                                                          │
│    Trades/week     5.2                                               │
│    Avg hold time   2.3 hours                                         │
│    Win rate        62%                                               │
│    Max losing streak 7 trades (3 days)                               │
│    Largest loss    $480                                              │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Monthly returns heatmap                                             │
│  [12-column x N-row heatmap of monthly P&L]                          │
├──────────────────────────────────────────────────────────────────────┤
│  Trade distribution                                                  │
│  [histogram of per-trade P&L]                                        │
├──────────────────────────────────────────────────────────────────────┤
│  Notes                                                               │
│  - Deflated Sharpe is borderline (PSR 87%, threshold 95%). Treat    │
│    this result as suggestive rather than confirmed.                  │
│  - Time underwater is 31% — strategy spends nearly a third of its   │
│    life in drawdown. Verify you can sit through this.                │
│  - Largest single loss ($480) is within risk parameters but is 1.4x │
│    the average winner. Watch for tail behavior in live.              │
└──────────────────────────────────────────────────────────────────────┘
```

**The notes section is generated automatically.** The skill includes a set of rules that look at the metric values and write plain-English observations. Examples:

- If deflated Sharpe PSR < 0.95: "Deflated Sharpe is borderline (PSR X%, threshold 95%). Treat this result as suggestive rather than confirmed."
- If time underwater > 25%: "Time underwater is X% — strategy spends a significant fraction of its life in drawdown. Verify you can sit through this."
- If largest single loss > 2x average winner: "Largest single loss is Xx the average winner. Watch for tail behavior in live."
- If trade count < 100: "Trade count (X) is too low for confident metric estimation. Most numbers above are noisy."
- If max consecutive losses > 10: "Max consecutive losses is X. The strategy will test your conviction during streaks like this."
- If trades per week > 30: "Trades per week is X. This is a high-frequency strategy by retail standards. Verify the slippage and commission assumptions match reality at this trade volume."
- If recovery time > max DD duration: "Recovery from the worst drawdown took longer than the drawdown itself. The strategy is slow to bounce back."

The notes section is the closest the framework comes to having an opinion. It surfaces things the human should look at, in plain English, without requiring them to interpret the numbers themselves.

## Strategy comparison reports

When evaluating multiple variants of a strategy (or multiple different strategies), the skill produces a comparison report that shows the metrics side by side:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Strategy comparison: zn_macd_rev variants                           │
├──────────────────────────────────────────────────────────────────────┤
│                       v1       v2       v3       v4                  │
│  Calmar              2.8      3.1      2.4      1.9                  │
│  Calmar CI lower     1.9      2.0      1.6      1.1                  │
│  Calmar CI upper     3.7      4.2      3.2      2.7                  │
│  Sharpe              1.4      1.6      1.2      1.0                  │
│  Deflated Sharpe     0.9      1.0      0.7      0.5                  │
│  PSR                 87%      91%      78%      62%                  │
│  Max DD              $4.2k    $3.8k    $5.1k    $6.7k                │
│  Trades              1,240    1,180    1,420    1,610                │
│  Trades/week         5.2      5.0      6.0      6.8                  │
│  Largest loss        $480     $510     $620     $810                 │
└──────────────────────────────────────────────────────────────────────┘
```

**The deflation across variants is critical.** When four variants are compared, the deflated Sharpe of the best variant accounts for the fact that you tried four. The raw Sharpe of v2 (1.6) deflates to 1.0 because some of that 1.6 is the noise of having tried multiple variants. The PSR of v2 is 91%, which is below the 95% significance threshold — meaning even the best variant might be noise.

The mentor and data scientist personas use comparison reports for the "which one should I pick" conversation. The data scientist will note the deflation. The mentor will ask whether the variants represent meaningfully different ideas or whether they're cosmetic tweaks of the same idea (in which case the deflation is a red flag).

## Standing rules this skill enforces

1. **Calmar is the headline metric.** Sharpe is shown but not centered.
2. **Every metric has a confidence interval.** Point estimates without CIs are not allowed in any report.
3. **Deflated Sharpe is computed whenever multiple variants exist.** Refusing to compute it for "single-strategy" runs is fine; refusing to compute it after a parameter sweep is a bug.
4. **Behavioral metrics are reported prominently.** Trades per week, max consecutive losses, holding period, and largest single loss are not buried.
5. **Notes are generated automatically.** Plain-English observations about the strategy's behavior are part of every report.
6. **Reports are self-contained HTML.** No external CSS, no external JS, no external images. The report can be opened anywhere.
7. **Reports are reproducible.** Bootstrap CIs use a fixed seed by default. Running the same evaluation twice produces identical reports.

## When to invoke this skill

Load this skill when the task involves:

- Computing performance metrics from a trade log
- Generating a one-page evaluation report
- Comparing multiple strategies or variants
- Computing deflated Sharpe or other robustness metrics
- Designing new metrics or modifying existing ones
- Interpreting backtest results in conversation with the personas

Don't load this skill for:

- Generating the trade log itself (use `backtesting`)
- Charting equity curves and drawdowns (use `charting` — this skill calls into charting for the visual elements but doesn't own them)
- Position sizing (use `risk-management`)

## Open questions for build time

1. **Whether to include Monte Carlo trade reordering** as an additional robustness check. Bootstrap resampling is one form of robustness; reordering trades while preserving the trade outcomes is another. They answer slightly different questions. Defer until the basic metrics are working.
2. **Whether monthly returns should use calendar months or rolling 21-trading-day windows.** Calendar months are conventional and easy to interpret; rolling windows are more statistically robust. Default to calendar months for the heatmap; offer rolling as an option.
3. **The exact threshold for "borderline" deflated Sharpe.** 95% PSR is the conventional bar. The framework warns at 95% and below. Some practitioners use 90%. Defer to the conventional 95% unless the human prefers otherwise.
4. **Whether to compute the Probability of Backtest Overfitting (PBO).** The full Lopez de Prado PBO calculation requires combinatorial cross-validation, which is expensive. Worth it for important strategies; overkill for exploratory backtests. Make it opt-in via config.
