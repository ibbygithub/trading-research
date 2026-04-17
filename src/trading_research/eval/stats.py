import math
import numpy as np
import pandas as pd
import scipy.stats as st

def bootstrap_metric(values, stat_fn, n_iter=10_000, ci=0.95):
    arr = np.asarray(values)
    if len(arr) == 0: return float('nan'), float('nan'), float('nan')
    point = float(stat_fn(arr))
    rng = np.random.default_rng(42)
    n = len(arr)
    samples = rng.choice(arr, size=(n_iter, n), replace=True)
    res = np.zeros(n_iter)
    for i in range(n_iter): res[i] = stat_fn(samples[i])
    finite = res[np.isfinite(res)]
    if len(finite) < 2: return point, float('nan'), float('nan')
    alpha = 1.0 - ci
    return point, float(np.percentile(finite, alpha/2*100)), float(np.percentile(finite, (1-alpha/2)*100))

def probabilistic_sharpe_ratio(sharpe: float, n_obs: int, skewness: float, kurtosis: float, sr_benchmark: float = 0.0) -> float:
    if n_obs < 3 or math.isnan(sharpe) or math.isnan(skewness) or math.isnan(kurtosis): return float('nan')
    var = (1 - skewness * sharpe + ((kurtosis - 1) / 4) * sharpe**2) / (n_obs - 1)
    if var <= 0: return float('nan')
    return float(st.norm.cdf((sharpe - sr_benchmark) / math.sqrt(var)))

def deflated_sharpe_ratio(sharpe: float, n_obs: int, n_trials: int, skewness: float, kurtosis: float) -> float:
    if n_trials < 1: n_trials = 1
    emc = 0.5772156649
    if n_trials == 1: sr_bench = 0.0
    else: sr_bench = (1 - emc) * st.norm.ppf(1 - 1.0/n_trials) + emc * st.norm.ppf(1 - 1.0/(n_trials*math.e))
    return probabilistic_sharpe_ratio(sharpe, n_obs, skewness, kurtosis, sr_bench)

def _get_drawdowns(equity_series: pd.Series) -> pd.Series:
    return equity_series.cummax() - equity_series

def mar_ratio(equity_series: pd.Series) -> float:
    if len(equity_series) < 2: return float('nan')
    days = (equity_series.index[-1] - equity_series.index[0]).days
    if days == 0: days = 1
    ann = float(equity_series.iloc[-1]) / days * 252
    dd = _get_drawdowns(equity_series)
    max_dd = float(dd.max())
    return float(ann / max_dd) if max_dd > 0 else float('nan')

def ulcer_index(equity_series: pd.Series) -> float:
    if len(equity_series) < 2: return float('nan')
    peak = equity_series.cummax()
    dd_pct = np.zeros(len(equity_series))
    for i in range(len(equity_series)):
        p = peak.iloc[i]
        if p > 0: dd_pct[i] = (p - equity_series.iloc[i]) / p
    return float(math.sqrt(np.mean(dd_pct**2)))

def ulcer_performance_index(equity_series: pd.Series, rf: float = 0.0) -> float:
    ui = ulcer_index(equity_series)
    if ui == 0 or math.isnan(ui): return float('nan')
    days = (equity_series.index[-1] - equity_series.index[0]).days
    if days == 0: days = 1
    return float((float(equity_series.iloc[-1]) / days * 252 - rf) / ui)

def recovery_factor(equity_series: pd.Series) -> float:
    if len(equity_series) < 2: return float('nan')
    dd = float(_get_drawdowns(equity_series).max())
    return float(float(equity_series.iloc[-1]) / dd) if dd > 0 else float('nan')

def pain_ratio(equity_series: pd.Series) -> float:
    if len(equity_series) < 2: return float('nan')
    dd = float(_get_drawdowns(equity_series).mean())
    return float(float(equity_series.iloc[-1]) / dd) if dd > 0 else float('nan')

def tail_ratio(returns: np.ndarray, pct: float = 0.95) -> float:
    if len(returns) < 2: return float('nan')
    p_high = np.percentile(returns, pct * 100)
    p_low = np.percentile(returns, (1 - pct) * 100)
    return float(abs(p_high) / abs(p_low)) if p_low != 0 else float('nan')

def omega_ratio(returns: np.ndarray, threshold: float = 0.0) -> float:
    if len(returns) < 2: return float('nan')
    gains = np.sum(returns[returns > threshold] - threshold)
    losses = np.sum(threshold - returns[returns < threshold])
    return float(gains / losses) if losses > 0 else float('nan')

def gain_to_pain_ratio(monthly_returns: np.ndarray) -> float:
    if len(monthly_returns) == 0: return float('nan')
    sum_pos = np.sum(monthly_returns[monthly_returns > 0])
    sum_neg = abs(np.sum(monthly_returns[monthly_returns < 0]))
    return float(sum_pos / sum_neg) if sum_neg > 0 else float('nan')
