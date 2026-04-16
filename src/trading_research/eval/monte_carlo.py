"""Monte Carlo trade-order shuffle for the Risk Officer's view.

Resamples the *order* of trades (preserving individual P&Ls) to measure
how much of the historical equity path was luck vs structural edge.

The key insight: if the actual max drawdown is at the 90th percentile of
shuffle outcomes, the historical sequence was lucky and the true expected
drawdown is worse than the backtest suggests.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def shuffle_trade_order(
    trades: pd.DataFrame,
    n_iter: int = 1000,
    seed: int = 42,
) -> dict:
    """Resample trade order and compute the distribution of key metrics.

    Parameters
    ----------
    trades:  Trade log with 'net_pnl_usd' column.
    n_iter:  Number of Monte Carlo iterations.
    seed:    RNG seed for reproducibility.

    Returns
    -------
    Dict with:
        equity_curves (np.ndarray):  Shape (n_iter, n_trades). Each row is
                                     the cumulative equity path for one shuffle.
        max_dd_dist (np.ndarray):    Max drawdown (absolute, positive) per shuffle.
        final_pnl_dist (np.ndarray): Final P&L per shuffle.
        calmar_dist (np.ndarray):    Calmar ratio per shuffle.
        actual_max_dd (float):       Observed max drawdown from the original sequence.
        actual_final_pnl (float):    Observed final P&L.
        actual_calmar (float):       Observed Calmar.
        actual_max_dd_pctile (float): Percentile of actual max DD in shuffle dist.
        actual_calmar_pctile (float): Percentile of actual Calmar in shuffle dist.
        n_trades (int):              Number of trades.
        n_iter (int):                Number of iterations actually run.
        interpretation (str):        Human-readable interpretation of percentiles.
    """
    if trades.empty or "net_pnl_usd" not in trades.columns:
        return _empty_mc_result()

    pnl = trades["net_pnl_usd"].values.astype(float)
    pnl = pnl[np.isfinite(pnl)]
    n = len(pnl)

    if n < 5:
        return _empty_mc_result()

    rng = np.random.default_rng(seed)

    # Actual metrics from original sequence.
    actual_equity = np.cumsum(pnl)
    actual_max_dd = _max_drawdown(actual_equity)
    actual_final_pnl = float(actual_equity[-1])
    actual_calmar = _calmar(actual_equity)

    # Monte Carlo shuffles.
    equity_curves = np.empty((n_iter, n), dtype=float)
    max_dd_dist = np.empty(n_iter, dtype=float)
    final_pnl_dist = np.empty(n_iter, dtype=float)
    calmar_dist = np.empty(n_iter, dtype=float)

    for i in range(n_iter):
        shuffled = rng.permutation(pnl)
        eq = np.cumsum(shuffled)
        equity_curves[i] = eq
        max_dd_dist[i] = _max_drawdown(eq)
        final_pnl_dist[i] = float(eq[-1])
        calmar_dist[i] = _calmar(eq)

    # Percentiles of actual values in shuffle distributions.
    finite_dd = max_dd_dist[np.isfinite(max_dd_dist)]
    finite_calmar = calmar_dist[np.isfinite(calmar_dist)]

    actual_dd_pctile = (
        float(np.mean(finite_dd <= actual_max_dd) * 100)
        if len(finite_dd) > 0 else float("nan")
    )
    actual_calmar_pctile = (
        float(np.mean(finite_calmar <= actual_calmar) * 100)
        if len(finite_calmar) > 0 else float("nan")
    )

    interpretation = _interpret(actual_dd_pctile, actual_calmar_pctile)

    return {
        "equity_curves": equity_curves,
        "max_dd_dist": max_dd_dist,
        "final_pnl_dist": final_pnl_dist,
        "calmar_dist": calmar_dist,
        "actual_max_dd": actual_max_dd,
        "actual_final_pnl": actual_final_pnl,
        "actual_calmar": actual_calmar,
        "actual_max_dd_pctile": actual_dd_pctile,
        "actual_calmar_pctile": actual_calmar_pctile,
        "n_trades": n,
        "n_iter": n_iter,
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _max_drawdown(equity: np.ndarray) -> float:
    """Max drawdown in absolute terms (positive number)."""
    if len(equity) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity)
    dd = running_max - equity
    return float(np.max(dd))


def _calmar(equity: np.ndarray) -> float:
    """Calmar = annualised return / max drawdown.

    Uses bar count as a rough proxy for time (assumes each bar ~5 min;
    252 trading days * 78 bars/day ≈ 19,656 bars/year for 5m data).
    For Monte Carlo purposes the exact value matters less than the
    relative ranking across shuffles.
    """
    if len(equity) == 0:
        return float("nan")
    mdd = _max_drawdown(equity)
    if mdd == 0:
        return float("nan")
    total_pnl = float(equity[-1])
    # Rough annualisation: assume each trade ≈ 1 observation, 252 per year.
    n = len(equity)
    annual_return = total_pnl / n * 252
    return annual_return / mdd


def _interpret(dd_pctile: float, calmar_pctile: float) -> str:
    """Human-readable interpretation of Monte Carlo percentiles."""
    if not math.isfinite(dd_pctile) or not math.isfinite(calmar_pctile):
        return "Insufficient data for interpretation."

    parts = []
    if dd_pctile >= 80:
        parts.append(
            f"The actual max drawdown is at the {dd_pctile:.0f}th percentile of shuffle "
            "outcomes — the historical sequence was lucky. The true expected drawdown "
            "is likely worse than the backtest showed."
        )
    elif dd_pctile <= 20:
        parts.append(
            f"The actual max drawdown is at the {dd_pctile:.0f}th percentile of shuffle "
            "outcomes — the historical sequence drew a harder path than typical. "
            "The strategy may have more favourable dynamics than the backtest showed."
        )
    else:
        parts.append(
            f"The actual max drawdown is at the {dd_pctile:.0f}th percentile of shuffle "
            "outcomes — the historical sequence is near the median and does not indicate "
            "unusual luck or misfortune."
        )

    if calmar_pctile >= 70:
        parts.append(
            f"The actual Calmar is at the {calmar_pctile:.0f}th percentile — "
            "the trade clustering in the historical sequence may have inflated the "
            "apparent risk-adjusted return."
        )

    return " ".join(parts)


def _empty_mc_result() -> dict:
    return {
        "equity_curves": np.empty((0, 0)),
        "max_dd_dist": np.array([]),
        "final_pnl_dist": np.array([]),
        "calmar_dist": np.array([]),
        "actual_max_dd": float("nan"),
        "actual_final_pnl": float("nan"),
        "actual_calmar": float("nan"),
        "actual_max_dd_pctile": float("nan"),
        "actual_calmar_pctile": float("nan"),
        "n_trades": 0,
        "n_iter": 0,
        "interpretation": "No trades available.",
    }
