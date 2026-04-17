"""Meta-labeling readout.

Evaluates if filtering the strategy via classifier probabilities
can improve headline metrics.
"""

import numpy as np
import pandas as pd


def evaluate_meta_labeling(
    trades: pd.DataFrame, 
    X_index: pd.Index, 
    oof_preds: np.ndarray
) -> dict:
    """Evaluate strategy filtering over probability thresholds.
    
    X_index is the subset of trade indices used in training.
    oof_preds is the out-of-fold probability of a winning trade.
    """
    if len(X_index) == 0:
        return {"error": "No trades to evaluate."}
        
    df = trades.loc[X_index].copy()
    df["win_prob"] = oof_preds
    
    thresholds = np.arange(0.30, 0.95, 0.05)
    results = []
    
    base_pnl = df["net_pnl_usd"].sum()
    base_count = len(df)
    base_win_rate = (df["net_pnl_usd"] > 0).mean()
    
    # Calculate base Calmar equivalent (using PnL series)
    cum_pnl = df["net_pnl_usd"].cumsum()
    max_dd = abs((cum_pnl - cum_pnl.cummax()).min())
    base_calmar = (base_pnl / 16.0) / max_dd if max_dd > 0 else 0
    
    for t in thresholds:
        filtered = df[df["win_prob"] >= t]
        count = len(filtered)
        if count == 0:
            results.append({"threshold": t, "count": 0, "win_rate": 0, "calmar": 0})
            continue
            
        pnl = filtered["net_pnl_usd"].sum()
        win_rate = (filtered["net_pnl_usd"] > 0).mean()
        
        f_cum_pnl = filtered["net_pnl_usd"].cumsum()
        f_max_dd = abs((f_cum_pnl - f_cum_pnl.cummax()).min())
        calmar = (pnl / 16.0) / f_max_dd if f_max_dd > 0 else 0
        
        results.append({
            "threshold": t,
            "count": count,
            "win_rate": win_rate,
            "calmar": calmar
        })
        
    df_res = pd.DataFrame(results)
    
    best_calmar = df_res["calmar"].max()
    improvement = best_calmar - base_calmar
    
    interp = (
        "If the filtered Calmar beats the unfiltered Calmar by more than the CI width, "
        "the base rule set is leaving money on the table and meta-labeling is a candidate "
        "for a follow-on strategy session. If it does not, the base rule set is efficient "
        "given these features."
    )
    
    return {
        "sweep_data": df_res,
        "base_calmar": base_calmar,
        "best_calmar": best_calmar,
        "improvement": improvement,
        "interpretation": interp
    }
