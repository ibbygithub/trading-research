# Chapter 24 — Stationarity Suite

> **Chapter status:** [EXISTS] — three independent tests in
> [`stats/stationarity.py`](../../src/trading_research/stats/stationarity.py),
> CLI subcommand `stationarity`, design record at
> [`docs/design/stationarity-suite.md`](../design/stationarity-suite.md).

---

## 24.0 What this chapter covers

Mean-reversion strategies assume the underlying series returns to a
mean. That assumption can fail silently — the strategy keeps firing
signals long after the structure that produced the edge has decayed.
The stationarity suite is the periodic check that the structure is
still there. After reading this chapter you will:

- Know what each of the three tests detects and what it does not
- Be able to read the composite verdict (`TRADEABLE_MR`, `TOO_SLOW`,
  `NON_STATIONARY`, etc.) and trust it for a go/no-go decision
- Know how to run the suite and where its outputs go

This chapter is roughly 3 pages. It is referenced by Chapters 9, 14,
27, 45.

---

## 24.1 Why stationarity matters

A series is *stationary* if its statistical properties — mean,
variance, autocorrelation — are stable over time. A mean-reverting
series is stationary by construction: it has a long-run mean it
returns to. A trending series, or a random walk, is not stationary.

For mean-reversion strategies the implication is direct. If the
spread or indicator the strategy fades is genuinely stationary, the
historical edge is likely to persist. If it is non-stationary, the
backtest's mean reversions were artefacts of the particular window;
the strategy will fail in production when the series wanders away
from its sample mean.

The suite computes three independent diagnostics. None is decisive on
its own; the composite verdict combines them. Thresholds are recorded
in
[`stats/stationarity.py:31`](../../src/trading_research/stats/stationarity.py)
and are not to be tuned without a written justification.

---

## 24.2 ADF — Augmented Dickey-Fuller

[`adf_test`](../../src/trading_research/stats/stationarity.py:225)
wraps `statsmodels.tsa.stattools.adfuller`. The null hypothesis is
that the series has a *unit root* — it is non-stationary. Rejecting
the null is evidence the series is stationary. The reported `p_value`
is the probability of seeing the observed test statistic under the
null.

The interpretation thresholds:

| p-value | Verdict |
|---|---|
| < 0.01 | `STATIONARY (strong)` |
| < 0.05 | `STATIONARY (weak)` |
| ≥ 0.05 | `NON_STATIONARY` |

ADF is the formal hypothesis test in the suite. It is precise about
what it rejects (a unit root) and silent about what is going on
instead — a series can be ADF-stationary and still be useless for
trading if its reversion speed is wrong (see §24.4). ADF is the
necessary first gate; the other two tests describe the *character* of
the stationarity once ADF has passed.

> *Common ADF pitfall:* ADF assumes the residuals after differencing
> are roughly homoskedastic. Volatility-regime shifts break this
> assumption. A series that is "stationary in a quiet regime and
> trending in a volatile one" can produce inconsistent ADF results
> across windows. The walk-forward (Chapter 22) is the second layer
> that catches this.

---

## 24.3 Hurst exponent

The Hurst exponent characterises long-range memory of a series.
Computed via detrended fluctuation analysis (DFA) in
[`stats/stationarity.py`](../../src/trading_research/stats/stationarity.py)
(the R/S estimator was replaced with DFA in session 27 after the R/S
variant was found to mis-classify short-memory OU processes — see
the commit `940506c` rationale).

Reading H:

| H | Verdict |
|---|---|
| < 0.40 | `MEAN_REVERTING (strong)` |
| < 0.45 | `MEAN_REVERTING (weak)` |
| 0.45 – 0.55 | `RANDOM_WALK` |
| 0.55 – 0.60 | `TRENDING (weak)` |
| > 0.60 | `TRENDING (strong)` |

Hurst's role in the composite is informational, not gating (session-27
decision). DFA returns H ≈ 0.5 for any short-memory stationary AR(1)
process — including the OU spreads the project's strategies target —
so requiring H < 0.45 would block genuinely tradeable series. Hurst
*does* still block the composite when it reports `TRENDING`, because
trending behaviour contradicts ADF stationarity and the contradiction
is itself a flag.

> *Why DFA over R/S:* the R/S estimator is biased upward on short
> series. The platform's earlier R/S implementation reported H ≈ 0.55
> on series whose true H was 0.45–0.50, producing false `TRENDING`
> verdicts. DFA is well-behaved on the short windows the suite is
> typically run against.

---

## 24.4 Ornstein-Uhlenbeck half-life

The OU model fits the series as `dX_t = -β·(X_t - μ) dt + σ dW_t`. The
parameter β determines the reversion speed; the **half-life** is the
expected number of bars for the series to revert halfway back to the
mean:

```
half_life = ln(2) / β
```

The fit is OLS-based; the report is in
[`stats/stationarity.py`](../../src/trading_research/stats/stationarity.py).
The interpretation depends on the timeframe — a half-life that is
tradeable at 1-minute resolution is much too fast at 15-minute. The
defaults from
[`stationarity.py:43`](../../src/trading_research/stats/stationarity.py):

| Timeframe | Tradeable half-life range (bars) |
|---|---|
| 1m | 5 – 60 |
| 5m | 3 – 24 |
| 15m | 2 – 8 |

These bounds are overridable per-instrument via the `Instrument`
registry — an instrument can declare custom OU bounds via
`get_ou_bounds(timeframe)` and the interpreter prefers them.

The verdicts:

| Half-life | Verdict |
|---|---|
| Below lower bound | `TOO_FAST` — reversion completes before a tradeable entry can be set up |
| Within bounds | `TRADEABLE` |
| Above upper bound | `TOO_SLOW` — reversion is so slow the position must be held through too many opposing moves |

A series can be ADF-stationary, have a Hurst of 0.5, and still be
`TOO_SLOW` to trade. The OU half-life is the most directly
actionable of the three diagnostics.

> *When the OU estimate is untrustworthy:* fewer than 10 observations,
> or β estimated as non-positive (which the math allows but
> economically implies trending behaviour). The implementation returns
> `inf` or `nan` in these cases and the composite collapses to
> `RANDOM_WALK` or `TRENDING` accordingly.

---

## 24.5 The composite verdict

[`_composite_classification`](../../src/trading_research/stats/stationarity.py:177)
combines the three results into a single label per series and
timeframe. The decision tree, post session-27:

1. If ADF p-value ≥ 0.05 → `NON_STATIONARY`.
2. Else if Hurst > 0.55 → `INDETERMINATE` (contradiction with ADF).
3. Else if OU half-life below lower bound → `TOO_FAST`.
4. Else if OU half-life above upper bound → `TOO_SLOW`.
5. Else if OU in tradeable range → `TRADEABLE_MR`.
6. Else → `INDETERMINATE`.

Only `TRADEABLE_MR` is a green light for a fresh mean-reversion
deployment. `TOO_FAST` and `TOO_SLOW` are also stationary verdicts
but flag that the instrument-timeframe combination is structurally
wrong for the strategy. `NON_STATIONARY` and `INDETERMINATE` block.

The composite is the right number to consult before promoting a
strategy to paper. The per-test results are the right numbers to
consult when the composite gives an unexpected answer and the
operator needs to know which test is driving it.

---

## 24.6 The `stationarity` CLI command

```
uv run trading-research stationarity --symbol ZN \
    --start 2024-01-01 --end 2024-12-31 \
    --timeframes 1m,5m,15m
```

The CLI loads the CLEAN 1-minute parquet for the symbol, resamples to
the requested timeframes, runs all three tests on each, and writes
output to
`runs/stationarity/<SYMBOL>/<YYYY-MM-DD-HH-MM>/`:

- `results.parquet` — one row per (series, timeframe), columns for each
  test's result and the composite verdict.
- `summary.json` — instrument metadata, code version, data version,
  per-series composite labels.
- `report.md` — human-readable Markdown summary.

The CLI is the standard way to run the suite. Programmatic invocation
is available via `run_stationarity_suite` and `write_report` in
[`stats/stationarity.py`](../../src/trading_research/stats/stationarity.py)
for in-process use (e.g. inside a notebook or a research script).

> *When to re-run:* whenever data is refreshed for an instrument the
> operator is actively trading, and at minimum at the start of each
> month for any paper or live strategy. A `TRADEABLE_MR` verdict from
> six months ago is not evidence the instrument is still in the same
> regime today.

---

## 24.7 Related references

### Code modules

- [`src/trading_research/stats/stationarity.py`](../../src/trading_research/stats/stationarity.py)
  — the suite: `adf_test`, Hurst (DFA), OU half-life,
  `_composite_classification`, `run_stationarity_suite`,
  `write_report`.
- [`src/trading_research/cli/main.py`](../../src/trading_research/cli/main.py)
  — the `stationarity` subcommand at line 909.

### Design and references

- [`docs/design/stationarity-suite.md`](../design/stationarity-suite.md)
  — the design record with full threshold derivation.
- López de Prado, M. (2018). *Advances in Financial Machine Learning*,
  Wiley. Chapter 5 covers fractional differentiation and stationarity
  in the trading context.

### Other manual chapters

- **Chapter 9** — Strategy Design Principles: when to consult the
  stationarity suite during design.
- **Chapter 14** — The Backtest Engine: the engine does not enforce
  stationarity; the operator does, via this suite.
- **Chapter 27** — Regime Metrics: complementary diagnostic for
  splitting performance by regime label.
- **Chapter 45** — The Gate Workflow: stationarity check is part of
  the pre-gate checklist.

---

*End of Chapter 24. Next: Chapter 25 — Distribution Analysis.*
