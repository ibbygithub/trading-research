import pandas as pd
import numpy as np
from trading_research.eval.portfolio import Portfolio

def apply_sizing(portfolio: Portfolio, method: str, target_vol: float = 0.10, lookback: int = 60) -> pd.Series:
    """Apply position sizing to the portfolio strategies without lookahead bias.
    Returns the daily PnL series of the combined portfolio under the chosen sizing method.
    """
    if len(portfolio.strategies) == 0:
        return pd.Series(dtype=float)
        
    df_pnl = pd.DataFrame({sid: s.daily_pnl for sid, s in portfolio.strategies.items()})
    df_pnl = df_pnl.fillna(0.0)
    
    if method == "equal_weight":
        # Current default
        weights = pd.DataFrame(1.0 / len(df_pnl.columns), index=df_pnl.index, columns=df_pnl.columns)
        return (df_pnl * weights).sum(axis=1)
        
    # For dynamic sizing, we need rolling metrics. We shift(1) to avoid lookahead bias!
    if method == "vol_target":
        # Target a fixed annualized portfolio vol. 
        # For simplicity, we calculate rolling vol per strategy and weight inversely.
        rolling_std = df_pnl.rolling(lookback).std().shift(1)
        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)
        inv_vol = 1.0 / rolling_std
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        weights = weights.fillna(1.0 / len(df_pnl.columns)) # fallback
        return (df_pnl * weights).sum(axis=1)
        
    if method == "risk_parity":
        # Naive risk parity: weight inversely proportional to volatility
        # Actually same as vol_target implementation for uncorrelated assets.
        # A true risk parity requires covariance matrix inversion, which is complex.
        # We will use inverse vol as a naive approximation here.
        rolling_std = df_pnl.rolling(lookback).std().shift(1)
        rolling_std = rolling_std.replace(0, np.nan)
        inv_vol = 1.0 / rolling_std
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        weights = weights.fillna(1.0 / len(df_pnl.columns))
        return (df_pnl * weights).sum(axis=1)
        
    if method == "inverse_dd":
        # Size inversely proportional to recent drawdown
        rolling_max = df_pnl.cumsum().rolling(lookback).max().shift(1)
        rolling_max = rolling_max.fillna(0)
        dd = (df_pnl.cumsum().shift(1) - rolling_max).abs()
        # To avoid division by zero when DD is 0, add a small epsilon
        inv_dd = 1.0 / (dd + 1.0)
        weights = inv_dd.div(inv_dd.sum(axis=1), axis=0)
        weights = weights.fillna(1.0 / len(df_pnl.columns))
        return (df_pnl * weights).sum(axis=1)
        
    raise ValueError(f"Unknown sizing method: {method}")

def compare_sizing_methods(portfolio: Portfolio, target_vol: float = 0.10, lookback: int = 60) -> dict:
    methods = ["equal_weight", "vol_target", "risk_parity", "inverse_dd"]
    results = {}
    
    # Calculate span for annualized return
    if portfolio.combined_equity.empty:
        return {}
    span_years = len(portfolio.combined_equity) / 252.0
    if span_years <= 0: span_years = 1.0
    
    for m in methods:
        sized_pnl = apply_sizing(portfolio, m, target_vol, lookback)
        cum_pnl = sized_pnl.cumsum()
        
        final_pnl = cum_pnl.iloc[-1]
        max_dd = (cum_pnl.cummax() - cum_pnl).max()
        calmar = (final_pnl / span_years) / max_dd if max_dd > 0 else np.nan
        
        mean_d = sized_pnl.mean()
        std_d = sized_pnl.std()
        sharpe = (mean_d / std_d) * np.sqrt(252) if std_d > 0 else np.nan
        
        results[m] = {
            "final_pnl": final_pnl,
            "max_dd": max_dd,
            "calmar": calmar,
            "sharpe": sharpe,
            "equity_curve": cum_pnl
        }
        
    return results
