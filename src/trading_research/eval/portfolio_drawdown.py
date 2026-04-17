import pandas as pd
import numpy as np
from trading_research.eval.portfolio import Portfolio

def portfolio_drawdown_attribution(portfolio: Portfolio, min_dd_pct: float = 0.01) -> pd.DataFrame:
    """Identify portfolio drawdowns > min_dd_pct and attribute losses to strategies."""
    if portfolio.combined_equity.empty:
        return pd.DataFrame()
        
    eq = portfolio.combined_equity
    if eq.max() <= 0:
        return pd.DataFrame() # No positive equity
        
    running_max = eq.cummax()
    # Replace zeros with a small number to avoid division by zero
    running_max_safe = running_max.replace(0, 1e-9)
    dd_pct = (eq - running_max) / running_max_safe
    
    # Identify drawdown periods
    is_dd = dd_pct < 0
    # Group contiguous dd periods
    dd_groups = (~is_dd).cumsum()[is_dd]
    
    if dd_groups.empty:
        return pd.DataFrame()
        
    df_pnl = pd.DataFrame({sid: s.daily_pnl for sid, s in portfolio.strategies.items()})
    df_pnl = df_pnl.fillna(0.0)
    
    results = []
    
    for g_idx, group in eq[is_dd].groupby(dd_groups):
        peak_date = running_max.loc[group.index[0]:].index[0] # date where running_max was established
        # Actually running_max is the value, the date is the first date the value was reached.
        # A simpler way: the peak is the day before the group starts.
        start_date = group.index[0]
        end_date = group.index[-1]
        
        # Max drawdown in this period
        group_dd = dd_pct.loc[group.index]
        max_dd_val = group_dd.min()
        
        if abs(max_dd_val) < min_dd_pct:
            continue
            
        trough_date = group_dd.idxmin()
        
        # Attribution: sum of daily PnL from start_date to trough_date for each strategy
        # Actually it should be from the peak to the trough. 
        # If start_date is the first down day, the peak is just before it.
        # We sum PnL from start_date up to trough_date.
        pnl_window = df_pnl.loc[start_date:trough_date]
        attr = pnl_window.sum()
        
        # Calculate percentage of the total loss
        total_loss = attr.sum()
        if total_loss < 0:
            attr_pct = attr / total_loss
        else:
            attr_pct = pd.Series(0.0, index=attr.index)
            
        res = {
            "start_date": start_date,
            "trough_date": trough_date,
            "end_date": end_date,
            "max_dd_pct": float(max_dd_val),
            "total_loss_usd": float(total_loss),
        }
        for sid in df_pnl.columns:
            res[f"{sid}_loss_usd"] = float(attr[sid])
            res[f"{sid}_attr_pct"] = float(attr_pct[sid])
            
        results.append(res)
        
    # Sort by worst drawdown
    if not results:
        return pd.DataFrame()
        
    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values("max_dd_pct", ascending=True).reset_index(drop=True)
    return df_res
