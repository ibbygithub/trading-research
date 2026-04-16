# Session 10 — Reporting v1: Trader's Desk

## Objective

Build a self-contained HTML report generator that produces an MT4-style-but-better
per-run report, plus fix the replay app trade markers and add a pipeline integrity
report. **No strategy changes this session.** The existing `zn_macd_pullback`
backtest from session 09 serves as the fixture trade log for all reporting work.

By end of session:
- `uv run trading-research report <run-id>` writes a self-contained HTML report
  to `runs/<run-id>/<ts>/report.html` that opens offline in a browser and can
  be handed to an outside AI agent for review.
- A pipeline integrity report is generated alongside the HTML report as
  `runs/<run-id>/<ts>/pipeline_integrity.md`.
- The Dash replay app shows entry and exit markers correctly on 5m, and
  supports 15m / 60m / Daily timeframe toggles that resample and re-plot
  the trades in place.
- A data dictionary (`runs/<run-id>/<ts>/data_dictionary.md`) defines every
  trade-log column and every metric in the HTML report.
- All reports are tagged with git SHA and feature-set version.

**Explicit non-goals:** no exit redesign, no stop recalibration, no new
strategies, no walk-forward, no deflated Sharpe, no SHAP. Those belong to
sessions 11 and 12.

---

## Entry Criteria

- Session 09 complete: `runs/zn_macd_pullback/<ts>/trades.parquet` exists
  with ~11,887 trades over 2010-2026.
- `src/trading_research/eval/summary.py` and `eval/bootstrap.py` exist.
- `src/trading_research/replay/app.py` and `replay/callbacks.py` have
  trade-marker code wired in but are not rendering markers — the bug must
  be reproduced and fixed, not worked around.
- `data/features/zn_5m_base-v1.parquet` and `data/clean/zn_60m.parquet`
  are current.

---

## Deliverables

### 1. Report generator module

**File:** `src/trading_research/eval/report.py`

A single `generate_report(run_dir: Path) -> Path` function that reads the
trade log, equity series, summary JSON, and feature parquet from a run
directory and emits a standalone HTML file. All Plotly figures are
inlined via `fig.to_html(include_plotlyjs='inline', full_html=False)` and
assembled into one document by a Jinja2 template at
`src/trading_research/eval/templates/report_v1.html.j2`.

No Dash. No server. One file, openable offline.

The function must:
- Join the trade log with market-context columns from the 5m features parquet
  (see section 3 below).
- Compute all headline metrics and section data.
- Render the Jinja template.
- Write `report.html` to the run directory.
- Write `data_dictionary.md` alongside.
- Return the path to the HTML.

### 2. Report sections

The HTML report must contain these sections, in order:

1. **Header block**
   - Strategy name, run ID, run timestamp, git SHA, feature-set version,
     backtest date range, instrument, contract count, cost assumptions.

2. **Headline metrics table**
   - Calmar, Sharpe (raw annualized), Sortino, profit factor, expectancy
     in dollars, expectancy in R-multiples, trades/week, win rate,
     max consecutive losses, longest drawdown in trading days, max drawdown
     in dollars and in percent.
   - Each metric gets a point estimate only (no CIs this session — that's 11).

3. **Equity curve + underwater drawdown**
   - Two stacked Plotly charts sharing the x-axis: cumulative P&L on top,
     percent drawdown from running high on bottom.

4. **Top 20 tables** (three tabs or three stacked tables)
   - Top 20 winners by dollar P&L
   - Top 20 losers by dollar P&L
   - Top 20 by R-multiple (positive and negative)
   - Each table shows: entry_time, exit_time, side, entry_price, exit_price,
     pnl_dollars, pnl_r, hold_bars, hold_minutes, exit_reason, mae_r, mfe_r.

5. **Time-in-trade analysis**
   - Hold-time histogram in bars and in minutes
   - Hold-time distribution split by outcome (winners / losers / scratches)
   - Hold-time distribution split by exit reason (signal / stop / target / EOD)
   - Time-to-MAE histogram (bars from entry until trade hit its worst point)
   - Time-to-MFE histogram (bars from entry until trade hit its best point)

6. **Exit-reason breakdown table**
   - For each of {signal, stop, target, EOD}:
     count, total PnL, avg PnL, win rate, median hold bars, median MAE_R,
     median MFE_R.

7. **R-multiple distribution**
   - Histogram of pnl / initial_risk_dollars per trade.
   - Expectancy in R printed prominently.

8. **MAE / MFE forensics**
   - Scatter: MAE_R (x) vs final PnL_R (y), colored by outcome.
   - Scatter: MFE_R (x) vs final PnL_R (y), colored by outcome.
   - Table: trades where MFE_R > 1.0 but closed at a loss ("gave back" table).

9. **Rolling expectancy**
   - Three line charts: 20-trade, 50-trade, 100-trade rolling expectancy in R.

10. **Streak distributions**
    - Longest winning streak, longest losing streak, distribution histograms
      of streak lengths.

11. **Day-of-week × hour-of-day heatmaps**
    - Two heatmaps side by side: one for total PnL, one for trade count.
    - Hours in America/New_York. Day-of-week Monday–Friday.
    - This is the "best day / best hour to trade" view.

12. **Per-month and per-year P&L tables**
    - Calendar-style monthly table (years as rows, months as columns,
      totals at right and bottom).
    - Per-year summary: trades, pnl, max_dd, trades/week, win rate.

13. **Cost sensitivity sweep**
    - Re-run the P&L accumulation at 1×, 2×, 3× the cost-per-trade
      assumption and show three equity curves overlaid.
    - Table: Calmar, Sharpe, expectancy at each cost level.

14. **Market context at entry** (from the feature join in section 3)
    - ATR_14 percentile at entry — histogram
    - Daily range used at entry — histogram
    - Distance from session VWAP at entry (in ATRs) — histogram
    - HTF bias strength at entry — histogram
    - Bar-of-day regime tag counts (Asia / London / NY pre-open / NY RTH /
      NY close / overnight) with per-regime P&L bars

15. **Run provenance footer**
    - Git SHA, Python version, package versions, feature-set manifest hash,
      config YAML verbatim.

### 3. Market-context join

**File:** `src/trading_research/eval/context.py`

Function `join_entry_context(trades: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame`
that looks up each trade's entry bar in the features parquet and attaches:

- `atr_14_pct_rank_252` — 252-session rolling percentile of ATR at entry
- `daily_range_used_pct` — (entry_price - daily_open) / daily_range_so_far
- `vwap_distance_atr` — (close - vwap_session) / atr_14
- `htf_bias_strength` — absolute value of the 60m MACD histogram at entry
- `session_regime` — categorical tag based on entry_time-of-day in ET:
  - Asia: 18:00–03:00
  - London: 03:00–08:00
  - NY pre-open: 08:00–09:30
  - NY RTH: 09:30–16:00
  - NY close: 16:00–17:00
  - Overnight: 17:00–18:00

All computations use only data available at entry time. Verify with a
unit test.

### 4. Pipeline integrity report

**File:** `src/trading_research/eval/pipeline_integrity.py`

Function `generate_pipeline_integrity_report(run_dir: Path) -> Path`
that writes a Markdown document with:

- Bar counts per session across the backtest date range, flagging any
  session with count > 2σ from the mean.
- HTF merge audit: sample 100 random entry bars, for each one verify that
  `htf_bias_60m` at that bar equals the MACD histogram computed on the
  *previous closed* 60m bar (shift(1)). Report pass/fail.
- Indicator look-ahead spot-checks: for RSI, MACD, ATR, Bollinger, VWAP,
  sample 20 random bars each, recompute the indicator using only data
  through bar T, and assert equality with the stored value.
- Feature-set manifest diff: compare the manifest the backtest consumed
  against the current `configs/featuresets/base-v1.yaml`. Report any drift.
- Trade-date boundary check: for every trade, verify that entry_time and
  exit_time fall within the same trade date (CME trade-date convention,
  +6h ET offset) unless exit_reason indicates a cross-session pair trade.

Output path: `runs/<run-id>/<ts>/pipeline_integrity.md`.

### 5. Data dictionary generator

**File:** `src/trading_research/eval/data_dictionary.py`

Function `generate_data_dictionary(run_dir: Path) -> Path` that writes
`data_dictionary.md` defining:

- Every column in the enriched trade log (the trade log after the
  market-context join). For each column: name, dtype, units, definition,
  computation formula or source.
- Every metric in the HTML report. For each: name, formula, units,
  interpretation, caveats.
- The data dictionary is static content maintained in code (a dict of
  definitions) rendered to Markdown. When new fields are added to the
  trade log in future sessions, the dictionary must be updated in the
  same PR.

### 6. Replay marker fix + timeframe toggles

**Files to modify:**
- `src/trading_research/replay/callbacks.py`
- `src/trading_research/replay/charts.py`
- `src/trading_research/replay/layout.py`
- `src/trading_research/replay/data.py`

Steps:

1. **Reproduce the bug.** Launch the replay app with the session 09 run
   loaded. Confirm trade markers do not render on the 5m chart. Capture
   the exact symptom (no scatter trace? trace present but invisible?
   wrong coordinates?).
2. **Fix it.** Most likely causes: marker timestamps not tz-aligned with
   chart x-axis; marker trace added before chart layout so it's hidden;
   marker `y` values using the wrong price field.
3. **Add timeframe toggle.** The layout currently shows only 5m. Add a
   dropdown or radio selector with {5m, 15m, 60m, Daily}. On change,
   `callbacks.py` resamples the CLEAN 1m bars (or loads the pre-resampled
   CLEAN parquet) and re-plots. Trade entry and exit markers must
   re-project onto the chosen timeframe: entry marker lands on the
   bar that contains the entry timestamp; exit marker lands on the
   bar that contains the exit timestamp. If a trade opens and closes
   within a single bar on the daily view, stack both markers on that
   bar with distinct symbols.
4. **Verify visually.** Screenshot the 5m, 15m, 60m, and Daily views
   each showing markers for at least one real session 09 trade. Save
   screenshots to `outputs/session-10-verification/`.

### 7. CLI command

Add a new subcommand to `src/trading_research/cli.py`:

```
uv run trading-research report <run-id> [--ts <timestamp>]
```

If `--ts` is omitted, use the latest run under `runs/<run-id>/`.
The command calls `generate_report()`, `generate_pipeline_integrity_report()`,
and `generate_data_dictionary()` in that order and prints the three
output paths.

### 8. Tests

- `tests/test_report.py` — smoke test that runs `generate_report()` on
  a tiny synthetic trade log and confirms the HTML file is created,
  is non-empty, and contains all 15 section anchors.
- `tests/test_context_join.py` — unit test for `join_entry_context()`
  covering the six context columns.
- `tests/test_pipeline_integrity.py` — unit test for HTF shift(1) audit
  logic on a synthetic dataset with a known violation (must fail) and
  a clean dataset (must pass).
- `tests/test_data_dictionary.py` — verify every column in
  `TRADE_SCHEMA` plus every added context column is documented.
- Total test suite must remain green. Target: 265+ tests passing.

---

## Execution Order

1. Reproduce the replay marker bug first. Document the symptom.
2. Build `context.py` and its test.
3. Build `report.py` skeleton with the Jinja template and section 1 (header)
   and section 2 (headline metrics) only. Run it end-to-end on the
   session 09 trade log. Verify the HTML opens in a browser.
4. Add sections 3–15 one at a time, running the generator after each.
   Keep the feedback loop tight.
5. Build `pipeline_integrity.py`.
6. Build `data_dictionary.py`.
7. Wire all three into the `report` CLI subcommand.
8. Fix the replay marker bug.
9. Add the timeframe toggle.
10. Capture verification screenshots.
11. Run the full test suite.
12. Write the session 10 work log.

---

## Success Criteria

- `uv run trading-research report zn_macd_pullback` produces three files
  and exits 0.
- The HTML report is < 10 MB, opens offline, has all 15 sections, and
  is legible without an internet connection.
- The pipeline integrity report runs clean on the session 09 data, or
  identifies specific issues that explain a known concern.
- Replay app shows trade markers correctly on all four timeframes,
  verified by screenshot.
- All 265+ tests pass.
- Work log written to `outputs/work-log/2026-MM-DD-HH-MM-session-10-summary.md`.

---

## What Ibby Should See at the End

Open `runs/zn_macd_pullback/<latest>/report.html` in a browser, scroll
through 15 sections of descriptive analytics, close it, and say
"okay, now I have a report I can hand to someone."
