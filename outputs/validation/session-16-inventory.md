# Session 16 — Commit Inventory: de03c04
**Date:** 2026-04-17  
**Commit:** `de03c04` — "feat(eval): implement portfolio analytics suite and GUI builder"  
**Author:** IbbyTech  
**Date of commit:** 2026-04-17 04:30 PDT  
**Session:** 16 — Precautionary Code Review (Antigravity Sessions 11–13)

---

## Commit Scale

| Metric | Count |
|---|---|
| Files changed | 60 |
| Files newly added | 37 |
| Files modified | 24 |
| Lines inserted | 4,057 |
| Lines deleted | 2,636 |
| Net new lines | +1,421 |

---

## Module-to-LOC Table

### `src/trading_research/eval/` — 27 Python modules

| Module | Current LOC | Status in de03c04 | Notes |
|---|---|---|---|
| `__init__.py` | 0 | pre-existing | Empty |
| `stats.py` | 87 | modified (heavy) | 421 diff lines; DSR/PSR/Omega/Gain-to-Pain/UPI/MAR/Recovery |
| `bootstrap.py` | 222 | pre-existing | Not in commit diff |
| `drawdowns.py` | 51 | modified (heavy) | 299 diff lines |
| `distribution.py` | 67 | modified (heavy) | 283 diff lines |
| `monte_carlo.py` | 52 | modified (heavy) | 237 diff lines |
| `subperiod.py` | 34 | modified (heavy) | 213 diff lines |
| `trials.py` | 41 | modified | 162 diff lines; multi-test DSR registry |
| `summary.py` | 255 | pre-existing | Not in commit diff |
| `report.py` | 1,479 | modified | 143 lines added; single-strategy HTML report (15 sections) |
| `regimes.py` | 91 | new | Volatility/trend/calendar/Fed/econ regime tagging |
| `regime_metrics.py` | 83 | new | Per-regime metric breakdowns |
| `classifier.py` | 148 | new | Winner/loser classifier with purged k-fold |
| `clustering.py` | 78 | new | Trade clustering (UMAP + HDBSCAN) |
| `capital.py` | 61 | new | Capital efficiency analysis |
| `context.py` | 183 | pre-existing | Not in commit diff |
| `correlation.py` | 54 | new | Portfolio correlation analysis |
| `data_dictionary.py` | 200 | modified | 12 lines added |
| `data_dictionary_portfolio.py` | 21 | new | Portfolio-level column docs |
| `event_study.py` | 67 | new | Event study around entry/exit |
| `kelly.py` | 56 | new | Kelly criterion (reference, not used in sizing by default) |
| `meta_label.py` | 78 | new | Meta-labeling readout |
| `portfolio.py` | 76 | new | Multi-strategy portfolio loading |
| `portfolio_drawdown.py` | 81 | new | Portfolio drawdown attribution |
| `portfolio_report.py` | 147 | new | Portfolio HTML report generator |
| `shap_analysis.py` | 74 | new | SHAP per-trade analysis |
| `sizing.py` | 87 | new | Sizing comparison: equal/vol-target/risk-parity/inverse-DD |
| `pipeline_integrity.py` | 402 | pre-existing | Not in commit diff |

**eval/ total (all 27 modules):** ~4,557 LOC

### `src/trading_research/backtest/`

| Module | Current LOC | Status in de03c04 |
|---|---|---|
| `walkforward.py` | 134 | modified (heavy) — 395 diff lines |

### `src/trading_research/gui/` — all new in de03c04

| Module | Current LOC | Status in de03c04 |
|---|---|---|
| `__init__.py` | 1 | new |
| `app.py` | 112 | new |
| `callbacks.py` | 100 | new |
| `schemas.py` | 11 | new |

**gui/ total:** 224 LOC

### `src/trading_research/eval/templates/` — Jinja2 HTML

| Template | LOC | Status in de03c04 |
|---|---|---|
| `report_v1.html.j2` | 407 | pre-existing |
| `report_v2.html.j2` | 617 | pre-existing |
| `report_v3.html.j2` | 667 | new |
| `portfolio_report.html.j2` | 81 | new |

### Other modules touched

| Module | Diff | Notes |
|---|---|---|
| `src/trading_research/indicators/vwap.py` | +72 | Modified — caused 10 failing VWAP tests |
| `src/trading_research/indicators/features.py` | +10 | Minor modification |
| `src/trading_research/cli/main.py` | +33 | Minor modification |

---

## Test-to-Code Ratio by Subpackage

### eval/ subpackage

| Test file | LOC | Maps to source |
|---|---|---|
| `test_classifier.py` | 18 | `classifier.py` (148 LOC) |
| `test_clustering.py` | 16 | `clustering.py` (78 LOC) |
| `test_correlation.py` | 21 | `correlation.py` (54 LOC) |
| `test_distribution.py` | 23 | `distribution.py` (67 LOC) |
| `test_drawdowns.py` | 17 | `drawdowns.py` (51 LOC) |
| `test_event_study.py` | 13 | `event_study.py` (67 LOC) |
| `test_meta_label.py` | 14 | `meta_label.py` (78 LOC) |
| `test_monte_carlo.py` | 20 | `monte_carlo.py` (52 LOC) |
| `test_portfolio.py` | 37 | `portfolio.py` (76 LOC) |
| `test_regimes.py` | 19 | `regimes.py` (91 LOC) |
| `test_shap.py` | 17 | `shap_analysis.py` (74 LOC) |
| `test_sizing.py` | 22 | `sizing.py` (87 LOC) |
| `test_stats.py` | 57 | `stats.py` (87 LOC) |
| `test_subperiod.py` | 20 | `subperiod.py` (34 LOC) |
| `test_trials.py` | 13 | `trials.py` (41 LOC) |
| **Total test LOC** | **327** | vs. ~4,557 source LOC |

**eval/ test ratio: 327 / 4,557 = 7.2%**

⚠️ This ratio is low. Even accounting for the test files that predate de03c04
(bootstrap, context, pipeline_integrity, report, eval_summary, data_dictionary),
the new modules in de03c04 average ~18 test LOC per 85 source LOC.

### backtest/ subpackage

| Test file | LOC | Maps to source |
|---|---|---|
| `test_walkforward.py` | 163 | `walkforward.py` (134 LOC) |

**backtest/ ratio: 163 / 134 = 1.22 — healthy.**

### gui/ subpackage

| Test file | LOC | Maps to source |
|---|---|---|
| *(none)* | 0 | `app.py`, `callbacks.py`, `schemas.py`, `__init__.py` (224 LOC) |

**gui/ ratio: 0 / 224 = 0% — zero test coverage.**

---

## New Dependencies (pyproject.toml delta)

Six dependencies added in de03c04:

| Package | Version Pin | Purpose | Notes |
|---|---|---|---|
| `scipy` | `>=1.10` | Statistical functions used in eval/stats.py and related | Well-maintained; standard scientific Python |
| `scikit-learn` | `>=1.4` | ML — classifier (purged k-fold), clustering (StandardScaler), sizing | Well-maintained; wide API surface |
| `shap` | `>=0.44` | SHAP per-trade attribution in shap_analysis.py | Actively maintained; heavy dependency (pulls numba) |
| `lightgbm` | `>=4.3` | GBM classifier used in classifier.py | Well-maintained; large binary |
| `hdbscan` | `>=0.8.33` | Clustering in clustering.py | Slower-maintained; requires compiled extension |
| `umap-learn` | `>=0.5` | Dimensionality reduction in clustering.py | Actively maintained; large dependency |

**Combined weight:** These 6 packages add significant install size (compiled extensions for numba via shap, lightgbm native binaries, hdbscan extension). The `uv.lock` grew by 433 lines. All 6 are imported lazily by their respective modules — they don't slow startup unless those modules are called.

**Risk flags:**
- `hdbscan` — maintenance velocity has slowed; the HDBSCAN algorithm is also available via `scikit-learn >= 1.3` as `sklearn.cluster.HDBSCAN`. Duplication risk.
- `shap` — pulls `numba` as a transitive dep, which adds compilation time on first run. One test (`test_shap.py`) is already in the known failures list (though this is from the `test_stats.py::test_deflated_sharpe_ratio` TypeError, not shap itself). Monitor for numba JIT issues on Windows.

---

## Configs Added

| File | LOC | Purpose |
|---|---|---|
| `configs/broker_margins.yaml` | 58 | Retail broker margin requirements (TradeStation/IBKR) for instruments |
| `configs/calendars/fomc_dates.yaml` | 32 | FOMC announcement dates for regime tagging in regimes.py |

---

## Import Smoke Test Result

**Status: PASS**

All packages imported successfully:
- `trading_research.eval` (all 27 modules sampled)
- `trading_research.backtest` + `walkforward`
- `trading_research.gui` + `app`, `callbacks`, `schemas`

Note: A fresh `.venv` was created during this test (worktree had no prior env).
uv installed 68 packages in ~10s. No import errors, no missing dependencies.

---

## Summary

| Category | Count |
|---|---|
| Python source files (new in de03c04) | 21 |
| Python source files (modified in de03c04) | 9 |
| Test files (new) | 11 |
| Test files (modified) | 7 |
| Config files (new) | 2 |
| Jinja2 templates (new) | 2 |
| New Python dependencies | 6 |
| Import smoke test | PASS |
| GUI test coverage | 0% |
| eval/ test ratio | 7.2% |
| backtest/ test ratio | 122% |
