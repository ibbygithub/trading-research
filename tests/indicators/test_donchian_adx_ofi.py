"""Tests for Donchian, ADX, and OFI indicators."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_research.indicators.adx import compute_adx
from trading_research.indicators.donchian import compute_donchian
from trading_research.indicators.ofi import compute_ofi
from tests.indicators.conftest import assert_no_lookahead, make_ohlcv


class TestDonchian:
    def test_columns_present(self):
        df = make_ohlcv(100)
        dc = compute_donchian(df)
        assert set(dc.columns) == {"donchian_upper", "donchian_lower", "donchian_mid"}

    def test_warmup_nan(self):
        df = make_ohlcv(100)
        dc = compute_donchian(df)
        assert dc["donchian_upper"].iloc[:19].isna().all()

    def test_upper_equals_rolling_max_high(self):
        df = make_ohlcv(100)
        dc = compute_donchian(df, period=20)
        expected_upper = df["high"].rolling(20).max()
        pd.testing.assert_series_equal(
            dc["donchian_upper"].reset_index(drop=True),
            expected_upper.reset_index(drop=True),
            check_names=False,
        )

    def test_upper_above_lower(self):
        df = make_ohlcv(100)
        dc = compute_donchian(df)
        valid = dc.dropna()
        assert (valid["donchian_upper"] >= valid["donchian_lower"]).all()

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(compute_donchian, df, n_warmup=50)


class TestADX:
    def test_warmup_nan(self):
        """First 2*period = 28 rows should be NaN."""
        df = make_ohlcv(200)
        adx = compute_adx(df)
        assert adx.iloc[: 2 * 14].isna().all()

    def test_positive_values(self):
        df = make_ohlcv(200)
        adx = compute_adx(df)
        assert (adx.dropna() >= 0).all()

    def test_trending_series_high_adx(self):
        """A strongly trending series should produce high ADX (> 25) eventually."""
        n = 300
        closes = [100.0 + i * 0.1 for i in range(n)]  # strong trend
        df = pd.DataFrame(
            {
                "close": closes,
                "high": [c + 0.2 for c in closes],
                "low": [c - 0.05 for c in closes],
            }
        )
        adx = compute_adx(df, period=14)
        # After enough bars, ADX should be high
        assert adx.iloc[-50:].max() > 25, "ADX not high enough on strongly trending series"

    def test_no_lookahead(self):
        df = make_ohlcv(300)
        assert_no_lookahead(compute_adx, df, n_warmup=80)

    def test_name(self):
        df = make_ohlcv(100)
        adx = compute_adx(df)
        assert adx.name == "adx_14"


class TestOFI:
    def test_all_buy_volume(self):
        """When all volume is buy volume, OFI → +1."""
        df = make_ohlcv(100, buy_vol_frac=1.0)
        df["sell_volume"] = 0
        ofi = compute_ofi(df)
        valid = ofi.dropna()
        assert (abs(valid - 1.0) < 1e-9).all()

    def test_all_sell_volume(self):
        """When all volume is sell volume, OFI → -1."""
        df = make_ohlcv(100, buy_vol_frac=0.0)
        df["buy_volume"] = 0
        df["sell_volume"] = 500
        ofi = compute_ofi(df)
        valid = ofi.dropna()
        assert (abs(valid - (-1.0)) < 1e-9).all()

    def test_null_buy_volume_produces_nan(self):
        """Rows with null buy_volume should produce NaN rolling OFI."""
        df = make_ohlcv(30)
        df["buy_volume"] = None
        ofi = compute_ofi(df)
        assert ofi.isna().all()

    def test_warmup_nan(self):
        df = make_ohlcv(100)
        ofi = compute_ofi(df, period=14)
        assert ofi.iloc[:13].isna().all()
        assert not pd.isna(ofi.iloc[13])

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(compute_ofi, df, n_warmup=50)

    def test_name(self):
        df = make_ohlcv(50)
        assert compute_ofi(df).name == "ofi_14"
