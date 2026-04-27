"""Bootstrap confidence intervals for backtest performance metrics.

Resamples the trade-level net_pnl_usd with replacement to estimate the
sampling distribution of each metric. Returns 5th and 95th percentiles
as 90% confidence intervals.

Usage
-----
    from trading_research.eval.bootstrap import bootstrap_summary
    from trading_research.eval.summary import compute_summary

    point = compute_summary(result)
    cis = bootstrap_summary(result, n_samples=1000, seed=42)

    # cis["calmar_ci"] == (p5, p95)

The data scientist note: CI width matters more than the point estimate.
A Calmar of 1.8 with CI [0.9, 2.7] is evidence of edge. A Calmar of 1.8
with CI [-0.1, 3.6] is noise — statistically indistinguishable from zero.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from trading_research.utils import stats as _stats

if TYPE_CHECKING:
    from trading_research.backtest.engine import BacktestResult

# Metrics we bootstrap (must be present in compute_summary output).
_METRICS_TO_BOOTSTRAP = [
    "sharpe",
    "calmar",
    "win_rate",
    "expectancy_usd",
    "profit_factor",
    "sortino",
]


def bootstrap_summary(
    result: "BacktestResult",
    n_samples: int = 1000,
    seed: int | None = 42,
) -> dict[str, tuple[float, float]]:
    """Return 90% CIs for key metrics via trade-level bootstrapping.

    Parameters
    ----------
    result:    BacktestResult from the engine.
    n_samples: Number of bootstrap samples (default 1000; use 5000 for
               publication-quality estimates, 500 for quick iteration).
    seed:      RNG seed for reproducibility. Pass None for unseeded.

    Returns
    -------
    Dict mapping metric names to (p5, p95) tuples.
    Keys: ``{metric}_ci`` for each metric in ``_METRICS_TO_BOOTSTRAP``.
    Returns all-NaN CIs when trade count < 10 (too few to resample).
    """
    trades = result.trades
    if trades.empty or len(trades) < 10:
        return {f"{m}_ci": (float("nan"), float("nan")) for m in _METRICS_TO_BOOTSTRAP}

    rng = np.random.default_rng(seed)
    n_trades = len(trades)

    # Pre-extract arrays used repeatedly across samples.
    net_pnl = trades["net_pnl_usd"].values.astype(float)
    exit_ts = pd.to_datetime(trades["exit_ts"])
    entry_ts = pd.to_datetime(trades["entry_ts"])

    span_days = (exit_ts.max() - entry_ts.min()).days
    if span_days <= 0:
        span_days = 1

    # Collect per-sample metric values.
    sample_values: dict[str, list[float]] = {m: [] for m in _METRICS_TO_BOOTSTRAP}

    for _ in range(n_samples):
        idx = rng.integers(0, n_trades, size=n_trades)
        sample_pnl = net_pnl[idx]

        sample_values["win_rate"].append(_win_rate(sample_pnl))
        sample_values["expectancy_usd"].append(float(np.mean(sample_pnl)))
        sample_values["profit_factor"].append(_profit_factor(sample_pnl))
        sample_values["sharpe"].append(_sharpe(sample_pnl))
        sample_values["sortino"].append(_sortino(sample_pnl))
        sample_values["calmar"].append(_calmar(sample_pnl, span_days))

    cis: dict[str, tuple[float, float]] = {}
    for metric, values in sample_values.items():
        arr = np.array(values, dtype=float)
        finite = arr[np.isfinite(arr)]
        if len(finite) < 10:
            cis[f"{metric}_ci"] = (float("nan"), float("nan"))
        else:
            cis[f"{metric}_ci"] = (
                float(np.percentile(finite, 5)),
                float(np.percentile(finite, 95)),
            )

    return cis


def format_with_ci(
    summary: dict,
    cis: dict[str, tuple[float, float]],
) -> str:
    """Return a summary table with CIs printed alongside point estimates."""
    lines = [
        "=" * 64,
        "  Backtest Performance Summary (with 90% bootstrap CI)",
        "=" * 64,
    ]

    def _fmt_val(v: object) -> str:
        if isinstance(v, float) and math.isnan(v):
            return "     N/A"
        if isinstance(v, float):
            return f"{v:>8.2f}"
        return f"{v:>8}"

    def _fmt_ci(ci: tuple[float, float] | None) -> str:
        if ci is None:
            return ""
        lo, hi = ci
        if math.isnan(lo) or math.isnan(hi):
            return "  CI: [N/A, N/A]"
        return f"  CI: [{lo:.2f}, {hi:.2f}]"

    rows = [
        ("Total trades",         summary.get("total_trades"),          None),
        ("Win rate",              summary.get("win_rate"),              cis.get("win_rate_ci")),
        ("Avg win (USD)",         summary.get("avg_win_usd"),           None),
        ("Avg loss (USD)",        summary.get("avg_loss_usd"),          None),
        ("Profit factor",         summary.get("profit_factor"),         cis.get("profit_factor_ci")),
        ("Expectancy (USD)",      summary.get("expectancy_usd"),        cis.get("expectancy_usd_ci")),
        ("Trades / week",         summary.get("trades_per_week"),       None),
        ("Max consec. losses",    summary.get("max_consec_losses"),     None),
        ("Sharpe (ann.)",         summary.get("sharpe"),                cis.get("sharpe_ci")),
        ("Sortino (ann.)",        summary.get("sortino"),               cis.get("sortino_ci")),
        ("Calmar  [headline]",    summary.get("calmar"),                cis.get("calmar_ci")),
        ("Max drawdown (USD)",    summary.get("max_drawdown_usd"),      None),
        ("Max drawdown (%)",      summary.get("max_drawdown_pct"),      None),
        ("Drawdown duration (d)", summary.get("drawdown_duration_days"),None),
        ("Avg MAE (pts)",         summary.get("avg_mae_points"),        None),
        ("Avg MFE (pts)",         summary.get("avg_mfe_points"),        None),
    ]

    for label, val, ci in rows:
        if isinstance(val, float) and not math.isnan(val) and abs(val) < 1 and label == "Win rate":
            val_str = f"  {val:.1%}"
            lines.append(f"  {label:<28} {val_str:>10}{_fmt_ci(ci)}")
        elif isinstance(val, float) and not math.isnan(val) and label == "Max drawdown (%)":
            val_str = f"  {val:.1%}"
            lines.append(f"  {label:<28} {val_str:>10}{_fmt_ci(ci)}")
        else:
            lines.append(f"  {label:<28} {_fmt_val(val)}{_fmt_ci(ci)}")

    lines.append("=" * 64)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Thin wrappers that delegate to utils/stats (single source of truth).
# ---------------------------------------------------------------------------

_TRADING_DAYS = 252


def _win_rate(pnl: np.ndarray) -> float:
    return _stats.win_rate(pnl)


def _profit_factor(pnl: np.ndarray) -> float:
    return _stats.profit_factor(pnl)


def _sharpe(pnl: np.ndarray) -> float:
    return _stats.annualised_sharpe(pnl, trading_days=_TRADING_DAYS)


def _sortino(pnl: np.ndarray) -> float:
    return _stats.annualised_sortino(pnl, trading_days=_TRADING_DAYS)


def _calmar(pnl: np.ndarray, span_days: int) -> float:
    return _stats.calmar(pnl, span_days, trading_days=_TRADING_DAYS)
