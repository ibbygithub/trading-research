"""Meta-labeling readout.

Evaluates if filtering the strategy via classifier probabilities
can improve headline metrics.
"""

import numpy as np
import pandas as pd

from trading_research.utils import stats as _stats


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

    # Derive span_days from trade timestamps when available, else fallback.
    if "exit_ts" in df.columns and "entry_ts" in df.columns:
        span_days = max(
            1,
            (pd.to_datetime(df["exit_ts"]).max() - pd.to_datetime(df["entry_ts"]).min()).days,
        )
    else:
        span_days = max(1, len(df))

    base_calmar = _stats.calmar(df["net_pnl_usd"].values, span_days)

    for t in thresholds:
        filtered = df[df["win_prob"] >= t]
        count = len(filtered)
        if count == 0:
            results.append({"threshold": t, "count": 0, "win_rate": 0, "calmar": 0})
            continue

        win_rate = (filtered["net_pnl_usd"] > 0).mean()

        if "exit_ts" in filtered.columns and "entry_ts" in filtered.columns:
            f_span = max(
                1,
                (pd.to_datetime(filtered["exit_ts"]).max() - pd.to_datetime(filtered["entry_ts"]).min()).days,
            )
        else:
            f_span = span_days
        calmar_val = _stats.calmar(filtered["net_pnl_usd"].values, f_span)
        
        results.append({
            "threshold": t,
            "count": count,
            "win_rate": win_rate,
            "calmar": calmar_val,
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
