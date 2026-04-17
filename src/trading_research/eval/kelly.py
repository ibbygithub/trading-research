import pandas as pd
import numpy as np
from trading_research.eval.portfolio import Portfolio

def kelly_fraction(returns: pd.Series, max_dd_target: float = 0.20) -> dict:
    """Calculate various Kelly fractions for reference only.
    
    Warning: Kelly fractions are shown for reference only. 
    This project sizes positions via volatility targeting. 
    Kelly assumes the historical distribution of returns will repeat; 
    real markets violate this assumption and Kelly sizing has destroyed 
    real traders using real strategies that looked real on paper.
    """
    if len(returns) < 2:
        return {}
        
    mean_ret = returns.mean()
    var_ret = returns.var()
    
    if var_ret <= 0 or mean_ret <= 0:
        full_kelly = 0.0
    else:
        full_kelly = mean_ret / var_ret
        
    half_kelly = full_kelly / 2.0
    quarter_kelly = full_kelly / 4.0
    
    # Simple drawdown constraint approximation:
    # If we want max DD to be roughly max_dd_target, and historical max DD at leverage 1 is hist_dd:
    # f = max_dd_target / hist_dd
    cum_ret = (1 + returns).cumprod()
    running_max = cum_ret.cummax()
    hist_dd = ((running_max - cum_ret) / running_max).max()
    
    if hist_dd > 0:
        dd_constrained_kelly = min(full_kelly, max_dd_target / hist_dd)
    else:
        dd_constrained_kelly = full_kelly
        
    return {
        "full_kelly": float(full_kelly),
        "half_kelly": float(half_kelly),
        "quarter_kelly": float(quarter_kelly),
        "dd_constrained_kelly": float(dd_constrained_kelly),
        "hist_max_dd": float(hist_dd)
    }

def portfolio_kelly(portfolio: Portfolio) -> dict:
    res = {}
    for sid, strat in portfolio.strategies.items():
        # Convert daily PnL to roughly return % (assuming $100k base capital for reference)
        # To compute Kelly properly we need % returns. If capital is unknown, we assume fixed.
        assumed_capital = 100000.0
        ret_series = strat.daily_pnl / assumed_capital
        res[sid] = kelly_fraction(ret_series)
    return res
