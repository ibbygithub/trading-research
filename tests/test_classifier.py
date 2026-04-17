import numpy as np
import pandas as pd
from trading_research.eval.classifier import train_winner_classifier

def test_classifier():
    n = 200
    dates = pd.date_range("2020-01-01", periods=n, freq="D").tz_localize("UTC")
    trades = pd.DataFrame({
        "entry_ts": dates,
        "exit_ts": dates + pd.Timedelta(hours=2),
        "net_pnl_usd": np.random.randn(n) * 100,
        "atr_14_pct_rank_252": np.random.rand(n),
        "direction": ["long"]*n
    })
    res = train_winner_classifier(trades, cv_folds=2, purge_bars=0)
    assert "model" in res
    assert "pdp_data" in res
    assert "importance_ci" in res["permutation_importance"].columns
