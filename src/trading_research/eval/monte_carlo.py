import pandas as pd
import numpy as np
import scipy.stats as st
from trading_research.eval.summary import compute_summary
from trading_research.backtest.engine import BacktestResult, BacktestConfig

def shuffle_trade_order(trades: pd.DataFrame, n_iter: int = 1000, seed: int = 42) -> dict:
    if trades.empty:
        return {"n_trades": 0, "n_iter": 0, "equity_curves": [], "max_dd_dist": [], "calmar_dist": [], "actual_max_dd": float('nan'), "actual_max_dd_pctile": float('nan'), "actual_calmar": float('nan'), "actual_calmar_pctile": float('nan'), "interpretation": "No data"}
        
    rng = np.random.default_rng(seed)
    n = len(trades)
    cfg = BacktestConfig(strategy_id="mc", symbol="UNKNOWN")
    
    dds, calmars, curves = [], [], []
    for i in range(n_iter):
        idx = rng.permutation(n)
        shuffled = trades.copy()
        shuffled['net_pnl_usd'] = trades['net_pnl_usd'].values[idx]
        shuffled = shuffled.sort_values('exit_ts')
        eq = shuffled.set_index('exit_ts')['net_pnl_usd'].cumsum()
        curves.append(eq.values.tolist())
        
        res = BacktestResult(trades=shuffled, equity_curve=eq, config=cfg, symbol_meta={})
        sm = compute_summary(res)
        dds.append(sm.get("max_drawdown_usd", float('nan')))
        calmars.append(sm.get("calmar", float('nan')))
        
    actual_eq = trades.set_index('exit_ts')['net_pnl_usd'].sort_index().cumsum()
    act_res = BacktestResult(trades=trades, equity_curve=actual_eq, config=cfg, symbol_meta={})
    act_sm = compute_summary(act_res)
    act_dd = act_sm.get("max_drawdown_usd", float('nan'))
    act_cal = act_sm.get("calmar", float('nan'))
    
    dds = np.array(dds)
    calmars = np.array(calmars)
    
    dd_pctile = float(st.percentileofscore(dds[np.isfinite(dds)], act_dd, kind="rank")) if np.any(np.isfinite(dds)) and not np.isnan(act_dd) else float('nan')
    cal_pctile = float(st.percentileofscore(calmars[np.isfinite(calmars)], act_cal, kind="rank")) if np.any(np.isfinite(calmars)) and not np.isnan(act_cal) else float('nan')
    
    interp = "Strategy performance is within expectation of random trade order."
    if cal_pctile > 95: interp = "Actual strategy significantly outperforms randomized order (path dependence is favorable)."
    elif cal_pctile < 5: interp = "Actual strategy significantly underperforms randomized order (path dependence is unfavorable)."
        
    return {
        "n_trades": n, "n_iter": n_iter,
        "equity_curves": curves,
        "max_dd_dist": dds, "calmar_dist": calmars,
        "actual_max_dd": act_dd, "actual_max_dd_pctile": dd_pctile,
        "actual_calmar": act_cal, "actual_calmar_pctile": cal_pctile,
        "interpretation": interp
    }
