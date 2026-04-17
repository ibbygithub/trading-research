"""Tests for MACD indicator including derived histogram features."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_research.indicators.macd import compute_macd
from tests.indicators.conftest import assert_no_lookahead, make_ohlcv


class TestMACDCore:
    def test_columns_present(self):
        df = make_ohlcv(200)
        macd = compute_macd(df)
        for col in (
            "macd", "macd_signal", "macd_hist",
            "macd_hist_above_zero", "macd_hist_slope",
            "macd_hist_bars_since_zero_cross", "macd_hist_decline_streak",
        ):
            assert col in macd.columns

    def test_warmup_is_nan(self):
        """First slow + signal - 1 = 34 rows should be NaN."""
        df = make_ohlcv(200)
        macd = compute_macd(df)
        warmup = 26 + 9 - 1
        assert macd["macd"].iloc[:warmup].isna().all()
        assert macd["macd_signal"].iloc[:warmup].isna().all()
        assert macd["macd_hist"].iloc[:warmup].isna().all()

    def test_hist_positive_when_fast_above_slow(self):
        """With ascending prices, fast EMA > slow EMA → hist > 0 after warmup."""
        df = make_ohlcv(200, close_step=0.015625)
        macd = compute_macd(df)
        assert (macd["macd_hist"].dropna() > 0).all()

    def test_no_lookahead_core(self):
        df = make_ohlcv(300)
        assert_no_lookahead(compute_macd, df, n_warmup=100)


class TestMACDDerivedFeatures:
    def _known_hist(self) -> pd.DataFrame:
        """Build a DataFrame with a prescribed histogram sequence by
        back-constructing a close series that produces the pattern:
        above zero, rising, then declining."""
        # We'll build a 150-bar dataset with a clear ascending then descending
        # close pattern to drive the histogram.
        closes = (
            [110.0] * 5                                    # flat
            + [110.0 + i * 0.1 for i in range(100)]        # ascending → hist rising
            + [220.0 - i * 0.1 for i in range(45)]         # descending → hist declining
        )
        df = pd.DataFrame(
            {
                "close": closes,
                "high": [c + 0.1 for c in closes],
                "low": [c - 0.1 for c in closes],
            }
        )
        return df

    def test_hist_above_zero_type(self):
        df = self._known_hist()
        macd = compute_macd(df)
        valid_above = macd["macd_hist_above_zero"].dropna()
        # Should be bool-like (True/False)
        assert valid_above.dtype in (bool, object, "bool")

    def test_hist_slope_is_diff_of_hist(self):
        df = self._known_hist()
        macd = compute_macd(df)
        hist = macd["macd_hist"]
        expected_slope = hist.diff()
        valid_idx = macd["macd_hist_slope"].dropna().index
        pd.testing.assert_series_equal(
            macd["macd_hist_slope"].loc[valid_idx].astype(float),
            expected_slope.loc[valid_idx].astype(float),
            check_names=False,
            rtol=1e-9,
        )

    def test_bars_since_zero_cross_resets(self):
        """bars_since_zero_cross should reset to 0 each time the histogram crosses zero."""
        df = self._known_hist()
        macd = compute_macd(df)
        bszc = macd["macd_hist_bars_since_zero_cross"].dropna()
        hist_valid = macd["macd_hist"].dropna()

        # Find zero crossings
        signs = hist_valid.apply(lambda x: 1 if x > 0 else -1)
        crossings = signs.diff().abs() > 0

        # At each crossing index, bars_since_zero_cross should be 0
        for idx in crossings[crossings].index:
            if idx in bszc.index:
                assert bszc[idx] == 0, f"Expected 0 at crossing {idx}, got {bszc[idx]}"

    def test_decline_streak_negative_when_shrinking(self):
        """During a declining histogram (same sign, each bar smaller), streak should be negative."""
        df = self._known_hist()
        macd = compute_macd(df)
        ds = macd["macd_hist_decline_streak"].dropna()
        # In the declining portion (last 30 valid bars), hist should be above zero
        # but each bar smaller → streak should become negative.
        # The last few bars may go negative hist, so check mid-decline.
        last_20 = ds.iloc[-30:-10]
        # At least some of those bars should have a negative streak
        assert (last_20 < 0).any(), "Expected negative decline streak in declining histogram portion"

    def test_decline_streak_positive_when_growing(self):
        """During a growing histogram (same sign, each bar larger), streak should be positive."""
        # Use _decline_streak directly on a known ascending histogram sequence.
        from trading_research.indicators.macd import _decline_streak
        warmup = [float("nan")] * 34
        # Values growing: 0.1, 0.2, 0.3 → streak +1, +2, +3
        hist = pd.Series(warmup + [0.1, 0.2, 0.3])
        result = _decline_streak(hist)
        valid = result.dropna()
        assert list(valid) == [1, 2, 3], f"Growing histogram should have +1,+2,+3 streak; got {list(valid)}"

    def test_table_driven_decline_streak(self):
        """Minimal table-driven test for decline_streak logic."""
        # Manually craft a histogram series with known expected streaks.
        # sign = above zero, values: 0.5, 0.4, 0.3  → declining → streaks: +1, -1, -2
        # Then 0.3, 0.4 (growing) → +1, +1... wait no, after -2 growing means +1 reset.
        from trading_research.indicators.macd import _decline_streak

        # Build a hist series manually:
        # idx 0: 0.5 (first above-zero) → +1
        # idx 1: 0.6 (bigger) → +2
        # idx 2: 0.5 (smaller) → -1 (reset to -1 because direction changed)
        # idx 3: 0.3 (smaller) → -2
        # idx 4: 0.4 (bigger) → +1 (reset to +1)
        warmup_nans = [float("nan")] * 34  # simulate warmup
        hist_vals = warmup_nans + [0.5, 0.6, 0.5, 0.3, 0.4]
        hist = pd.Series(hist_vals)
        result = _decline_streak(hist)
        valid = result.dropna()
        assert list(valid) == [1, 2, -1, -2, 1], f"Got {list(valid)}"
