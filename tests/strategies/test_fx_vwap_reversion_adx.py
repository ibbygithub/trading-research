"""Tests for fx_vwap_reversion_adx strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_research.strategies.fx_vwap_reversion_adx import generate_signals


def _make_df(
    *,
    n: int = 16,  # 16 * 15min = 4 hours, fits inside 12:00-17:00 overlap
    start: str = "2024-06-03 12:00",
    freq: str = "15min",
    close_offset_atr: float = 0.0,
    adx_value: float = 15.0,
    vwap: float = 0.6800,
    atr: float = 0.0010,
) -> pd.DataFrame:
    """Build a synthetic 6A-shaped features DataFrame."""
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    close = np.full(n, vwap + close_offset_atr * atr)
    return pd.DataFrame(
        {
            "close": close,
            "vwap_session": np.full(n, vwap),
            "atr_14": np.full(n, atr),
            "adx_14": np.full(n, adx_value),
        },
        index=idx,
    )


def test_long_entry_when_close_below_vwap_minus_threshold():
    df = _make_df(close_offset_atr=-2.0, adx_value=15.0)
    out = generate_signals(df, entry_atr_mult=1.5, adx_max=22.0)
    assert (out["signal"] == 1).all()
    # Stop is below entry close.
    assert (out["stop"] < df["close"]).all()
    # Target equals VWAP at signal time.
    np.testing.assert_array_equal(out["target"].values, df["vwap_session"].values)


def test_short_entry_when_close_above_vwap_plus_threshold():
    df = _make_df(close_offset_atr=+2.0, adx_value=15.0)
    out = generate_signals(df, entry_atr_mult=1.5, adx_max=22.0)
    assert (out["signal"] == -1).all()
    assert (out["stop"] > df["close"]).all()


def test_no_entry_when_adx_above_threshold():
    df = _make_df(close_offset_atr=-2.0, adx_value=30.0)
    out = generate_signals(df, entry_atr_mult=1.5, adx_max=22.0)
    assert (out["signal"] == 0).all()
    assert out["stop"].isna().all()


def test_no_entry_when_outside_overlap_window():
    df = _make_df(
        n=16,
        start="2024-06-03 02:00",  # Asian session, 02:00-06:00 UTC
        close_offset_atr=-2.0,
        adx_value=15.0,
    )
    out = generate_signals(
        df, entry_atr_mult=1.5, adx_max=22.0,
        overlap_start_utc="12:00", overlap_end_utc="17:00",
    )
    assert (out["signal"] == 0).all()


def test_no_entry_when_close_inside_band():
    df = _make_df(close_offset_atr=0.5, adx_value=15.0)  # well inside +/-1.5*ATR
    out = generate_signals(df, entry_atr_mult=1.5, adx_max=22.0)
    assert (out["signal"] == 0).all()


def test_window_boundary_inclusive_start_exclusive_end():
    # start=12:00 inclusive, end=17:00 exclusive.
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-06-03 11:59", tz="UTC"),
            pd.Timestamp("2024-06-03 12:00", tz="UTC"),
            pd.Timestamp("2024-06-03 16:59", tz="UTC"),
            pd.Timestamp("2024-06-03 17:00", tz="UTC"),
        ]
    )
    n = len(idx)
    df = pd.DataFrame(
        {
            "close": np.full(n, 0.6800 + (-2.0) * 0.0010),
            "vwap_session": np.full(n, 0.6800),
            "atr_14": np.full(n, 0.0010),
            "adx_14": np.full(n, 15.0),
        },
        index=idx,
    )
    out = generate_signals(df, entry_atr_mult=1.5, adx_max=22.0)
    assert out["signal"].tolist() == [0, 1, 1, 0]


def test_missing_required_column_raises():
    df = _make_df()
    df = df.drop(columns=["adx_14"])
    with pytest.raises(KeyError, match="adx_14"):
        generate_signals(df)


def test_naive_index_raises():
    idx = pd.date_range("2024-06-03 12:00", periods=4, freq="15min")
    df = pd.DataFrame(
        {
            "close": [0.6790] * 4,
            "vwap_session": [0.6800] * 4,
            "atr_14": [0.0010] * 4,
            "adx_14": [15.0] * 4,
        },
        index=idx,
    )
    with pytest.raises(ValueError, match="tz-aware"):
        generate_signals(df)


def test_nan_inputs_produce_no_signal():
    df = _make_df(close_offset_atr=-2.0, adx_value=15.0)
    df.loc[df.index[0], "atr_14"] = np.nan
    out = generate_signals(df)
    assert out["signal"].iloc[0] == 0
    assert pd.isna(out["stop"].iloc[0])
