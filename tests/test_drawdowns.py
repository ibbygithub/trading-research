import pandas as pd
from trading_research.eval.drawdowns import catalog_drawdowns, time_underwater

def test_catalog_drawdowns():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    equity = pd.Series([100, 200, 150, 100, 250, 400, 350, 500, 450, 600], index=dates)
    
    df = catalog_drawdowns(equity, threshold_pct=0.01)
    assert not df.empty
    assert len(df) == 3 # 200->100, 400->350, 500->450

def test_time_underwater():
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    equity = pd.Series([100, 200, 150, 180, 250], index=dates)
    res = time_underwater(equity)
    assert res["longest_run_days"] > 0
    assert len(res["run_lengths"]) > 0
