"""Tests for RSI indicator."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_research.indicators.rsi import compute_rsi
from tests.indicators.conftest import assert_no_lookahead, make_ohlcv


class TestRSI:
    def test_warmup_is_nan(self):
        df = make_ohlcv(100)
        rsi = compute_rsi(df)
        assert rsi.iloc[:14].isna().all()

    def test_first_valid_row_not_nan(self):
        # Use a balanced series (alternating up/down) so avg_loss > 0.
        closes = [110.0 + (0.05 if i % 2 == 0 else -0.05) for i in range(100)]
        df = pd.DataFrame({"close": closes, "high": closes, "low": closes})
        rsi = compute_rsi(df)
        assert not pd.isna(rsi.iloc[14])

    def test_ascending_series_near_100(self):
        """Strictly ascending prices → RSI should converge near 100."""
        df = make_ohlcv(200, close_step=0.015625)
        rsi = compute_rsi(df)
        # After enough bars the RSI should be very high (well above 80).
        assert rsi.iloc[100] > 80

    def test_descending_series_near_0(self):
        """Strictly descending prices → RSI should converge near 0."""
        df = make_ohlcv(200, close_step=-0.015625)
        rsi = compute_rsi(df)
        assert rsi.iloc[100] < 20

    def test_range_0_to_100(self):
        df = make_ohlcv(200)
        rsi = compute_rsi(df)
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(compute_rsi, df, n_warmup=50)

    def test_name(self):
        df = make_ohlcv(50)
        assert compute_rsi(df).name == "rsi_14"
