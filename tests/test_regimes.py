import numpy as np
import pandas as pd
from trading_research.eval.regimes import tag_regimes
from trading_research.eval.regime_metrics import breakdown_by_regime

def test_regime_tagging():
    dates = pd.date_range("2020-01-01", periods=50, freq="D").tz_localize("UTC")
    trades = pd.DataFrame({
        "entry_ts": dates,
        "exit_ts": dates + pd.Timedelta(hours=2),
        "atr_14_pct_rank_252": np.linspace(0, 1, 50),
        "daily_adx_14": np.linspace(0, 60, 50),
        "net_pnl_usd": np.random.randn(50) * 100
    })
    tagged = tag_regimes(trades, ["2020-01-15"])
    assert "vol_regime" in tagged.columns
    assert "trend_regime" in tagged.columns
    res = breakdown_by_regime(tagged, "vol_regime")
    assert len(res) > 0
