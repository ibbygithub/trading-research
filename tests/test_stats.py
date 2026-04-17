import numpy as np
import pandas as pd
import pytest
from trading_research.eval.stats import (
    bootstrap_metric, deflated_sharpe_ratio, probabilistic_sharpe_ratio,
    mar_ratio, ulcer_index, ulcer_performance_index, recovery_factor,
    pain_ratio, tail_ratio, omega_ratio, gain_to_pain_ratio
)

def test_bootstrap_metric():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    def mean_fn(arr): return np.mean(arr)
    point, lo, hi = bootstrap_metric(values, mean_fn, n_iter=100)
    assert point == 3.0
    assert lo <= point <= hi

def test_probabilistic_sharpe_ratio():
    psr = probabilistic_sharpe_ratio(1.0, 100, 0.0, 3.0)
    assert 0.0 <= psr <= 1.0

def test_deflated_sharpe_ratio():
    returns = np.random.normal(0.1, 1.0, 1000)
    dsr = deflated_sharpe_ratio(returns, 10)
    assert 0.0 <= dsr <= 1.0

def test_ratios():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    equity = pd.Series([100, 200, 150, 300, 250, 400, 350, 500, 450, 600], index=dates)
    mar = mar_ratio(equity)
    assert mar > 0
    
    ui = ulcer_index(equity)
    assert ui >= 0
    
    upi = ulcer_performance_index(equity)
    assert upi > 0
    
    rf = recovery_factor(equity)
    assert rf > 0
    
    pr = pain_ratio(equity)
    assert pr > 0

def test_tail_ratio():
    returns = np.array([-10, -2, -1, 1, 2, 10])
    tr = tail_ratio(returns, 0.95)
    assert tr > 0

def test_omega_ratio():
    returns = np.array([-10, -2, -1, 1, 2, 10])
    om = omega_ratio(returns, 0)
    assert om == 1.0

def test_gain_to_pain_ratio():
    returns = np.array([-10, -2, 5, 10])
    gtp = gain_to_pain_ratio(returns)
    assert gtp == 15 / 12
