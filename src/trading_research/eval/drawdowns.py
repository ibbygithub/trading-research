"""Drawdown forensics for the Risk Officer's view.

Catalogs every discrete drawdown exceeding a threshold with full metadata:
start, trough, recovery, depth, duration, trades touched.

Time-underwater series and histogram are also provided.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd


def catalog_drawdowns(
    equity: pd.Series,
    trades: pd.DataFrame | None = None,
    threshold_pct: float = 0.01,
) -> pd.DataFrame:
    """Catalog all drawdown episodes exceeding *threshold_pct*.

    Parameters
    ----------
    equity:        Equity curve (cumulative net P&L), datetime-indexed.
    trades:        Optional trade log with 'entry_ts' and 'exit_ts'.
                   Used to count trades opened during each drawdown.
    threshold_pct: Minimum drawdown depth (as fraction of peak) to include.
                   Default 0.01 = 1%.

    Returns
    -------
    DataFrame with one row per drawdown episode:
        start_date        — date drawdown began (equity fell below prior peak)
        trough_date       — date of the lowest point
        recovery_date     — date equity recovered the prior peak (NaT = unrecovered)
        depth_usd         — depth in absolute dollar terms (positive number)
        depth_pct         — depth as fraction of peak (positive number)
        duration_bars     — bars from start to trough
        recovery_bars     — bars from trough to recovery (0 = unrecovered)
        total_bars        — bars from start to recovery (or end of series)
        duration_days     — calendar days from start to trough
        recovery_days     — calendar days from trough to recovery (0 = unrecovered)
        total_days        — calendar days from start to recovery (or end)
        trades_in_dd      — trades opened while drawdown was active (if trades provided)
        trades_to_trough  — trades opened before the trough was reached
        trades_to_recovery — trades opened after the trough until recovery
    """
    if equity.empty:
        return _empty_dd_catalog()

    equity = equity.sort_index()
    running_peak = equity.cummax()
    dd_series = equity - running_peak  # non-positive

    rows = []
    in_dd = False
    start_idx: int | None = None
    trough_idx: int | None = None
    trough_val: float = 0.0

    n = len(equity)
    vals = equity.values
    peak_vals = running_peak.values
    idx = equity.index

    for i in range(n):
        dd = vals[i] - peak_vals[i]
        if not in_dd:
            if dd < 0:
                in_dd = True
                start_idx = i
                trough_idx = i
                trough_val = dd
        else:
            if dd < trough_val:
                trough_val = dd
                trough_idx = i
            if dd >= 0:
                # Recovered.
                _add_row(
                    rows, idx, vals, peak_vals, trades,
                    start_idx, trough_idx, i,
                    recovered=True, threshold_pct=threshold_pct,
                )
                in_dd = False
                start_idx = None
                trough_idx = None
                trough_val = 0.0

    # Still in drawdown at end of series.
    if in_dd and start_idx is not None and trough_idx is not None:
        _add_row(
            rows, idx, vals, peak_vals, trades,
            start_idx, trough_idx, n - 1,
            recovered=False, threshold_pct=threshold_pct,
        )

    if not rows:
        return _empty_dd_catalog()

    return pd.DataFrame(rows)


def time_underwater(equity: pd.Series) -> dict:
    """Compute time-underwater series and run histogram.

    Parameters
    ----------
    equity: Equity curve, datetime-indexed.

    Returns
    -------
    Dict with:
        series (pd.Series[bool]):  True at each bar below the running peak.
        pct_time_underwater (float): Fraction of bars spent below peak.
        longest_run_bars (int):    Longest contiguous underwater run in bars.
        longest_run_days (int):    Longest contiguous underwater run in days.
        run_lengths (list[int]):   All contiguous run lengths (bars).
    """
    if equity.empty:
        return {
            "series": pd.Series(dtype=bool),
            "pct_time_underwater": float("nan"),
            "longest_run_bars": 0,
            "longest_run_days": 0,
            "run_lengths": [],
        }

    equity = equity.sort_index()
    peak = equity.cummax()
    underwater = equity < peak

    run_lengths: list[int] = []
    current_run = 0
    longest_run_bars = 0
    longest_start_idx: int | None = None
    longest_end_idx: int | None = None
    current_start_idx: int | None = None

    for i, is_under in enumerate(underwater.values):
        if is_under:
            if current_run == 0:
                current_start_idx = i
            current_run += 1
            if current_run > longest_run_bars:
                longest_run_bars = current_run
                longest_start_idx = current_start_idx
                longest_end_idx = i
        else:
            if current_run > 0:
                run_lengths.append(current_run)
                current_run = 0
                current_start_idx = None

    if current_run > 0:
        run_lengths.append(current_run)

    pct = float(underwater.sum()) / len(underwater)

    # Calendar days for longest run.
    longest_days = 0
    if longest_start_idx is not None and longest_end_idx is not None:
        t_start = equity.index[longest_start_idx]
        t_end = equity.index[longest_end_idx]
        if hasattr(t_start, "date"):
            longest_days = (t_end - t_start).days
        else:
            longest_days = longest_end_idx - longest_start_idx

    return {
        "series": underwater,
        "pct_time_underwater": pct,
        "longest_run_bars": longest_run_bars,
        "longest_run_days": longest_days,
        "run_lengths": run_lengths,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _add_row(
    rows: list,
    idx,
    vals: np.ndarray,
    peak_vals: np.ndarray,
    trades: pd.DataFrame | None,
    start_i: int,
    trough_i: int,
    end_i: int,
    recovered: bool,
    threshold_pct: float,
) -> None:
    """Compute one drawdown row and append to rows if it exceeds threshold."""
    peak_at_start = float(peak_vals[start_i])
    depth_usd = float(abs(vals[trough_i] - peak_vals[trough_i]))
    depth_pct = depth_usd / abs(peak_at_start) if peak_at_start != 0 else 0.0

    if depth_pct < threshold_pct:
        return

    start_ts = idx[start_i]
    trough_ts = idx[trough_i]
    end_ts = idx[end_i]

    def _days(a, b) -> int:
        try:
            return max(0, (b - a).days)
        except Exception:
            return max(0, int(b) - int(a))

    duration_days = _days(start_ts, trough_ts)
    recovery_days = _days(trough_ts, end_ts) if recovered else 0
    total_days = _days(start_ts, end_ts)

    # Inclusive counts: number of bars *in* each phase.
    duration_bars = trough_i - start_i + 1
    recovery_bars = (end_i - trough_i) if recovered else 0
    total_bars = end_i - start_i + 1

    trades_in_dd = trades_to_trough = trades_to_recovery = 0
    if trades is not None and not trades.empty and "entry_ts" in trades.columns:
        entry_ts = pd.to_datetime(trades["entry_ts"])
        mask_in_dd = (entry_ts >= start_ts) & (entry_ts <= end_ts)
        mask_to_trough = (entry_ts >= start_ts) & (entry_ts <= trough_ts)
        trades_in_dd = int(mask_in_dd.sum())
        trades_to_trough = int(mask_to_trough.sum())
        trades_to_recovery = trades_in_dd - trades_to_trough

    rows.append({
        "start_date": start_ts,
        "trough_date": trough_ts,
        "recovery_date": end_ts if recovered else pd.NaT,
        "depth_usd": round(depth_usd, 2),
        "depth_pct": round(depth_pct, 6),
        "duration_bars": duration_bars,
        "recovery_bars": recovery_bars,
        "total_bars": total_bars,
        "duration_days": duration_days,
        "recovery_days": recovery_days,
        "total_days": total_days,
        "trades_in_dd": trades_in_dd,
        "trades_to_trough": trades_to_trough,
        "trades_to_recovery": trades_to_recovery,
    })


def _empty_dd_catalog() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "start_date", "trough_date", "recovery_date",
        "depth_usd", "depth_pct",
        "duration_bars", "recovery_bars", "total_bars",
        "duration_days", "recovery_days", "total_days",
        "trades_in_dd", "trades_to_trough", "trades_to_recovery",
    ])
