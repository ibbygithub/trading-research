"""Tests for eval/drawdowns.py.

Uses synthetic equity curves with hand-crafted drawdowns so the expected
values are precisely known.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from trading_research.eval.drawdowns import catalog_drawdowns, time_underwater


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_equity(*segments: tuple[float, int]) -> pd.Series:
    """Build an equity curve from (step_size, n_bars) segments.

    Each segment adds `step_size` per bar for `n_bars` bars.
    """
    values = []
    for step, n in segments:
        for i in range(n):
            prev = values[-1] if values else 0.0
            values.append(prev + step)
    idx = pd.date_range("2020-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx)


# ---------------------------------------------------------------------------
# catalog_drawdowns
# ---------------------------------------------------------------------------


def test_catalog_no_drawdown():
    """Monotonically rising equity → no drawdowns."""
    eq = _make_equity((1.0, 100))
    df = catalog_drawdowns(eq, threshold_pct=0.01)
    assert len(df) == 0


def test_catalog_one_drawdown():
    """One clear drawdown, recovers. Check depth and dates."""
    # Rise to 100, fall to 80, recover to 105.
    eq = _make_equity((1.0, 100), (-1.0, 20), (1.25, 20))
    df = catalog_drawdowns(eq, threshold_pct=0.01)
    assert len(df) == 1
    row = df.iloc[0]
    # Peak at bar 100 (value=100), trough at bar 120 (value=80).
    assert row["depth_usd"] == pytest.approx(20.0, abs=0.01)
    assert row["depth_pct"] == pytest.approx(0.2, abs=0.001)
    # Inclusive bar counts: bars 100-119 = 20 bars (trough_i - start_i + 1).
    assert row["duration_bars"] == 20
    # Recovery: bars from trough to recovery (exclusive of start, inclusive of end).
    assert row["recovery_bars"] > 0
    assert row["total_bars"] > 20
    assert pd.notna(row["recovery_date"])


def test_catalog_unrecovered_drawdown():
    """Drawdown that doesn't recover by end of series."""
    eq = _make_equity((1.0, 50), (-0.5, 20))
    df = catalog_drawdowns(eq, threshold_pct=0.01)
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["recovery_date"])
    assert df.iloc[0]["recovery_bars"] == 0


def test_catalog_threshold_filters_small_dd():
    """Small drawdown below threshold is excluded."""
    # Rise 100, fall 0.5 (0.5%), recover.
    eq = _make_equity((1.0, 100), (-0.05, 10), (0.1, 10))
    # threshold = 1%: 0.5% dd should be filtered.
    df = catalog_drawdowns(eq, threshold_pct=0.01)
    assert len(df) == 0

    # With threshold 0%: it's included.
    df2 = catalog_drawdowns(eq, threshold_pct=0.0)
    assert len(df2) == 1


def test_catalog_three_drawdowns():
    """Three distinct drawdown episodes, all recovered."""
    eq = _make_equity(
        (1.0, 50),   # rise to 50
        (-0.5, 20),  # fall 10
        (0.5, 20),   # recover
        (1.0, 50),   # rise to ~70
        (-0.5, 30),  # fall 15
        (0.5, 30),   # recover
        (1.0, 50),   # rise to ~85
        (-0.5, 10),  # fall 5
        (0.5, 10),   # recover
    )
    df = catalog_drawdowns(eq, threshold_pct=0.01)
    assert len(df) == 3
    # All recovered.
    assert df["recovery_date"].notna().all()


def test_catalog_trades_count():
    """Trade count within drawdown is accurate."""
    eq = _make_equity((1.0, 50), (-1.0, 20), (1.0, 20))
    # 5 trades: 2 during drawdown rise phase, 3 during recovery.
    start_dd = eq.index[50]
    trough_dd = eq.index[70]
    end_dd = eq.index[89]

    trades = pd.DataFrame({
        "entry_ts": [
            start_dd,            # in DD, before trough
            start_dd + pd.Timedelta(days=5),   # in DD, before trough
            trough_dd,           # exactly at trough
            trough_dd + pd.Timedelta(days=3),  # after trough
            end_dd,              # at recovery
        ],
        "net_pnl_usd": [10.0, -5.0, 3.0, 7.0, 2.0],
    })
    df = catalog_drawdowns(eq, trades=trades, threshold_pct=0.01)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["trades_in_dd"] > 0


def test_catalog_empty_equity():
    """Empty equity returns empty DataFrame."""
    df = catalog_drawdowns(pd.Series(dtype=float))
    assert df.empty


# ---------------------------------------------------------------------------
# time_underwater
# ---------------------------------------------------------------------------


def test_underwater_flat():
    """Flat equity → zero time underwater."""
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    eq = pd.Series([100.0] * 50, index=idx)
    result = time_underwater(eq)
    assert result["pct_time_underwater"] == pytest.approx(0.0)
    assert result["longest_run_bars"] == 0


def test_underwater_full():
    """Equity that only falls → always underwater (after first bar)."""
    eq = _make_equity((1.0, 1), (-0.5, 99))
    result = time_underwater(eq)
    # All bars after the peak (bar 0) are underwater.
    assert result["pct_time_underwater"] > 0.9
    assert result["longest_run_bars"] > 90


def test_underwater_run_lengths():
    """Two separate underwater runs are cataloged."""
    eq = _make_equity(
        (1.0, 20),   # rise
        (-0.5, 5),   # underwater run 1 (5 bars)
        (0.5, 5),    # recover
        (1.0, 20),   # rise
        (-0.5, 10),  # underwater run 2 (10 bars)
        (0.5, 10),   # recover
    )
    result = time_underwater(eq)
    runs = result["run_lengths"]
    assert len(runs) == 2
    assert max(runs) == result["longest_run_bars"]


def test_underwater_empty():
    """Empty equity returns nan pct."""
    result = time_underwater(pd.Series(dtype=float))
    assert math.isnan(result["pct_time_underwater"])
