import numpy as np
import pandas as pd
from trading_research.eval.distribution import return_distribution_stats, qq_plot_data, autocorrelation_data

def test_distribution_diagnostics():
    normal_returns = np.random.normal(0, 1, 1000)
    diag = return_distribution_stats(normal_returns)
    assert "skewness" in diag
    assert "jb_pvalue" in diag
    # normal distribution should generally not reject JB at very low alpha, but we just check keys

def test_qq_plot_data():
    returns = np.random.normal(0, 1, 100)
    res = qq_plot_data(returns)
    assert len(res["theoretical_quantiles"]) == 100
    assert len(res["sample_quantiles"]) == 100

def test_autocorrelation_plot_data():
    returns = pd.Series(np.random.normal(0, 1, 100))
    res = autocorrelation_data(returns, 10)
    assert len(res["lags"]) == 10
    assert len(res["acf"]) == 10
    assert not np.isnan(res["ljung_box_pvalue"])
