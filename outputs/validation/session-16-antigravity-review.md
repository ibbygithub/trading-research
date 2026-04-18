# Session 16 — Antigravity Code Review: main@de03c04
**Date:** 2026-04-18  
**Reviewer:** Claude Code (Sonnet — mechanical pass; Opus — architectural verdict)  
**Commit:** `de03c04` — "feat(eval): implement portfolio analytics suite and GUI builder"  
**Session branch:** `session/16-antigravity-review`  
**Import smoke test:** PASS (all modules import cleanly)

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ✓ | Clean — no structural red flags |
| ⚠️ | Has-questions — flagged issue, needs follow-up or explanation |
| 🚫 | Blocking — broken behavior, leakage risk, or import failure |

---

## File-by-File Review Table

### `src/trading_research/eval/`

| File | LOC | Has Tests | Status | Notes |
|---|---|---|---|---|
| `__init__.py` | 0 | — | ✓ | Empty |
| `stats.py` | 87 | ✓ (failing) | ⚠️ | No docstring; no type hints; duplicate `bootstrap_metric` vs `bootstrap.py`; DSR formula uses `st.norm.ppf` — flag Session 17. Test failing: API mismatch (test passes `np.ndarray` as `sharpe`, function expects `float`). |
| `bootstrap.py` | 222 | ✓ | ✓ | Pre-existing. Good docstring; type hints; CIs on Calmar, Sharpe, Sortino, win rate. Minor: treats each trade as a daily observation in `_sharpe()` — documented in comment but non-standard. Session 17 flag. |
| `summary.py` | 255 | ✓ | ✓ | Pre-existing. Good docstring; type hints; Calmar as headline metric; correct daily PnL aggregation. |
| `drawdowns.py` | 51 | ✓ | ⚠️ | No docstring; no type hints. Pure-Python loop through equity series — correct logic, O(n) pass. No structlog. |
| `distribution.py` | 67 | ✓ | ⚠️ | No docstring; no type hints. `autocorrelation_data()` returns numpy arrays in dict (not lists) — JSON serialization will silently fail downstream. |
| `monte_carlo.py` | 52 | ✓ (failing) | ⚠️ | No docstring; no type hints. Hardcoded `symbol="UNKNOWN"` at line 13. Test failing: `shuffle_trade_order()` was refactored to return dict; test still expects DataFrame with `.columns`. API mismatch. |
| `subperiod.py` | 34 | ✓ (failing) | ⚠️ | No docstring; no type hints. Hardcoded `symbol="UNKNOWN"` at line 21. Test failing: `subperiod_analysis()` returns `{"table": ..., "degradation_flag": ..., ...}` dict; test does `df.columns` and `len(df)` expecting a DataFrame. API mismatch. |
| `trials.py` | 41 | ✓ | ⚠️ | No docstring. Silent `except Exception: pass` at line 16 (JSON parse failure) and `except Exception: return 1` at line 41 (trials count failure). No structlog. If `runs/.trials.json` becomes corrupt, DSR silently degrades to 1-trial assumption. |
| `regimes.py` | 91 | ✓ | ✓ | Good docstring; type hints on public function; tz-aware timestamps. FOMC config gap is a config issue, not a code bug (see configs section). |
| `classifier.py` | 148 | ✓ | 🚫 | **BLOCKING.** Docstring claims "purged k-fold cross validation." Implementation: `if purge_bars > 0: pass` (lines 86-91). The purge is a stub — no observations are removed from training windows. Standard `KFold` is used without any temporal purge gap. For a mean-reversion strategy where the same regime can persist across hundreds of bars, overlapping labels between train and val are likely. Any AUC reported by this module is potentially optimistic. |
| `clustering.py` | 78 | ✓ | ⚠️ | Good docstring; type hints. `import umap` deferred inside function body (line 69) — should be at module level per project convention; suggests the author anticipated an import failure and buried it. `hdbscan` standalone package duplicates `sklearn.cluster.HDBSCAN` (available since sklearn 1.3). `X_num.fillna(X_num.median())` is a silent data manipulation — no log. |
| `capital.py` | 61 | — | ⚠️ | No docstring; no type hints. Default `path = Path("configs/broker_margins.yaml")` is a relative path that breaks if run from any directory other than project root. `starting_capital = 100000.0` hardcoded (line 33) — assumes $100k when project account is $25k. |
| `context.py` | 183 | ✓ | ✓ | Pre-existing. Not reviewed in depth (predates de03c04). |
| `correlation.py` | 54 | ✓ | ✓ | No docstring but simple utility. Pearson + Spearman + rolling correlation. Correct use of `fillna(0.0)` for missing trading days. |
| `data_dictionary.py` | 200 | ✓ | ✓ | Lookup table for 34 trade-log column definitions. Pre-existing with minor additions. |
| `data_dictionary_portfolio.py` | 21 | — | ✓ | Tiny portfolio column doc. Fine. |
| `event_study.py` | 67 | ✓ | ✓ | Good docstring; type hints; tz-aware. Correct distance-to-nearest-event logic. Averages PnL per event instance. |
| `kelly.py` | 56 | — | ⚠️ | Good docstring with mentor disclaimer ✓. Hardcoded `assumed_capital = 100000.0` at line 54 — Kelly sizing assumes $100k base when project is $25k. No type hints on `portfolio_kelly`. |
| `meta_label.py` | 78 | ✓ | ⚠️ | Good docstring; type hints. **Magic number:** `/ 16.0` divisor in Calmar approximation at lines 37 and 51 — no comment explaining what 16 represents (months? trading weeks? trading fortnight?). This Calmar approximation is not the same formula as in `summary.py` and `stats.py`. |
| `portfolio.py` | 76 | ✓ | ⚠️ | No docstring; no type hints on `load_portfolio`. Line 65-66: `trades.groupby(pd.to_datetime(trades["exit_ts"]).dt.date)["net_pnl_usd"].sum()` strips timezone via `.dt.date`, then `pd.DatetimeIndex(daily_pnl.index)` creates naive datetime index. Violates project tz-aware standard. Downstream: `combined_equity` has naive index. |
| `portfolio_drawdown.py` | 81 | — | ✓ | No docstring; no type hints. Logic correct: contiguous drawdown grouping, attribution per strategy. |
| `portfolio_report.py` | 147 | — | ✓ | No docstring; no type hints. Assembles sections and renders to portfolio Jinja2 template. Consistent with `report.py` pattern. |
| `regime_metrics.py` | 83 | ✓ | ✓ | No docstring; no type hints. Per-regime metric breakdowns — straightforward groupby aggregation. |
| `report.py` | 1,479 | ✓ | ✓ | Pre-existing with 143 lines added. Large but well-structured: 15+ sections, Plotly inline, three template versions (v1/v2/v3). No look-ahead visible at structural level. |
| `shap_analysis.py` | 74 | ✓ | ⚠️ | Good docstring; type hints. `hasattr(model, "booster_")` is fragile — depends on LightGBM internal attribute name. If LightGBM changes this attribute, code silently falls to the generic `shap.Explainer` path which may behave differently. |
| `sizing.py` | 87 | ✓ | ✓ | No docstring; no type hints. `.shift(1)` on rolling std is correctly documented (line 23 comment). Honest note that risk parity is "naive approximation." |
| `pipeline_integrity.py` | 402 | ✓ | ⚠️ | Pre-existing. Good docstring; type hints; pathlib ✓. Two issues: (a) Line 176: `feat.index.get_loc(ts, method="nearest")` — deprecated in pandas 2.0, will raise `FutureWarning` or `TypeError` on pandas ≥2.0. Should use `feat.index.get_indexer([ts], method="nearest")[0]`. (b) Line 356 comment: "Drift check: visual inspection required — automated diff deferred to Session 11." Session 11 shipped without completing this. The manifest diff section is structurally a stub. |

---

### `src/trading_research/backtest/walkforward.py`

| File | LOC | Has Tests | Status | Notes |
|---|---|---|---|---|
| `walkforward.py` | 134 | ✓ | ⚠️ | No docstring; type hints present (`Optional`). **Three findings:** (1) `gap_bars` and `embargo_bars` parameters defined in function signature (lines 24-25) but never used in the implementation — silently ignored. (2) Line 109: `BacktestEngine(bt_config, inst).run(bars.iloc[:1], signals_df.iloc[:1])` — creates a dummy 1-bar run just to get a `BacktestResult` object, then overwrites `trades` and `equity_curve`. Fragile hack around the dataclass API. (3) `signals_df = mod.generate_signals(bars, ...)` generates signals on the *full* dataset before folding — correct for rule-based strategies, potentially wrong for any future ML strategy that uses future data in signal generation. |

---

### `src/trading_research/gui/`

| File | LOC | Has Tests | Status | Notes |
|---|---|---|---|---|
| `__init__.py` | 1 | — | ✓ | Empty. |
| `app.py` | 112 | ✗ | ⚠️ | No docstring; no type hints; no structlog. Hardcoded `"ES"` instrument in dropdown (line 21) — ES is not a project instrument. Hardcoded `"mom-v2"` feature set (line 38) — this config does not exist. `import subprocess` in `callbacks.py` is unused. GUI runtime behavior not exercised this session (see Known Limitations). |
| `callbacks.py` | 100 | ✗ | ⚠️ | No docstring; no type hints. `import subprocess` unused (line 2). `STRATEGY_SCHEMAS` imported but never consumed — GUI does not render schema-driven parameter inputs, so strategy parameters (MACD fast/slow/signal, ATR multiplier) cannot be changed from the UI despite the schema existing. `data_root = Path("data")` (line 52) is relative — app must be launched from project root or fails silently to find data. Broad `except Exception` swallows all failures into the iframe. |
| `schemas.py` | 11 | ✗ | ⚠️ | Module docstring ✓. `STRATEGY_SCHEMAS` defines ZN MACD parameters but they are not wired into any Dash component IDs in `app.py`. The schema exists but is dead code in the current GUI. |

---

## Test Surface Review

### Summary of test files touched in de03c04

| Test File | LOC | Coverage Type | Notes |
|---|---|---|---|
| `test_classifier.py` | 18 | Smoke | Confirms function runs and returns expected keys. Does not verify AUC, purge behavior, or OOF quality. |
| `test_clustering.py` | 16 | Smoke | Confirms function runs. Does not verify cluster quality or UMAP embedding validity. |
| `test_correlation.py` | 21 | Behavioral | Verifies Pearson/Spearman values against known data. Reasonable. |
| `test_distribution.py` | 23 | Behavioral | Verifies JB test flags non-normal distributions. Reasonable. |
| `test_drawdowns.py` | 17 | Behavioral | Verifies drawdown depths on synthetic equity. Reasonable. |
| `test_event_study.py` | 13 | Smoke | Confirms function runs and returns expected structure. |
| `test_meta_label.py` | 14 | Smoke | Confirms function runs without error. |
| `test_monte_carlo.py` | 20 | **FAILING** | API mismatch — test expects DataFrame, function returns dict. |
| `test_portfolio.py` | 37 | Behavioral | Tests alignment and combined PnL arithmetic. Good behavioral coverage. |
| `test_regimes.py` | 19 | Behavioral | Verifies vol/trend regime tag values. Reasonable. |
| `test_shap.py` | 17 | Smoke | Confirms SHAP runs and returns DataFrame. |
| `test_sizing.py` | 22 | Behavioral | Checks sizing output shapes and direction. Reasonable. |
| `test_stats.py` | 57 | Mixed — **partially FAILING** | `test_deflated_sharpe_ratio` failing: passes `np.ndarray` as `sharpe` arg but function expects `float`. Other ratios tested behaviorally. |
| `test_subperiod.py` | 20 | **FAILING** | API mismatch — test expects DataFrame with `.columns`, function returns dict. |
| `test_trials.py` | 13 | Behavioral | Verifies trial counting and registry write/read. Reasonable. |
| `test_walkforward.py` | 163 | Mixed | 2 of 6 tests are real; 3 are `pass` stubs. Critically: `test_purge_gap_respected` and `test_fold_boundaries_non_overlapping` are both `pass` — exactly the behavior the function claims but doesn't implement. |

### Failing test root-cause summary

All 3 non-VWAP failures share the same pattern: **function API was refactored to return richer dict structures, but tests were not updated to match.**

| Test | Old expected return | Actual return |
|---|---|---|
| `test_monte_carlo.py::test_shuffle_trade_order` | DataFrame with `max_drawdown_usd` col | dict with `max_dd_dist`, `calmar_dist`, etc. |
| `test_stats.py::test_deflated_sharpe_ratio` | Called with `(returns_array, n_trials)` | Signature now `(sharpe, n_obs, n_trials, skewness, kurtosis)` |
| `test_subperiod.py::test_subperiod_analysis` | DataFrame with `period` col | dict `{"table": ..., "degradation_flag": ..., ...}` |

These are fixable in Session 17 as part of the rigor audit. The underlying functions appear structurally correct; the tests are stale.

---

## Template + HTML Review

**Scope:** `eval/templates/` — report_v1/v2/v3.html.j2, portfolio_report.html.j2

| Check | Result |
|---|---|
| `{% autoescape false %}` present? | ✓ No |
| `| safe` filters used? | Yes — 30+ occurrences across templates |
| `| safe` on user-controlled input? | ✓ No — all `| safe` filters inject Python-generated Plotly HTML or DataFrame HTML from trusted backtest code |
| Remote CDN asset loads (googleapis, jsdelivr, unpkg, cloudflare)? | ✓ None found |
| Self-contained / offline? | ✓ Yes — all CSS inline, Plotly charts embedded as inline JS |
| Jinja2 injection risk? | ✓ None at structural level |

**Templates are clean.** The `| safe` filter usage is a legitimate pattern for embedding pre-rendered Plotly figures; there is no user-controlled HTML injection pathway in this codebase.

---

## Config Review

### `configs/broker_margins.yaml`

| Check | Result |
|---|---|
| Unit consistency | ⚠️ Values are bare numbers — USD is implied but not documented |
| ES instrument present | ⚠️ ES is not a project instrument (project scope: ZN, 6A, 6C, 6N) |
| Values have source comment | ✓ "Last Updated: 2026-04-16 — Source: TradeStation & IBKR Official Margin Tables" |
| IBKR day-trade margins | ⚠️ IBKR day_trade_initial = overnight_initial for all instruments — this may not reflect IBKR's actual Reg-T or SPAN rules for intraday |

### `configs/calendars/fomc_dates.yaml`

| Check | Result |
|---|---|
| Coverage vs backtest window | 🚫 **CRITICAL GAP**: 2011-2017 explicitly mocked out with comment "# Mocked middle years". Only 2010 (8 dates), 2018 (4 dates), 2023-2025 (29 dates) are present. For a ZN strategy backtested 2010-2026, approximately 56 FOMC meetings (2011-2017) are missing. |
| Impact | `regimes.py::tag_regimes()` will classify all 2011-2017 ZN trades as `fomc_far` regardless of actual Fed meeting proximity. Fed meeting day and ±1 effects are the most important calendar events for Treasury futures. Any per-regime performance breakdown for this period is materially wrong. |
| Fix required | Full FOMC calendar for 2010-2026 must be populated. Source: Federal Reserve website. This is a data fix, not a code fix. |

---

## Duplicate-Idiom Findings

| Idiom | Location 1 | Location 2 | Resolution needed |
|---|---|---|---|
| Bootstrap metric computation | `stats.py::bootstrap_metric()` — generic, takes `stat_fn` callback | `bootstrap.py::bootstrap_summary()` — trade-specific, computes 6 metrics | Two bootstrap implementations, different interfaces. Unclear which is canonical. `stats.py` version is less documented and has no docstring. `bootstrap.py` version is the one called by the backtest pipeline. Consolidate. |
| Calmar approximation | `summary.py::_drawdown_stats()` — correct drawdown calc | `meta_label.py` lines 37/51 — `(pnl / 16.0) / max_dd` — magic divisor, no explanation | `meta_label.py` uses a non-standard Calmar approximation with an unexplained `/ 16.0` divisor. Not consistent with `summary.py`. |
| `symbol="UNKNOWN"` | `monte_carlo.py` line 13 | `subperiod.py` line 21 | Both create dummy `BacktestConfig` objects with hardcoded `"UNKNOWN"` symbol. Should accept symbol from the trades DataFrame or be made explicit. |
| Logger setup | Pre-existing modules: `structlog` configured via `utils/logging.py` | New Antigravity modules: no logging at all (no `structlog`, no `logging`) | 21 new modules produce zero log output. Silent failures in `trials.py` are the worst case. |

---

## Look-Ahead Surface Flag Pass

The session plan identified three known Antigravity handoff risks. Status:

| Risk | Finding |
|---|---|
| HTF aggregation in `resample_daily()` | `pipeline_integrity.py::_check_htf_merge()` exists and checks `htf_bias shift(1)` — the audit mechanism is in place. The actual data-level check requires running the report against a real dataset (deferred to Session 17). |
| Look-ahead under next-bar-open fill | No obvious `bar[t].close` used to compute `indicator[t]` found in the new eval modules. The eval modules consume pre-computed features from the FEATURES layer, not raw bars — they don't recompute indicators. Look-ahead risk lives in the `indicators/` and `data/` layers which predate this commit. Structural pass is clean. |
| Unadjusted ZN roll consumption | `walkforward.py` line 55: loads `{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet` — explicitly uses back-adjusted data. The GUI `callbacks.py` also routes to the same adjusted parquet. Unadjusted consumption is not present in the new code. |

---

## Architectural-Fit Verdict

*Written by Opus 4, quant-mentor voice.*

**Verdict: Adjacent but salvageable**

> This is a graft that thinks it's a cohesive extension, and that's the part that bothers me. The shape is right — DSR, PSR, regime tagging, walk-forward, meta-labeling, a sandbox GUI — these are the things a real desk builds once a strategy starts to look real. The skeleton matches what we actually want. But the load-bearing beams are painted cardboard. A walk-forward runner whose purge gap is `pass` isn't a walk-forward runner; it's a single train/test split wearing a lab coat. A regime tagger that's missing FOMC dates for 2011-2017 is mis-tagging seven years of a 2010-2026 ZN dataset — and ZN lives and dies on the Fed. The GUI hardcodes ES, which isn't even a project instrument. The bones are good. The wiring is theater. Before any of this touches a live P&L decision, the purge has to actually purge, the calendar has to actually cover the backtest window, and the tests that matter have to do more than `pass`.

*Data-scientist methodology assessment, Opus 4:*

> The evidence does not currently support calling any of this validated. (a) The purge stub combined with `pass`-body tests for `test_purge_gap_respected` and `test_fold_boundaries_non_overlapping` is a material leakage risk — the runner accepts `gap_bars` and `embargo_bars`, silently ignores them, and the test suite certifies the silence. Any classifier result produced by this pipeline is contaminated with overlapping-label leakage until proven otherwise. (b) The FOMC gap is material: regime-conditional statistics on 2011-2017 ZN are computed against an incomplete event set, so every "FOMC vs non-FOMC" metric in that window is mislabeled. (c) 7.2% test ratio, dominated by smoke tests, does not constitute validation. It demonstrates the modules import and execute. It says nothing about whether they compute the right numbers.

---

## Status Bucket Summary

| Bucket | Count | Files |
|---|---|---|
| ✓ clean | 14 | `__init__.py`, `bootstrap.py`, `summary.py`, `regimes.py`, `correlation.py`, `data_dictionary.py`, `data_dictionary_portfolio.py`, `event_study.py`, `context.py`, `portfolio_drawdown.py`, `portfolio_report.py`, `regime_metrics.py`, `sizing.py`, `gui/__init__.py` + all 4 templates |
| ⚠️ has-questions | 18 | `stats.py`, `drawdowns.py`, `distribution.py`, `monte_carlo.py`, `subperiod.py`, `trials.py`, `clustering.py`, `capital.py`, `kelly.py`, `meta_label.py`, `portfolio.py`, `shap_analysis.py`, `pipeline_integrity.py`, `walkforward.py`, `gui/app.py`, `gui/callbacks.py`, `gui/schemas.py`, `broker_margins.yaml` |
| 🚫 blocking | 2 | `classifier.py` (purge stub), `fomc_dates.yaml` (2011-2017 missing) |

**Totals:** 34 files reviewed. 14 clean, 18 has-questions, 2 blocking.

---

## Files Flagged for Session 17 Statistical-Rigor Audit

Ordered by priority. Session 17 should work this list in order.

| Priority | File | Check Required |
|---|---|---|
| 1 | `src/trading_research/eval/classifier.py` | Implement real purge gap. Verify AUC improvement over baseline is statistically significant after purge. |
| 2 | `src/trading_research/backtest/walkforward.py` | Wire `gap_bars` and `embargo_bars` into the fold implementation. Verify `test_purge_gap_respected` actually asserts something. |
| 3 | `configs/calendars/fomc_dates.yaml` | Populate complete 2010-2026 FOMC calendar. Re-run `regimes.py` regime analysis after fix. |
| 4 | `src/trading_research/eval/stats.py` | Verify DSR formula against Lopez de Prado (2014). Compare `deflated_sharpe_ratio()` output against reference implementation. Fix `test_deflated_sharpe_ratio` (API mismatch). |
| 5 | `src/trading_research/eval/bootstrap.py` | Verify that treating each trade as a daily observation in `_sharpe()` is appropriate. Compare bootstrap CIs against analytical CIs on a known distribution. |
| 6 | `tests/test_walkforward.py` | Replace the 3 `pass` stub tests with real behavioral assertions. Test that gap_bars > 0 actually excludes bars from training. |
| 7 | `tests/test_monte_carlo.py` | Fix API mismatch. Assert that total PnL is invariant across shuffles (conservation property). |
| 8 | `tests/test_subperiod.py` | Fix API mismatch. Assert degradation flag fires correctly on synthetic declining performance. |
| 9 | `src/trading_research/eval/meta_label.py` | Explain the `/ 16.0` divisor or replace with a proper Calmar computation using `summary.compute_summary`. |
| 10 | `src/trading_research/eval/trials.py` | Replace silent `except Exception: pass` with structlog error logging. Add test for corrupt registry behavior. |
| 11 | `src/trading_research/eval/portfolio.py` | Fix naive datetime index from `.dt.date` strip — preserve tz-awareness through `daily_pnl` construction. |
| 12 | `src/trading_research/eval/pipeline_integrity.py` | Fix deprecated `get_loc(method="nearest")` call (line 176). Complete manifest diff section (currently deferred with stale comment). |
| 13 | `src/trading_research/indicators/vwap.py` | Diagnose 10 failing VWAP KeyError tests. Interface change in de03c04 broke the test harness. |
| 14 | `src/trading_research/gui/callbacks.py` | Remove unused `import subprocess`. Wire `STRATEGY_SCHEMAS` into Dash component IDs so strategy parameters are actually adjustable from the GUI. |
| 15 | `src/trading_research/gui/app.py` | Remove `"ES"` and `"mom-v2"` hardcoded dead options. Instrument list should come from `instruments.yaml`. |
