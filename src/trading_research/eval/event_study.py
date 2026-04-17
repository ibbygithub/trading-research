"""Event study module.

Analyzes strategy performance around specified macro events.
"""

import numpy as np
import pandas as pd


def event_study(trades: pd.DataFrame, event_dates: list[str], window_days: int = 5) -> dict:
    """Compute strategy performance within an event window."""
    if len(trades) == 0 or not event_dates:
        return {"error": "No trades or event dates provided."}
        
    df = trades.copy()
    entry_dates = pd.to_datetime(df["entry_ts"]).dt.tz_convert("America/New_York").dt.normalize()
    event_ts = pd.to_datetime(event_dates).tz_localize("America/New_York")
    
    # Calculate distance to nearest event
    distances = []
    for d in entry_dates:
        diffs = (event_ts - d).days
        if len(diffs) > 0:
            idx = np.argmin(np.abs(diffs))
            nearest = diffs[idx]
            distances.append(nearest)
        else:
            distances.append(np.nan)
            
    df["event_distance"] = distances
    
    # Inside window vs Outside window
    in_window_mask = df["event_distance"].abs() <= window_days
    
    in_window = df[in_window_mask]
    out_window = df[~in_window_mask]
    
    # Summary stats
    summary = {
        "in_window_trades": len(in_window),
        "out_window_trades": len(out_window),
        "in_window_pnl": float(in_window["net_pnl_usd"].sum()) if len(in_window) else 0,
        "out_window_pnl": float(out_window["net_pnl_usd"].sum()) if len(out_window) else 0,
        "in_window_win_rate": float((in_window["net_pnl_usd"] > 0).mean()) if len(in_window) else 0,
        "out_window_win_rate": float((out_window["net_pnl_usd"] > 0).mean()) if len(out_window) else 0,
    }
    
    # Cumulative PnL curve centered on event date
    # Aggregate PnL for each distance in [-window_days, window_days]
    curve_data = df[df["event_distance"].abs() <= window_days].groupby("event_distance")["net_pnl_usd"].sum().sort_index()
    
    # Fill missing days with 0
    idx = np.arange(-window_days, window_days + 1)
    curve_data = curve_data.reindex(idx, fill_value=0)
    
    # Average PnL per event instance
    n_events = len(event_ts)
    curve_data = curve_data / n_events
    
    # Cumulative sum
    cum_curve = curve_data.cumsum()
    
    return {
        "summary": summary,
        "curve_x": cum_curve.index.tolist(),
        "curve_y": cum_curve.values.tolist(),
    }
