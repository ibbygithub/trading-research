import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from trading_research.eval.portfolio import Portfolio, PortfolioStrategy

def test_portfolio_loading_and_alignment():
    dates = pd.date_range("2024-01-01", periods=10, freq="D").tz_localize("UTC")
    
    # Strategy 1 trades
    s1_trades = pd.DataFrame({
        "exit_ts": dates,
        "net_pnl_usd": np.ones(10) * 100
    })
    s1_pnl = s1_trades.groupby(pd.to_datetime(s1_trades["exit_ts"]).dt.date)["net_pnl_usd"].sum()
    s1_pnl.index = pd.DatetimeIndex(s1_pnl.index)
    
    # Strategy 2 trades (starts 2 days later)
    s2_trades = pd.DataFrame({
        "exit_ts": dates[2:],
        "net_pnl_usd": np.ones(8) * -50
    })
    s2_pnl = s2_trades.groupby(pd.to_datetime(s2_trades["exit_ts"]).dt.date)["net_pnl_usd"].sum()
    s2_pnl.index = pd.DatetimeIndex(s2_pnl.index)
    
    strat1 = PortfolioStrategy("s1", s1_trades, s1_pnl.cumsum(), {}, s1_pnl)
    strat2 = PortfolioStrategy("s2", s2_trades, s2_pnl.cumsum(), {}, s2_pnl)
    
    port = Portfolio(strategies={"s1": strat1, "s2": strat2})
    
    assert len(port.combined_daily_pnl) == 10
    # Day 1: s1=100, s2=0 (not trading yet)
    assert port.combined_daily_pnl.iloc[0] == 100
    # Day 3: s1=100, s2=-50 -> 50
    assert port.combined_daily_pnl.iloc[2] == 50
    
    assert port.combined_equity.iloc[-1] == (10*100) + (8*-50)
