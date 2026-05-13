# Chapter 22 — Walk-Forward Validation

> **Chapter status:** [EXISTS] — two implementations live in
> [`backtest/walkforward.py`](../../src/trading_research/backtest/walkforward.py):
> `run_walkforward` (purged, fixed-fold) and `run_rolling_walkforward`
> (rolling-fit). Both write a per-fold metrics parquet
> ([`write_walkforward_outputs`](../../src/trading_research/backtest/walkforward.py:574))
> and are surfaced in §24 of the Trader's Desk Report with the fold
> variance table added in session 46.

---

## 22.0 What this chapter covers

Walk-forward validation is the platform's primary defence against
in-sample optimism. A single train/test split tests one regime
transition; walk-forward tests many. After reading this chapter you
will:

- Know why walk-forward is the minimum standard and what it replaces
- Understand the difference between purged and rolling walk-forward,
  and when each is the correct tool
- Be able to size the gap and embargo for your timeframe and your
  strategy class
- Know how to read the per-fold metrics table and what fold variance
  means
- Be able to apply the gate criterion and recognise when the literal
  rule fails the spirit

This chapter is roughly 5 pages and is the deeper of Part V's two
teaching chapters. It is referenced by Chapters 17, 19, 21, 23, 31,
45, 46.

---

## 22.1 Why walk-forward

A standard backtest reports performance on a single contiguous window
of history. If that window happened to include the regime the strategy
was designed for, the result will be flattering. If the strategy's
designer looked at the window's chart while building the rules — and
he did, because that is how strategy design happens — the result will
be flattering in a deeper way: every parameter has been tuned, even
implicitly, against the very data being tested.

The honest version of "does this strategy work?" is: *does it work on
data it has never seen?* The cleanest answer would be to lock away a
hold-out set and never touch it until the strategy is finalised. In
practice the operator looks at every chart he loads, so even a
declared hold-out leaks information through his decisions. Walk-forward
is the practical compromise: split history into many adjacent windows,
evaluate on each one in turn, and report how the strategy behaves
across all of them. If the strategy survives multiple regime
transitions, it is more likely to survive the next one.

The mentor's framing: a strategy that prints Calmar 3.5 on a single
2018–2022 backtest and Calmar 0.4 on a 2023 walk-forward fold is not a
strategy with good 2018–2022 performance and bad 2023 performance. It
is a strategy that does not generalise. The walk-forward number is the
honest one.

> *What walk-forward does NOT replace:* the bootstrap (Chapter 21) and
> the deflated Sharpe (Chapter 23) address orthogonal questions —
> sample-size noise and multiple-testing bias. A strategy must pass
> all three layers to be promotion-eligible. Walk-forward is the
> *regime* test; the bootstrap is the *sample* test; deflation is the
> *trial count* test.

---

## 22.2 Purged walk-forward — `run_walkforward`

[`run_walkforward`](../../src/trading_research/backtest/walkforward.py:120)
is the default validator. It is appropriate for *rules-based*
strategies — strategies whose parameters are fixed in the YAML and not
fit from data. The flow:

1. Load the full feature dataset and join any higher timeframes.
2. Auto-fit regime filters on the *full* dataset (see §22.2.2 for the
   leakage implication).
3. Generate signals on the full dataset in one pass.
4. Split the dataset into N folds with `gap_bars` between adjacent
   folds and `embargo_bars` at the start of each test fold.
5. For each fold: run the backtest engine on the fold's signals only
   and record per-fold metrics.
6. Aggregate trades across folds into a single equity curve and
   compute the aggregated metrics.

The fold layout:

```
[fold_0_test][gap_bars][embargo_bars][fold_1_test][gap_bars][embargo_bars]...
```

Every test fold is evaluated on its own bars; the gap and embargo
bars are excluded entirely. The CLI:

```
uv run trading-research walkforward --strategy configs/strategies/<name>.yaml \
    --n-folds 10 --gap 100 --embargo 50
```

The defaults are 10 folds, `gap=100` bars, `embargo=50` bars. On a 16-
year 5-minute dataset that yields roughly 1.6 years per fold — enough
to span a regime transition, not so short that the per-fold metric is
unreadable.

### 22.2.1 When this is the right choice

`run_walkforward` is the right tool when:

- No strategy parameter is fit from data. Knobs are set in the YAML
  and do not change across folds.
- Regime filters use thresholds that are stable across the dataset,
  or are intentionally calibrated on the full history rather than
  per-fold.
- The operator wants a fast, low-variance pass to confirm a rules-
  based strategy is not a single-regime artefact.

### 22.2.2 The auto-fit caveat

Step 2 above is a real concession: when a YAML strategy declares
`regime_filter` blocks, `run_walkforward` calls `strategy.fit_filters(bars)`
on the full dataset before generating signals
([`walkforward.py:201`](../../src/trading_research/backtest/walkforward.py)).
This is convenient and statistically slightly leaky — the regime
filter's threshold is being chosen with knowledge of the test bars.

For strategies whose regime filter is *the* edge (volatility regime,
trend regime, anything where the threshold drives the trade selection)
this is the wrong tool. Use `run_rolling_walkforward` instead. The
auto-fit is acceptable for rules-based strategies where the regime
filter is an exclusion rule rather than the source of the alpha.

---

## 22.3 Rolling walk-forward — `run_rolling_walkforward`

[`run_rolling_walkforward`](../../src/trading_research/backtest/walkforward.py:327)
is the strict validator. For any strategy whose parameters or filter
thresholds are fit from data, this is the only honest tool. The flow:

1. Compute fold boundaries by calendar months. Default: 18 months of
   training, 6 months of testing, with `embargo_bars` bars between the
   end of training and the start of testing.
2. Per fold:
   a. Slice `train_bars` and `test_bars` by date.
   b. Fresh strategy instance per fold — ensures filter state does not
      leak between folds.
   c. `strategy.fit_filters(train_bars)` — fit any regime filters on
      training data ONLY.
   d. `strategy.generate_signals(test_bars, ...)` — generate signals on
      the test window with the fitted filter.
   e. Run the backtest engine on the test window's signals and record
      per-fold metrics, including the fitted threshold for audit.
3. Aggregate trades across folds; compute aggregated metrics.

This is the procedure described in Lopez de Prado's *Advances in
Financial Machine Learning* Chapter 7. The platform's implementation
follows the same purge/embargo discipline.

### 22.3.1 When this is the right choice

`run_rolling_walkforward` is required when:

- Any regime filter has a fitted threshold (volatility-regime
  percentile, trend strength cutoff, anything that depends on a
  rolling statistic of the data).
- The strategy uses an ML model whose parameters are trained per fold.
- The operator is preparing the gate-criterion run for promotion.

### 22.3.2 What it costs

Rolling walk-forward runs more compute than the purged variant — the
strategy is instantiated and fit once per fold rather than once total,
and signals are generated per fold rather than once. For a 5-minute
strategy on a 16-year dataset with 24 folds (18 months train, 6 months
test, rolling forward), expect roughly 2–3× the runtime of the purged
variant. Worth it.

---

## 22.4 Gap and embargo

The two boundary parameters do different jobs.

**`gap_bars`** is a hard buffer between adjacent test folds. Its job is
to prevent boundary leakage when a strategy has multi-bar holding
periods: a trade entered near the end of fold N might exit inside
fold N+1's evaluation window. The bars in the gap are not evaluated
in either fold.

**`embargo_bars`** is an additional buffer at the *start* of each test
fold (after the gap). For rules-based strategies the bars at the
beginning of a test fold are functionally identical to bars deep in
the fold, so the embargo is conservative; it costs little. For ML-
augmented strategies the embargo prevents autocorrelation in the
features from leaking information from the prior fold's predictions.

### 22.4.1 Sizing them

The right gap is larger than the strategy's typical holding period.
For an intraday EOD-flat strategy on 5-minute bars, all holds are
under one session — a `gap=100` is well over a day and is safe. For a
multi-day swing strategy on 60-minute bars, a typical hold of 12 bars
across two sessions means `gap=100` is barely enough; consider
`gap=200` or larger.

The right embargo depends on the strategy class. Rules-based
strategies tolerate small embargoes (50 bars is the default and is
adequate). ML strategies — even shallow ones — should use an embargo
on the order of the longest feature lookback in the model, because
features computed near the fold boundary will encode information that
was used to fit the previous fold's parameters.

### 22.4.2 What happens when they are too large

`run_walkforward` checks for this in
[`walkforward.py:254`](../../src/trading_research/backtest/walkforward.py):

```python
total_buffer_per_fold = gap_bars + embargo_bars
usable_bars = len(bars) - total_buffer_per_fold * (n_folds - 1)
if usable_bars < n_folds * 10:
    raise ValueError(...)
```

If `gap + embargo` consume too much of the dataset, the engine refuses
to run. The fix is to reduce the buffers or increase the data span,
not to silently shrink the folds. Errors loud, never quiet.

---

## 22.5 Per-fold and aggregated metrics

`WalkforwardResult` ([`walkforward.py:52`](../../src/trading_research/backtest/walkforward.py))
has four fields:

| Field | Contents |
|---|---|
| `per_fold_metrics` | DataFrame, one row per fold: `fold`, `test_start`, `trades`, `sharpe`, `calmar`, `win_rate`, etc. |
| `aggregated_metrics` | Dict, the summary across all folds' trades as a single equity curve |
| `aggregated_trades` | DataFrame, every test-fold trade concatenated and sorted by `exit_ts` |
| `aggregated_equity` | The cumulative net P&L of `aggregated_trades` |

`write_walkforward_outputs` ([`walkforward.py:574`](../../src/trading_research/backtest/walkforward.py))
writes `walkforward.parquet` (per-fold) and `walkforward_equity.parquet`
(aggregated). The report consumes both.

### 22.5.1 Reading the per-fold table

The CLI prints the per-fold table at the end of every walk-forward run
([`cli/main.py:863`](../../src/trading_research/cli/main.py)):

```
 Fold    Test start    Bars   Trades  WinRate   Sharpe   Calmar
    1    2018-03-01   25420       82    62.2%     1.4      1.8
    2    2018-09-01   25380       91    58.1%     0.9      0.6
    ...
```

What to look at:

- **Positive Calmar in the majority of folds.** This is the literal
  gate criterion. A strategy that wins 7 of 10 folds is robust; one
  that wins 5 of 10 is at the boundary; one that wins 3 of 10 is a
  fail regardless of the aggregated number.
- **Fold variance.** Wide variance is a flag even when the mean looks
  good. A strategy with per-fold Calmar of (3.0, -0.5, 2.5, -0.3, 2.1)
  has the same mean as one with (1.4, 1.4, 1.3, 1.5, 1.2) but is
  much less runnable.
- **Trend over folds.** Calmar that monotonically decays across folds
  is a regime-decay signature — the strategy was working when the
  regime that produced it was active and stopped working when the
  regime shifted. This is the most common failure pattern in retail
  mean reversion.

### 22.5.2 The fold variance table

Session 46 added a fold variance table to §24 of the report
([`eval/report.py`](../../src/trading_research/eval/report.py)). For
each metric it shows mean, std, CV (coefficient of variation),
min, max, and "positive folds" count.

CV is the most useful single number. A CV below 0.5 on Calmar is
remarkably stable. A CV above 1.0 means the per-fold values are
swinging wider than their average, which is a flag even if the mean
is good. The data-scientist persona reaches for this number every
time.

---

## 22.6 The validation gate criterion

The gate criterion from the standing rules:

> **OOS Calmar > 0 across a majority of folds, and aggregated Calmar
> > 0.1.**

The number 0.1 is the noise floor, not a target. A strategy hitting
exactly 0.1 has barely survived; the gate's job is to filter out
strategies that *can't even clear that*, not to certify trading
quality. The quality bar is set by the bootstrap CIs and DSR on top.

### 22.6.1 When the literal rule fails the spirit

The criterion is a starting point, not a contract. Real walk-forward
results have edge cases where the literal rule produces the wrong
verdict.

**Case 1 — five of ten folds positive, but the negative ones are
catastrophic.** A strategy with per-fold Calmars of (1.5, 2.0, -3.0,
1.5, -2.5, 2.0, 1.8, -2.8, 1.6, 2.1) has 6/10 positive and an
aggregate that might look OK, but no operator is going to ride out a
fold where the strategy is firing at -2.8 Calmar. The gate should
fail this even though the literal majority rule passes. Read the fold
distribution before you read the verdict.

**Case 2 — all folds positive but trade counts are tiny.** A strategy
with 8 trades per fold across 10 folds has 80 trades total. The
per-fold metrics are uninformatively noisy; whether each fold is
positive is essentially coin-flips around a small mean. The literal
gate may pass; the spirit fails because there is no sample. Demand a
trade-count floor (the gate's 100-trade minimum) before reading the
fold table.

**Case 3 — the latest fold is the negative one.** Per-fold Calmars of
(2.0, 1.8, 1.5, 1.4, 1.2, 0.8, 0.4, -0.2). Seven of eight positive,
aggregate is fine, literal rule passes — but the trajectory is
decay-to-zero. The strategy worked once and isn't working now. The
mentor's question: "what are you going to live-trade, the 2017 fold
or the 2024 fold?" Reject decay-pattern strategies regardless of
aggregate.

**Case 4 — fold variance dominates the result.** Per-fold Calmars of
(0.4, 0.5, 0.3, 0.5, 0.4) and aggregate 0.42. Literal rule passes
(all positive, aggregate > 0.1). The bootstrap CI on the aggregate
will almost certainly include zero because the per-fold mean is so
close to it. This is a strategy that *barely survives the test* and
will not survive live costs. Read this together with the bootstrap.

> *Why the rule is not absolute:* a hard pass/fail rule on a noisy
> multi-dimensional question always has edge cases where the wrong
> answer is the technically-correct answer. The walk-forward
> criterion in Chapter 46 is the *floor*; the data-scientist persona's
> CI reading and the mentor's regime-decay nose are the *ceiling*.
> Both must agree before the strategy crosses into paper.

---

## 22.7 Walk-forward report integration

§24 of the Trader's Desk Report consumes `walkforward.parquet` and
renders:

- The per-fold OOS metrics table (same columns as the CLI output).
- The fold variance table (mean, std, CV, min, max, positive-folds
  count for each metric).
- The OOS equity curve, drawn from `walkforward_equity.parquet`,
  stacked with the in-sample equity for visual comparison.

The variance table addition closed [PARTIAL] §22.7 in session 46. The
HTML template is in
[`eval/templates/report_v3.html.j2`](../../src/trading_research/eval/templates/report_v3.html.j2);
the renderer is `_build_walkforward_section` in
[`eval/report.py`](../../src/trading_research/eval/report.py).

---

## 22.8 Related references

### Code modules

- [`src/trading_research/backtest/walkforward.py`](../../src/trading_research/backtest/walkforward.py)
  — `run_walkforward`, `run_rolling_walkforward`,
  `write_walkforward_outputs`, `WalkforwardResult`.
- [`src/trading_research/eval/report.py`](../../src/trading_research/eval/report.py)
  — `_build_walkforward_section` (fold table + variance + equity).
- [`src/trading_research/cli/main.py`](../../src/trading_research/cli/main.py)
  — the `walkforward` subcommand at line 801.

### Other manual chapters

- **Chapter 12** — Composable Regime Filters: the `fit_filters`
  lifecycle that motivates `run_rolling_walkforward`.
- **Chapter 17** — Trader's Desk Report: §24 (per-fold table, fold
  variance, OOS equity).
- **Chapter 19** — Headline Metrics: the per-fold and aggregated
  Calmar/Sharpe/Sortino.
- **Chapter 21** — Bootstrap Confidence Intervals: the orthogonal
  sample-size layer.
- **Chapter 23** — Deflated Sharpe: the multiple-testing layer applied
  on top of walk-forward.
- **Chapter 31** — The Sweep Tool: when walk-forward replaces a
  sweep's optimisation step.
- **Chapter 45–46** — The Gate Workflow and Pass/Fail Criteria.

---

*End of Chapter 22. Next: Chapter 23 — Deflated Sharpe.*
