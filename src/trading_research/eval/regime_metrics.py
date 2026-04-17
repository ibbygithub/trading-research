"""Regime metric breakdown.

Breaks down backtest performance by regime tags.
"""

import numpy as np
import pandas as pd
from scipy import stats



def breakdown_by_regime(trades: pd.DataFrame, regime_column: str) -> list[dict]:
    """Calculate summary metrics for each distinct value of a regime column."""
    if regime_column not in trades.columns:
        return []

    # Filter out trades where the regime couldn't be tagged
    valid = trades[trades[regime_column].notna()]
    if len(valid) == 0:
        return []

    results = []
    groups = valid.groupby(regime_column, observed=False)
    
    # Need full backtest duration for annualized metrics
    # If the strategy was running the whole time, the span is roughly constant.
    # To be perfectly correct, we should use the overall backtest span
    ts = pd.to_datetime(trades["entry_ts"])
    span_years = (ts.max() - ts.min()).total_seconds() / (365.25 * 86400)
    if span_years <= 0:
        span_years = 1.0

    for name, group in groups:
        if len(group) == 0:
            continue
            
        pnl = group["net_pnl_usd"]
        count = len(group)
        win_rate = (pnl > 0).mean()
        
        # Approximate Sharpe for the regime (assuming random draw)
        # Using the standard deviation of trade PnL multiplied by sqrt(N_per_year)
        # To match the main report, we use daily PnL if possible.
        # But this is a grouping. Better to just use per-trade expectation
        # or construct a daily series for this regime.
        
        # Construct daily series for this regime
        group_daily = group.groupby(pd.to_datetime(group["exit_ts"]).dt.date)["net_pnl_usd"].sum()
        
        sharpe = np.nan
        calmar = np.nan
        
        if len(group_daily) > 2:
            mean_d = group_daily.mean()
            std_d = group_daily.std()
            if std_d > 0:
                sharpe = (mean_d / std_d) * np.sqrt(252)
                
            # Calmar is hard to define exactly for a disjoint regime without cumulative equity
            # We'll just calculate Max DD of the cumulative PnL of this regime
            cum_pnl = group_daily.cumsum()
            running_max = cum_pnl.cummax()
            dd = cum_pnl - running_max
            max_dd = abs(dd.min())
            
            annual_ret = cum_pnl.iloc[-1] / span_years
            if max_dd > 0:
                calmar = annual_ret / max_dd

        results.append({
            "regime": str(name),
            "count": count,
            "total_pnl": float(pnl.sum()),
            "avg_pnl": float(pnl.mean()),
            "win_rate": float(win_rate),
            "calmar": float(calmar) if not np.isnan(calmar) else None,
            "sharpe": float(sharpe) if not np.isnan(sharpe) else None,
            "trades_per_week": count / (span_years * 52)
        })

    # Sort by total PnL descending
    results.sort(key=lambda x: x["total_pnl"], reverse=True)
    return results
