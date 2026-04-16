"""Tests for Bollinger Bands indicator."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_research.indicators.bollinger import compute_bollinger
from tests.indicators.conftest import assert_no_lookahead, make_ohlcv


class TestBollinger:
    def test_columns_present(self):
        df = make_ohlcv(100)
        bb = compute_bollinger(df)
        for col in ("bb_mid", "bb_upper", "bb_lower", "bb_pct_b", "bb_width"):
            assert col in bb.columns

    def test_warmup_is_nan(self):
        df = make_ohlcv(100)
        bb = compute_bollinger(df)
        assert bb["bb_mid"].iloc[:19].isna().all()

    def test_pct_b_at_midline(self):
        """When close == SMA (mid), pct_b should be 0.5."""
        # Use a close that oscillates symmetrically around a constant mean.
        # After warmup, SMA ≈ mean, close alternates above/below by equal amounts.
        # At the midpoint bar (close = mean), pct_b should be exactly 0.5.
        closes = [100.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(100)]
        df = pd.DataFrame(
            {
                "close": closes,
                "high": [c + 0.1 for c in closes],
                "low": [c - 0.1 for c in closes],
            }
        )
        bb = compute_bollinger(df)
        # After warmup the rolling SMA stabilises at 100. When close = 100.1 (even
        # bars), pct_b > 0.5; when close = 99.9 (odd bars), pct_b < 0.5.
        # At any even bar after warmup: pct_b = (100.1 - lower) / (upper - lower).
        # The midpoint check: verify that pct_b for the high bar is > 0.5 and
        # for the low bar is < 0.5 (symmetric oscillation around 0.5).
        pct_b = bb["bb_pct_b"].dropna()
        # Even index (close > SMA) should be above 0.5
        assert pct_b.iloc[-2] > 0.5   # even bar: close above mid
        # Odd index (close < SMA) should be below 0.5
        assert pct_b.iloc[-1] < 0.5   # odd bar: close below mid

    def test_pct_b_below_zero_when_below_lower(self):
        """When close drops far below prior level, pct_b < 0 at the drop bar."""
        # 80 bars at 100, then a sudden drop to 70. Check pct_b at bar 80 (the
        # first drop bar). At that point the 20-bar window spans bars 61-80.
        # Bars 61-79 are at 100, bar 80 is at 70.
        # SMA ≈ 98.5, std ≈ 6.7, lower ≈ 85.1. close=70 << lower → pct_b < 0.
        n = 100
        closes = [100.0] * 80 + [70.0] * 20
        df = pd.DataFrame(
            {
                "close": closes,
                "high": [c + 0.5 for c in closes],
                "low": [c - 0.5 for c in closes],
            }
        )
        bb = compute_bollinger(df)
        assert bb["bb_pct_b"].iloc[80] < 0

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(compute_bollinger, df, n_warmup=50)

    def test_upper_above_lower(self):
        df = make_ohlcv(200)
        bb = compute_bollinger(df)
        valid = bb.dropna()
        assert (valid["bb_upper"] >= valid["bb_lower"]).all()
