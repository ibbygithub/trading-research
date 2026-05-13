"""Tests for fx_donchian_breakout strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_research.strategies.fx_donchian_breakout import generate_signals


def _make_df(
    *,
    n: int = 30,
    start: str = "2024-06-03 12:00",
    freq: str = "60min",
    close: float = 0.7300,
    donchian_upper: float = 0.7295,
    donchian_lower: float = 0.7250,
    atr: float = 0.0010,
    ema_50: float = 0.7280,
    ema_200: float = 0.7260,
) -> pd.DataFrame:
    """Build a synthetic 6C-shaped features DataFrame."""
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "close": np.full(n, close),
            "donchian_upper": np.full(n, donchian_upper),
            "donchian_lower": np.full(n, donchian_lower),
            "atr_14": np.full(n, atr),
            "daily_ema_50": np.full(n, ema_50),
            "daily_ema_200": np.full(n, ema_200),
        },
        index=idx,
    )


def test_long_entry_on_breakout_above_prior_donchian_with_uptrend():
    # close > donchian_upper.shift(1) AND ema_50 > ema_200
    df = _make_df(
        close=0.7300, donchian_upper=0.7295, ema_50=0.7280, ema_200=0.7260
    )
    out = generate_signals(df, target_atr_mult=3.0, stop_atr_mult=1.5)
    # First bar is NaN due to shift; subsequent bars all signal long.
    assert pd.isna(out["stop"].iloc[0])
    assert (out["signal"].iloc[1:] == 1).all()
    assert (out["target"].iloc[1:] > out["stop"].iloc[1:]).all()


def test_short_entry_on_breakdown_below_prior_donchian_with_downtrend():
    df = _make_df(
        close=0.7240, donchian_upper=0.7300, donchian_lower=0.7250,
        ema_50=0.7250, ema_200=0.7280,
    )
    out = generate_signals(df, target_atr_mult=3.0, stop_atr_mult=1.5)
    assert pd.isna(out["stop"].iloc[0])
    assert (out["signal"].iloc[1:] == -1).all()
    # Short stop is above entry close.
    assert (out["stop"].iloc[1:] > out["target"].iloc[1:]).all()


def test_no_entry_when_breakout_but_trend_filter_disagrees():
    # close breaks above donchian, but ema_50 < ema_200 (downtrend)
    df = _make_df(
        close=0.7300, donchian_upper=0.7295,
        ema_50=0.7250, ema_200=0.7280,
    )
    out = generate_signals(df)
    assert (out["signal"] == 0).all()


def test_no_entry_when_close_inside_channel():
    # close in middle of channel; no breakout
    df = _make_df(
        close=0.7270, donchian_upper=0.7300, donchian_lower=0.7240,
        ema_50=0.7280, ema_200=0.7260,
    )
    out = generate_signals(df)
    assert (out["signal"] == 0).all()


def test_donchian_shift_prevents_lookahead():
    """A bar that exactly equals its own donchian_upper should NOT trigger.

    The shift(1) means the comparison is against the *previous* bar's
    donchian_upper; a bar that is the new max but not yet exceeding the
    prior 20-bar high should not signal.
    """
    n = 5
    idx = pd.date_range("2024-06-03 12:00", periods=n, freq="60min", tz="UTC")
    # First 4 bars: close = donchian_upper = 0.7290 (no breakout yet, equal to channel)
    # Bar 5: close = 0.7300, donchian_upper = 0.7290 (broke prior high)
    closes = np.array([0.7290, 0.7290, 0.7290, 0.7290, 0.7300])
    uppers = np.array([0.7290, 0.7290, 0.7290, 0.7290, 0.7290])
    df = pd.DataFrame(
        {
            "close": closes,
            "donchian_upper": uppers,
            "donchian_lower": np.full(n, 0.7240),
            "atr_14": np.full(n, 0.0010),
            "daily_ema_50": np.full(n, 0.7280),
            "daily_ema_200": np.full(n, 0.7260),
        },
        index=idx,
    )
    out = generate_signals(df)
    # Bar 0: NaN (shift). Bars 1-3: close==prior upper (not >), so 0.
    # Bar 4: close=0.7300 > prior upper=0.7290, so signal=1.
    assert out["signal"].iloc[0] == 0
    assert (out["signal"].iloc[1:4] == 0).all()
    assert out["signal"].iloc[4] == 1


def test_long_target_above_stop_short_target_below_stop():
    df = _make_df(close=0.7300, donchian_upper=0.7295, ema_50=0.7280, ema_200=0.7260)
    out = generate_signals(df, target_atr_mult=3.0, stop_atr_mult=1.5)
    long_row = out.iloc[1]
    assert long_row["signal"] == 1
    assert long_row["target"] > long_row["stop"]

    df2 = _make_df(
        close=0.7240, donchian_upper=0.7300, donchian_lower=0.7250,
        ema_50=0.7250, ema_200=0.7280,
    )
    out2 = generate_signals(df2, target_atr_mult=3.0, stop_atr_mult=1.5)
    short_row = out2.iloc[1]
    assert short_row["signal"] == -1
    assert short_row["target"] < short_row["stop"]


def test_missing_required_column_raises():
    df = _make_df()
    df = df.drop(columns=["donchian_upper"])
    with pytest.raises(KeyError, match="donchian_upper"):
        generate_signals(df)


def test_naive_index_raises():
    idx = pd.date_range("2024-06-03 12:00", periods=4, freq="60min")
    df = pd.DataFrame(
        {
            "close": [0.7300] * 4,
            "donchian_upper": [0.7290] * 4,
            "donchian_lower": [0.7240] * 4,
            "atr_14": [0.0010] * 4,
            "daily_ema_50": [0.7280] * 4,
            "daily_ema_200": [0.7260] * 4,
        },
        index=idx,
    )
    with pytest.raises(ValueError, match="tz-aware"):
        generate_signals(df)
