# Chapter 17 — The Trader's Desk Report

> **Chapter status:** [EXISTS] — the report generator and all sections
> documented here are live at commit `0472139`. The v2 report includes
> 24 sections spanning the Trader's Desk view (§§1–15) and the Risk
> Officer's view (§§16–24). This session added DSR and CI flags to the
> headline metrics, fold variance to the walk-forward section, DSR to
> the `format_with_ci` text output, and CI columns to the leaderboard.

---

## 17.0 What this chapter covers

The Trader's Desk Report is the platform's single-run summary artifact —
a self-contained HTML file that an operator opens in a browser to evaluate
whether a backtest result is worth promoting to the next stage of the
validation pipeline.

After reading this chapter you will:

- Know what each of the report's 24 sections shows and why it matters
- Be able to generate a report from the CLI or programmatically
- Understand which metrics carry bootstrap CIs and what the CI flags mean
- Know where Deflated Sharpe and fold variance appear and how to read them
- Be able to use the pipeline integrity audit to catch stale or
  contaminated inputs
- Understand the data dictionary that accompanies every report

This chapter is roughly 5 pages. It is referenced by Chapters 16
(Running a Single Backtest), 22 (Walk-Forward Validation), 23 (Deflated
Sharpe), and 32 (Trial Registry & Leaderboard).

---

## 17.1 What the report shows

The report is a single HTML file with 24 sections organised into two
views:

### Trader's Desk (§§1–15)

These sections answer "is this strategy worth pursuing?" from an
operator's perspective:

| Section | Title | What it shows |
|---------|-------|---------------|
| §1 | Header | Strategy ID, symbol, date range, feature set, git SHA, cost per round trip |
| §2 | Headline Metrics | Calmar (headline), Sharpe, **Deflated Sharpe**, Sortino, win rate, profit factor, expectancy, trades/week, max DD, max consec losses, MAE/MFE. CI-includes-zero flags on metrics with bootstrap CIs |
| §3 | Equity Curve & Drawdown | Cumulative P&L chart stacked with percentage drawdown |
| §4 | Top 20 Tables | Best and worst trades by dollar P&L and R-multiple |
| §5 | Time-in-Trade | Hold-time histograms by outcome and exit reason |
| §6 | Exit-Reason Breakdown | Table: count, total P&L, avg P&L, win rate, median hold, median MAE/MFE per exit reason |
| §7 | R-Multiple Distribution | Histogram with expectancy line |
| §8 | MAE / MFE Forensics | Scatter plots (MAE vs final, MFE vs final) plus gave-back-winners table |
| §9 | Rolling Expectancy | 20/50/100-trade rolling E[R] line chart |
| §10 | Streaks | Win and loss streak histograms |
| §11 | Heatmaps | Day-of-week × hour P&L and trade-count heatmaps (ET) |
| §12 | Calendar | Monthly P&L calendar table + per-year summary |
| §13 | Cost Sensitivity | Equity curves at 1×, 2×, 3× cost assumption |
| §14 | Market Context | Histograms of entry-bar ATR rank, VWAP distance, HTF bias |
| §15 | Provenance | Git SHA, Python version, feature set, full strategy YAML |

### Risk Officer (§§16–24)

These sections answer "should I *trust* this result?" with statistical
rigour:

| Section | Title | What it shows |
|---------|-------|---------------|
| §16 | Confidence Intervals | Same headline metrics as §2, with bootstrap 90% CIs |
| §17 | DSR / PSR | Deflated Sharpe, PSR vs SR=0 and SR=1, trial count, skewness, kurtosis |
| §18 | Extended Risk Metrics | MAR, Ulcer Index, UPI, Recovery Factor, Pain Ratio, Tail Ratio, Omega, Gain-to-Pain |
| §19 | Drawdown Forensics | Every drawdown episode >1% — start, trough, recovery, depth, duration |
| §20 | Time Underwater | Percentage of time below peak, longest run, histogram |
| §21 | Distribution Diagnostics | Skew, kurtosis, normality tests, Q-Q plot, ACF, return histogram |
| §22 | Subperiod Stability | Year-by-year metrics table + Calmar bar chart, degradation flag |
| §23 | Monte Carlo | 1,000-shuffle equity fan, drawdown and Calmar distributions |
| §24 | Walk-Forward | Per-fold OOS metrics table, fold variance table, OOS equity curve |

> *Why two views:* The Trader's Desk view is what the operator looks at
> to understand the *character* of a strategy — where it makes money,
> where it bleeds, how it holds, how it exits. The Risk Officer view is
> what the data scientist persona cares about — whether the numbers are
> statistically honest. Separating them lets the operator scan §§1–15
> quickly while the full rigour lives in §§16–24 for when promotion
> decisions need to be defended.

---

## 17.2 Generating a report

### CLI

```
uv run trading-research report <run_id> [--ts <timestamp>]
```

- `<run_id>` — the strategy directory name under `runs/`,
  e.g. `zn-macd-pullback-v1`.
- `--ts` — specific timestamp subdirectory. When omitted, the CLI
  auto-resolves to the **most recent** timestamp directory by
  lexicographic sort (which is chronological because timestamps use
  `YYYY-MM-DD-HH-MM` format).

The report writes three files to the run directory:

| File | Purpose |
|------|---------|
| `report.html` | Self-contained HTML, openable offline |
| `data_dictionary.md` | Markdown data dictionary for the run |

### Programmatic

```python
from trading_research.eval.report import generate_report

paths = generate_report(run_dir)
print(paths.report)           # Path to report.html
print(paths.data_dictionary)  # Path to data_dictionary.md
```

`generate_report` accepts a `version` parameter (`"v1"`, `"v2"`,
`"v3"`). The default is `"v2"` — the 24-section report with both
views. `"v3"` adds regime-conditional analysis, SHAP attribution, and
event studies; it requires additional dependencies (scikit-learn, SHAP,
umap-learn) and is used for deep forensics, not routine evaluation.

> *Why the default is v2, not v3:* v3 trains an ML classifier on the
> trade features, which adds 30–60 seconds of compute and pulls in
> heavyweight dependencies. For routine iteration — which is what the
> operator does 90% of the time — v2 gives the honest statistical
> picture without the wait. v3 is for deep dives on candidate strategies
> that have already passed the validation gate.

---

## 17.3 The pipeline integrity audit

Every report implicitly audits the input data pipeline by checking:

1. **Data freshness** — the features parquet's manifest records when it
   was last built. If the build timestamp is older than the most recent
   bar in the data, the report flags it.

2. **Manifest presence** — every parquet consumed by the backtest should
   have a `.manifest.json` sidecar. Missing manifests indicate files
   built outside the pipeline.

3. **Code commit at backtest time** — the report header records the git
   SHA at generation time. If the current HEAD has moved since the
   backtest was run (visible by comparing §15 provenance with the current
   commit), the report's results may not be reproducible from the current
   code.

The audit is implemented in
[`src/trading_research/eval/pipeline_integrity.py`](../../src/trading_research/eval/pipeline_integrity.py).
It does not block report generation — it surfaces warnings that the
operator can act on or consciously ignore.

> *Why this matters:* A backtest run on stale features can produce
> misleading results. If an indicator bug was fixed after the features
> were built, the backtest used the buggy indicator values. The audit
> makes this visible.

---

## 17.4 The data dictionary

Every `generate_report` call also writes a `data_dictionary.md` file to
the run directory. The data dictionary is a Markdown document that
describes every column in the trade log, every metric in the summary,
and every field in the equity curve — with types, units, and
computation notes.

The data dictionary is generated by
[`src/trading_research/eval/data_dictionary.py`](../../src/trading_research/eval/data_dictionary.py).
It is deterministic: the same run always produces the same dictionary
content (modulo the generation timestamp in the header).

The operator should read the data dictionary when:

- A metric name is unfamiliar (e.g. "What exactly is `pnl_r`?")
- A column's unit is ambiguous (e.g. "Is `mae_points` in ticks or
  points?")
- Sharing results with someone who hasn't read this manual

---

## 17.5 Headline statistical reporting

The headline metrics section (§2) and the `format_with_ci` text output
surface the platform's key statistical claims about a strategy. At v1.0,
these include:

### Point estimates (always shown)

- **Calmar [headline]** — annual return / max drawdown. The platform's
  primary risk-adjusted metric. See Chapter 19 §19.1.
- **Sharpe (annualised)** — reported but not centred. See §19.2.
- **Deflated Sharpe (DSR)** — adjusts raw Sharpe for the number of
  strategy variants tested. Computed from the trial registry. See
  Chapter 23.
- **Sortino (annualised)** — downside-only Sharpe. See §19.3.
- **Profit factor, expectancy, win rate** — see §19.4–§19.5.
- **Behavioural metrics** — trades/week, max consecutive losses,
  drawdown depth and duration. See Chapter 20.

### Bootstrap confidence intervals

Every CI-eligible metric (Sharpe, Calmar, Sortino, win rate, profit
factor, expectancy) carries a 90% bootstrap CI computed from 1,000
trade-level resamples. CIs appear:

- In the report §2 headline metrics: as a **CI-includes-zero flag**
  ("⚠ CI includes zero") rendered in red beneath the point estimate.
  This is the kill criterion — a Calmar CI that includes zero means
  the strategy is statistically indistinguishable from breakeven.

- In the report §16 CI section: as explicit `[lo, hi]` ranges
  alongside each metric.

- In the `format_with_ci` text output (printed by the `backtest` CLI):
  as `CI: [lo, hi]` inline with each row. When DSR has been computed,
  it appears as a separate line at the bottom.

- In the leaderboard: as `Calmar CI` and `Sharpe CI` columns showing
  `[lo, hi]` ranges per trial (when the trial was recorded with CI
  bounds).

### Deflated Sharpe in the header

DSR appears directly in §2 alongside raw Sharpe. This is deliberate:
the operator should never see a raw Sharpe without immediately seeing
the deflated version. If 30 variants were tested and the best has
raw Sharpe 1.8, the DSR might be 0.4 — that honest number belongs
in the headline, not buried in §17.

DSR is computed from:
- The trial registry (`runs/.trials.json`) — specifically, the count
  of trials matching the strategy's `trial_group`.
- The observed return moments (skewness, kurtosis) of the current
  backtest.
- The Bailey & Lopez de Prado (2014) formula via
  [`src/trading_research/eval/stats.py:deflated_sharpe_ratio`](../../src/trading_research/eval/stats.py).

### Fold variance in the walk-forward section

When a `walkforward.parquet` file exists in the run directory, §24
computes and displays a **fold variance table** showing, for each
metric (Calmar, Sharpe, win rate):

| Column | Meaning |
|--------|---------|
| Mean | Average across folds |
| Std | Standard deviation across folds |
| CV | Coefficient of variation (std / |mean|) — high CV = fragile edge |
| Min / Max | Range across folds |
| +ve Folds | Count of folds where the metric is positive |

High fold variance is the statistical signature of a strategy that
works in some market regimes but not others. A Calmar CV above 1.0
should be investigated; a positive-fold ratio below 60% should be
investigated harder.

### The `format_with_ci` text output

The `backtest` CLI prints a summary table after every run:

```
================================================================
  Backtest Performance Summary (with 90% bootstrap CI)
================================================================
  Total trades                          150
  Win rate                           55.0%  CI: [0.48, 0.62]
  ...
  Sharpe (ann.)                       1.20  CI: [0.40, 2.00]
  Calmar  [headline]                  0.80  CI: [0.10, 1.50]
  ...
----------------------------------------------------------------
  Deflated Sharpe (DSR)               0.72  (n_trials=5)
================================================================
```

When a CI includes zero, the row is flagged with
`⚠ CI includes zero` — a visual cue that the metric is not
statistically significant.

---

## 17.6 Related references

- **Chapter 16** — Running a Single Backtest: how the run directory and
  its artifacts are created.
- **Chapter 19** — Headline Metrics: detailed definitions of Calmar,
  Sharpe, Sortino, profit factor, expectancy, win rate.
- **Chapter 20** — Behavioural Metrics: trades/week, max consecutive
  losses, drawdown duration.
- **Chapter 21** — Bootstrap Confidence Intervals: the methodology
  behind the CIs.
- **Chapter 22** — Walk-Forward Validation: fold structure, fold
  variance, the validation gate.
- **Chapter 23** — Deflated Sharpe: the multiple-testing correction
  and the trial registry's role.
- **Chapter 32** — Trial Registry & Leaderboard: CI columns in the
  leaderboard table.
- [`src/trading_research/eval/report.py`](../../src/trading_research/eval/report.py)
  — report generator, all section builders.
- [`src/trading_research/eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py)
  — `format_with_ci` text output with DSR.
- [`src/trading_research/eval/templates/report_v2.html.j2`](../../src/trading_research/eval/templates/report_v2.html.j2)
  — Jinja2 template for the v2 report.
