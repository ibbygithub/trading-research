"""Tests for ATR indicator."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_research.indicators.atr import compute_atr
from tests.indicators.conftest import assert_no_lookahead, make_ohlcv


class TestATR:
    def test_warmup_is_nan(self):
        df = make_ohlcv(100)
        atr = compute_atr(df)
        assert atr.iloc[:14].isna().all()

    def test_first_valid_row_not_nan(self):
        df = make_ohlcv(100)
        atr = compute_atr(df)
        assert not pd.isna(atr.iloc[14])

    def test_constant_range_converges(self):
        """With constant high-low range (= 2 * step = 0.03125), ATR should
        converge to that range after warmup (TR = high - low when no gap)."""
        n = 200
        closes = [110.0 + i * 0.015625 for i in range(n)]
        highs = [c + 0.015625 for c in closes]
        lows = [c - 0.015625 for c in closes]
        df = pd.DataFrame({"close": closes, "high": highs, "low": lows})
        atr = compute_atr(df, period=14)
        # TR for each bar (after the first) = high - low = 0.03125
        expected_tr = 0.03125
        # By row 100 the EWM should be very close to the true range.
        assert abs(atr.iloc[100] - expected_tr) < 0.001

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(compute_atr, df, n_warmup=50)

    def test_name(self):
        df = make_ohlcv(50)
        atr = compute_atr(df, period=14)
        assert atr.name == "atr_14"

    def test_positive_values(self):
        df = make_ohlcv(100)
        atr = compute_atr(df)
        assert (atr.dropna() > 0).all()
