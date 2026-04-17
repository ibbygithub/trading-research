import numpy as np
import pandas as pd
from trading_research.eval.event_study import event_study

def test_event_study():
    dates = pd.date_range("2020-01-01", periods=100, freq="D").tz_localize("UTC")
    trades = pd.DataFrame({
        "entry_ts": dates,
        "net_pnl_usd": np.random.randn(100) * 100
    })
    fomc = ["2020-01-15", "2020-02-15"]
    res = event_study(trades, fomc)
    assert "summary" in res
