"""Hurst exponent tests — DFA method (session 27+).

DFA (Detrended Fluctuation Analysis) replaced R/S in session 27 because R/S
misclassified AR(1) φ=0.5 (positive-φ OU, typical VWAP-spread behaviour) as
TRENDING (H > 0.55).  DFA gives H ≈ 0.5 for the same series — still technically
RANDOM_WALK, but no longer TRENDING.

The composite classification was simultaneously fixed (Option A): ADF + OU
half-life are now the primary TRADEABLE_MR gates.  Hurst RANDOM_WALK no longer
blocks TRADEABLE_MR.  Hurst TRENDING still flags INDETERMINATE (ADF contradiction).

DFA correctly gives H < 0.45 for strongly anti-persistent series (AR(1) φ < 0),
which R/S also handled.  The meaningful win over R/S is for positive-φ OU:
R/S → TRENDING (worst misclassification); DFA → RANDOM_WALK (not blocking with
the Option A composite).

Reference: design doc §2.2, §4.2, §8.2.  Tolerances ±0.10 per §8.2.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trading_research.stats.stationarity import HurstResult, _rs_hurst, dfa_hurst, hurst_exponent

N = 2000  # longer series for more stable Hurst estimates


def _white_noise(n: int = N) -> pd.Series:
    """i.i.d. N(0,1) — random-walk returns. Theoretical H = 0.5 under DFA."""
    return pd.Series(np.random.default_rng(42).standard_normal(n))


def _random_walk(n: int = N) -> pd.Series:
    """Cumulative sum of white noise — I(1) price level. DFA gives H ≈ 1.0."""
    return pd.Series(np.cumsum(np.random.default_rng(42).standard_normal(n)))


def _ar1(phi: float, n: int = N) -> pd.Series:
    """AR(1): y_t = phi * y_{t-1} + ε_t.

    phi < 0 → anti-persistent (oscillating). DFA gives H < 0.5.
    phi > 0 → positive autocorrelation (slow OU / VWAP spread).
              DFA gives H ≈ 0.5 for short-memory processes (|phi| << 1).
    """
    rng = np.random.default_rng(42)
    eps = rng.standard_normal(n)
    y = np.empty(n)
    y[0] = eps[0]
    for t in range(1, n):
        y[t] = phi * y[t - 1] + eps[t]
    return pd.Series(y)


def _trending(n: int = N) -> pd.Series:
    """Cumulative sum with positive drift. H > 0.55."""
    rng = np.random.default_rng(42)
    steps = rng.standard_normal(n) + 0.3
    return pd.Series(np.cumsum(steps))


# ---------------------------------------------------------------------------
# Basic type and validity tests
# ---------------------------------------------------------------------------


def test_hurst_returns_correct_type() -> None:
    result = hurst_exponent(_white_noise())
    assert isinstance(result, HurstResult)


def test_hurst_r_squared_positive() -> None:
    result = hurst_exponent(_white_noise())
    assert result.r_squared >= 0.0


def test_hurst_n_windows_positive() -> None:
    result = hurst_exponent(_random_walk())
    assert result.n_windows >= 2


def test_hurst_insufficient_data() -> None:
    """Series shorter than HURST_MIN_OBS (32) should return NaN."""
    short = pd.Series(np.random.default_rng(42).standard_normal(20))
    result = hurst_exponent(short)
    assert math.isnan(result.exponent)
    assert result.interpretation == "INSUFFICIENT_DATA"


def test_hurst_nan_dropped() -> None:
    """NaNs in input must be dropped without error."""
    rng = np.random.default_rng(42)
    arr = rng.standard_normal(N).copy()
    arr[::20] = float("nan")
    result = hurst_exponent(pd.Series(arr))
    assert isinstance(result.exponent, float)


# ---------------------------------------------------------------------------
# DFA behavioural tests
# ---------------------------------------------------------------------------


def test_hurst_brownian_motion() -> None:
    """White noise (i.i.d. returns) — DFA gives H ≈ 0.5 (within ±0.10)."""
    result = hurst_exponent(_white_noise())
    h = result.exponent
    assert 0.40 <= h <= 0.60, f"White noise Hurst={h:.4f}, expected [0.40, 0.60]"


def test_hurst_trending_series() -> None:
    """Cumulative sum with drift — DFA gives H > 0.55."""
    result = hurst_exponent(_trending())
    h = result.exponent
    assert h > 0.55, f"Trending series Hurst={h:.4f}, expected > 0.55"
    assert "TRENDING" in result.interpretation


def test_hurst_mean_reverting_series() -> None:
    """AR(1) φ=-0.7 (strongly anti-persistent) — DFA gives H < 0.40.

    Negative-φ AR(1) processes have strong negative lag-1 autocorrelation
    that survives DFA's integration step.  This is the regime where DFA
    gives a clean MEAN_REVERTING signal.
    """
    result = hurst_exponent(_ar1(-0.7))
    h = result.exponent
    assert h < 0.40, f"AR(1) φ=-0.7 DFA Hurst={h:.4f}, expected < 0.40"
    assert "MEAN_REVERTING" in result.interpretation


def test_hurst_ar1_positive_phi_documented_behaviour() -> None:
    """AR(1) φ=0.5 (slow OU / VWAP spread) — DFA gives H ≈ 0.5 (RANDOM_WALK).

    This documents the known limitation of DFA-1 for short-memory stationary
    processes with positive autocorrelation: the correlation length (~1.4 bars
    for φ=0.5) is far below all usable window sizes, so the integrated series
    appears indistinguishable from a random walk at those scales.

    The composite classification handles this via Option A (session 27):
    ADF stationarity + tradeable OU half-life → TRADEABLE_MR regardless of
    whether Hurst reports RANDOM_WALK.  This test documents expected behaviour,
    not a defect.
    """
    result = hurst_exponent(_ar1(0.5))
    h = result.exponent
    # DFA gives H close to 0.5 for short-memory positive-φ AR(1).
    # Must NOT be classified as TRENDING (that was the R/S defect).
    assert h <= 0.55, (
        f"AR(1) φ=0.5 DFA Hurst={h:.4f}: should not be TRENDING. "
        "If H > 0.55, DFA is incorrectly producing the R/S defect."
    )
    assert "TRENDING" not in result.interpretation, (
        f"AR(1) φ=0.5 must not be TRENDING; got '{result.interpretation}'"
    )


# ---------------------------------------------------------------------------
# Regression test: DFA vs R/S comparison
# ---------------------------------------------------------------------------


def test_dfa_vs_rs_comparison() -> None:
    """For AR(1) φ=0.5, R/S gives H > 0.55 (TRENDING); DFA gives H ≤ 0.55 (not TRENDING).

    This documents the improvement that motivated the session 27 switch:
    R/S misclassified positive-φ OU as TRENDING, which blocked composite
    TRADEABLE_MR classification entirely.  DFA gives RANDOM_WALK (H ≈ 0.5),
    which with the Option A composite fix allows TRADEABLE_MR when ADF and OU
    half-life agree.
    """
    series = _ar1(0.5, n=N)
    arr = np.asarray(series.dropna(), dtype=float)

    dfa_result = dfa_hurst(series)
    rs_result = _rs_hurst(arr, min_window=10, max_window=len(arr) // 2)

    # R/S defect: classifies positive-φ OU as TRENDING.
    assert rs_result.exponent > 0.55, (
        f"R/S should give H > 0.55 for AR(1) φ=0.5 (the old TRENDING defect); "
        f"got {rs_result.exponent:.4f}"
    )
    # DFA improvement: does not classify it as TRENDING.
    assert dfa_result.exponent <= 0.55, (
        f"DFA should give H ≤ 0.55 for AR(1) φ=0.5 (not TRENDING); "
        f"got {dfa_result.exponent:.4f}"
    )
