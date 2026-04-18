"""Performance summary computation.

Takes a BacktestResult and produces a flat dict of metrics.
The headline metric is Calmar; Sharpe is reported but not centred.

All metrics that depend on a time window (Sharpe, Sortino, Calmar,
trades_per_week) are computed from the range [first entry_ts, last exit_ts].
If the trade log is empty, all rate-based metrics are NaN.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from trading_research.utils import stats as _stats

if TYPE_CHECKING:
    from trading_research.backtest.engine import BacktestResult

# Annualisation constants.
_TRADING_DAYS_PER_YEAR = 252
_WEEKS_PER_YEAR = 52


def compute_summary(result: "BacktestResult") -> dict:
    """Compute performance metrics from a BacktestResult.

    Returns a flat dict.  All monetary values are in USD.  Ratios are
    dimensionless.  Duration metrics are in calendar days.
    """
    trades = result.trades
    equity = result.equity_curve

    if trades.empty:
        return _empty_summary()

    net = trades["net_pnl_usd"].values
    n = len(net)
    winners = net[net > 0]
    losers = net[net <= 0]

    total_trades = n
    win_rate = len(winners) / n if n > 0 else float("nan")
    avg_win = float(winners.mean()) if len(winners) > 0 else float("nan")
    avg_loss = float(losers.mean()) if len(losers) > 0 else float("nan")

    gross_wins = float(winners.sum()) if len(winners) > 0 else 0.0
    gross_losses = abs(float(losers.sum())) if len(losers) > 0 else 0.0
    profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else float("inf")
    expectancy = float(net.mean())

    # Time span.
    first_entry = pd.Timestamp(trades["entry_ts"].min())
    last_exit = pd.Timestamp(trades["exit_ts"].max())
    span_days = (last_exit - first_entry).days
    span_weeks = span_days / 7.0 if span_days > 0 else float("nan")
    trades_per_week = total_trades / span_weeks if span_weeks and span_weeks > 0 else float("nan")

    # Max consecutive losses.
    max_consec_losses = _max_consecutive_losses(net)

    # Daily P&L for ratio metrics.
    daily_pnl = _daily_pnl(trades)
    sharpe = _annualised_sharpe(daily_pnl)
    sortino = _annualised_sortino(daily_pnl)

    # Drawdown metrics.
    dd_usd, dd_pct, dd_duration_days = _drawdown_stats(equity)

    # Calmar: annualised return / max drawdown.
    total_net = float(trades["net_pnl_usd"].sum())
    annual_return = (total_net / span_days * _TRADING_DAYS_PER_YEAR) if span_days > 0 else float("nan")
    calmar = (annual_return / abs(dd_usd)) if dd_usd != 0 else float("nan")

    # MAE/MFE.
    avg_mae = float(trades["mae_points"].mean()) if "mae_points" in trades.columns else float("nan")
    avg_mfe = float(trades["mfe_points"].mean()) if "mfe_points" in trades.columns else float("nan")

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "profit_factor": profit_factor,
        "expectancy_usd": expectancy,
        "trades_per_week": trades_per_week,
        "max_consec_losses": max_consec_losses,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown_usd": dd_usd,
        "max_drawdown_pct": dd_pct,
        "drawdown_duration_days": dd_duration_days,
        "avg_mae_points": avg_mae,
        "avg_mfe_points": avg_mfe,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_summary() -> dict:
    keys = [
        "total_trades", "win_rate", "avg_win_usd", "avg_loss_usd",
        "profit_factor", "expectancy_usd", "trades_per_week",
        "max_consec_losses", "sharpe", "sortino", "calmar",
        "max_drawdown_usd", "max_drawdown_pct", "drawdown_duration_days",
        "avg_mae_points", "avg_mfe_points",
    ]
    d = {k: float("nan") for k in keys}
    d["total_trades"] = 0
    d["max_consec_losses"] = 0
    return d


def _max_consecutive_losses(net: np.ndarray) -> int:
    max_streak = 0
    streak = 0
    for v in net:
        if v <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _daily_pnl(trades: pd.DataFrame) -> pd.Series:
    """Aggregate net_pnl_usd by calendar date of exit_ts."""
    daily = trades.copy()
    daily["exit_date"] = pd.to_datetime(daily["exit_ts"]).dt.date
    return daily.groupby("exit_date")["net_pnl_usd"].sum()


def _annualised_sharpe(daily_pnl: pd.Series) -> float:
    return _stats.annualised_sharpe(daily_pnl.values, trading_days=_TRADING_DAYS_PER_YEAR)


def _annualised_sortino(daily_pnl: pd.Series) -> float:
    return _stats.annualised_sortino(daily_pnl.values, trading_days=_TRADING_DAYS_PER_YEAR)


def _drawdown_stats(equity: pd.Series) -> tuple[float, float, int]:
    """Return (max_drawdown_usd, max_drawdown_pct, longest_dd_duration_days).

    All measured on the equity curve (cumulative net P&L).
    """
    if equity.empty:
        return 0.0, 0.0, 0

    peak = equity.cummax()
    drawdown = equity - peak  # negative values

    max_dd_usd = float(drawdown.min())
    # Percentage relative to peak at that point.
    peak_at_max = float(peak[drawdown.idxmin()]) if not drawdown.empty else float("nan")
    if peak_at_max != 0 and not math.isnan(peak_at_max):
        max_dd_pct = max_dd_usd / abs(peak_at_max)
    else:
        max_dd_pct = float("nan")

    # Longest drawdown duration in calendar days.
    dd_duration = _longest_drawdown_duration(equity)

    return max_dd_usd, max_dd_pct, dd_duration


def _longest_drawdown_duration(equity: pd.Series) -> int:
    """Return the number of calendar days in the longest peak-to-recovery period."""
    if equity.empty:
        return 0

    peak = equity.cummax()
    in_dd = equity < peak

    max_days = 0
    start: pd.Timestamp | None = None

    for ts, flag in in_dd.items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            days = (ts - start).days
            max_days = max(max_days, days)
            start = None

    # Still in drawdown at end of series.
    if start is not None:
        days = (equity.index[-1] - start).days
        max_days = max(max_days, days)

    return max_days


def format_summary(summary: dict) -> str:
    """Return a human-readable table of the summary dict."""
    lines = [
        "=" * 50,
        "  Backtest Performance Summary",
        "=" * 50,
    ]

    def _fmt(v: object) -> str:
        if isinstance(v, float):
            if math.isnan(v):
                return "  N/A"
            return f"{v:>10.2f}"
        return f"{v:>10}"

    rows = [
        ("Total trades",          summary.get("total_trades")),
        ("Win rate",               f"{summary.get('win_rate', float('nan')):.1%}" if not math.isnan(summary.get('win_rate', float('nan'))) else "N/A"),
        ("Avg win (USD)",          summary.get("avg_win_usd")),
        ("Avg loss (USD)",         summary.get("avg_loss_usd")),
        ("Profit factor",          summary.get("profit_factor")),
        ("Expectancy (USD)",       summary.get("expectancy_usd")),
        ("Trades / week",          summary.get("trades_per_week")),
        ("Max consec. losses",     summary.get("max_consec_losses")),
        ("Sharpe (ann.)",          summary.get("sharpe")),
        ("Sortino (ann.)",         summary.get("sortino")),
        ("Calmar  [headline]",      summary.get("calmar")),
        ("Max drawdown (USD)",     summary.get("max_drawdown_usd")),
        ("Max drawdown (%)",       f"{summary.get('max_drawdown_pct', float('nan')):.1%}" if not math.isnan(summary.get('max_drawdown_pct', float('nan'))) else "N/A"),
        ("Drawdown duration (d)",  summary.get("drawdown_duration_days")),
        ("Avg MAE (pts)",          summary.get("avg_mae_points")),
        ("Avg MFE (pts)",          summary.get("avg_mfe_points")),
    ]

    for label, val in rows:
        if isinstance(val, str):
            lines.append(f"  {label:<30} {val:>10}")
        else:
            lines.append(f"  {label:<30} {_fmt(val)}")

    lines.append("=" * 50)
    return "\n".join(lines)
