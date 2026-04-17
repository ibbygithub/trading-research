"""Tests for VWAP indicators (session, weekly, monthly)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from trading_research.indicators.vwap import (
    compute_monthly_vwap,
    compute_session_vwap,
    compute_weekly_vwap,
)
from tests.indicators.conftest import make_ohlcv


def _make_with_gap(gap_minutes: int = 120) -> pd.DataFrame:
    """Two 10-bar sessions separated by a gap."""
    s1 = make_ohlcv(10, start="2024-01-03 23:00:00+00:00", close_start=110.0)
    # Session 2 starts after a gap.
    s2_start = pd.Timestamp("2024-01-03 23:00:00+00:00") + pd.Timedelta(minutes=10 + gap_minutes)
    s2 = make_ohlcv(10, start=str(s2_start), close_start=112.0)
    df = pd.concat([s1, s2], ignore_index=True)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = df["timestamp_utc"].dt.tz_convert("America/New_York")
    return df


class TestSessionVWAP:
    def test_resets_on_gap(self):
        """A gap > 60 min should reset the session VWAP."""
        df = _make_with_gap(gap_minutes=120)
        vwap = compute_session_vwap(df)['vwap']
        # Session 1: first bar's vwap should equal its own close (single bar cumulative).
        assert vwap.iloc[0] == pytest.approx(df["close"].iloc[0], rel=1e-6)
        # Session 2 starts at index 10: vwap should reset to the first bar of session 2.
        assert vwap.iloc[10] == pytest.approx(df["close"].iloc[10], rel=1e-6)

    def test_no_reset_within_session(self):
        """Without a gap, VWAP accumulates across all bars."""
        df = make_ohlcv(20)
        vwap = compute_session_vwap(df)['vwap']
        # VWAP should be a running weighted average, not repeating single bar values.
        # First bar equals its close; subsequent bars are weighted means.
        assert vwap.iloc[0] == pytest.approx(df["close"].iloc[0], rel=1e-6)
        # After bar 1, vwap should be the average of bar 0 and bar 1, not bar 1's close.
        expected_vwap_bar1 = (df["close"].iloc[0] + df["close"].iloc[1]) / 2.0
        assert vwap.iloc[1] == pytest.approx(expected_vwap_bar1, rel=1e-6)

    def test_single_bar_session(self):
        """A session with one bar: VWAP == close of that bar."""
        df = make_ohlcv(1)
        vwap = compute_session_vwap(df)['vwap']
        assert vwap.iloc[0] == pytest.approx(df["close"].iloc[0], rel=1e-6)

    def test_no_lookahead(self):
        """Session VWAP should not use future bars."""
        df = make_ohlcv(100)
        full = compute_session_vwap(df)['vwap']
        partial = compute_session_vwap(df.iloc[:51])
        assert full.iloc[50] == pytest.approx(partial.iloc[-1], rel=1e-6)

    def test_gap_59_does_not_reset(self):
        """A gap < 60 min should NOT reset session VWAP (still same session)."""
        # _make_with_gap: s1 has 10 bars at 1-min intervals (0..9 min from start),
        # s2_start = start + (10 + gap_minutes) min. Gap between s1[-1]=9min and
        # s2[0]=(10+gap)min is (gap+1) minutes. To get a gap of 59 min use gap_minutes=58.
        df = _make_with_gap(gap_minutes=58)  # actual gap = 59 min, < 60 → no reset
        vwap = compute_session_vwap(df)['vwap']
        # No reset: bar 10's VWAP accumulates from bar 0, so it's NOT equal to bar 10's close alone.
        expected_if_reset = df["close"].iloc[10]
        # If VWAP reset, it would equal the close of the first bar of session 2.
        # If no reset, it's a weighted average of all 11 bars.
        assert vwap.iloc[10] != pytest.approx(expected_if_reset, abs=0.01)


class TestWeeklyVWAP:
    def _multi_week_df(self) -> pd.DataFrame:
        """Create bars spanning two ISO weeks (Mon 2024-01-08 and Mon 2024-01-15)."""
        # Use 18:00 ET Monday which is 23:00 UTC (trade_date = Monday via +6h)
        week1 = make_ohlcv(
            10, start="2024-01-08 23:00:00+00:00", close_start=110.0
        )
        # Second week starts at 2024-01-15 23:00 UTC = start of Jan 15 trade_date
        week2 = make_ohlcv(
            10, start="2024-01-15 23:00:00+00:00", close_start=115.0
        )
        df = pd.concat([week1, week2], ignore_index=True)
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df["timestamp_ny"] = df["timestamp_utc"].dt.tz_convert("America/New_York")
        return df

    def test_resets_at_new_week(self):
        df = self._multi_week_df()
        vwap = compute_weekly_vwap(df)['vwap']
        # First bar of week 2 (index 10) should reset to its own close.
        assert vwap.iloc[10] == pytest.approx(df["close"].iloc[10], rel=1e-6)

    def test_accumulates_within_week(self):
        df = self._multi_week_df()
        vwap = compute_weekly_vwap(df)['vwap']
        # Bar 1 of week 1: vwap is the average of bar 0 and bar 1 (equal volumes).
        expected = (df["close"].iloc[0] + df["close"].iloc[1]) / 2.0
        assert vwap.iloc[1] == pytest.approx(expected, rel=1e-6)

    def test_no_lookahead(self):
        df = self._multi_week_df()
        full = compute_weekly_vwap(df)['vwap']
        partial = compute_weekly_vwap(df.iloc[:11])
        assert full.iloc[10] == pytest.approx(partial.iloc[-1], rel=1e-6)


class TestMonthlyVWAP:
    def _multi_month_df(self) -> pd.DataFrame:
        """Create bars spanning two months: Jan and Feb 2024.

        CME trade-date convention: 18:00 ET session open = timestamp + 6h lands on
        the next calendar day. So bars starting at 2024-01-08 23:00 UTC (18:00 ET
        Jan 8) have trade_date = Jan 9 (January). Bars at 2024-02-05 23:00 UTC
        (18:00 ET Feb 5) have trade_date = Feb 6 (February).
        """
        jan = make_ohlcv(10, start="2024-01-08 23:00:00+00:00", close_start=110.0)
        feb = make_ohlcv(10, start="2024-02-05 23:00:00+00:00", close_start=115.0)
        df = pd.concat([jan, feb], ignore_index=True)
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df["timestamp_ny"] = df["timestamp_utc"].dt.tz_convert("America/New_York")
        return df

    def test_resets_at_new_month(self):
        df = self._multi_month_df()
        vwap = compute_monthly_vwap(df)['vwap']
        # First bar of Feb (index 10) should reset.
        assert vwap.iloc[10] == pytest.approx(df["close"].iloc[10], rel=1e-6)

    def test_no_lookahead(self):
        df = self._multi_month_df()
        full = compute_monthly_vwap(df)['vwap']
        partial = compute_monthly_vwap(df.iloc[:11])
        assert full.iloc[10] == pytest.approx(partial.iloc[-1], rel=1e-6)
