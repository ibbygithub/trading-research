import numpy as np
import pandas as pd
from trading_research.eval.clustering import cluster_trades

def test_clustering():
    n = 100
    trades = pd.DataFrame({
        "net_pnl_usd": np.random.randn(n)
    })
    X = pd.DataFrame({
        "feat1": np.random.rand(n),
        "feat2": np.random.rand(n)
    })
    res = cluster_trades(trades, X)
    assert "labels" in res
    assert "umap_x" in res
