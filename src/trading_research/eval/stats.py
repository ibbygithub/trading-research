"""Statistical metrics for the Risk Officer's view.

All functions are pure (no I/O) and return plain Python scalars or dicts.
Each has a known-answer unit test in tests/test_stats.py.

References
----------
- Lopez de Prado (2014) — Deflated Sharpe Ratio
- Pezier & White (2006) — Omega Ratio
- Bailey & Lopez de Prado (2012) — Probabilistic Sharpe Ratio
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# Generic bootstrap
# ---------------------------------------------------------------------------


def bootstrap_metric(
    values: np.ndarray,
    stat_fn: Callable[[np.ndarray], float],
    n_iter: int = 10_000,
    ci: float = 0.95,
    seed: int | None = 42,
) -> tuple[float, float, float]:
    """Bootstrap a scalar metric.

    Parameters
    ----------
    values:  1-D array of observations.
    stat_fn: Function that takes a 1-D array and returns a float.
    n_iter:  Number of bootstrap iterations.
    ci:      Confidence level (0 < ci < 1).
    seed:    RNG seed (None = unseeded).

    Returns
    -------
    (point_estimate, lo, hi) where lo/hi are the (1-ci)/2 and (1+ci)/2
    percentiles of the bootstrap distribution.
    """
    values = np.asarray(values, dtype=float)
    point = stat_fn(values)

    if len(values) < 2:
        half = (1.0 - ci) / 2
        return point, float("nan"), float("nan")

    rng = np.random.default_rng(seed)
    n = len(values)
    boot_stats: list[float] = []
    for _ in range(n_iter):
        sample = values[rng.integers(0, n, size=n)]
        v = stat_fn(sample)
        if math.isfinite(v):
            boot_stats.append(v)

    if len(boot_stats) < 10:
        return point, float("nan"), float("nan")

    arr = np.array(boot_stats)
    half = (1.0 - ci) / 2
    lo = float(np.percentile(arr, half * 100))
    hi = float(np.percentile(arr, (1 - half) * 100))
    return point, lo, hi


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (Lopez de Prado, 2014)
# ---------------------------------------------------------------------------


def deflated_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    n_trials: int,
    skewness: float,
    kurtosis: float,
) -> float:
    """Compute the Deflated Sharpe Ratio.

    Adjusts the observed Sharpe for multiple-testing bias.  When n_trials
    variants of a strategy are evaluated, the best observed Sharpe is
    biased upward.  DSR converts this to the honest out-of-sample Sharpe.

    Parameters
    ----------
    sharpe:    Observed (best) annualised Sharpe ratio.
    n_obs:     Number of observations (trades or daily P&L points).
    n_trials:  Number of strategy variants that were tested.
    skewness:  Skewness of the return distribution.
    kurtosis:  Excess kurtosis of the return distribution.

    Returns
    -------
    DSR: probability that the *true* Sharpe is positive, accounting for
    the number of trials.  A value of 0.95 means 95% confidence the edge
    is real; 0.5 is indistinguishable from noise.

    Reference: Lopez de Prado (2014), "The Deflated Sharpe Ratio:
    Correcting for Selection Bias, Backtest Overfitting and Non-Normality."
    """
    if n_obs < 4 or n_trials < 1:
        return float("nan")

    # Expected maximum Sharpe from n_trials IID standard-normal draws.
    # Euler-Mascheroni constant γ ≈ 0.5772
    gamma = 0.5772156649

    e_max_sr = (
        (1 - gamma) * scipy_stats.norm.ppf(1 - 1.0 / n_trials)
        + gamma * scipy_stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
        if n_trials > 1
        else 0.0
    )

    # Variance of Sharpe estimator (non-normal correction).
    sr_var = (
        (1 - skewness * sharpe + (kurtosis - 1) / 4.0 * sharpe**2)
        / (n_obs - 1)
    )
    sr_var = max(sr_var, 1e-12)

    z = (sharpe - e_max_sr) / math.sqrt(sr_var)
    return float(scipy_stats.norm.cdf(z))


# ---------------------------------------------------------------------------
# Probabilistic Sharpe Ratio
# ---------------------------------------------------------------------------


def probabilistic_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    skewness: float,
    kurtosis: float,
    sr_benchmark: float = 0.0,
) -> float:
    """Probability that the true Sharpe exceeds *sr_benchmark*.

    Parameters
    ----------
    sharpe:       Observed annualised Sharpe ratio.
    n_obs:        Number of observations.
    skewness:     Skewness of return distribution.
    kurtosis:     Excess kurtosis of return distribution.
    sr_benchmark: Benchmark Sharpe to compare against (default 0).

    Returns
    -------
    Probability ∈ [0, 1] that true SR > sr_benchmark.

    Reference: Bailey & Lopez de Prado (2012).
    """
    if n_obs < 4:
        return float("nan")
    sr_var = (
        (1 - skewness * sharpe + (kurtosis - 1) / 4.0 * sharpe**2)
        / (n_obs - 1)
    )
    sr_var = max(sr_var, 1e-12)
    z = (sharpe - sr_benchmark) / math.sqrt(sr_var)
    return float(scipy_stats.norm.cdf(z))


# ---------------------------------------------------------------------------
# Equity-curve metrics
# ---------------------------------------------------------------------------


def _cagr(equity: pd.Series) -> float:
    """Compound annual growth rate from equity curve (P&L-based, not price-based)."""
    if equity.empty or len(equity) < 2:
        return float("nan")
    span_days = (equity.index[-1] - equity.index[0]).days
    if span_days <= 0:
        return float("nan")
    total_return = float(equity.iloc[-1])
    years = span_days / 365.25
    # CAGR of absolute P&L is just annualised return.
    return total_return / years


def _max_drawdown(equity: pd.Series) -> float:
    """Maximum drawdown in absolute terms (negative number)."""
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = equity - peak
    return float(dd.min())


def mar_ratio(equity: pd.Series) -> float:
    """MAR ratio = CAGR / |max drawdown|.

    Also known as Calmar when drawdown is in dollar terms.
    Identical to the headline Calmar this project computes.
    """
    cagr = _cagr(equity)
    mdd = _max_drawdown(equity)
    if math.isnan(cagr) or mdd == 0:
        return float("nan")
    return cagr / abs(mdd)


def ulcer_index(equity: pd.Series) -> float:
    """Ulcer Index = RMS of percentage drawdowns from running peak.

    Captures drawdown frequency and severity together.
    A lower UI is better.
    """
    if equity.empty:
        return float("nan")
    peak = equity.cummax()
    # Percentage drawdown relative to running peak.
    # For absolute P&L curves the baseline is 0 (starting capital),
    # so we compute relative to the running high-water mark.
    # Guard against zero peaks.
    safe_peak = peak.replace(0, float("nan")).ffill().bfill()
    if safe_peak.isna().all():
        return float("nan")
    pct_dd = ((equity - safe_peak) / safe_peak.abs()).fillna(0.0)
    return float(math.sqrt((pct_dd**2).mean()))


def ulcer_performance_index(equity: pd.Series, rf: float = 0.0) -> float:
    """UPI = (CAGR - rf) / UI.

    The UPI is a pain-adjusted return metric.  Higher is better.
    """
    ui = ulcer_index(equity)
    if math.isnan(ui) or ui == 0:
        return float("nan")
    cagr = _cagr(equity)
    if math.isnan(cagr):
        return float("nan")
    return (cagr - rf) / ui


def recovery_factor(equity: pd.Series) -> float:
    """Recovery Factor = net profit / |max drawdown|.

    A dimensionless ratio showing how many times the max drawdown the
    strategy earns back in total profit.  Higher is better.
    """
    if equity.empty:
        return float("nan")
    net_profit = float(equity.iloc[-1])
    mdd = _max_drawdown(equity)
    if mdd == 0:
        return float("nan")
    return net_profit / abs(mdd)


def pain_ratio(equity: pd.Series) -> float:
    """Pain Ratio = CAGR / average drawdown.

    The average drawdown is the mean of all percentage drawdowns from
    the running peak.  Pain Ratio is similar to UPI but uses mean
    rather than RMS — slightly less punishing on deep single events.
    """
    if equity.empty:
        return float("nan")
    peak = equity.cummax()
    safe_peak = peak.replace(0, float("nan")).ffill().bfill()
    if safe_peak.isna().all():
        return float("nan")
    pct_dd = ((equity - safe_peak) / safe_peak.abs()).fillna(0.0)
    avg_dd = float(pct_dd.mean())
    if avg_dd == 0:
        return float("nan")
    cagr = _cagr(equity)
    if math.isnan(cagr):
        return float("nan")
    # avg_dd is negative; take absolute value so ratio is positive when CAGR > 0.
    return cagr / abs(avg_dd)


# ---------------------------------------------------------------------------
# Return-distribution metrics
# ---------------------------------------------------------------------------


def tail_ratio(returns: np.ndarray, pct: float = 0.95) -> float:
    """Tail Ratio = |p_{pct}| / |p_{1-pct}|.

    Measures the relative size of the right tail to the left tail.
    A tail ratio > 1 means wins are larger than losses at the extremes.
    Default: 95th percentile (right) vs 5th percentile (left).
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 10:
        return float("nan")
    right = abs(float(np.percentile(returns, pct * 100)))
    left = abs(float(np.percentile(returns, (1 - pct) * 100)))
    if left == 0:
        return float("nan")
    return right / left


def omega_ratio(returns: np.ndarray, threshold: float = 0.0) -> float:
    """Omega Ratio = sum(gains above threshold) / sum(losses below threshold).

    Unlike Sharpe, Omega uses the full return distribution without
    assuming normality.  Omega > 1 means more probability-weighted gain
    than loss relative to the threshold.
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 2:
        return float("nan")
    gains = returns[returns > threshold] - threshold
    losses = threshold - returns[returns < threshold]
    gross_gains = float(gains.sum()) if len(gains) > 0 else 0.0
    gross_losses = float(losses.sum()) if len(losses) > 0 else 0.0
    if gross_losses == 0:
        return float("nan") if gross_gains == 0 else float("inf")
    return gross_gains / gross_losses


def gain_to_pain_ratio(monthly_returns: np.ndarray) -> float:
    """Gain-to-Pain Ratio = sum(positive months) / |sum(negative months)|.

    A simple but robust ratio that measures how much you earn vs how much
    you give back across calendar months.  GPR > 1 means total gains
    exceed total losses in absolute terms.

    Parameters
    ----------
    monthly_returns: 1-D array of monthly P&L or return values.
    """
    monthly_returns = np.asarray(monthly_returns, dtype=float)
    monthly_returns = monthly_returns[np.isfinite(monthly_returns)]
    if len(monthly_returns) < 2:
        return float("nan")
    positives = monthly_returns[monthly_returns > 0]
    negatives = monthly_returns[monthly_returns < 0]
    gross_gain = float(positives.sum()) if len(positives) > 0 else 0.0
    gross_pain = abs(float(negatives.sum())) if len(negatives) > 0 else 0.0
    if gross_pain == 0:
        return float("nan") if gross_gain == 0 else float("inf")
    return gross_gain / gross_pain
