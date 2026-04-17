import pandas as pd
import numpy as np
from trading_research.eval.monte_carlo import shuffle_trade_order

def test_shuffle_trade_order():
    dates = pd.date_range("2020-01-01", periods=10, freq="D", tz="UTC")
    trades = pd.DataFrame({
        "net_pnl_usd": [100, -50, 200, 100, -50, 200, 100, -50, 200, 100],
        "exit_ts": dates,
        "entry_ts": dates - pd.Timedelta(hours=1),
        "mae_points": [-10] * 10,
        "mfe_points": [20] * 10
    })
    
    df = shuffle_trade_order(trades, n_iter=5, seed=42)
    assert isinstance(df, dict)
    assert "max_drawdown_usd" in df.columns
    assert "calmar" in df.columns
    # Total PNL should remain identical for all shuffles
    assert df["net_pnl_usd"].nunique() == 1
