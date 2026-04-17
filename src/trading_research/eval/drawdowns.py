import pandas as pd
import numpy as np

def catalog_drawdowns(equity: pd.Series, trades: pd.DataFrame | None = None, threshold_pct: float = 0.01) -> pd.DataFrame:
    if equity.empty: return pd.DataFrame()
    peak = equity.cummax()
    is_dd = equity < peak
    drawdowns, start, peak_val = [], None, 0.0
    for ts, flag in is_dd.items():
        if flag and start is None:
            start, peak_val = ts, peak.loc[ts]
        elif not flag and start is not None:
            end = ts
            dd_win = equity.loc[start:end]
            tr_val, tr_ts = dd_win.min(), dd_win.idxmin()
            depth_usd = peak_val - tr_val
            depth_pct = depth_usd / abs(peak_val) if peak_val != 0 else float('nan')
            if pd.isna(depth_pct) or depth_pct >= threshold_pct:
                drawdowns.append({"start_date": start, "trough_date": tr_ts, "recovery_date": end, "depth_pct": depth_pct, "depth_usd": depth_usd})
            start = None
    if start is not None:
        end = equity.index[-1]
        dd_win = equity.loc[start:end]
        tr_val, tr_ts = dd_win.min(), dd_win.idxmin()
        depth_usd = peak_val - tr_val
        depth_pct = depth_usd / abs(peak_val) if peak_val != 0 else float('nan')
        if pd.isna(depth_pct) or depth_pct >= threshold_pct:
            drawdowns.append({"start_date": start, "trough_date": tr_ts, "recovery_date": pd.NaT, "depth_pct": depth_pct, "depth_usd": depth_usd})
    return pd.DataFrame(drawdowns)

def time_underwater(equity: pd.Series) -> dict:
    if equity.empty: return {"pct_time_underwater": float('nan'), "longest_run_days": 0, "run_lengths": []}
    peak = equity.cummax()
    is_dd = equity < peak
    runs, curr = [], 0
    for flag in is_dd:
        if flag: curr += 1
        else:
            if curr > 0: runs.append(curr)
            curr = 0
    if curr > 0: runs.append(curr)
    pct = is_dd.mean()
    start = None
    max_days = 0
    for ts, flag in is_dd.items():
        if flag and start is None: start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).days)
            start = None
    if start is not None: max_days = max(max_days, (equity.index[-1] - start).days)
    return {"pct_time_underwater": pct, "longest_run_days": max_days, "run_lengths": runs}
