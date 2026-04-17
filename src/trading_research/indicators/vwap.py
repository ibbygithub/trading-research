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

import pandas as pd


def _vwap_from_groups(df: pd.DataFrame, group_key: pd.Series) -> pd.Series:
    """Compute cumulative VWAP within each group defined by ``group_key``.

    group_key: a Series (same index as df) whose distinct values label groups.
    """
    close = df["close"]
    volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    tp_vol = close * volume  # typical-price × volume (close used as typical price)

    cum_tp_vol = tp_vol.groupby(group_key).cumsum()
    cum_vol = volume.groupby(group_key).cumsum()

    return (cum_tp_vol / cum_vol.replace(0, float("nan"))).rename("vwap")


def compute_session_vwap(df_1m: pd.DataFrame) -> pd.Series:
    """Session VWAP: resets whenever the gap to the previous bar exceeds 60 min.

    Parameters
    ----------
    df_1m:
        1-minute bar DataFrame with ``timestamp_utc`` (tz-aware) and
        ``close``, ``volume`` columns.

    Returns
    -------
    pd.Series named ``"vwap_session"``.
    """
    df = df_1m.copy()
    ts = pd.to_datetime(df["timestamp_utc"], utc=True)
    gap_minutes = ts.diff().dt.total_seconds().div(60).fillna(0)
    session_id = (gap_minutes > 60).cumsum()

    result = _vwap_from_groups(df, session_id)
    return result.rename("vwap_session")


def _trade_date_series(df_1m: pd.DataFrame) -> pd.Series:
    """Return a trade_date Series using the CME +6h convention."""
    ts_ny = pd.to_datetime(df_1m["timestamp_ny"]).dt.tz_convert("America/New_York")
    return (ts_ny + pd.Timedelta(hours=6)).dt.date


def compute_weekly_vwap(df_1m: pd.DataFrame) -> pd.Series:
    """Weekly VWAP: resets at the first bar of each ISO week (by trade_date).

    Parameters
    ----------
    df_1m:
        1-minute bar DataFrame with ``timestamp_ny``, ``close``, ``volume``.

    Returns
    -------
    pd.Series named ``"vwap_weekly"``.
    """
    df = df_1m.copy()
    trade_date = _trade_date_series(df)
    # ISO year-week (e.g., "2024-W03") as the group key.
    iso_week = trade_date.apply(
        lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" if d is not None else None
    )
    result = _vwap_from_groups(df, iso_week)
    return result.rename("vwap_weekly")


def compute_monthly_vwap(df_1m: pd.DataFrame) -> pd.Series:
    """Monthly VWAP: resets at the first bar of each calendar month (by trade_date).

    Parameters
    ----------
    df_1m:
        1-minute bar DataFrame with ``timestamp_ny``, ``close``, ``volume``.

    Returns
    -------
    pd.Series named ``"vwap_monthly"``.
    """
    df = df_1m.copy()
    trade_date = _trade_date_series(df)
    month_key = trade_date.apply(
        lambda d: f"{d.year}-{d.month:02d}" if d is not None else None
    )
    result = _vwap_from_groups(df, month_key)
    return result.rename("vwap_monthly")
