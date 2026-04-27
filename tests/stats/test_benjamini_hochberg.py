"""Benjamini-Hochberg FDR correction tests.

Validates against scipy.stats.false_discovery_control (scipy ≥ 1.11) as the
reference implementation.

Key correctness properties tested:
- Significant mask and adjusted p-values agree with scipy to float tolerance.
- All-null input (uniform p-values) produces near-zero rejections.
- All-signal input (tiny p-values) rejects everything.
- Mixed input recovers most true positives at FDR = 0.05.
- BH is more powerful than Bonferroni (expected: more rejections at same alpha).
"""

from __future__ import annotations

import numpy as np
import pytest

from trading_research.stats.multiple_testing import BHResult, benjamini_hochberg

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mixed(n_signal: int = 10, n_null: int = 90, seed: int = 42) -> np.ndarray:
    """Mix of truly significant (tiny p) and null (uniform) p-values."""
    rng = np.random.default_rng(seed)
    signal_p = rng.uniform(0.0, 0.001, n_signal)
    null_p = rng.uniform(0.0, 1.0, n_null)
    return np.concatenate([signal_p, null_p])


# ---------------------------------------------------------------------------
# Type and API tests
# ---------------------------------------------------------------------------


def test_bh_returns_correct_type() -> None:
    p = np.array([0.01, 0.04, 0.03, 0.20, 0.60])
    result = benjamini_hochberg(p, alpha=0.05)
    assert isinstance(result, BHResult)


def test_bh_output_lengths_match_input() -> None:
    p = np.array([0.01, 0.04, 0.03, 0.20, 0.60])
    result = benjamini_hochberg(p, alpha=0.05)
    assert len(result.significant) == len(p)
    assert len(result.adjusted_p_values) == len(p)


def test_bh_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        benjamini_hochberg(np.array([]))


def test_bh_n_tests_attribute() -> None:
    p = np.array([0.01, 0.04, 0.50])
    result = benjamini_hochberg(p, alpha=0.05)
    assert result.n_tests == 3
    assert result.alpha == 0.05


# ---------------------------------------------------------------------------
# Correctness vs scipy reference
# ---------------------------------------------------------------------------


def test_bh_matches_scipy() -> None:
    """BH significant mask must agree with scipy.stats.false_discovery_control.

    scipy ≥ 1.11 provides false_discovery_control(ps, method='bh') which
    returns adjusted p-values.  A test is significant if adjusted_p ≤ alpha.
    We compare both the boolean mask and the adjusted p-values.
    """
    pytest.importorskip("scipy", minversion="1.11")
    from scipy.stats import false_discovery_control

    rng = np.random.default_rng(7)
    p = np.concatenate([
        rng.uniform(0.0, 0.005, 10),   # 10 truly significant
        rng.uniform(0.0, 1.0, 90),     # 90 null
    ])
    alpha = 0.05

    our_result = benjamini_hochberg(p, alpha=alpha)
    scipy_adjusted = false_discovery_control(p, method="bh")
    scipy_significant = scipy_adjusted <= alpha

    np.testing.assert_array_equal(
        our_result.significant,
        scipy_significant,
        err_msg="BH significant mask differs from scipy reference",
    )
    np.testing.assert_allclose(
        our_result.adjusted_p_values,
        scipy_adjusted,
        rtol=1e-10,
        err_msg="BH adjusted p-values differ from scipy reference",
    )


def test_bh_small_known_example() -> None:
    """Hand-verified 5-test example from BH (1995) Table 1.

    p-values (sorted): 0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344, 0.0459
    At alpha=0.05 with m=9, BH rejects the first 4 (thresholds: k/9 * 0.05).
    Using a simplified 5-test subset for a cleaner hand-check.
    """
    # 5 tests; alpha = 0.05; thresholds: 0.01, 0.02, 0.03, 0.04, 0.05
    p = np.array([0.005, 0.009, 0.035, 0.041, 0.060])
    result = benjamini_hochberg(p, alpha=0.05)
    # p_(1)=0.005 ≤ 1/5*0.05=0.010 → significant
    # p_(2)=0.009 ≤ 2/5*0.05=0.020 → significant
    # p_(3)=0.035 ≤ 3/5*0.05=0.030? No (0.035 > 0.030) → not significant
    # But BH is step-up: reject all up to max k that satisfies the threshold.
    # Max k satisfied: k=2.  So only first 2 rejected.
    assert result.n_significant == 2
    assert result.significant[0]   # p=0.005
    assert result.significant[1]   # p=0.009
    assert not result.significant[2]  # p=0.035
    assert not result.significant[3]  # p=0.041
    assert not result.significant[4]  # p=0.060


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


def test_bh_all_null() -> None:
    """Uniform p-values on [0,1] — BH should reject very few at alpha=0.05.

    On average, FDR control means at most 5% of the (zero) true positives
    are rejected.  For uniform nulls, the expected number of rejections is 0.
    With finite samples and random seeds, a small number may sneak through.
    We allow at most 5 (5%) rejections out of 100 as a generous tolerance.
    """
    rng = np.random.default_rng(42)
    p = rng.uniform(0.0, 1.0, 100)
    result = benjamini_hochberg(p, alpha=0.05)
    # BH controls the expected FDR; in practice, rejections are very rare
    # for purely uniform p-values with no signal.
    assert result.n_significant <= 5, (
        f"Expected ≤5 rejections for all-null input; got {result.n_significant}"
    )


def test_bh_all_significant() -> None:
    """All tiny p-values — BH rejects all of them."""
    p = np.full(50, 1e-10)
    result = benjamini_hochberg(p, alpha=0.05)
    assert result.n_significant == 50
    assert result.significant.all()


def test_bh_single_p_value() -> None:
    """Single p-value below alpha → rejected; above → not."""
    result_sig = benjamini_hochberg(np.array([0.01]), alpha=0.05)
    assert result_sig.n_significant == 1

    result_not = benjamini_hochberg(np.array([0.10]), alpha=0.05)
    assert result_not.n_significant == 0


# ---------------------------------------------------------------------------
# Mixed signal/null: BH recovers most true positives
# ---------------------------------------------------------------------------


def test_bh_mixed_recovers_true_positives() -> None:
    """10 signal + 90 null — BH recovers most of the 10 at FDR 0.05.

    True signals have p ~ Uniform(0, 0.001); null have p ~ Uniform(0, 1).
    With this separation BH should identify at least 8 of the 10 signals.
    """
    n_signal = 10
    p = _make_mixed(n_signal=n_signal, n_null=90, seed=42)
    result = benjamini_hochberg(p, alpha=0.05)

    # True positives are the first n_signal entries (by construction).
    true_positive_mask = np.zeros(len(p), dtype=bool)
    true_positive_mask[:n_signal] = True

    tp = int((result.significant & true_positive_mask).sum())
    fp = int((result.significant & ~true_positive_mask).sum())

    assert tp >= 8, f"Expected ≥8 true positives recovered; got {tp}"
    assert fp <= 3, f"Expected ≤3 false positives; got {fp}"


def test_bh_more_powerful_than_bonferroni() -> None:
    """BH rejects at least as many tests as Bonferroni at the same alpha.

    Bonferroni: reject if p ≤ alpha/m.  BH controls FDR at the same alpha
    level but is uniformly more powerful (more rejections).
    """
    p = _make_mixed(n_signal=15, n_null=85, seed=99)
    alpha = 0.05
    m = len(p)

    bh_result = benjamini_hochberg(p, alpha=alpha)
    bonferroni_significant = (p <= alpha / m).sum()

    assert bh_result.n_significant >= bonferroni_significant, (
        f"BH ({bh_result.n_significant}) should be ≥ Bonferroni ({bonferroni_significant})"
    )


def test_bh_adjusted_p_values_monotone() -> None:
    """Adjusted p-values must be non-decreasing when sorted by raw p-value."""
    p = _make_mixed(seed=7)
    result = benjamini_hochberg(p)
    sorted_adj = result.adjusted_p_values[np.argsort(p)]
    # Each step must be non-decreasing (monotonicity of BH adjustment).
    diffs = np.diff(sorted_adj)
    assert (diffs >= -1e-12).all(), (
        f"Adjusted p-values not monotone; min diff = {diffs.min():.2e}"
    )
