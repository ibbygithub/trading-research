"""Tests for the bar dataset validator.

These tests use synthetic parquet data so they never touch the network or
require real downloaded files to be present.
"""

from __future__ import annotations

from datetime import date, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trading_research.core.instruments import InstrumentRegistry
from trading_research.data.schema import BAR_SCHEMA
from trading_research.data.validate import validate_bar_dataset, _is_post_maintenance_gap

_registry = InstrumentRegistry()
_ZN = _registry.get("ZN")
_6A = _registry.get("6A")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parquet(tmp_path: Path, timestamps_utc: list[str], **overrides) -> Path:
    """Write a minimal valid parquet with the given UTC timestamps."""
    rows = []
    for ts_str in timestamps_utc:
        ts_utc = pd.Timestamp(ts_str, tz="UTC")
        ts_ny = ts_utc.tz_convert("America/New_York")
        row = {
            "timestamp_utc": ts_utc,
            "timestamp_ny": ts_ny,
            "open": 113.5,
            "high": 113.75,
            "low": 113.25,
            "close": 113.5,
            "volume": 100,
            "buy_volume": 60,
            "sell_volume": 40,
            "up_ticks": 10,
            "down_ticks": 8,
            "total_ticks": 18,
        }
        row.update(overrides)
        rows.append(row)

    df = pd.DataFrame(rows)
    for col in ["timestamp_utc", "timestamp_ny"]:
        df[col] = pd.to_datetime(df[col], utc=True) if col == "timestamp_utc" else pd.to_datetime(df[col])

    table = pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)
    path = tmp_path / "ZN_1m_test.parquet"
    pq.write_table(table, path)
    return path


def _all_jan2_bars() -> list[str]:
    """All expected 1-minute bars for Jan 2 2024 per the CBOT_Bond calendar."""
    import pandas_market_calendars as mcal
    cal = mcal.get_calendar("CBOT_Bond")
    sched = cal.schedule("2024-01-02", "2024-01-02")
    return [str(ts) for ts in mcal.date_range(sched, frequency="1min")]


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------

def test_perfect_dataset_passes(tmp_path: Path) -> None:
    """A dataset that exactly matches the calendar for a single day passes."""
    timestamps = _all_jan2_bars()
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is True
    assert report["failures"] == []
    assert report["duplicate_timestamps"] == 0
    assert report["negative_volumes"] == 0
    assert report["inverted_high_low"] == 0
    assert report["row_count"] == len(timestamps)


def test_report_written_next_to_parquet(tmp_path: Path) -> None:
    """Quality JSON is written next to the parquet when write_report=True."""
    timestamps = _all_jan2_bars()
    path = _make_parquet(tmp_path, timestamps)
    validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=True
    )
    expected_json = tmp_path / "ZN_1m_test.quality.json"
    assert expected_json.exists()
    import json
    report = json.loads(expected_json.read_text())
    assert "passed" in report
    assert "failures" in report


def test_report_not_written_when_suppressed(tmp_path: Path) -> None:
    """write_report=False leaves no quality.json on disk."""
    timestamps = _all_jan2_bars()
    path = _make_parquet(tmp_path, timestamps)
    validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert not list(tmp_path.glob("*.quality.json"))


# ---------------------------------------------------------------------------
# Structural failure detection
# ---------------------------------------------------------------------------

def test_duplicate_timestamps_fails(tmp_path: Path) -> None:
    timestamps = _all_jan2_bars()
    timestamps.append(timestamps[10])
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is False
    assert report["duplicate_timestamps"] == 1
    assert any("duplicate" in f.lower() for f in report["failures"])


def test_inverted_ohlc_fails(tmp_path: Path) -> None:
    timestamps = _all_jan2_bars()[:5]
    path = _make_parquet(tmp_path, timestamps, high=113.0, low=114.0)  # low > high
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is False
    assert report["inverted_high_low"] == len(timestamps)


def test_missing_full_session_fails(tmp_path: Path) -> None:
    """A session with only 5 bars (huge gap for the rest) is a structural failure.

    The Jan 2 session starts at 23:00 UTC Jan 1. Providing only the first 5 bars
    leaves a >1300-bar gap — far longer than the 30-bar post-maintenance exclusion
    limit — so it must be classified as structural and cause passed=False.
    """
    timestamps = _all_jan2_bars()[:5]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is False
    assert len(report["large_gaps"]) > 0


def test_large_gap_fails(tmp_path: Path) -> None:
    """A gap of > 5 bars in RTH is a structural failure.

    Bar 900 is well inside RTH (RTH opens ~bar 860 for the Jan 2 session).
    Off-hours gaps of 6-60 bars are treated as overnight_minor, not structural.
    """
    all_ts = _all_jan2_bars()
    gap_start = 900  # RTH — ~10:00 AM ET
    gap_end = gap_start + 10
    timestamps = all_ts[:gap_start] + all_ts[gap_end:]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is False
    assert len(report["large_gaps"]) >= 1
    assert report["large_gaps"][0]["bars_missing"] == 10


def test_minor_gap_does_not_fail(tmp_path: Path) -> None:
    """A gap of ≤ 5 consecutive bars is informational, not a failure."""
    all_ts = _all_jan2_bars()
    gap_start = 300
    gap_end = gap_start + 5
    timestamps = all_ts[:gap_start] + all_ts[gap_end:]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is True
    assert report["large_gaps"] == []
    assert report["minor_gap_count"] == 1
    assert report["missing_bars_minor_gaps"] == 5


# ---------------------------------------------------------------------------
# Failure reporting completeness — the top-3 truncation bug is fixed
# ---------------------------------------------------------------------------

def test_all_large_gaps_reported_not_truncated(tmp_path: Path) -> None:
    """ALL structural large gaps appear in large_gaps — not just the top-3.

    Gaps are placed in RTH (bar 860+) where the >5-bar threshold applies.
    Off-hours 10-bar gaps would be classified as overnight_minor, not structural.
    """
    all_ts = _all_jan2_bars()
    # 5 separate 10-bar gaps spread across RTH (bars 860-1200).
    gaps = [(870, 880), (940, 950), (1010, 1020), (1080, 1090), (1150, 1160)]
    keep = set(range(len(all_ts)))
    for start, end in gaps:
        keep -= set(range(start, end))
    timestamps = [all_ts[i] for i in sorted(keep)]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is False
    # All 5 gaps must appear in large_gaps — not truncated to 3.
    assert len(report["large_gaps"]) == 5
    assert all(g["bars_missing"] == 10 for g in report["large_gaps"])


def test_failures_list_covers_all_rth_gaps(tmp_path: Path) -> None:
    """Each RTH large gap gets its own entry in failures (not grouped).

    The Jan 2 2024 session opens at 23:00 UTC Jan 1. RTH starts at 08:20 ET =
    13:20 UTC Jan 2, which is ~860 bars into the session. Gaps must be placed
    at bar indices >= 860 to land inside RTH.
    """
    all_ts = _all_jan2_bars()
    # Bar 860 ≈ RTH open (13:20 UTC Jan 2 = 08:20 ET). Place 4 gaps well inside RTH.
    gaps = [(900, 910), (1000, 1010), (1050, 1060), (1100, 1110)]
    keep = set(range(len(all_ts)))
    for start, end in gaps:
        keep -= set(range(start, end))
    timestamps = [all_ts[i] for i in sorted(keep)]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is False
    rth_failure_lines = [f for f in report["failures"] if "RTH" in f]
    # Each of the 4 gaps in RTH should have its own failure line.
    assert len(rth_failure_lines) == 4


# ---------------------------------------------------------------------------
# Post-maintenance gap exclusion
# ---------------------------------------------------------------------------

def test_is_post_maintenance_gap_true_in_window() -> None:
    """Gaps starting right after CME maintenance reopen are classified as excluded.

    CDT = UTC-5 (summer). CME reopen 17:00 CT = 22:00 UTC in summer.
    A 20-bar gap starting at 22:01 UTC on a summer date is in the window.
    """
    # June 3 2024 is in CDT (UTC-5). 17:01 CT = 22:01 UTC.
    run = [
        pd.Timestamp("2024-06-03 22:01:00+00:00") + pd.Timedelta(minutes=i)
        for i in range(20)
    ]
    assert _is_post_maintenance_gap(run) is True


def test_is_post_maintenance_gap_false_outside_window() -> None:
    """A gap at 14:00 UTC is not in the post-maintenance window."""
    run = [
        pd.Timestamp("2024-06-03 14:00:00+00:00") + pd.Timedelta(minutes=i)
        for i in range(20)
    ]
    assert _is_post_maintenance_gap(run) is False


def test_is_post_maintenance_gap_false_if_too_long() -> None:
    """A gap longer than 30 bars is structural even if it starts in the window."""
    # 31 bars starting at 22:01 UTC (summer) = 17:01 CT — in the window, but too long.
    run = [
        pd.Timestamp("2024-06-03 22:01:00+00:00") + pd.Timedelta(minutes=i)
        for i in range(31)
    ]
    assert _is_post_maintenance_gap(run) is False


def test_post_maintenance_gaps_excluded_from_verdict(tmp_path: Path) -> None:
    """A gap in the post-maintenance window does not cause passed=False.

    January is CST (UTC-6). CME reopen 17:00 CT = 23:00 UTC.
    The Jan 2 2024 TRADE DATE session opens at 23:00 UTC on Jan 1 (the previous
    calendar day in UTC). Post-maintenance bars are at 23:01–23:30 UTC on Jan 1.
    """
    all_ts = _all_jan2_bars()
    # The session starts at 23:00 UTC Jan 1 2024 (Jan 2 trade date).
    # Post-maintenance window: 23:01–23:30 UTC Jan 1 2024.
    maintenance_start = pd.Timestamp("2024-01-01 23:01:00+00:00")
    excluded_ts = {
        str(maintenance_start + pd.Timedelta(minutes=i)) for i in range(20)
    }
    timestamps = [ts for ts in all_ts if ts not in excluded_ts]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is True, f"Should pass but got failures: {report['failures']}"
    assert report["excluded_gaps_count"] >= 1
    assert any(
        g["exclusion_reason"] == "post_maintenance"
        for g in report["excluded_gaps"]
    )


# ---------------------------------------------------------------------------
# Juneteenth calendar patch
# ---------------------------------------------------------------------------

def test_juneteenth_not_a_failure_for_cbot(tmp_path: Path) -> None:
    """June 19 2024 (Juneteenth) is a CME closure — missing bars should not fail."""
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar("CBOT_Bond")
    sched = cal.schedule("2024-06-18", "2024-06-20")
    all_ts = [str(ts) for ts in mcal.date_range(sched, frequency="1min")]

    june19_key = pd.Timestamp("2024-06-19")
    sess_open = sched.loc[june19_key, "market_open"]
    sess_close = sched.loc[june19_key, "market_close"]
    june19_session_ts = {
        str(sess_open + pd.Timedelta(minutes=i))
        for i in range(int((sess_close - sess_open).total_seconds() // 60))
    }
    timestamps = [ts for ts in all_ts if ts not in june19_session_ts]

    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 6, 18), date(2024, 6, 20), write_report=False
    )
    assert report["passed"] is True, f"Juneteenth gap caused failure: {report['failures']}"
    assert "juneteenth_2022+" in report.get("calendar_patches_applied", [])


def test_juneteenth_not_applied_before_2022(tmp_path: Path) -> None:
    """Juneteenth patch is not applied for years before 2022."""
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar("CBOT_Bond")
    sched = cal.schedule("2019-06-19", "2019-06-19")
    if len(sched) == 0:
        pytest.skip("CBOT_Bond has no session on 2019-06-19 in this library version")

    all_ts = [str(ts) for ts in mcal.date_range(sched, frequency="1min")]
    timestamps = all_ts[:5]
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2019, 6, 19), date(2019, 6, 19), write_report=False
    )
    assert report["passed"] is False


# ---------------------------------------------------------------------------
# Calendar-level checks
# ---------------------------------------------------------------------------

def test_holiday_exclusion(tmp_path: Path) -> None:
    """Jan 1 is a holiday — the calendar should have no sessions for it."""
    import pandas_market_calendars as mcal
    cal = mcal.get_calendar("CBOT_Bond")
    sched = cal.schedule("2024-01-01", "2024-01-01")
    assert len(sched) == 0


def test_expected_count_matches_calendar(tmp_path: Path) -> None:
    """The report's expected_row_count matches what we independently compute."""
    import pandas_market_calendars as mcal
    cal = mcal.get_calendar("CBOT_Bond")
    sched = cal.schedule("2024-01-02", "2024-01-02")
    expected = len(mcal.date_range(sched, frequency="1min"))

    timestamps = _all_jan2_bars()
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["expected_row_count"] == expected


def test_calendar_read_from_instrument(tmp_path: Path) -> None:
    """calendar field in the report comes from instrument.calendar_name."""
    timestamps = _all_jan2_bars()
    path = _make_parquet(tmp_path, timestamps)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["calendar"] == _ZN.calendar_name


# ---------------------------------------------------------------------------
# Buy/sell volume coverage
# ---------------------------------------------------------------------------

def test_zero_buy_sell_coverage_still_passes(tmp_path: Path) -> None:
    """A dataset with all-null buy/sell volume passes — coverage is informational."""
    timestamps = _all_jan2_bars()
    path = _make_parquet(tmp_path, timestamps, buy_volume=None, sell_volume=None)
    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )
    assert report["passed"] is True
    assert report["buy_sell_volume_coverage_pct"] == 0.0


# ---------------------------------------------------------------------------
# Per-symbol RTH window (OI-010)
# ---------------------------------------------------------------------------

def test_rth_window_is_per_symbol(tmp_path: Path) -> None:
    """Gap classification must use the symbol's RTH window, not ZN's hardcoded one.

    ZN RTH: 08:20–15:00 ET.  6A RTH: 08:00–17:00 ET.

    A gap at 08:05 ET is *outside* ZN RTH but *inside* 6A RTH.  When
    validate_bar_dataset is called with instrument=_6A, that gap must be
    classified as an RTH gap (structural), not an overnight gap.
    """
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar("CMEGlobex_FX")
    sched = cal.schedule("2024-01-02", "2024-01-02")
    all_bars = [str(ts) for ts in mcal.date_range(sched, frequency="1min")]

    remove_utc = {
        "2024-01-02 13:05:00+00:00",
        "2024-01-02 13:06:00+00:00",
        "2024-01-02 13:07:00+00:00",
        "2024-01-02 13:08:00+00:00",
        "2024-01-02 13:09:00+00:00",
        "2024-01-02 13:10:00+00:00",
    }
    trimmed = [ts for ts in all_bars if ts not in remove_utc]

    rows = []
    for ts_str in trimmed:
        ts_utc = pd.Timestamp(ts_str, tz="UTC")
        ts_ny = ts_utc.tz_convert("America/New_York")
        rows.append({
            "timestamp_utc": ts_utc,
            "timestamp_ny": ts_ny,
            "open": 0.6500,
            "high": 0.6510,
            "low": 0.6490,
            "close": 0.6505,
            "volume": 100,
            "buy_volume": 60,
            "sell_volume": 40,
            "up_ticks": 10,
            "down_ticks": 8,
            "total_ticks": 18,
        })

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = pd.to_datetime(df["timestamp_ny"])
    tbl = pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)
    path = tmp_path / "6A_1m_test.parquet"
    pq.write_table(tbl, path)

    report = validate_bar_dataset(
        path, _6A, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )

    rth_large = [g for g in report["large_gaps"] if g["in_rth"]]
    assert len(rth_large) >= 1, (
        "A gap inside 6A RTH (08:05 ET) was not classified as an RTH gap. "
        "Likely still using ZN's 08:20 open instead of 6A's 08:00 open."
    )


def test_zn_rth_window_unchanged(tmp_path: Path) -> None:
    """ZN RTH (08:20 ET open) still reads correctly from the registry after OI-010."""
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar("CBOT_Bond")
    sched = cal.schedule("2024-01-02", "2024-01-02")
    all_bars = [str(ts) for ts in mcal.date_range(sched, frequency="1min")]

    remove_utc = {
        "2024-01-02 13:05:00+00:00",
        "2024-01-02 13:06:00+00:00",
        "2024-01-02 13:07:00+00:00",
        "2024-01-02 13:08:00+00:00",
        "2024-01-02 13:09:00+00:00",
        "2024-01-02 13:10:00+00:00",
    }
    trimmed = [ts for ts in all_bars if ts not in remove_utc]

    rows = []
    for ts_str in trimmed:
        ts_utc = pd.Timestamp(ts_str, tz="UTC")
        ts_ny = ts_utc.tz_convert("America/New_York")
        rows.append({
            "timestamp_utc": ts_utc,
            "timestamp_ny": ts_ny,
            "open": 113.5,
            "high": 113.75,
            "low": 113.25,
            "close": 113.5,
            "volume": 100,
            "buy_volume": 60,
            "sell_volume": 40,
            "up_ticks": 10,
            "down_ticks": 8,
            "total_ticks": 18,
        })

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = pd.to_datetime(df["timestamp_ny"])
    tbl = pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)
    path = tmp_path / "ZN_1m_rth_test.parquet"
    pq.write_table(tbl, path)

    report = validate_bar_dataset(
        path, _ZN, date(2024, 1, 2), date(2024, 1, 2), write_report=False
    )

    rth_large = [g for g in report["large_gaps"] if g["in_rth"]]
    assert len(rth_large) == 0, (
        "A pre-RTH gap (08:05 ET, before ZN's 08:20 open) was misclassified "
        "as an RTH gap. ZN RTH window may have changed incorrectly."
    )
