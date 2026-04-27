"""Integration tests for run_stationarity_suite and StationarityReport persistence.

Uses synthetic OHLCV bars throughout — no real data required.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from trading_research.stats.stationarity import (
    StationarityReport,
    run_stationarity_suite,
    write_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_instrument(symbol: str = "TEST") -> SimpleNamespace:
    """Minimal instrument stand-in — stationarity suite only needs .symbol."""
    return SimpleNamespace(symbol=symbol)


def _make_bars(n: int = 2000, phi: float = 0.5, seed: int = 42) -> pd.DataFrame:
    """Synthetic 1-minute OHLCV bars.

    Close is an AR(1) process centred on 1.1000 (EUR/USD-ish).
    Volume is random positive integers.  Timestamps are minute-spaced UTC.
    """
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(n) * 0.001  # small tick-sized noise
    close = np.empty(n)
    close[0] = 1.1000
    for t in range(1, n):
        close[t] = 1.1000 + phi * (close[t - 1] - 1.1000) + eps[t]

    volume = rng.integers(100, 1000, size=n).astype(float)

    ts_utc = pd.date_range("2024-01-02 14:30:00", periods=n, freq="1min", tz="UTC")

    return pd.DataFrame(
        {
            "timestamp_utc": ts_utc,
            "timestamp_ny": ts_utc.tz_convert("America/New_York"),
            "open": close * (1 + rng.uniform(-0.0001, 0.0001, n)),
            "high": close * (1 + rng.uniform(0.0, 0.0005, n)),
            "low": close * (1 - rng.uniform(0.0, 0.0005, n)),
            "close": close,
            "volume": volume,
        }
    )


# ---------------------------------------------------------------------------
# Suite structure tests
# ---------------------------------------------------------------------------


def test_suite_runs_on_synthetic_bars() -> None:
    """run_stationarity_suite returns a StationarityReport with expected keys."""
    instrument = _make_instrument()
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["1m", "5m"])

    assert isinstance(report, StationarityReport)
    assert report.instrument == "TEST"
    assert isinstance(report.run_ts, datetime)
    assert isinstance(report.composite, dict)
    assert len(report.composite) > 0

    # Expected series for timeframes 1m and 5m
    expected_series = {"log_returns_1m", "log_price_level", "log_returns_5m", "vwap_spread_5m"}
    assert set(report.composite.keys()) == expected_series


def test_suite_results_dataframe_schema() -> None:
    """Results DataFrame must have all required columns from design doc §5."""
    instrument = _make_instrument()
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["1m"])

    required_cols = {
        "instrument", "timeframe", "series_name", "test_name",
        "statistic", "p_value", "n_lags", "n_obs", "interpretation",
        "composite", "run_ts", "code_version", "data_version",
    }
    assert required_cols.issubset(set(report.results.columns))


def test_suite_three_rows_per_series() -> None:
    """Each series produces exactly 3 rows: adf, hurst, ou_halflife."""
    instrument = _make_instrument()
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["1m"])

    for series_name in report.composite:
        series_rows = report.results[report.results["series_name"] == series_name]
        tests = set(series_rows["test_name"])
        assert tests == {"adf", "hurst", "ou_halflife"}, (
            f"{series_name}: expected {{adf, hurst, ou_halflife}}, got {tests}"
        )


def test_suite_composite_labels_are_valid() -> None:
    """All composite labels must be one of the design doc §4.4 values."""
    valid_labels = {
        "TRADEABLE_MR", "NON_STATIONARY", "RANDOM_WALK", "TRENDING",
        "TOO_FAST", "TOO_SLOW", "INDETERMINATE",
    }
    instrument = _make_instrument()
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])

    for series_name, label in report.composite.items():
        assert label in valid_labels, (
            f"{series_name}: unexpected label '{label}'"
        )


def test_suite_all_timeframes() -> None:
    """Suite runs on all three standard timeframes without error."""
    instrument = _make_instrument()
    bars = _make_bars(n=3000)
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["1m", "5m", "15m"])

    expected = {
        "log_returns_1m", "log_price_level",
        "log_returns_5m", "vwap_spread_5m",
        "log_returns_15m", "vwap_spread_15m",
    }
    assert set(report.composite.keys()) == expected


# ---------------------------------------------------------------------------
# Composite classification correctness — design doc §8.5
# ---------------------------------------------------------------------------


def test_composite_non_stationary_random_walk() -> None:
    """Random walk (φ=1.0) price level should be NON_STATIONARY."""
    rng = np.random.default_rng(42)
    n = 2000
    close = np.cumsum(rng.standard_normal(n) * 0.001) + 1.1
    ts = pd.date_range("2024-01-02 14:30:00", periods=n, freq="1min", tz="UTC")
    volume = rng.integers(100, 500, size=n).astype(float)
    bars = pd.DataFrame({
        "timestamp_utc": ts,
        "open": close, "high": close * 1.0001, "low": close * 0.9999,
        "close": close, "volume": volume,
    })
    instrument = _make_instrument()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["1m"])
    # log_price_level on a random walk must be NON_STATIONARY
    assert report.composite.get("log_price_level") == "NON_STATIONARY", (
        f"log_price_level composite={report.composite.get('log_price_level')}"
    )


def test_composite_near_unit_root_too_slow() -> None:
    """AR(1) φ=0.999 on 5m bars: stationary but half-life >> max (24 bars) → TOO_SLOW."""
    rng = np.random.default_rng(42)
    n = 4000
    phi = 0.999
    close = np.empty(n)
    close[0] = 1.1
    eps = rng.standard_normal(n) * 0.0001
    for t in range(1, n):
        close[t] = 1.1 + phi * (close[t - 1] - 1.1) + eps[t]

    ts = pd.date_range("2024-01-02 14:30:00", periods=n, freq="1min", tz="UTC")
    volume = rng.integers(100, 500, size=n).astype(float)
    bars = pd.DataFrame({
        "timestamp_utc": ts,
        "open": close, "high": close * 1.0001, "low": close * 0.9999,
        "close": close, "volume": volume,
    })
    instrument = _make_instrument()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])
    # vwap_spread_5m on near-unit-root process should not be TRADEABLE_MR
    label = report.composite.get("vwap_spread_5m", "MISSING")
    assert label in {"TOO_SLOW", "NON_STATIONARY", "RANDOM_WALK", "INDETERMINATE"}, (
        f"Expected non-tradeable label for φ=0.999, got {label}"
    )


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


def test_report_serialization_round_trip() -> None:
    """report → to_summary_dict → JSON → parsed → composite is identical."""
    instrument = _make_instrument("6E")
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])

    json_str = json.dumps(report.to_summary_dict())
    restored = json.loads(json_str)

    assert restored["instrument"] == report.instrument
    assert restored["series"] == report.composite


def test_report_to_json_valid() -> None:
    """to_summary_json() must produce valid JSON."""
    instrument = _make_instrument()
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])
    json_str = report.to_summary_json()
    parsed = json.loads(json_str)
    assert "instrument" in parsed
    assert "series" in parsed


def test_write_report_creates_files(tmp_path: Path) -> None:
    """write_report() must create all three output files."""
    instrument = _make_instrument("ZN")
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])

    parquet_path, json_path, md_path = write_report(report, tmp_path)

    assert parquet_path.exists(), "parquet not written"
    assert json_path.exists(), "JSON not written"
    assert md_path.exists(), "markdown not written"


def test_write_report_json_roundtrip(tmp_path: Path) -> None:
    """JSON written by write_report() must deserialise to the correct composite."""
    instrument = _make_instrument("ZN")
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])

    _, json_path, _ = write_report(report, tmp_path)
    restored = json.loads(json_path.read_text(encoding="utf-8"))

    assert restored["instrument"] == "ZN"
    assert restored["series"] == report.composite


def test_write_report_parquet_roundtrip(tmp_path: Path) -> None:
    """Parquet written by write_report() must roundtrip without data loss."""
    instrument = _make_instrument("ZN")
    bars = _make_bars()
    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=["5m"])

    parquet_path, _, _ = write_report(report, tmp_path)
    df = pd.read_parquet(parquet_path, engine="pyarrow")

    assert len(df) == len(report.results)
    assert set(df.columns) == set(report.results.columns)
