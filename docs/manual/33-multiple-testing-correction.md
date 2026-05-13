# Chapter 33 — Multiple-Testing Correction

> **Chapter status:** [EXISTS] — Benjamini-Hochberg correction is
> implemented in
> [`stats/multiple_testing.py`](../../src/trading_research/stats/multiple_testing.py).
> A convenience wrapper for feature tables lives in
> [`eval/ranking.py:258`](../../src/trading_research/eval/ranking.py).
> Bonferroni is not implemented as a separate function because BH
> dominates it in all practical cases; this chapter documents both for
> conceptual completeness.

---

## 33.0 What this chapter covers

When you test the same hypothesis many times against different features
or parameter values, ordinary p-values overstate the significance of
the best result. This chapter explains why, and shows how the platform
corrects for it. After reading this chapter you will:

- Know when multiple-testing correction is needed and when it is not
- Understand the difference between Bonferroni and Benjamini-Hochberg
- Be able to invoke the `benjamini_hochberg` function on a set of
  feature p-values
- Know the limits of the correction and when it doesn't help

This chapter is roughly 2 pages. It is referenced by Chapters 23
(Deflated Sharpe), 34 (Composite Ranking), and the feature-engineering
workflow.

---

## 33.1 Why correction matters

Suppose you test 50 candidate features to see which predict next-bar
direction. Each test has a 5% chance of producing a "significant" result
by pure chance (false positive). If none of the features is genuinely
predictive, you still expect roughly 2–3 of them to pass a p < 0.05
threshold. Without correction, you would add those 2–3 features to the
strategy, confident in their significance — and trade noise.

The false discovery rate (FDR) is the expected proportion of selected
features that are actually noise. Ordinary significance testing does not
control FDR. Benjamini-Hochberg does.

This is distinct from the multiple-testing problem that Deflated Sharpe
addresses. DSR handles the case where you try N *strategy variants* and
pick the best. BH handles the case where you test N *features* and pick
the significant ones. Both problems stem from the same root: human
curiosity generates comparisons, and comparisons inflate apparent
significance.

---

## 33.2 Bonferroni vs Benjamini-Hochberg

**Bonferroni** divides the significance threshold by the number of
tests: to achieve overall α = 0.05 across 50 tests, each individual
test must clear α/50 = 0.001. Bonferroni controls the family-wise error
rate (FWER) — the probability of any false positive. It is conservative
enough to guarantee this, but so conservative that genuinely predictive
features with moderate effect sizes often fail the tighter threshold.

**Benjamini-Hochberg (BH)** controls the false discovery *rate* — the
expected fraction of rejected tests that are false positives — rather
than eliminating all false positives. For a target FDR of 5%, BH
guarantees that at most 5% of the features you call "significant" are
actually noise. This is a weaker guarantee than Bonferroni's but
practically more useful: it finds more real features at the cost of a
small, bounded rate of false inclusions.

The BH procedure (implemented in
[`stats/multiple_testing.py:61`](../../src/trading_research/stats/multiple_testing.py)):

1. Sort p-values ascending: p₍₁₎ ≤ p₍₂₎ ≤ … ≤ p₍ₘ₎
2. Find the largest k such that p₍ₖ₎ ≤ (k/m) × α
3. Reject the null for all tests up to rank k

The platform uses BH because in a feature search across 30–100
candidates, Bonferroni is too strict to be useful. BH's FDR guarantee
at α = 0.05 means roughly 1 in 20 features you call significant will be
noise — acceptable for an initial feature filter that is subsequently
validated by walk-forward.

---

## 33.3 The `stats/multiple_testing.py` module

```python
from trading_research.stats.multiple_testing import benjamini_hochberg
import numpy as np

# p_values: array of per-feature p-values from your significance tests
result = benjamini_hochberg(p_values=p_array, alpha=0.05)

result.significant         # bool array — True where null is rejected
result.adjusted_p_values   # BH-corrected p-values
result.n_significant       # count of rejected tests
```

A convenience wrapper for feature DataFrames is in
[`eval/ranking.py:258`](../../src/trading_research/eval/ranking.py):

```python
from trading_research.eval.ranking import apply_bh_to_feature_table

df_corrected = apply_bh_to_feature_table(
    feature_df,         # DataFrame with a p_value column
    p_col="p_value",
    alpha=0.05,
)
# df_corrected now has columns bh_adjusted_p and bh_significant
```

**When not to use BH:** single hypothesis tests (testing one strategy,
one ADF test, one feature); Calmar and Sharpe are point estimates, not
p-values — do not feed them to BH; portfolio-level P&L is not a test.
The module's docstring enumerates the anti-patterns.

---

## Related references

- Code: [`stats/multiple_testing.py`](../../src/trading_research/stats/multiple_testing.py) —
  `benjamini_hochberg`, `BHResult`
- Code: [`eval/ranking.py:258`](../../src/trading_research/eval/ranking.py) —
  `apply_bh_to_feature_table`
- Chapter 23 — Deflated Sharpe (the strategy-level multiple-testing correction)
- Chapter 34 — Composite Ranking

---

*Chapter 33 of the Trading Research Platform Operator's Manual*
