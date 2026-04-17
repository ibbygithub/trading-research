"""Subperiod stability analysis for the Risk Officer's view.

Splits the backtest by year (or other splits) and recomputes headline metrics
per subperiod.  Flags degradation in the most recent subperiod.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd

from trading_research.eval.summary import compute_summary
from trading_research.backtest.engine import BacktestResult


SplitMode = Literal["yearly", "halves", "thirds", "rolling_2y"]


def subperiod_analysis(
    trades: pd.DataFrame,
    equity: pd.Series,
    splits: SplitMode = "yearly",
) -> dict:
    """Compute headline metrics per subperiod.

    Parameters
    ----------
    trades:  Trade log DataFrame (must have 'entry_ts', 'exit_ts', 'net_pnl_usd').
    equity:  Full equity curve (cumulative net_pnl_usd), datetime-indexed.
    splits:  How to split: 'yearly' | 'halves' | 'thirds' | 'rolling_2y'.

    Returns
    -------
    Dict with:
        table (pd.DataFrame): One row per subperiod with metrics.
        degradation_flag (bool): True if most-recent period is worst.
        degradation_message (str): Human-readable warning.
    """
    if trades.empty:
        return {
            "table": pd.DataFrame(),
            "degradation_flag": False,
            "degradation_message": "No trades to analyse.",
        }

    trades = trades.copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"])
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"])

    first = trades["entry_ts"].min()
    last = trades["exit_ts"].max()

    periods = _build_periods(first, last, splits)

    rows = []
    for label, (p_start, p_end) in periods.items():
        mask = (trades["entry_ts"] >= p_start) & (trades["exit_ts"] <= p_end)
        sub_trades = trades[mask].copy()

        if sub_trades.empty:
            rows.append(_empty_period_row(label))
            continue

        # Build a minimal BacktestResult-like object for compute_summary.
        sub_equity = _sub_equity(sub_trades)
        from trading_research.backtest.engine import BacktestConfig, BacktestResult
        dummy_result = BacktestResult(
            trades=sub_trades,
            equity_curve=sub_equity,
            config=BacktestConfig(strategy_id="sub", symbol="ZN"),
            symbol_meta={},
        )
        m = compute_summary(dummy_result)
        rows.append({
            "period": label,
            "trades": m.get("total_trades", 0),
            "win_rate": m.get("win_rate", float("nan")),
            "profit_factor": m.get("profit_factor", float("nan")),
            "sharpe": m.get("sharpe", float("nan")),
            "calmar": m.get("calmar", float("nan")),
            "max_dd_usd": m.get("max_drawdown_usd", float("nan")),
            "expectancy_usd": m.get("expectancy_usd", float("nan")),
        })

    table = pd.DataFrame(rows)

    # Degradation: is the most recent period's Calmar the worst?
    degradation_flag = False
    degradation_message = ""
    if len(table) >= 2:
        calmar_col = table["calmar"].values.astype(float)
        if len(calmar_col) >= 2:
            last_calmar = calmar_col[-1]
            historical = calmar_col[:-1]
            # Treat NaN historical Calmar as +inf (no drawdown = best possible).
            historical_clean = np.where(np.isfinite(historical), historical, np.inf)
            worst_historical = float(np.min(historical_clean))
            if math.isfinite(last_calmar) and last_calmar < worst_historical:
                degradation_flag = True
                degradation_message = (
                    f"Most recent subperiod Calmar ({last_calmar:.2f}) is worse "
                    f"than the worst historical subperiod ({worst_historical:.2f}). "
                    "Out-of-sample degradation detected."
                )

    return {
        "table": table,
        "degradation_flag": degradation_flag,
        "degradation_message": degradation_message,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_periods(
    first: pd.Timestamp,
    last: pd.Timestamp,
    splits: SplitMode,
) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Return an ordered dict of label → (start, end) pairs."""
    if splits == "yearly":
        years = range(first.year, last.year + 1)
        return {
            str(y): (
                pd.Timestamp(f"{y}-01-01", tz="UTC"),
                pd.Timestamp(f"{y}-12-31 23:59:59", tz="UTC"),
            )
            for y in years
        }
    elif splits == "halves":
        midpoint = first + (last - first) / 2
        return {
            "H1": (first, midpoint),
            "H2": (midpoint, last),
        }
    elif splits == "thirds":
        span = (last - first) / 3
        t1 = first + span
        t2 = first + 2 * span
        return {
            "T1": (first, t1),
            "T2": (t1, t2),
            "T3": (t2, last),
        }
    elif splits == "rolling_2y":
        periods = {}
        start = first
        window = pd.Timedelta(days=365 * 2)
        step = pd.Timedelta(days=365)
        i = 1
        while start < last:
            end = min(start + window, last)
            label = f"2y_{i}"
            periods[label] = (start, end)
            start += step
            i += 1
            if start + window / 4 > last:
                break
        return periods
    else:
        raise ValueError(f"Unknown splits mode: {splits!r}")


def _sub_equity(trades: pd.DataFrame) -> pd.Series:
    """Build an equity curve from a sub-trade slice."""
    trades = trades.sort_values("exit_ts")
    cum = trades["net_pnl_usd"].cumsum()
    return cum.set_axis(pd.to_datetime(trades["exit_ts"]).values)


def _empty_period_row(label: str) -> dict:
    return {
        "period": label,
        "trades": 0,
        "win_rate": float("nan"),
        "profit_factor": float("nan"),
        "sharpe": float("nan"),
        "calmar": float("nan"),
        "max_dd_usd": float("nan"),
        "expectancy_usd": float("nan"),
    }
