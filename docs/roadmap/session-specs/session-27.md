# Session 27 — Hurst Fix + Benjamini-Hochberg + Composite Top-X Ranking

**Agent fit:** either
**Estimated effort:** L (4h+)
**Depends on:** 26
**Unblocks:** 28 (Hurst fix required before first real stationarity run on 6E), 29

## Goal

Three work items, in priority order:

1. **Fix the R/S Hurst estimator** (blocking session 28) — the session 26 implementation has a methodological defect that would cause VWAP spread mean reversion to be misclassified. Fix before any real data is run.
2. **Benjamini-Hochberg FDR correction** — standard multi-testing correction for feature selection and multi-strategy evaluation.
3. **Composite top-X ranking** — profit factor × max-DD-penalty × trade-count-floor for the backtest HTML report.

## Context — Hurst R/S Defect

The session 26 R/S implementation applies rescaled-range analysis to the input series **at the level**. This has a known behavior:

- A random walk (I(1) level) gives H ≈ 1.0 — correct.
- Any stationary AR(1) process with **positive φ** gives H > 0.5 — classified as TRENDING or RANDOM_WALK, regardless of how fast it reverts to its mean.
- Only a series with **negative autocorrelation** (oscillating, φ < 0) gives H < 0.5 — classified as MEAN_REVERTING.

The VWAP spread in practice behaves like an OU process with **positive φ** at the bar level — the price overshoots VWAP and takes several bars to come back, meaning the spread has positive autocorrelation at lag 1 even though it is stationary and mean-reverting. The current R/S implementation will classify this as RANDOM_WALK or TRENDING, making the composite label INDETERMINATE, which blocks the session 29 strategy class decision.

The fix is to replace R/S with **DFA (Detrended Fluctuation Analysis)**. DFA computes the Hurst exponent by measuring how local fluctuations (after removing local polynomial trends) scale with window size. It gives:

- H < 0.5: mean-reverting (anti-persistent fluctuations), regardless of φ sign
- H ≈ 0.5: random walk
- H > 0.5: trending / persistent long-range memory

For an OU process, DFA gives H significantly below 0.5 even when φ is positive. This is the correct discriminant for the "is this spread tradeable for mean reversion?" question.

**Reference:** Peng et al. (1994), "Mosaic organization of DNA nucleotides." DFA is standard in computational biology and financial time series (Mantegna & Stanley, 1999, ch. 4).

## Context — BH and Composite (unchanged from original spec)

When the platform tests multiple strategy variants or evaluates multiple features for predictive power, naive p-values inflate the false-discovery rate. Benjamini-Hochberg controls FDR and is the standard multi-testing correction for quant work. It is more powerful than Bonferroni while still controlling the expected false-discovery rate.

Separately, Ibby's preferred ranking method for strategy results is composite: profit factor, max drawdown, trade count — in a single score that filters out strategies with too few trades regardless of other metrics.

## In scope

### Part 1 — Hurst fix (do this first)

In `src/trading_research/stats/stationarity.py`:

- Add `dfa_hurst(series: pd.Series, min_window: int = 10, max_window: int | None = None, poly_order: int = 1) -> HurstResult` — DFA estimator. Algorithm:
  1. Choose window sizes `[8, 16, 32, 64, 128, 256, 512]` (same as R/S, respecting min/max).
  2. For each window size `n`, split series into non-overlapping segments of length `n`.
  3. For each segment, fit a polynomial of degree `poly_order` (default 1 = linear) and compute the RMS of residuals (the "fluctuation function" F(n)).
  4. Average F(n) across segments.
  5. Log-log regression of mean F(n) vs n. Slope = Hurst exponent.
- Change `hurst_exponent` to call `dfa_hurst` by default. Keep `_rs_hurst` as a private function for reference/comparison. The public API (`HurstResult`, `hurst_exponent`) is unchanged.
- Update the docstring on `hurst_exponent` to document the switch to DFA and the reason.
- Update `docs/design/stationarity-suite.md` §2.2 to replace the R/S description with DFA, and correct §8.2's statement that "AR(1) φ=0.5 should return H < 0.5" (correct for DFA, was incorrect for R/S).

Update tests in `tests/stats/test_stationarity_hurst.py`:
- `test_hurst_brownian_motion` — DFA on white noise or random walk returns H ≈ 0.5 (within ±0.10).
- `test_hurst_trending_series` — DFA on cumulative sum with drift returns H > 0.55.
- `test_hurst_mean_reverting_series` — DFA on AR(1) φ=0.5 (slow OU) returns H < 0.45. This is the key test that was failing with R/S.
- `test_hurst_random_walk_levels_high` — remove or update (R/S gives H≈1.0 for levels; DFA behavior may differ).
- `test_hurst_ar1_positive_phi_persistent` — remove (this was documenting the R/S defect, not desired behavior).

Add a regression test:
- `test_dfa_vs_rs_comparison` — on a known OU process (AR(1) φ=0.5), confirm that DFA gives H < 0.45 while the old R/S gave H > 0.5. This documents why the switch was made.

### Part 2 — Benjamini-Hochberg

Create under `src/trading_research/stats/`:

- `multiple_testing.py`:
  - `benjamini_hochberg(p_values: np.ndarray, alpha: float = 0.05) -> BHResult` — returns boolean mask of significant tests, adjusted p-values, and the actual FDR threshold applied.
  - `BHResult` dataclass.

Create under `src/trading_research/eval/`:

- `ranking.py`:
  - `composite_score(profit_factor: float, max_dd_pct: float, trade_count: int, min_trades: int = 100) -> float` — returns composite score. Strategies with `trade_count < min_trades` get score `-inf` (excluded from top rankings).
  - `top_x_strategies(trials: list[Trial], x: int = 10, min_trades: int = 100) -> list[Trial]` — returns top X by composite score.

Integrate into backtest HTML report:

- When the backtest report is generated with multi-strategy input (or multi-trial from the registry), include:
  - A "Top 10 by composite score" section.
  - A note explaining the composite formula in trader-language + the formula itself.
  - For any feature significance table, apply BH correction and show both raw p-values and BH-adjusted p-values.

Create tests:

- `tests/stats/test_benjamini_hochberg.py`:
  - `test_bh_matches_scipy` — compare against `scipy.stats.false_discovery_control` (available in scipy >= 1.11).
  - `test_bh_all_null` — uniform p-values on [0,1], BH identifies near-zero as false discoveries.
  - `test_bh_all_significant` — tiny p-values all pass.
  - `test_bh_mixed` — mix of 10 true positives and 90 nulls, BH recovers most of the true positives.
- `tests/eval/test_composite_ranking.py`:
  - `test_high_pf_low_dd_high_trades` — ranks high.
  - `test_low_trades_excluded` — trade count below threshold returns `-inf`.
  - `test_top_x_returns_sorted` — output is sorted desc by composite score.

## Out of scope

- Do NOT modify the strategy registry or trial registry schema. Those are 24's scope.
- Do NOT add new ranking methods beyond composite. One is enough.
- Do NOT refactor the HTML report engine — only add new sections.
- Do NOT apply BH anywhere it isn't appropriate (e.g., to a single strategy's own trades; BH is for *sets of hypothesis tests*, not for P&L evaluation).
- Do NOT rewrite the full stationarity suite — only replace the Hurst estimator in `hurst_exponent`. The ADF and OU functions are unchanged.

## Acceptance tests

- [ ] `uv run pytest tests/stats/test_stationarity_hurst.py -v` — all tests pass with DFA-based Hurst.
- [ ] `test_hurst_mean_reverting_series` confirms DFA gives H < 0.45 for AR(1) φ=0.5 (this test FAILED in session 26 with R/S — its passage here is the acceptance signal for the fix).
- [ ] `test_dfa_vs_rs_comparison` documents that R/S gave H > 0.5 for the same series (regression test).
- [ ] `uv run pytest tests/stats/test_benjamini_hochberg.py tests/eval/test_composite_ranking.py -v` passes.
- [ ] `uv run pytest` — full suite passes.
- [ ] A generated backtest HTML report, when given multi-strategy input, shows the "Top 10 by composite score" section.
- [ ] BH-adjusted p-values column appears alongside raw p-values in feature significance tables.

## Definition of done

- [ ] All tests pass.
- [ ] `docs/design/stationarity-suite.md` §2.2 updated to describe DFA; §8.2 corrected to match DFA's actual behavior.
- [ ] HTML report visual check — render a sample report and verify the new sections render correctly.
- [ ] Work log includes: (a) DFA canonical test values on AR(1) φ=0.5 (the series that broke R/S), (b) the composite formula and its rationale, (c) a before/after BH example.
- [ ] Committed on feature branch `session-27-hurst-fix-bh-composite`.
- [ ] Session 26 work-log "Observed Debt" item about design doc §8.2 wording is resolved.

## Persona review

- **Data scientist: required.** DFA implementation correctness, BH implementation, composite formula justification, appropriate use of multi-testing correction. Must sign off that DFA gives the expected H values on the canonical test series before session 28 runs.
- **Mentor: optional.** May weigh in on whether composite formula weights match how a real trader thinks about strategy quality.
- **Architect: optional.** Reviews that the R/S → DFA switch is a clean replacement (no leaking private functions into public API).

## Design notes

### DFA algorithm

```python
def dfa_hurst(
    series: pd.Series,
    min_window: int = 10,
    max_window: int | None = None,
    poly_order: int = 1,
) -> HurstResult:
    arr = np.asarray(series.dropna(), dtype=float)
    # Integrate (cumulative sum of mean-subtracted series) before DFA
    arr = np.cumsum(arr - np.mean(arr))
    n = len(arr)
    # ... window loop same structure as R/S ...
    # For each window w and each segment:
    #   1. fit polynomial of degree poly_order to segment
    #   2. compute RMS of residuals → F(w) for that segment
    # Average F(w) across segments, then log-log regression
    # slope = Hurst exponent
```

The cumulative-sum step (integrating the series before DFA) is standard in the original DFA formulation. For a random walk (already integrated), this would double-integrate — so input series should be the **raw level** (spread or return series), not pre-integrated. The function handles this internally.

**Expected DFA values (approximate, finite-sample, n=500):**

| Series type | Expected H | Threshold |
|---|---|---|
| White noise / returns | ≈ 0.5 | — |
| Random walk (level) | ≈ 1.0 | — |
| AR(1) φ=0.5 (OU-like spread) | < 0.45 | MEAN_REVERTING |
| AR(1) φ=-0.7 (oscillating) | < 0.30 | MEAN_REVERTING (strong) |
| Trending (cumsum + drift) | > 0.55 | TRENDING |

### Composite score formula

Proposed (data scientist will review):

```python
def composite_score(profit_factor: float, max_dd_pct: float, trade_count: int, min_trades: int = 100) -> float:
    if trade_count < min_trades:
        return float("-inf")
    if max_dd_pct >= 1.0:
        # 100% drawdown = strategy blew up
        return float("-inf")
    # Higher profit factor = better; higher drawdown = worse
    # Log to compress high-PF outliers; penalty is multiplicative
    pf_component = math.log(max(profit_factor, 1e-6))
    dd_penalty = 1.0 - min(max_dd_pct, 0.99)
    trade_count_bonus = math.log10(trade_count / min_trades)
    return pf_component * dd_penalty * (1 + trade_count_bonus)
```

This is a proposal. Data scientist reviews. Mentor may adjust weights. Final formula documented in the work log and in `docs/design/composite-ranking.md`.

### BH procedure

Standard algorithm:

```python
def benjamini_hochberg(p_values: np.ndarray, alpha: float = 0.05) -> BHResult:
    n = len(p_values)
    sorted_idx = np.argsort(p_values)
    sorted_p = p_values[sorted_idx]
    thresholds = (np.arange(1, n + 1) / n) * alpha
    below = sorted_p <= thresholds
    if not below.any():
        max_sig_idx = -1
    else:
        max_sig_idx = np.where(below)[0].max()
    significant = np.zeros(n, dtype=bool)
    significant[sorted_idx[:max_sig_idx + 1]] = True
    # BH-adjusted p-values
    adjusted = np.minimum.accumulate((sorted_p * n / np.arange(1, n + 1))[::-1])[::-1]
    adjusted = np.minimum(adjusted, 1.0)
    adjusted_restored = np.empty_like(adjusted)
    adjusted_restored[sorted_idx] = adjusted
    return BHResult(significant=significant, adjusted_p_values=adjusted_restored, alpha=alpha)
```

Validate against scipy's `false_discovery_control` to catch off-by-one errors.

### When to apply BH

Apply to:
- Feature significance tests (if session 26's stationarity or future feature-importance tests produce multiple p-values).
- Multi-strategy hypothesis tests.

Do not apply to:
- A single strategy's trade P&L evaluation.
- Sharpe ratio or Calmar — those are point estimates with CIs, not p-values.

## Risks

- **Composite formula weights are arbitrary.** Mitigation: document the rationale, make weights tunable via config, let data scientist + mentor push back.
- **BH misused.** Mitigation: docstring and `docs/design/` note clearly states what BH is appropriate for.

## Reference

- Benjamini & Hochberg (1995), "Controlling the false discovery rate: a practical and powerful approach to multiple testing."
- `scipy.stats.false_discovery_control` — reference implementation (scipy ≥ 1.11).
- `.claude/rules/data-scientist.md` — "Multiple-testing correction in feature selection" section.

## Success signal

**Hurst fix:** `test_hurst_mean_reverting_series` passes — DFA on AR(1) φ=0.5 returns H < 0.45. This test FAILED in session 26 with R/S; its passage is the go/no-go signal for session 28's real 6E run.

**BH + ranking:** A sample HTML report from three strategy variants shows the composite ranking table with the correct top-3 order. A synthetic test with 100 p-values (5 truly significant, 95 null) has BH correctly identifying approximately the 5 at FDR = 0.05.
