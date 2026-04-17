import numpy as np
import pandas as pd
from trading_research.eval.meta_label import evaluate_meta_labeling

def test_meta_label():
    trades = pd.DataFrame({
        "net_pnl_usd": np.random.randn(100),
        "entry_ts": pd.date_range("2020-01-01", periods=100),
        "exit_ts": pd.date_range("2020-01-02", periods=100)
    })
    idx = trades.index
    oof = np.random.rand(100)
    res = evaluate_meta_labeling(trades, idx, oof)
    assert "sweep_data" in res
