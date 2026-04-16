"""Tests for data/resample.py — session-boundary-aware bar resampling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trading_research.data.resample import resample_bars, write_resampled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_1m_bars(
    start: str,
    periods: int,
    freq: str = "1min",
    close_start: float = 110.0,
    tz: str = "UTC",
) -> pd.DataFrame:
    """Build a minimal 1-minute bar DataFrame for testing."""
    ts = pd.date_range(start, periods=periods, freq=freq, tz=tz)
    n = len(ts)
    return pd.DataFrame(
        {
            "timestamp_utc": ts,
            "timestamp_ny": ts.tz_convert("America/New_York"),
            "open": [close_start + i * 0.015625 for i in range(n)],
            "high": [close_start + i * 0.015625 + 0.015625 for i in range(n)],
            "low": [close_start + i * 0.015625 - 0.015625 for i in range(n)],
            "close": [close_start + i * 0.015625 for i in range(n)],
            "volume": [500] * n,
            "buy_volume": [250] * n,
            "sell_volume": [250] * n,
            "up_ticks": [10] * n,
            "down_ticks": [10] * n,
            "total_ticks": [20] * n,
        }
    )


# ---------------------------------------------------------------------------
# Basic aggregation tests
# ---------------------------------------------------------------------------

class TestResampleBars:
    def test_5min_row_count(self):
        """60 consecutive 1m bars → exactly 12 5m bars."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 60)
        out = resample_bars(df, "5min")
        assert len(out) == 12

    def test_ohlc_aggregation(self):
        """open=first open, high=max high, low=min low, close=last close."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)
        out = resample_bars(df, "5min")
        assert len(out) == 1
        row = out.iloc[0]
        assert row["open"] == df["open"].iloc[0]
        assert row["high"] == df["high"].max()
        assert row["low"] == df["low"].min()
        assert row["close"] == df["close"].iloc[-1]

    def test_volume_summed(self):
        """Volume is summed across all 1m bars in the bucket."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)
        out = resample_bars(df, "5min")
        assert out.iloc[0]["volume"] == 5 * 500

    def test_nullable_int_columns_summed(self):
        """buy_volume and friends are summed; if all NaN, stay NaN."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)
        out = resample_bars(df, "5min")
        assert out.iloc[0]["buy_volume"] == 5 * 250

    def test_nullable_all_none_stays_null(self):
        """If all values in a bucket are None, the bucket value is NaN/NA."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)
        df["buy_volume"] = None
        out = resample_bars(df, "5min")
        assert pd.isna(out.iloc[0]["buy_volume"])

    def test_timestamp_ny_recomputed(self):
        """timestamp_ny in output equals timestamp_utc converted to NY."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)
        out = resample_bars(df, "5min")
        expected_ny = out["timestamp_utc"].dt.tz_convert("America/New_York")
        pd.testing.assert_series_equal(
            out["timestamp_ny"].reset_index(drop=True),
            expected_ny.reset_index(drop=True),
            check_names=False,
        )

    def test_empty_input_returns_empty(self):
        """Empty input → empty output with schema columns present."""
        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 0)
        out = resample_bars(df, "5min")
        assert len(out) == 0
        assert "open" in out.columns


# ---------------------------------------------------------------------------
# Session boundary tests
# ---------------------------------------------------------------------------

class TestSessionBoundary:
    def test_gap_produces_no_bar(self):
        """A 60-min gap between sessions should not produce a bar for the gap."""
        # Session 1: 5 bars at 23:00–23:04
        s1 = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)
        # Session 2: 5 bars at 00:05–00:09 next day (simulates a 61-min gap)
        s2 = _make_1m_bars("2024-01-04 00:05:00+00:00", 5)
        df = pd.concat([s1, s2], ignore_index=True)
        out = resample_bars(df, "5min")
        # Both sessions' 5 bars exactly fill one 5m bucket each
        assert len(out) == 2

    def test_maintenance_halt_creates_no_bar(self):
        """60-minute maintenance halt (17:00–18:00 ET = 22:00–23:00 UTC winter)
        should not create a bar that spans the break."""
        # Bars up to 22:00 UTC (17:00 ET = session close)
        pre = _make_1m_bars("2024-01-03 21:55:00+00:00", 5)   # 21:55–21:59
        # Bars from 23:00 UTC (18:00 ET = reopen)
        post = _make_1m_bars("2024-01-03 23:00:00+00:00", 5)  # 23:00–23:04
        df = pd.concat([pre, post], ignore_index=True)
        out = resample_bars(df, "5min")
        # Both groups fall on clean 5m boundaries, no bridging bar
        assert len(out) == 2

    def test_no_gap_across_boundary(self):
        """Each bucket's open/close must come from its own side of the gap,
        not bleed across the session break."""
        # pre starts at 110.0, post starts at 120.0 — clearly distinct prices
        pre = _make_1m_bars("2024-01-03 21:55:00+00:00", 5, close_start=110.0)
        post = _make_1m_bars("2024-01-03 23:00:00+00:00", 5, close_start=120.0)
        df = pd.concat([pre, post], ignore_index=True)
        out = resample_bars(df, "5min")
        assert len(out) == 2
        # First bucket: open should be pre's first open (~110), close ~110.0625
        assert abs(out.iloc[0]["open"] - pre["open"].iloc[0]) < 0.001
        assert abs(out.iloc[0]["close"] - pre["close"].iloc[-1]) < 0.001
        # Second bucket: open should be post's first open (~120), close ~120.0625
        assert abs(out.iloc[1]["open"] - post["open"].iloc[0]) < 0.001
        assert abs(out.iloc[1]["close"] - post["close"].iloc[-1]) < 0.001


# ---------------------------------------------------------------------------
# Output schema test
# ---------------------------------------------------------------------------

class TestWriteResampled:
    def test_write_reads_back_correctly(self, tmp_path: Path):
        """write_resampled roundtrip: written parquet reads back with correct types."""
        import pyarrow.parquet as pq

        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 15)
        out = resample_bars(df, "5min")
        path = tmp_path / "test_5m.parquet"
        write_resampled(out, path)

        assert path.exists()
        tbl = pq.read_table(path)
        assert tbl.num_rows == 3
        assert "timestamp_utc" in tbl.schema.names
        assert "timestamp_ny" in tbl.schema.names
        assert "open" in tbl.schema.names

    def test_written_parquet_matches_bar_schema(self, tmp_path: Path):
        """Written parquet has the correct pyarrow field types from BAR_SCHEMA."""
        import pyarrow as pa
        import pyarrow.parquet as pq
        from trading_research.data.schema import BAR_SCHEMA

        df = _make_1m_bars("2024-01-03 23:00:00+00:00", 15)
        out = resample_bars(df, "5min")
        path = tmp_path / "test_15m.parquet"
        write_resampled(out, path)

        tbl = pq.read_table(path)
        for field in BAR_SCHEMA:
            assert field.name in tbl.schema.names, f"Missing column: {field.name}"
            written_type = tbl.schema.field(field.name).type
            expected_type = field.type
            assert written_type == expected_type, (
                f"{field.name}: got {written_type}, expected {expected_type}"
            )
