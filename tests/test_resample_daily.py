"""Tests for resample_daily — CME trade-date daily bar aggregation."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading_research.data.resample import resample_daily


def _make_1m_bars(start_utc: str, periods: int, close_start: float = 110.0) -> pd.DataFrame:
    ts = pd.date_range(start_utc, periods=periods, freq="1min", tz="UTC")
    ts_ny = ts.tz_convert("America/New_York")
    closes = [close_start + i * 0.015625 for i in range(periods)]
    return pd.DataFrame(
        {
            "timestamp_utc": ts,
            "timestamp_ny": ts_ny,
            "open": closes,
            "high": [c + 0.015625 for c in closes],
            "low": [c - 0.015625 for c in closes],
            "close": closes,
            "volume": 500,
            "buy_volume": pd.array([250] * periods, dtype="Int64"),
            "sell_volume": pd.array([250] * periods, dtype="Int64"),
            "up_ticks": pd.array([10] * periods, dtype="Int64"),
            "down_ticks": pd.array([10] * periods, dtype="Int64"),
            "total_ticks": pd.array([20] * periods, dtype="Int64"),
        }
    )


class TestResampleDaily:
    def test_two_sessions_produce_two_rows(self):
        """Bars from two separate sessions should aggregate into exactly 2 daily rows."""
        # Session 1: 2024-01-08 session — open at 2024-01-07 23:00 UTC
        s1 = _make_1m_bars("2024-01-07 23:00:00+00:00", 300)
        # Session 2: 2024-01-09 session — open at 2024-01-08 23:00 UTC
        s2 = _make_1m_bars("2024-01-08 23:00:00+00:00", 300, close_start=112.0)
        df = pd.concat([s1, s2], ignore_index=True)
        daily = resample_daily(df)
        assert len(daily) == 2

    def test_single_session_ohlcv(self):
        """Single session: open=first close, high=max, low=min, close=last."""
        # Session starting 2024-01-07 23:00 UTC → trade_date 2024-01-08
        df = _make_1m_bars("2024-01-07 23:00:00+00:00", 60)
        daily = resample_daily(df)
        assert len(daily) == 1
        row = daily.iloc[0]
        assert row["open"] == pytest.approx(df["open"].iloc[0])
        assert row["high"] == pytest.approx(df["high"].max())
        assert row["low"] == pytest.approx(df["low"].min())
        assert row["close"] == pytest.approx(df["close"].iloc[-1])

    def test_volume_summed(self):
        df = _make_1m_bars("2024-01-07 23:00:00+00:00", 60)
        daily = resample_daily(df)
        assert daily.iloc[0]["volume"] == 60 * 500

    def test_18_et_open_assigns_to_next_calendar_day(self):
        """18:00 ET on Sunday 2024-01-07 = 23:00 UTC → trade_date = 2024-01-08 (Monday)."""
        # One bar at 23:00 UTC Sunday.
        df = _make_1m_bars("2024-01-07 23:00:00+00:00", 1)
        daily = resample_daily(df)
        # The session open timestamp should be the 23:00 UTC Sunday bar.
        assert daily.iloc[0]["timestamp_utc"] == pd.Timestamp(
            "2024-01-07 23:00:00", tz="UTC"
        )

    def test_empty_input_returns_empty(self):
        df = _make_1m_bars("2024-01-07 23:00:00+00:00", 0)
        daily = resample_daily(df)
        assert len(daily) == 0

    def test_nullable_int_summed(self):
        df = _make_1m_bars("2024-01-07 23:00:00+00:00", 10)
        daily = resample_daily(df)
        assert daily.iloc[0]["buy_volume"] == 10 * 250

    def test_nullable_all_none_stays_null(self):
        df = _make_1m_bars("2024-01-07 23:00:00+00:00", 10)
        df["buy_volume"] = pd.NA
        daily = resample_daily(df)
        assert pd.isna(daily.iloc[0]["buy_volume"])
