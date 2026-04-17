import pytest
import pandas as pd
import numpy as np
from trading_research.eval.portfolio import Portfolio, PortfolioStrategy
from trading_research.eval.correlation import daily_pnl_correlation

def test_correlation():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    
    # Perfectly correlated
    pnl1 = pd.Series(np.linspace(1, 100, 100), index=dates)
    pnl2 = pd.Series(np.linspace(1, 100, 100) * 2, index=dates)
    
    strat1 = PortfolioStrategy("s1", pd.DataFrame(), pd.Series(), {}, pnl1)
    strat2 = PortfolioStrategy("s2", pd.DataFrame(), pd.Series(), {}, pnl2)
    
    port = Portfolio({"s1": strat1, "s2": strat2})
    
    res = daily_pnl_correlation(port)
    assert np.isclose(res["pearson"].loc["s1", "s2"], 1.0)
    assert np.isclose(res["spearman"].loc["s1", "s2"], 1.0)
