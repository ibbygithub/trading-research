import pandas as pd
from trading_research.eval.summary import compute_summary
from trading_research.backtest.engine import BacktestResult, BacktestConfig

def subperiod_analysis(trades: pd.DataFrame, equity: pd.Series, splits: str = 'yearly') -> dict:
    if trades.empty:
        return {"table": pd.DataFrame(), "degradation_flag": False, "degradation_message": ""}
    
    df = trades.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['exit_ts']):
        df['exit_ts'] = pd.to_datetime(df['exit_ts'], utc=True)
        
    df['year'] = df['exit_ts'].dt.year
    records = []
    
    if splits == 'yearly':
        for year, group in df.groupby('year'):
            start_ts, end_ts = group['exit_ts'].min(), group['exit_ts'].max()
            group_eq = equity.loc[start_ts:end_ts]
            if not group_eq.empty: group_eq = group_eq - (group_eq.iloc[0] - group['net_pnl_usd'].iloc[0])
            cfg = BacktestConfig(strategy_id="subperiod", symbol="UNKNOWN")
            res = BacktestResult(trades=group, equity_curve=group_eq, config=cfg, symbol_meta={})
            metrics = compute_summary(res)
            metrics['period'] = str(year)
            records.append(metrics)
            
    res_df = pd.DataFrame(records)
    degradation, msg = False, ""
    if not res_df.empty and 'calmar' in res_df.columns:
        cals = res_df['calmar'].dropna().values
        if len(cals) >= 3 and cals[-1] < 0 and cals[-2] < 0:
            degradation = True
            msg = "Recent periods show significant performance degradation."
    return {"table": res_df, "degradation_flag": degradation, "degradation_message": msg}
