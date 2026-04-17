import numpy as np
import pandas as pd
from trading_research.eval.classifier import train_winner_classifier
from trading_research.eval.shap_analysis import compute_shap_per_trade

def test_shap():
    n = 100
    trades = pd.DataFrame({
        "net_pnl_usd": np.random.randn(n),
        "atr_14_pct_rank_252": np.random.rand(n),
        "rsi_14": np.random.rand(n) * 100,
        "direction": ["long"]*n
    })
    cls_res = train_winner_classifier(trades, cv_folds=2)
    shap_df = compute_shap_per_trade(cls_res["model"], cls_res["X_train"])
    assert len(shap_df) == len(cls_res["X_train"])
    assert "shap_top_pos_1" in shap_df.columns
