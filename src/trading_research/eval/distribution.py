import pandas as pd
import numpy as np
import scipy.stats as st

def return_distribution_stats(returns: np.ndarray) -> dict:
    arr = np.asarray(returns)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 4:
        return {"skew": float('nan'), "kurtosis": float('nan'), "excess_kurtosis": float('nan'),
                "jb_stat": float('nan'), "jb_pvalue": float('nan'), "normality_flag": False, "normality_warning": "Not enough data"}
    
    skew = float(st.skew(arr))
    kurt = float(st.kurtosis(arr, fisher=False))
    exc_kurt = float(st.kurtosis(arr, fisher=True))
    jb_stat, jb_pval = st.jarque_bera(arr)
    
    warn = ""
    if jb_pval < 0.05: warn = "Distribution is non-normal (p < 0.05)"
    
    return {
        "count": len(arr),
        "skewness": skew,
        "kurtosis": kurt,
        "excess_kurtosis": exc_kurt,
        "jb_stat": float(jb_stat),
        "jb_pvalue": float(jb_pval),
        "normality_flag": jb_pval < 0.05,
        "normality_warning": warn
    }

def qq_plot_data(returns: np.ndarray) -> dict:
    arr = np.asarray(returns)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2: return {"theoretical_quantiles": [], "sample_quantiles": [], "fit_line_x": [], "fit_line_y": []}
    std_arr = (arr - np.mean(arr)) / np.std(arr, ddof=1)
    std_arr.sort()
    theo = st.norm.ppf(np.linspace(0.01, 0.99, len(std_arr)))
    return {
        "theoretical_quantiles": theo.tolist(),
        "sample_quantiles": std_arr.tolist(),
        "fit_line_x": [-3, 3], "fit_line_y": [-3, 3]
    }

def autocorrelation_data(returns: np.ndarray, max_lags: int = 20) -> dict:
    arr = np.asarray(returns)
    arr = arr[np.isfinite(arr)]
    if len(arr) < max_lags + 2:
        return {"lags": [], "acf": [], "confidence_bounds": float('nan'), "ljung_box_pvalue": float('nan'), "serial_correlation_flag": False}
        
    acf = np.zeros(max_lags)
    mu, var = np.mean(arr), np.var(arr)
    if var == 0: return {"lags": np.arange(1, max_lags+1).tolist(), "acf": [0]*max_lags, "confidence_bounds": 0, "ljung_box_pvalue": 1.0, "serial_correlation_flag": False}
        
    for i in range(1, max_lags + 1):
        acf[i-1] = np.mean((arr[:-i] - mu) * (arr[i:] - mu)) / var
        
    n = len(arr)
    q_stat = n * (n + 2) * np.sum((acf**2) / (n - np.arange(1, max_lags + 1)))
    p_val = float(st.chi2.sf(q_stat, max_lags))
    
    return {
        "lags": np.arange(1, max_lags + 1),
        "acf": acf,
        "confidence_bounds": 1.96 / np.sqrt(n),
        "ljung_box_pvalue": p_val,
        "serial_correlation_flag": p_val < 0.05
    }
