# Session 11 — Reporting v2: Risk Officer's View + Walk-Forward

## Objective

Add the statistical and robustness layer the session 10 report lacks, and
build a walk-forward runner that can actually validate a strategy over the
16-year dataset. **No strategy changes this session.** The goal is to
answer "is this edge real, and is it robust?" with honest numbers.

By end of session:
- `report.html` gets a Risk Officer section with bootstrap CIs on every
  headline metric, deflated Sharpe, PSR, and the full drawdown forensics.
- `uv run trading-research walkforward <config>` runs a purged k-fold
  walk-forward over the 16-year ZN dataset and produces a walk-forward
  summary embedded in the HTML report.
- Monte Carlo trade-order shuffle is computed and visualized.
- Subperiod stability analysis is computed and displayed.
- The data dictionary is updated with every new metric.

**Non-goals:** no regime tagging (session 12), no ML/SHAP (session 12),
no new strategies, no exit redesign.

---

## Entry Criteria

- Session 10 complete: `eval/report.py`, `eval/context.py`,
  `eval/pipeline_integrity.py`, `eval/data_dictionary.py` all exist and
  produce working output on the session 09 fixture.
- Replay app trade markers work on all four timeframes.
- `eval/bootstrap.py` from session 08 exists and provides a basic
  bootstrap primitive.

---

## Deliverables

### 1. Statistical metrics module

**File:** `src/trading_research/eval/stats.py`

Functions:

- `bootstrap_metric(values, stat_fn, n_iter=10_000, ci=0.95)` — returns
  (point_estimate, lo, hi). Reuse or extend the existing bootstrap module.
- `deflated_sharpe_ratio(returns, n_trials, skew, kurtosis)` — Lopez de
  Prado (2014). Takes the raw Sharpe, the number of strategy variants
  tested, and the higher moments of the return distribution.
- `probabilistic_sharpe_ratio(sharpe, n_obs, skew, kurtosis, sr_benchmark=0)` —
  returns the probability that the true Sharpe exceeds the benchmark.
- `mar_ratio(equity_series)` — CAGR / max DD.
- `ulcer_index(equity_series)` — RMS of percentage drawdowns.
- `ulcer_performance_index(equity_series, rf=0)` — (CAGR - rf) / UI.
- `recovery_factor(equity_series)` — net_profit / max_dd.
- `pain_ratio(equity_series)` — return / avg_dd.
- `tail_ratio(returns, pct=0.95)` — abs(p95) / abs(p5).
- `omega_ratio(returns, threshold=0)` — sum(gains above threshold) /
  sum(losses below threshold).
- `gain_to_pain_ratio(monthly_returns)` — sum(positive months) /
  abs(sum(negative months)).

All functions are pure and unit-tested with known-answer fixtures.

### 2. Return distribution diagnostics

**File:** `src/trading_research/eval/distribution.py`

Functions that compute and return plot-ready data for:
- Skew, kurtosis, excess kurtosis
- Jarque-Bera test statistic and p-value
- QQ plot coordinates vs normal distribution
- Autocorrelation of trade returns at lags 1–20 with Ljung-Box p-value
- Serial correlation of daily P&L at lags 1–20

The report section for this module must **flag loudly** when Jarque-Bera
rejects normality (which it will for mean-reversion strategies). The
flag says: "Return distribution is non-normal. Sharpe understates the
true risk. Use Sortino, Calmar, or MAR as the primary metric."

### 3. Drawdown forensics

**File:** `src/trading_research/eval/drawdowns.py`

Function `catalog_drawdowns(equity_series, threshold_pct=0.01)` returns
a DataFrame with one row per drawdown exceeding the threshold:

- start_date, trough_date, recovery_date (or NaT if unrecovered at end)
- depth_pct, depth_dollars
- duration_days, recovery_days, total_days
- trades_in_drawdown (count of trades opened during the drawdown window)
- trades_to_trough, trades_to_recovery

Function `time_underwater_series(equity_series)` returns a boolean
series indicating bars spent below a prior equity high, and a histogram
of contiguous underwater runs.

### 4. Subperiod stability

**File:** `src/trading_research/eval/subperiod.py`

Function `subperiod_analysis(trades, equity, splits='yearly')` — splits
the backtest by year (or configurable: thirds, halves, rolling 2y windows)
and recomputes headline metrics within each subperiod. Returns a DataFrame
suitable for a table and a bar chart.

The report section flags degradation: if the most recent subperiod has
metrics worse than the worst historical subperiod, surface a warning.

### 5. Monte Carlo trade-order shuffle

**File:** `src/trading_research/eval/monte_carlo.py`

Function `shuffle_trade_order(trades, n_iter=1000, seed=42)` — resamples
the trade order (preserving individual trade P&Ls) and recomputes the
equity curve. Returns the distribution of max drawdown, final P&L, and
Calmar across the shuffles.

Report section: fan chart of the shuffled equity curves with the actual
equity curve overlaid, plus histograms of max DD and Calmar across
shuffles with the actual values marked.

Interpretation shown in-report: "If the actual max DD is at the 90th
percentile of shuffle outcomes, the historical sequence was lucky and
the true expected DD is worse. If it's at the 10th percentile, the
historical sequence was unlucky."

### 6. Walk-forward runner

**File:** `src/trading_research/backtest/walkforward.py`

Function `run_walkforward(config_path, n_folds=10, gap_bars=100, embargo_bars=50)`
that:

1. Loads the strategy config.
2. Splits the 16-year dataset into `n_folds` contiguous folds.
3. For each fold k: train on folds 0..k-1, purge `gap_bars` between train
   and test, embargo `embargo_bars` after test to prevent leakage into the
   next fold, test on fold k, record results.
4. Since session 11's fixture strategy is rule-based with fixed parameters,
   "training" is a no-op for now — the walk-forward is purely a
   **subperiod robustness test** in this session. Parameter-tuning
   walk-forward (where train data actually selects params) comes with
   the first ML strategy.
5. Produces a walk-forward summary: per-fold Calmar, Sharpe, trade count,
   win rate, expectancy, and the aggregated out-of-sample equity curve.
6. Writes `runs/<run-id>/<ts>/walkforward.parquet` with per-fold metrics
   and `runs/<run-id>/<ts>/walkforward_equity.parquet` with the OOS
   equity curve.

CLI: `uv run trading-research walkforward <config>`.

### 7. Report v2 additions

Add these sections to `report_v1.html.j2`, creating `report_v2.html.j2`:

16. **Confidence intervals on headline metrics** — rerender section 2 with
    bootstrap CIs next to every point estimate.
17. **Probabilistic and deflated Sharpe** — raw Sharpe, deflated Sharpe
    (with trials count disclosed), PSR at benchmark 0 and benchmark 1.
18. **Extended risk metrics** — MAR, UI, UPI, Recovery Factor, Pain Ratio,
    Tail Ratio, Omega(0), Gain-to-Pain.
19. **Drawdown forensics table** — every DD > 1% with full columns.
20. **Time underwater histogram** — plus summary: % of time underwater,
    longest continuous underwater run in days.
21. **Return distribution diagnostics** — skew, kurtosis, JB test, QQ plot,
    autocorrelation plot, Ljung-Box summary.
22. **Subperiod stability table + bar chart** — year-by-year metrics with
    degradation flag.
23. **Monte Carlo shuffle** — fan chart, max DD histogram, Calmar histogram.
24. **Walk-forward results** — per-fold metrics table, OOS equity curve,
    comparison vs in-sample equity curve.

The `generate_report()` function gets a `version` parameter (default "v2")
and dispatches to the correct template.

### 8. Number of trials tracking

**File:** `src/trading_research/eval/trials.py`

Lightweight trials registry: every backtest run records itself into
`runs/.trials.json` with timestamp, strategy name, config hash, and
top-line Sharpe. The deflated Sharpe calculation reads this registry
to count how many variants have actually been tested against the same
instrument and uses that count as `n_trials`. This is how we make
deflated Sharpe honest instead of cosmetic.

Add a CLI flag `--trial-group <name>` to `backtest` and `walkforward`
so related variants can be grouped.

### 9. Data dictionary update

Every metric, table column, and statistical concept added this session
gets a definition in `data_dictionary.md`. Especially important:
deflated Sharpe, PSR, UPI, and the "n_trials" concept need plain-English
explanations aimed at a reader who may not know the Lopez de Prado canon.

### 10. Tests

- `tests/test_stats.py` — known-answer tests for every function in
  `eval/stats.py`. Deflated Sharpe gets tested against Lopez de Prado's
  published worked example.
- `tests/test_distribution.py` — JB test on a known-normal and known-fat-tailed
  fixture.
- `tests/test_drawdowns.py` — synthetic equity curve with three hand-crafted
  drawdowns, verify catalog matches.
- `tests/test_subperiod.py` — verify yearly split and metric recomputation.
- `tests/test_monte_carlo.py` — shuffle determinism with seed.
- `tests/test_walkforward.py` — synthetic 1000-bar dataset, verify purge
  and embargo exclude the correct bars.
- Total target: 300+ tests passing.

---

## Execution Order

1. `eval/stats.py` + tests.
2. `eval/distribution.py` + tests.
3. `eval/drawdowns.py` + tests.
4. `eval/subperiod.py` + tests.
5. `eval/monte_carlo.py` + tests.
6. `backtest/walkforward.py` + tests + CLI.
7. `eval/trials.py` + wire into backtest and walkforward CLIs.
8. Template `report_v2.html.j2` + new sections wired into `generate_report()`.
9. Run the session 09 fixture through the full v2 report end-to-end.
10. Data dictionary update.
11. Work log.

---

## Success Criteria

- `uv run trading-research report zn_macd_pullback` now produces a report
  with 24 sections including all risk, robustness, and walk-forward
  content.
- Deflated Sharpe shows a realistic number, not a cosmetic copy of raw
  Sharpe, and the trials count is accurate.
- Walk-forward runs cleanly over 16 years in < 5 minutes.
- All tests pass.
- Work log written.

---

## What Ibby Should See at the End

The session 09 fixture strategy is a bad strategy. By the end of session 11,
the report should make that unambiguous in honest statistical terms:
wide CIs, deflated Sharpe near zero, failed normality test, degraded
subperiods, poor walk-forward OOS. The report should **prove the
strategy is broken** with numbers, not opinions. That's the value of
the risk-officer view.
