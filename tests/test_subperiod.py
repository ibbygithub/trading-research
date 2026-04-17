import pandas as pd
import numpy as np
from trading_research.eval.subperiod import subperiod_analysis

def test_subperiod_analysis():
    dates = pd.date_range("2020-01-01", periods=10, freq="100D", tz="UTC")
    trades = pd.DataFrame({
        "net_pnl_usd": [100, -50, 200, 100, -50, 200, 100, -50, 200, 100],
        "exit_ts": dates,
        "entry_ts": dates - pd.Timedelta(days=1),
        "mae_points": [-10] * 10,
        "mfe_points": [20] * 10
    })
    equity = trades.set_index("exit_ts")["net_pnl_usd"].cumsum()
    
    df = subperiod_analysis(trades, equity, splits="yearly")
    assert isinstance(df, dict)
    assert "period" in df.columns
    # 2020, 2021, 2022
    assert len(df) == 3
