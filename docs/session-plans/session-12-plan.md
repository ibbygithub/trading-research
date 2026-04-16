# Session 12 — Reporting v3: Regime & ML Analytics

## Objective

Add regime tagging and ML-grounded analytics to the report so we can
answer "when does this strategy work and when doesn't it?" and "what
features actually separate winners from losers?" **No strategy changes
this session.** The ML analytics are purely descriptive — they analyze
the existing trade log, they do not alter the strategy.

By end of session:
- Every trade is tagged with volatility, trend, calendar, and Fed-cycle
  regimes.
- The report has a per-regime metric breakdown for each regime type.
- A winner/loser classifier is trained with purged k-fold cross-val and
  its feature importance (permutation-based) is displayed.
- SHAP values are computed per trade and the top contributors are
  embedded in the trade log tables.
- A meta-labeling readout shows whether a classifier could improve the
  base strategy by filtering signals.
- Event study: Fed days, CPI days, NFP days, and their impact on strategy
  behavior.
- Trade clustering: K-means or HDBSCAN on the entry-bar feature vector
  to surface natural trade types.

**Non-goals:** no new strategies, no meta-labeling used as a live filter
(that becomes a separate strategy in a later session), no portfolio work.

---

## Entry Criteria

- Session 11 complete: full risk-officer report, walk-forward runner,
  trials registry.
- Session 11 left the session 09 fixture strategy statistically
  characterized as broken — that's fine, the ML work in session 12
  doesn't need a good strategy to demonstrate value.

---

## Deliverables

### 1. Regime tagging module

**File:** `src/trading_research/eval/regimes.py`

Function `tag_regimes(trades, features, fed_calendar, econ_calendar)`
attaches regime tags to each trade:

- **Volatility regime** (per trade): based on ATR_14 percentile at entry
  over a trailing 252-session window. Tags: `vol_low` (< p33),
  `vol_mid` (p33–p66), `vol_high` (> p66).
- **Trend regime** (per trade): based on daily ADX at entry.
  Tags: `trend_weak` (< 20), `trend_moderate` (20–40), `trend_strong` (> 40).
- **Calendar regime** (per trade): day of week, week of month, quarter,
  year, month_of_year.
- **Fed-cycle regime** (per trade): distance in days to the nearest FOMC
  meeting. Tags: `fomc_today`, `fomc_tm1` (1 day before), `fomc_tp1`
  (1 day after), `fomc_week` (within 5 sessions), `fomc_far` (> 5 sessions).
- **Econ-release regime** (per trade): whether entry occurred on a day
  with a major US release (CPI, NFP, PCE, PPI, FOMC, retail sales, ISM).
  Requires an econ calendar data source — if none is available, this
  tag is optional and falls back to FOMC-only.

**Data dependencies:**
- FOMC meeting dates: stored in `data/calendars/fomc.csv`. If absent,
  generate from a hand-maintained list of meeting dates for 2010–2026
  committed to the repo under `configs/calendars/fomc_dates.yaml`.
- Econ releases: stored in `data/calendars/us_econ.csv`. If absent,
  the econ-release regime is skipped this session with a warning.

### 2. Per-regime metric breakdown

**File:** `src/trading_research/eval/regime_metrics.py`

Function `breakdown_by_regime(trades, regime_column)` returns a DataFrame
with one row per regime value and columns for count, total PnL, avg PnL,
win rate, Calmar, Sharpe (with CI), trades/week. This is reused for
every regime type.

### 3. Winner/loser classifier

**File:** `src/trading_research/eval/classifier.py`

Function `train_winner_classifier(trades, features, cv_folds=5, purge_bars=100)`:

1. Builds a feature matrix X from entry-bar context:
   - All context columns from session 10 (atr_14_pct_rank, daily_range_used_pct,
     vwap_distance_atr, htf_bias_strength, session_regime)
   - All regime tags from module 1
   - Raw indicator values at entry: RSI, MACD, MACD_hist, BB position,
     Donchian position, ADX
   - Entry hour, day of week, minute of day
2. Builds label y from trade outcome: 1 if PnL > 0 else 0 (scratches
   excluded from training).
3. Uses purged k-fold CV with the purge gap to prevent leakage from
   overlapping holding periods.
4. Trains a LightGBM or sklearn GradientBoostingClassifier.
5. Returns: trained model, per-fold accuracy and AUC with CIs,
   permutation importance for every feature, partial dependence data
   for the top 5 features.

**Hard rule from the data scientist persona:** the classifier's importance
table must be from **permutation importance on held-out folds**, not
from the model's built-in feature importance. Built-in importance is
biased toward high-cardinality features and will mislead. No exceptions.

### 4. SHAP values per trade

**File:** `src/trading_research/eval/shap_analysis.py`

Function `compute_shap_per_trade(model, X)` uses the `shap` library to
compute per-trade contribution values for every feature.

For each trade, identify the top 3 positive and top 3 negative SHAP
contributors. Attach these as columns to the enriched trade log:
`shap_top_pos_1`, `shap_top_pos_2`, `shap_top_pos_3`, `shap_top_neg_1`,
`shap_top_neg_2`, `shap_top_neg_3` (each as "feature_name:value"
strings).

In the report, the top 20 winners and top 20 losers tables gain two
new columns showing the top positive and top negative SHAP features
for each row.

### 5. Meta-labeling readout

**File:** `src/trading_research/eval/meta_label.py`

Function `evaluate_meta_labeling(trades, classifier_probs, threshold=0.5)`:

1. Takes the out-of-fold predicted probabilities from the winner
   classifier.
2. Simulates a filtered version of the strategy where only trades with
   predicted probability > threshold are taken.
3. Computes the filtered strategy's headline metrics (Calmar, Sharpe,
   trades/week, expectancy) with CIs via bootstrap.
4. Sweeps threshold from 0.3 to 0.9 in 0.05 steps and produces a curve
   of metric vs threshold.

**Interpretation line in the report:** "If the filtered Calmar beats
the unfiltered Calmar by more than the CI width, the base rule set is
leaving money on the table and meta-labeling is a candidate for a
follow-on strategy session. If it does not, the base rule set is
efficient given these features."

This is analysis, not a new strategy. The meta-labeled strategy does
not get deployed — it's a diagnostic on the base strategy's efficiency.

### 6. Event studies

**File:** `src/trading_research/eval/event_study.py`

Function `event_study(trades, event_dates, window_days=5)` — for each
event type (FOMC, CPI, NFP), computes:

- Average strategy P&L in the window [event - window, event + window]
- Win rate in that window vs outside
- Trade count in that window vs outside
- A chart showing cumulative P&L centered on event date, averaged over
  all instances of the event

Output: one chart and one summary table per event type.

### 7. Trade clustering

**File:** `src/trading_research/eval/clustering.py`

Function `cluster_trades(trades, n_clusters=None)`:

1. Takes the same feature matrix as the classifier.
2. Standardizes it.
3. Runs HDBSCAN (preferred) or K-means if HDBSCAN is unavailable.
4. Returns cluster labels per trade.
5. Produces a per-cluster summary: count, avg PnL, win rate, median
   hold time, top distinguishing features.

Interpretation in the report: clusters are natural trade types
("morning-reversal-quiet", "afternoon-trend-follow", etc.). If one
cluster has 80% of the losses, that's the filter candidate.

### 8. Report v3 additions

Create `report_v3.html.j2` with these additional sections:

25. **Regime breakdown — volatility** — metric table + bar chart.
26. **Regime breakdown — trend** — metric table + bar chart.
27. **Regime breakdown — calendar** — day of week, month of year metric
    heatmaps (reuses session 10 heatmap logic with PnL aggregation).
28. **Regime breakdown — Fed cycle** — metrics by FOMC proximity tag.
29. **Regime breakdown — econ releases** (if calendar available) —
    metrics by release type.
30. **Feature importance (permutation)** — ranked bar chart with CIs.
31. **Partial dependence plots** — for top 5 features.
32. **SHAP-enriched trade tables** — top 20 winners and losers with SHAP
    contributor columns.
33. **Meta-labeling readout** — threshold sweep curve and summary.
34. **Event studies** — FOMC, CPI, NFP window charts.
35. **Trade clusters** — cluster summary table and 2D projection (UMAP
    or t-SNE) colored by cluster.

### 9. Data dictionary update

Every regime tag, classifier metric, SHAP column, and event study
output gets a definition. Especially important: plain-English
explanation of SHAP values, permutation importance vs built-in, and
the meaning of the meta-labeling threshold sweep.

### 10. Tests

- `tests/test_regimes.py` — synthetic trades with hand-crafted ATR and
  ADX values, verify correct regime assignment.
- `tests/test_classifier.py` — synthetic feature matrix with a known
  linearly-separable signal, verify permutation importance ranks the
  signal feature highest.
- `tests/test_shap.py` — smoke test that SHAP values sum to model output
  (the SHAP additivity property).
- `tests/test_meta_label.py` — synthetic trades where a known filter
  should improve metrics, verify the readout detects it.
- `tests/test_event_study.py` — synthetic event window with known signal.
- `tests/test_clustering.py` — synthetic 3-cluster dataset, verify
  HDBSCAN recovers 3 clusters.
- Target: 340+ tests passing.

---

## Execution Order

1. Build `configs/calendars/fomc_dates.yaml` by hand (session 12 pre-work).
2. `eval/regimes.py` + tests.
3. `eval/regime_metrics.py` + wire into report.
4. `eval/classifier.py` + tests.
5. `eval/shap_analysis.py` + tests.
6. `eval/meta_label.py` + tests.
7. `eval/event_study.py` + tests.
8. `eval/clustering.py` + tests.
9. `report_v3.html.j2` + new sections wired in.
10. Run session 09 fixture through full v3 report.
11. Data dictionary update.
12. Work log.

---

## Success Criteria

- `uv run trading-research report zn_macd_pullback` produces a report
  with 35 sections.
- Classifier cross-val AUC has an honest CI.
- SHAP contributors are visible in the trade tables.
- Meta-labeling readout either shows clear efficiency gains (surprising,
  given session 09 fixture is broken) or confirms the base rule set is
  already extracting what it can from these features.
- All tests pass.
- Work log written.

---

## What Ibby Should See at the End

A report that tells him not just *what* the strategy does but *when
it works and why*. The meta-labeling readout and the SHAP-per-trade
tables are the parts he can hand to an outside AI agent and get a
genuine second opinion on. That's the goal.
