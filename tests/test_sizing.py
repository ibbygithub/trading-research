import pytest
import pandas as pd
import numpy as np
from trading_research.eval.portfolio import Portfolio, PortfolioStrategy
from trading_research.eval.sizing import apply_sizing

def test_sizing_methods():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    
    pnl1 = pd.Series(np.random.randn(100) * 10 + 1, index=dates)
    pnl2 = pd.Series(np.random.randn(100) * 5 + 0.5, index=dates)
    
    strat1 = PortfolioStrategy("s1", pd.DataFrame(), pd.Series(), {}, pnl1)
    strat2 = PortfolioStrategy("s2", pd.DataFrame(), pd.Series(), {}, pnl2)
    
    port = Portfolio({"s1": strat1, "s2": strat2})
    
    eq_wt = apply_sizing(port, "equal_weight")
    vol_wt = apply_sizing(port, "vol_target")
    
    assert len(eq_wt) == 100
    assert len(vol_wt) == 100
