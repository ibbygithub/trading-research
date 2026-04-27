"""Multiple-testing correction utilities.

Currently provides the Benjamini-Hochberg (BH) false-discovery-rate procedure.

When to use BH
--------------
Apply to *sets of hypothesis tests* where you want to control the expected
proportion of false discoveries among rejected tests.  Appropriate examples:

- Feature significance tests: which of N candidate features are predictive?
- Multi-strategy hypothesis tests: which strategy variants beat a benchmark?

Do NOT apply to:
- A single strategy's trade P&L evaluation.
- Point estimates like Sharpe or Calmar (those are not p-values).
- Individual ADF tests (each tests one series — no multiple testing issue).

Reference
---------
Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate:
a practical and powerful approach to multiple testing. Journal of the Royal
Statistical Society, Series B, 57(1), 289-300.

Validated against ``scipy.stats.false_discovery_control`` (scipy ≥ 1.11).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BHResult:
    """Results from a Benjamini-Hochberg correction.

    Attributes
    ----------
    significant : np.ndarray of bool
        Boolean mask (same length as input) — True where the null is rejected
        at the controlled FDR level.
    adjusted_p_values : np.ndarray of float
        BH-adjusted p-values (Benjamini-Hochberg step-up corrected).  A test
        is significant iff adjusted_p_value ≤ alpha.
    alpha : float
        The FDR level used.
    n_tests : int
        Total number of tests submitted.
    n_significant : int
        Number of tests rejected at this FDR level.
    """

    significant: np.ndarray
    adjusted_p_values: np.ndarray
    alpha: float
    n_tests: int
    n_significant: int


def benjamini_hochberg(
    p_values: np.ndarray,
    alpha: float = 0.05,
) -> BHResult:
    """Benjamini-Hochberg false-discovery-rate correction.

    Implements the standard BH step-up procedure.  Given m p-values, sort
    them ascending (p_(1) ≤ … ≤ p_(m)), then reject the null for all tests
    p_(k) where k ≤ max{i : p_(i) ≤ i/m * alpha}.

    Adjusted p-values (BH-corrected) are computed using the step-down formula
    so that a test is significant iff its adjusted p-value ≤ alpha:

        adjusted_p_(k) = min(p_(k) * m / k, 1.0)

    applied cumulatively from the largest to smallest rank to enforce
    monotonicity.

    Parameters
    ----------
    p_values : np.ndarray
        Array of raw p-values, one per test.  May be any length ≥ 1.
        Values must be in [0, 1].
    alpha : float
        Desired FDR level.  Default 0.05.

    Returns
    -------
    BHResult
        .significant  — boolean mask of rejected tests.
        .adjusted_p_values — BH-adjusted p-values in the original input order.
        .alpha        — the FDR level used.
        .n_tests      — total tests.
        .n_significant — number rejected.

    Examples
    --------
    >>> import numpy as np
    >>> from trading_research.stats.multiple_testing import benjamini_hochberg
    >>> # 5 truly significant (tiny p) + 95 null (uniform)
    >>> rng = np.random.default_rng(0)
    >>> p = np.concatenate([rng.uniform(0, 0.001, 5), rng.uniform(0, 1, 95)])
    >>> result = benjamini_hochberg(p, alpha=0.05)
    >>> result.n_significant  # should recover most of the 5 true positives
    5
    """
    p_values = np.asarray(p_values, dtype=float)
    if p_values.ndim != 1:
        raise ValueError(f"p_values must be 1-D; got shape {p_values.shape}")
    m = len(p_values)
    if m == 0:
        raise ValueError("p_values must not be empty")

    # Rank by ascending p-value (1-indexed in the BH formulation).
    sorted_idx = np.argsort(p_values)
    sorted_p = p_values[sorted_idx]
    ranks = np.arange(1, m + 1, dtype=float)

    # BH threshold for each rank: p_(k) ≤ (k/m) * alpha.
    thresholds = (ranks / m) * alpha
    below = sorted_p <= thresholds

    # Largest rank where BH threshold is met (step-up: reject all up to max k).
    max_sig_rank = 0 if not below.any() else int(np.where(below)[0].max()) + 1

    significant_sorted = np.zeros(m, dtype=bool)
    significant_sorted[:max_sig_rank] = True

    # Restore to original order.
    significant = np.empty(m, dtype=bool)
    significant[sorted_idx] = significant_sorted

    # BH-adjusted p-values: p_adj_(k) = min(p_(k) * m/k, 1).
    # Applied step-down from largest to smallest rank to enforce monotonicity
    # (adjacent values must be non-increasing when walking from large to small).
    raw_adjusted = np.minimum(sorted_p * m / ranks, 1.0)
    # Monotone step-down: accumulate minimum from the right.
    adjusted_sorted = np.minimum.accumulate(raw_adjusted[::-1])[::-1]

    adjusted = np.empty(m, dtype=float)
    adjusted[sorted_idx] = adjusted_sorted

    return BHResult(
        significant=significant,
        adjusted_p_values=adjusted,
        alpha=alpha,
        n_tests=m,
        n_significant=int(significant.sum()),
    )
