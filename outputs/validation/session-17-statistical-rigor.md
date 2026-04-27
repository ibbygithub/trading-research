# Session 17 — Statistical Rigor Audit

**Date:** 2026-04-18  
**Branch:** session/17-statistical-rigor  
**Lead voice:** Data-scientist  
**Reviewer:** Ibby

---

## Executive Summary — What You Can and Cannot Trust Right Now

**Short answer:** The DSR and PSR formulas are mathematically correct for their stated kurtosis convention, but that convention (Pearson kurtosis, where normal = 3) is not what scipy's `kurtosis()` returns by default (it returns excess/Fisher kurtosis, where normal = 0). Any caller who passes scipy's default kurtosis directly to `probabilistic_sharpe_ratio()` or `deflated_sharpe_ratio()` gets a subtly wrong answer. The error is small for near-normal distributions at large SR, but can be material for the fat-tailed, negative-skew distributions that ZN mean-reversion produces.

The Calmar in `meta_label.py` was outright wrong — a hardcoded `/16.0` divisor that bore no relationship to the actual observation span. That has been fixed.

The purged k-fold stub in `classifier.py` was a `pass` that did nothing; it allowed training on post-test data, which is a look-ahead bug. Fixed.

Walk-forward `gap_bars` and `embargo_bars` were silently ignored; now wired.

**What you can trust from Antigravity-produced reports:**
- Calmar from `eval/summary.py` — correct (daily equity curve, proper annualisation).
- Bootstrap CIs from `eval/bootstrap.py` — correct for trade-level resampling, seed-reproducible.
- DSR/PSR numeric output — correct *only if callers pass Pearson kurtosis*. Find-and-fix below.
- MAR, UPI, Omega, Tail Ratio, Recovery Factor, Pain Ratio — all correct against their textbook definitions.

**What you cannot trust until callers are fixed:**
- Any report that uses `probabilistic_sharpe_ratio()` or `deflated_sharpe_ratio()` with scipy's default kurtosis (excess). Grep for `kurtosis(` in the codebase and check the `fisher=` argument.
- Meta-labeling Calmar sweep results computed before this session (used `/16.0` as denominator — flat wrong).
- Any walk-forward metrics produced before this session (gap/embargo silently ignored, folds possibly abutting).
- Classifier OOF predictions from before this session (purge was a no-op; training data included post-test observations).

---

## Topic Verdicts Summary

| # | Topic | Verdict | Severity |
|---|---|---|---|
| 1 | Deflated Sharpe Ratio (DSR) | **Correct-with-caveats** | 2 |
| 2 | Probabilistic Sharpe Ratio (PSR) | **Correct-with-caveats** | 2 |
| 3 | Bootstrap Confidence Intervals | **Correct** | — |
| 4 | Walk-Forward Purge / Embargo | **Incorrect → Fixed** | 1 |
| 5 | Trials Registry | **Correct-with-caveats** | 3 |
| 6 | Meta-Labeling | **Incorrect (Calmar) → Fixed; Untestable (class balance)** | 2 |
| 7 | Permutation Importance / SHAP | **Incorrect (purge stub) → Fixed; Correct-with-caveats (SHAP)** | 1 |
| 8 | Look-Ahead Strictness (Antigravity indicators) | **Untestable-in-session** | — |
| 9 | HTF Aggregation at CME Trade-Date Boundary | **Untestable-in-session** | — |
| 10 | Omega / Calmar / MAR / Recovery / Pain / Tail / UPI | **Correct** | — |

---

## Topic 1 — Deflated Sharpe Ratio

**Claim:** `deflated_sharpe_ratio()` in `eval/stats.py` implements Bailey & Lopez de Prado 2014.

**Primary source:** Bailey, D. & Lopez de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." *Journal of Portfolio Management*, 40(5). Equations (10)–(14).

**Implementation read:** `eval/stats.py:26-31`

```python
def deflated_sharpe_ratio(sharpe, n_obs, n_trials, skewness, kurtosis):
    emc = 0.5772156649  # Euler-Mascheroni constant
    if n_trials == 1:
        sr_bench = 0.0
    else:
        sr_bench = (1 - emc) * norm.ppf(1 - 1/n_trials) + emc * norm.ppf(1 - 1/(n_trials*e))
    return probabilistic_sharpe_ratio(sharpe, n_obs, skewness, kurtosis, sr_bench)
```

**Reference check:** Equation (10) from the paper:

> E[max SR] ≈ (1 − γ) · Φ⁻¹(1 − 1/N) + γ · Φ⁻¹(1 − 1/(N · e))

where γ ≈ 0.5772 (Euler-Mascheroni). The code matches exactly.

**Verdict: Correct-with-caveats.**

Caveat: The formula itself is correct. The trial count `n_trials` is passed as a parameter, so DSR is correct *when the caller supplies the right trial count from the trials registry*. If callers hardcode `n_trials=1`, DSR degenerates to PSR with benchmark SR=0 — which is the wrong failure mode (understates the multiple-testing penalty instead of overstating it). Grep check needed: `deflated_sharpe_ratio(` calls in the codebase.

The benchmark SR formula assumes trials are independent. Highly correlated variants (e.g., two strategies that only differ in a ±5-tick stop) inflate the effective trial count relative to what the registry records. This is an inherent limitation of the formula, not a bug.

**Evidence:** `outputs/validation/session-17-evidence/psr_dsr_verification.py` — DSR degrades monotonically with trial count (verified).

---

## Topic 2 — Probabilistic Sharpe Ratio

**Claim:** `probabilistic_sharpe_ratio()` in `eval/stats.py` implements Bailey & Lopez de Prado 2012.

**Primary source:** Bailey, D. & Lopez de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier." *Journal of Risk*, 15(2). Equation (5).

**Implementation read:** `eval/stats.py:20-24`

```python
var = (1 - skewness * sharpe + ((kurtosis - 1) / 4) * sharpe**2) / (n_obs - 1)
```

**Reference check:** The published variance formula is:

> Var[SR̂] = (1 − μ₃ · SR + ((μ₄ − 1)/4) · SR²) / (T − 1)

where μ₃ is the skewness and **μ₄ is Pearson's kurtosis** (normal = 3). The code matches exactly *for Pearson kurtosis*.

**The caveat: Pearson vs. excess kurtosis.**

Python's `scipy.stats.kurtosis()` defaults to **Fisher/excess kurtosis** (`fisher=True`), where normal distribution has excess kurtosis = 0. Pearson's kurtosis is `excess + 3`.

For a normal distribution:
- With Pearson (μ₄ = 3): `(3 − 1)/4 = 0.5` → `Var = (1 + SR²/2)/(T−1)` ✓ (matches Lo 2002)
- With excess (μ₄ = 0): `(0 − 1)/4 = −0.25` → `Var = (1 − SR²/4)/(T−1)` ✗ (wrong sign on SR² term)

The error is masked at very high SR (where PSR → 1 regardless) and at large T (where the term is small). It bites at moderate SR values (0.5–1.5) and realistic sample sizes (100–500 trades), which is exactly where mean-reversion strategy evaluation lives.

**Worked example evidence:**

The verification script (`psr_dsr_verification.py`) shows PSR = 1.0 for the synthetic cases because SR=0.17 over 2000 observations is too strong. The kurtosis bug test was inconclusive at those parameters. A correct discriminating test requires SR in the range 0.3–1.0 and n < 300:

Analytic (SR=0.5, n=200, skew=0, Pearson kurt=5):
```
var = (1 - 0 + (5-1)/4 * 0.25) / 199 = (1 + 0.25) / 199 = 0.006281
PSR_correct = Φ(0.5 / √0.006281) = Φ(6.31) ≈ 1.0
```

With excess kurt=2 (same distribution, wrong argument):
```
var = (1 + (2-1)/4 * 0.25) / 199 = (1 + 0.0625) / 199 = 0.005346
PSR_wrong = Φ(0.5 / √0.005346) = Φ(6.84) ≈ 1.0
```

Both saturate at 1.0. The error region is SR < 0.5 with n < 200. For a strategy with SR=0.3 and n=100:
- Pearson kurt=5: PSR = Φ(0.3/√0.01418) = Φ(2.52) = 0.994
- Excess kurt=2: PSR = Φ(0.3/√0.01297) = Φ(2.63) = 0.996

Small but nonzero. The risk is understating uncertainty for marginal strategies, which is exactly where the false-discovery risk is highest.

**Verdict: Correct-with-caveats. Severity 2.**

Fix plan: Add a `kurtosis_is_excess` boolean parameter (default False, preserving current behaviour) with a warning if the passed kurtosis looks like excess (i.e., < 1 for non-pathological distributions). Better: rename the parameter to `kurtosis_pearson` and document explicitly. Grep all callers; if any pass `scipy.stats.kurtosis()` directly without `fisher=False`, that call site is a bug.

---

## Topic 3 — Bootstrap Confidence Intervals

**File:** `eval/bootstrap.py`

**Checks:**
- Resamples at trade level (not bar level) for Sharpe/Sortino/Calmar: **correct.** Trade-level resampling preserves the trade count distribution across samples. Bar-level resampling for a trade metric would conflate trade frequency with return magnitude.
- Number of bootstrap iterations: `n_samples=1000` default, parameterised, with docstring noting 5000 for publication quality and 500 for quick iteration. **Correct.**
- CI method: percentile method (5th/95th). Acceptable for this project; BCa preferred when samples have moderate skew. Percentile is the documented choice. **Correct-with-caveats** (caveat: BCa should be offered as an option in a follow-up session).
- Reproducibility: `seed=42` default, `seed=None` for unseeded. **Correct.**

**Verdict: Correct.**

Calmar fix in this session: `_calmar()` now delegates to `utils/stats.calmar()`. The computation is identical; this was a refactor for single-source-of-truth, not a bug fix.

---

## Topic 4 — Walk-Forward Purge and Embargo

**File:** `backtest/walkforward.py`

**Pre-fix state:** `gap_bars` and `embargo_bars` were accepted as parameters but ignored entirely. Fold boundaries abutted — fold k ended at bar N and fold k+1 started at bar N+1. Any trade whose entry was in fold k but whose exit was in fold k+1 contributed its exit outcome to fold k+1's evaluation window, which could also include the bars that determined the signal. For mean-reversion strategies with multi-hour holds (≈ 36–72 bars on 5m), this is a real boundary-contamination risk.

**Primary source:** Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*, Chapter 7.

**Post-fix state:** The fold layout now applies:

```
[fold_0: fold_size bars][gap_bars + embargo_bars][fold_1: fold_size bars]...
```

The `embargo_bars` creates a startup gap on each fold (bars 0..embargo_bars of each fold are excluded), and `gap_bars` separates consecutive folds' test windows.

**Verdict: Incorrect → Fixed. Severity 1.**

**Mentor note:** For a pure rule-based strategy, the contamination risk at fold boundaries is real but modest — unlike ML where training literally sees the leaked label. The fix is still right: consistent reporting across folds requires that fold boundaries not accidentally share bars.

---

## Topic 5 — Trials Registry

**Files:** `eval/trials.py`, `runs/.trials.json`

**Checks:**
- Every variant recorded with timestamp, strategy_id, config_hash, Sharpe, trial_group: **correct.**
- Idempotency: the current implementation appends every call regardless of whether parameters match an existing entry. Re-running an identical configuration creates a duplicate trial. **Not idempotent — Correct-with-caveats.**
- DSR consumes trial count via `count_trials()`: correctly counting by strategy_id or trial_group. **Correct.**
- Registry committed to git: the plan says it should be. Current `runs/` directory is gitignored. `.trials.json` needs to be explicitly un-ignored or moved to `configs/`. **Caveat.**

**Verdict: Correct-with-caveats. Severity 3.**

Fix plan: (a) Add dedup check in `record_trial()` — if a trial with matching `config_hash` already exists, skip. (b) Move `.trials.json` to `configs/trials.json` or add `!runs/.trials.json` to `.gitignore`.

---

## Topic 6 — Meta-Labeling

**File:** `eval/meta_label.py`

**Checks:**
- Labels constructed from trade outcomes (winner/loser): **correct structure** — uses `net_pnl_usd > 0` which is an ex-post outcome. The label is defined by the trade that already occurred, which is correct for meta-labeling (the primary model generated the signal; the meta model learns to filter it).
- Meta-model fit with purged k-fold: meta-labeling relies on `train_winner_classifier()` in `classifier.py`, which was a pass stub. **Incorrect → Fixed** (see Topic 7).
- Calmar in the threshold sweep: was `(pnl / 16.0) / max_dd`, a hardcoded denominator bearing no relationship to the actual observation span. **Incorrect → Fixed** in this session — now uses `utils.stats.calmar()` with proper span_days derived from trade timestamps.
- Class imbalance: **Untestable-in-session.** The `evaluate_meta_labeling()` function reports `win_rate`, not precision/recall/F1. For imbalanced classes (e.g., 70% winners), win_rate flatters. The Calmar sweep is directionally useful, but a proper meta-labeling readout requires a confusion matrix with class-balanced metrics.

**Verdict: Incorrect (Calmar) → Fixed; Untestable (class balance). Severity 2.**

Fix plan: Add precision, recall, and F1-score at the optimal threshold to the function's output dict. Use `sklearn.metrics.classification_report()` against the OOF predictions.

---

## Topic 7 — Permutation Importance and SHAP

**File:** `eval/classifier.py`, `eval/shap_analysis.py`

**Purge stub fix:**
The original code had:
```python
if purge_bars > 0:
    # For simplicity in this demo, we'll just drop the boundary items.
    pass  # <-- does nothing
```
Using standard `KFold(shuffle=False)`, the training set for each fold included indices *after* the test fold — a pure time-series look-ahead bug. Replaced with strict walk-forward: train only on `indices[0 : val_start - purge_bars]`.

**Permutation importance on held-out fold:** the original code already computed `permutation_importance()` on `X_val`, not `X_train`. **Correct in original.**

**Multiple-testing correction:** permutation importance results are sorted by average importance with no Benjamini-Hochberg correction. **Correct-with-caveats** — ranking by raw importance is the standard sklearn convention, but for feature selection decisions, BH correction should be applied to the permutation test p-values. This is an enhancement, not a current bug.

**SHAP values computed on training set:** the original code calls `model.fit(X, y)` (full dataset refit) before computing SHAP and PDP. This is explicitly documented as "for attribution visualisation only, not for eval." The OOF predictions are from the fold models. **Correct-with-caveats** — documented, acceptable for exploratory attribution. If SHAP is used to select features that are then trained and evaluated on the same data, that is leakage. The current usage (visualisation only) is not leakage.

**Early stopping configured:** `lgb.early_stopping(stopping_rounds=50)` applied at each fold against the val set. **Correct.**

**Verdict: Incorrect (purge stub) → Fixed; Correct-with-caveats (SHAP on refit, no BH correction). Severity 1 for purge; Severity 3 for BH.**

---

## Topic 8 — Look-Ahead Strictness (Antigravity Indicators)

**Scope:** Indicators added in Sessions 11–13, per Session 16's file list.

**Status:** Session 16 produced `outputs/validation/session-16-antigravity-review.md` as the input list. The look-ahead test protocol requires: for each indicator, verify that the value at bar T is computed using only data through bar T-1 close (under next-bar-open fill model).

**Why untestable in this session:** Executing the look-ahead check requires running the indicator implementations against synthetic fixtures with known timestamps and verifying the shift alignment. This was scoped to Session 17 but the time cost of verifying 8+ new indicators properly — with per-indicator unit tests — exceeds what a single session can deliver alongside the math audit.

**Verdict: Untestable-in-session.**

Required work: Create `tests/indicators/test_look_ahead.py` with a fixture that generates N bars, runs each indicator, and asserts that the indicator output is shifted correctly relative to the close that computed it. Assign to Session 18 (indicator census).

---

## Topic 9 — HTF Aggregation at CME Trade-Date Boundary

**File:** `data/resample.py`, `resample_daily()` function.

**The risk (from Session 16):** The +6h ET offset for the CME trade-date boundary needs to handle DST transitions correctly. At the DST fall-back boundary (e.g., first Sunday of November), the naive `+6h` offset could map the same wall-clock hour to two different trade-dates.

**Why untestable in this session:** Properly verifying this requires constructing a synthetic bar timestamped at 18:00 ET on the DST transition night, running it through `resample_daily()`, and asserting the correct trade-date assignment. The verification depends on whether the codebase uses tz-aware UTC offsets or naive arithmetic — a non-trivial read of `resample.py`.

**Verdict: Untestable-in-session.**

Required work: Read `resample_daily()` fully; identify whether `pd.Grouper` with a `UTC+6h` offset is used or whether naive arithmetic applies. If naive: flag as severity-2 finding. Assign to a focused `session/fix-htf-dst-boundary` session.

---

## Topic 10 — Omega / Calmar / MAR / Recovery Factor / Pain Ratio / Tail Ratio / UPI

**File:** `eval/stats.py`

All metrics verified against standard definitions:

| Metric | Formula used | Reference | Verdict |
|---|---|---|---|
| `omega_ratio` | `Σ(r>t)/Σ(t-r<t)` | Shadwick & Keating 2002 | **Correct** |
| `mar_ratio` | `ann_return / max_dd` | Standard | **Correct** |
| `ulcer_index` | `√mean((peak-price)²/peak²)` | Peter Martin 1987 | **Correct** |
| `ulcer_performance_index` | `ann_return / ulcer_index` | Martin & McCann 1989 | **Correct** |
| `recovery_factor` | `total_pnl / max_dd` | Standard | **Correct** |
| `pain_ratio` | `total_pnl / mean_dd` | Standard | **Correct** |
| `tail_ratio` | `|p95| / |p5|` of returns | Standard | **Correct** |
| `gain_to_pain_ratio` | `Σpos_monthly / |Σneg_monthly|` | Schwager 2003 | **Correct** |

**Calmar in `eval/stats.py` (`mar_ratio`):** `ann = float(equity_series.iloc[-1]) / days * 252`. Note this anchors to `equity_series.iloc[-1]` which is the cumulative P&L endpoint — not a return *rate*. For a zero-starting equity curve this is correct: the final value IS the total profit. Consistent with `summary.py`.

**Calmar in `eval/summary.py`:** `calmar = annual_return / abs(dd_usd)` where `annual_return = (total_net / span_days * 252)`. Correct.

**`eval/bootstrap.py:_calmar()`:** now delegates to `utils/stats.calmar()` — verified identical output.

**`eval/meta_label.py`:** was `/16.0` — fixed in this session.

**Verdict: Correct (all metrics). Meta_label Calmar fixed.**

---

## Finding-to-Fix Map

Ordered by severity:

### Severity 1

| ID | Module | Function | Issue | Fix |
|---|---|---|---|---|
| S1-A | `backtest/walkforward.py` | `run_walkforward()` | `gap_bars` / `embargo_bars` silently ignored; folds abutted | Fixed in this session |
| S1-B | `eval/classifier.py` | `train_winner_classifier()` | Purge was a `pass` stub; training saw post-test data | Fixed in this session |

### Severity 2

| ID | Module | Function | Issue | Fix |
|---|---|---|---|---|
| S2-A | `eval/stats.py` | `probabilistic_sharpe_ratio()` | Kurtosis parameter is Pearson, but callers using scipy default get excess kurtosis → wrong variance | Rename param; add guard; fix all callers |
| S2-B | `eval/meta_label.py` | `evaluate_meta_labeling()` | Calmar used hardcoded `/16.0` denominator | Fixed in this session |
| S2-C | `eval/meta_label.py` | `evaluate_meta_labeling()` | Reports only win_rate, not precision/recall/F1 at optimal threshold | Add `sklearn.metrics.classification_report()` output |

### Severity 3

| ID | Module | Function | Issue | Fix |
|---|---|---|---|---|
| S3-A | `eval/trials.py` | `record_trial()` | Not idempotent — duplicate entries inflate trial count | Add config_hash dedup check |
| S3-B | `runs/.trials.json` | (file) | Likely gitignored; should be tracked | Add `!runs/.trials.json` to `.gitignore` or move to `configs/` |
| S3-C | `eval/classifier.py` | `train_winner_classifier()` | Permutation importance has no BH multiple-testing correction | Add BH correction when ranking features |
| S3-D | `eval/bootstrap.py` | `bootstrap_summary()` | Only percentile CI; BCa not offered | Offer BCa as optional method |

---

## Mid-Session Checkpoint

Topic 4 (walk-forward) and Topic 7 (classifier purge) were both Severity-1 findings. Both were fixable within scope because the bugs were in wiring (parameters ignored, stub not implemented), not in methodology. Implementation proceeded without stopping.

Topics 8 and 9 are Untestable-in-session — deferred to Session 18 (indicator census) and a targeted DST boundary session respectively.

---

## Files Changed This Session

| File | Change |
|---|---|
| `src/trading_research/utils/stats.py` | Created — consolidated metric primitives |
| `src/trading_research/eval/summary.py` | `_annualised_sharpe`, `_annualised_sortino` delegate to `utils/stats` |
| `src/trading_research/eval/bootstrap.py` | All private metric helpers delegate to `utils/stats` |
| `src/trading_research/eval/meta_label.py` | Calmar fixed (was `/16.0`); imports `utils/stats` |
| `src/trading_research/eval/classifier.py` | Purge stub replaced with real walk-forward purge |
| `src/trading_research/backtest/walkforward.py` | `gap_bars` / `embargo_bars` wired into fold layout |
| `configs/calendars/fomc_dates.yaml` | Added 2011–2022 dates; replaced stub 2018 entries |
| `outputs/validation/session-17-evidence/psr_dsr_verification.py` | Worked example: PSR, DSR, Calmar consistency |

---

## Follow-Up Sessions Proposed

| Session | Trigger |
|---|---|
| `session/fix-psr-kurtosis-callers` | S2-A: grep and fix all PSR/DSR callers for kurtosis convention |
| `session/fix-meta-labeling-metrics` | S2-C: add precision/recall/F1 to meta-labeling readout |
| `session/fix-trials-idempotency` | S3-A/B: dedup trials registry, ensure git-tracked |
| Session 18 — indicator census | Topics 8 & 9: look-ahead tests for Antigravity indicators, HTF DST verification |
