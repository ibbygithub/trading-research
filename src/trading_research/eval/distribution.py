"""Return distribution diagnostics for the Risk Officer's view.

All functions return plain Python dicts or DataFrames with plot-ready data.
No I/O, no side effects.

The Jarque-Bera test will almost always reject normality for mean-reversion
strategy returns.  The report section that uses these functions flags this
clearly and redirects to Sortino/Calmar as the primary metric.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def return_distribution_stats(returns: np.ndarray | pd.Series) -> dict:
    """Compute summary statistics of the return distribution.

    Parameters
    ----------
    returns: Trade-level or daily P&L values.

    Returns
    -------
    Dict with:
        count, mean, std, min, max, median,
        skewness, kurtosis (excess), excess_kurtosis (same as kurtosis),
        jb_stat, jb_pvalue, normality_flag (bool: True = not normal),
        normality_warning (str for display).
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = len(returns)

    if n < 4:
        return {
            "count": n,
            "mean": float("nan"),
            "std": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "median": float("nan"),
            "skewness": float("nan"),
            "kurtosis": float("nan"),
            "excess_kurtosis": float("nan"),
            "jb_stat": float("nan"),
            "jb_pvalue": float("nan"),
            "normality_flag": False,
            "normality_warning": "Insufficient data (< 4 observations).",
        }

    skew = float(scipy_stats.skew(returns))
    # scipy kurtosis is excess kurtosis (normal = 0).
    kurt = float(scipy_stats.kurtosis(returns))
    jb_stat, jb_pvalue = scipy_stats.jarque_bera(returns)

    normality_flag = bool(jb_pvalue < 0.05)
    if normality_flag:
        normality_warning = (
            "Return distribution is non-normal (Jarque-Bera p={:.4f}). "
            "Sharpe understates the true risk. "
            "Use Sortino, Calmar, or MAR as the primary metric.".format(jb_pvalue)
        )
    else:
        normality_warning = "Return distribution does not reject normality (p={:.4f}).".format(jb_pvalue)

    return {
        "count": n,
        "mean": float(np.mean(returns)),
        "std": float(np.std(returns, ddof=1)),
        "min": float(np.min(returns)),
        "max": float(np.max(returns)),
        "median": float(np.median(returns)),
        "skewness": skew,
        "kurtosis": kurt,
        "excess_kurtosis": kurt,  # alias for clarity
        "jb_stat": float(jb_stat),
        "jb_pvalue": float(jb_pvalue),
        "normality_flag": normality_flag,
        "normality_warning": normality_warning,
    }


def qq_plot_data(returns: np.ndarray | pd.Series) -> dict:
    """Compute QQ plot coordinates vs normal distribution.

    Returns
    -------
    Dict with:
        theoretical_quantiles (array): Normal distribution quantiles.
        sample_quantiles (array):      Sorted sample values.
        fit_line_x (array):            x-coords of the reference line.
        fit_line_y (array):            y-coords of the reference line.
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 4:
        return {
            "theoretical_quantiles": np.array([]),
            "sample_quantiles": np.array([]),
            "fit_line_x": np.array([]),
            "fit_line_y": np.array([]),
        }

    sorted_returns = np.sort(returns)
    n = len(sorted_returns)
    # Theoretical quantiles from standard normal.
    theoretical = scipy_stats.norm.ppf(np.linspace(1 / (n + 1), n / (n + 1), n))

    # Reference line through first and third quartiles.
    q25, q75 = float(np.percentile(sorted_returns, 25)), float(np.percentile(sorted_returns, 75))
    tq25, tq75 = float(scipy_stats.norm.ppf(0.25)), float(scipy_stats.norm.ppf(0.75))
    slope = (q75 - q25) / (tq75 - tq25) if (tq75 - tq25) != 0 else 1.0
    intercept = q25 - slope * tq25

    line_x = np.array([float(theoretical[0]), float(theoretical[-1])])
    line_y = intercept + slope * line_x

    return {
        "theoretical_quantiles": theoretical,
        "sample_quantiles": sorted_returns,
        "fit_line_x": line_x,
        "fit_line_y": line_y,
    }


def autocorrelation_data(
    returns: np.ndarray | pd.Series,
    max_lags: int = 20,
) -> dict:
    """Compute autocorrelation of returns at lags 1..max_lags.

    Parameters
    ----------
    returns:  Trade-level or daily P&L values.
    max_lags: Maximum lag to compute (default 20).

    Returns
    -------
    Dict with:
        lags (array):          Lag integers 1..max_lags.
        acf (array):           Autocorrelation at each lag.
        ljung_box_stat (float): Ljung-Box Q statistic.
        ljung_box_pvalue (float): p-value (low = serial correlation present).
        serial_correlation_flag (bool): True when p < 0.05.
        confidence_bounds (float): ±1.96/sqrt(n) — 95% CI for white noise.
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = len(returns)

    if n < max_lags + 5:
        empty = np.full(max_lags, float("nan"))
        return {
            "lags": np.arange(1, max_lags + 1),
            "acf": empty,
            "ljung_box_stat": float("nan"),
            "ljung_box_pvalue": float("nan"),
            "serial_correlation_flag": False,
            "confidence_bounds": float("nan"),
        }

    # Full ACF including lag 0 (= 1.0), then slice lags 1..max_lags.
    acf_full = _acf(returns, max_lags)
    acf_values = acf_full[1 : max_lags + 1]

    # Ljung-Box using scipy.
    lb_result = scipy_stats.acf_ljungbox_test(returns, lags=max_lags) if False else None
    # Use manual Ljung-Box since scipy doesn't have a clean 1-liner here.
    lb_stat, lb_pvalue = _ljung_box(returns, acf_values, max_lags)

    confidence = 1.96 / math.sqrt(n)

    return {
        "lags": np.arange(1, max_lags + 1),
        "acf": acf_values,
        "ljung_box_stat": lb_stat,
        "ljung_box_pvalue": lb_pvalue,
        "serial_correlation_flag": bool(lb_pvalue < 0.05),
        "confidence_bounds": confidence,
    }


def daily_acf_data(
    trades: pd.DataFrame,
    max_lags: int = 20,
) -> dict:
    """Compute autocorrelation of daily P&L aggregated from trades.

    Parameters
    ----------
    trades:   Trade log DataFrame with 'net_pnl_usd' and 'exit_ts'.
    max_lags: Maximum lag.

    Returns same structure as autocorrelation_data().
    """
    if trades.empty or "net_pnl_usd" not in trades.columns:
        return autocorrelation_data(np.array([]), max_lags)

    daily = trades.copy()
    daily["exit_date"] = pd.to_datetime(daily["exit_ts"]).dt.date
    daily_pnl = daily.groupby("exit_date")["net_pnl_usd"].sum().values
    return autocorrelation_data(daily_pnl.astype(float), max_lags)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _acf(x: np.ndarray, max_lags: int) -> np.ndarray:
    """Compute ACF at lags 0..max_lags."""
    n = len(x)
    x_centered = x - np.mean(x)
    var = np.dot(x_centered, x_centered) / n
    if var == 0:
        return np.zeros(max_lags + 1)
    result = []
    for lag in range(max_lags + 1):
        if lag == 0:
            result.append(1.0)
        else:
            cov = np.dot(x_centered[lag:], x_centered[:-lag]) / n
            result.append(cov / var)
    return np.array(result)


def _ljung_box(x: np.ndarray, acf_values: np.ndarray, max_lags: int) -> tuple[float, float]:
    """Ljung-Box Q statistic and p-value."""
    n = len(x)
    q = 0.0
    for k in range(1, max_lags + 1):
        rk = acf_values[k - 1]
        if math.isfinite(rk):
            q += (rk**2) / (n - k)
    q *= n * (n + 2)
    pvalue = 1.0 - float(scipy_stats.chi2.cdf(q, df=max_lags))
    return float(q), pvalue
