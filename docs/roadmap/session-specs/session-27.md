# Session 27 — Benjamini-Hochberg + Composite Top-X Ranking

**Agent fit:** either
**Estimated effort:** M (2–4h)
**Depends on:** 26
**Unblocks:** 29 (strategy work can be evaluated with proper multi-testing correction)

## Goal

Implement Benjamini-Hochberg false-discovery-rate correction for multi-strategy and multi-feature testing, plus the composite top-X ranking (profit factor × max-DD-penalty × trade-count-floor) for the backtest HTML report.

## Context

When the platform tests multiple strategy variants or evaluates multiple features for predictive power, naive p-values inflate the false-discovery rate. Benjamini-Hochberg controls FDR and is the standard multi-testing correction for quant work. It is more powerful than Bonferroni while still controlling the expected false-discovery rate.

Separately, Ibby's preferred ranking method for strategy results is composite: profit factor, max drawdown, trade count — in a single score that filters out strategies with too few trades regardless of other metrics.

## In scope

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

## Acceptance tests

- [ ] `uv run pytest tests/stats/test_benjamini_hochberg.py tests/eval/test_composite_ranking.py -v` passes.
- [ ] `uv run pytest` — full suite passes.
- [ ] A generated backtest HTML report, when given multi-strategy input, shows the "Top 10 by composite score" section.
- [ ] BH-adjusted p-values column appears alongside raw p-values in feature significance tables.

## Definition of done

- [ ] All tests pass.
- [ ] HTML report visual check — render a sample report and verify the new sections render correctly.
- [ ] Work log includes the composite formula and its rationale, plus a before/after BH example (10 strategies, show which pass raw vs BH).
- [ ] Committed on feature branch `session-27-bh-composite`.

## Persona review

- **Data scientist: required.** BH implementation, composite formula justification, appropriate use of multi-testing correction.
- **Mentor: optional.** May weigh in on whether composite formula weights match how a real trader thinks about strategy quality.
- **Architect: optional.** Reviews module placement and coupling.

## Design notes

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

A sample HTML report from three strategy variants shows the composite ranking table with the correct top-3 order. A synthetic test with 100 p-values (5 truly significant, 95 null) has BH correctly identifying approximately the 5 at FDR = 0.05.
