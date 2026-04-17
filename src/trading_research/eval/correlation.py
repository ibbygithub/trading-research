import pandas as pd
from trading_research.eval.portfolio import Portfolio

def daily_pnl_correlation(portfolio: Portfolio) -> dict:
    """Compute Pearson and Spearman correlation matrices for strategy daily PnL."""
    if len(portfolio.strategies) < 2:
        return {"error": "Need at least 2 strategies for correlation."}
        
    df = pd.DataFrame({sid: s.daily_pnl for sid, s in portfolio.strategies.items()})
    df = df.fillna(0.0)
    
    pearson_corr = df.corr(method="pearson")
    spearman_corr = df.corr(method="spearman")
    
    return {
        "pearson": pearson_corr,
        "spearman": spearman_corr
    }

def rolling_correlation(portfolio: Portfolio, window_days: int = 60) -> dict:
    """Compute rolling pairwise correlations."""
    if len(portfolio.strategies) < 2:
        return {"error": "Need at least 2 strategies for correlation."}
        
    df = pd.DataFrame({sid: s.daily_pnl for sid, s in portfolio.strategies.items()})
    df = df.fillna(0.0)
    
    pairs = {}
    cols = df.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            col1, col2 = cols[i], cols[j]
            pair_name = f"{col1} vs {col2}"
            rolling_corr = df[col1].rolling(window_days).corr(df[col2])
            pairs[pair_name] = rolling_corr
            
    return pairs

def return_correlation_vs_market(portfolio: Portfolio, benchmark_series: pd.Series = None) -> dict:
    """Compute correlation against a benchmark like SPY."""
    if benchmark_series is None or benchmark_series.empty:
        return {"error": "No benchmark series provided."}
        
    df = pd.DataFrame({sid: s.daily_pnl for sid, s in portfolio.strategies.items()})
    df = df.fillna(0.0)
    
    # Align dates
    df, bm = df.align(benchmark_series, join='inner', axis=0)
    
    corrs = {}
    for col in df.columns:
        corrs[col] = df[col].corr(bm)
        
    return corrs
