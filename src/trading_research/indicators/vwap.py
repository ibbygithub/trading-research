"""VWAP with session, weekly, and monthly reset flavors.

All three flavors are computed on the 1-minute frame.  To use in a higher
timeframe feature file, sample the 1m series at each bucket's close timestamp
(the last 1m bar within the bucket).

Session VWAP:   resets whenever there is a gap > 60 minutes between bars.
Weekly VWAP:    resets at the first 1m bar of each ISO week (by trade_date).
Monthly VWAP:   resets at the first 1m bar of each calendar month (by trade_date).

Trade-date is derived with the CME +6h convention:
    trade_date = (timestamp_ny + 6h).date()
so bars from 18:00 ET on Sunday night are assigned to Monday's trade_date.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _vwap_and_std_from_groups(df: pd.DataFrame, group_key: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Compute cumulative VWAP and volume-weighted standard deviation.

    group_key: a Series (same index as df) whose distinct values label groups.
    """
    close = df["close"]
    volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    tp_vol = close * volume  # typical-price × volume
    tp_sq_vol = (close ** 2) * volume

    cum_vol = volume.groupby(group_key).cumsum()
    cum_tp_vol = tp_vol.groupby(group_key).cumsum()
    cum_tp_sq_vol = tp_sq_vol.groupby(group_key).cumsum()

    vwap = cum_tp_vol / cum_vol.replace(0, float("nan"))
    
    # E[X^2] - (E[X])^2
    vwap_var = (cum_tp_sq_vol / cum_vol.replace(0, float("nan"))) - (vwap ** 2)
    # Floating point precision can cause tiny negative values
    vwap_var = vwap_var.clip(lower=0)
    vwap_std = np.sqrt(vwap_var)

    return vwap, vwap_std


def _build_bands(vwap: pd.Series, vwap_std: pd.Series, prefix: str) -> pd.DataFrame:
    """Build a DataFrame containing the VWAP and its standard deviation bands."""
    return pd.DataFrame({
        f"{prefix}": vwap,
        f"{prefix}_std_1_0": vwap_std * 1.0,
        f"{prefix}_std_1_5": vwap_std * 1.5,
        f"{prefix}_std_2_0": vwap_std * 2.0,
        f"{prefix}_std_3_0": vwap_std * 3.0,
    })


def compute_session_vwap(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Session VWAP: resets whenever the gap to the previous bar exceeds 60 min.

    Returns
    -------
    pd.DataFrame with columns: vwap_session, vwap_session_std_1_0, etc.
    """
    df = df_1m.copy()
    ts = pd.to_datetime(df["timestamp_utc"], utc=True)
    gap_minutes = ts.diff().dt.total_seconds().div(60).fillna(0)
    session_id = (gap_minutes > 60).cumsum()

    vwap, vwap_std = _vwap_and_std_from_groups(df, session_id)
    return _build_bands(vwap, vwap_std, "vwap_session")


def _trade_date_series(df_1m: pd.DataFrame) -> pd.Series:
    """Return a trade_date Series using the CME +6h convention."""
    ts_ny = pd.to_datetime(df_1m["timestamp_ny"]).dt.tz_convert("America/New_York")
    return (ts_ny + pd.Timedelta(hours=6)).dt.date


def compute_weekly_vwap(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Weekly VWAP: resets at the first bar of each ISO week (by trade_date).

    Returns
    -------
    pd.DataFrame with columns: vwap_weekly, vwap_weekly_std_1_0, etc.
    """
    df = df_1m.copy()
    trade_date = _trade_date_series(df)
    # ISO year-week (e.g., "2024-W03") as the group key.
    iso_week = trade_date.apply(
        lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" if d is not None else None
    )
    vwap, vwap_std = _vwap_and_std_from_groups(df, iso_week)
    return _build_bands(vwap, vwap_std, "vwap_weekly")


def compute_monthly_vwap(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Monthly VWAP: resets at the first bar of each calendar month (by trade_date).

    Returns
    -------
    pd.DataFrame with columns: vwap_monthly, vwap_monthly_std_1_0, etc.
    """
    df = df_1m.copy()
    trade_date = _trade_date_series(df)
    month_key = trade_date.apply(
        lambda d: f"{d.year}-{d.month:02d}" if d is not None else None
    )
    vwap, vwap_std = _vwap_and_std_from_groups(df, month_key)
    return _build_bands(vwap, vwap_std, "vwap_monthly")
