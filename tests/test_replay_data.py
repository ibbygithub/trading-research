"""Tests for replay.data — load_window() and DataNotFoundError."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from trading_research.replay.data import DataNotFoundError, load_window

# Use the real data directory relative to this file.
_DATA_ROOT = Path(__file__).parents[1] / "data"

# 30-day window well within the available history.
_FROM = datetime(2024, 1, 2)
_TO = datetime(2024, 2, 1)


@pytest.fixture(scope="module")
def window() -> dict[str, pd.DataFrame]:
    return load_window("ZN", _FROM, _TO, data_root=_DATA_ROOT)


def test_all_timeframes_present(window):
    assert set(window.keys()) == {"5m", "15m", "60m", "1D"}


def test_dataframes_nonempty(window):
    for tf, df in window.items():
        assert not df.empty, f"{tf} DataFrame is empty"


def test_index_is_utc_datetimeindex(window):
    for tf, df in window.items():
        assert isinstance(df.index, pd.DatetimeIndex), f"{tf} index is not DatetimeIndex"
        assert str(df.index.tz) == "UTC", f"{tf} index is not UTC (got {df.index.tz})"


def test_window_bounds_respected(window):
    from_ts = pd.Timestamp(_FROM, tz="UTC")
    to_ts = pd.Timestamp(_TO, tz="UTC")
    for tf, df in window.items():
        assert df.index.min() >= from_ts, f"{tf} has rows before from_dt"
        assert df.index.max() <= to_ts, f"{tf} has rows after to_dt"


def test_5m_15m_have_indicator_columns(window):
    required = {"vwap_session", "bb_upper", "bb_lower", "ofi_14", "sma_200"}
    for tf in ("5m", "15m"):
        missing = required - set(window[tf].columns)
        assert not missing, f"{tf} missing indicator columns: {missing}"


def test_60m_1d_have_sma_200(window):
    for tf in ("60m", "1D"):
        assert "sma_200" in window[tf].columns, f"{tf} missing sma_200"
        # sma_200 should have valid (non-NaN) values — full history was loaded
        # before filtering so warm-up NaNs are excluded from the window.
        valid = window[tf]["sma_200"].dropna()
        assert not valid.empty, f"{tf} sma_200 is all NaN"


def test_60m_1d_no_indicator_columns(window):
    """CLEAN DataFrames must not contain columns that belong in FEATURES."""
    features_only = {"bb_upper", "rsi_14", "vwap_session", "macd"}
    for tf in ("60m", "1D"):
        unexpected = features_only & set(window[tf].columns)
        assert not unexpected, f"{tf} contains FEATURES-only columns: {unexpected}"


def test_data_not_found_error():
    with pytest.raises(DataNotFoundError):
        load_window("INVALID_SYMBOL", _FROM, _TO, data_root=_DATA_ROOT)
