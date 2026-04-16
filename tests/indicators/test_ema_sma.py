"""Tests for EMA and SMA indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_research.indicators.ema import compute_ema
from trading_research.indicators.sma import compute_sma
from tests.indicators.conftest import assert_no_lookahead, make_ohlcv


class TestEMA:
    def test_warmup_masked(self):
        df = make_ohlcv(100)
        result = compute_ema(df["close"], 20)
        assert result.iloc[:19].isna().all()

    def test_constant_series_equals_constant(self):
        """EMA of a constant series equals that constant after warmup."""
        closes = pd.Series([100.0] * 100)
        result = compute_ema(closes, 20)
        assert result.iloc[20:].apply(lambda v: abs(v - 100.0) < 1e-9).all()

    def test_ascending_ema_lags_close(self):
        """EMA lags close on an ascending series (weighted toward recent, but still below current)."""
        df = make_ohlcv(100)
        ema = compute_ema(df["close"], 10)
        valid = ema.dropna()
        closes = df["close"].loc[valid.index]
        assert (closes > valid).all()

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(lambda d, **kw: compute_ema(d["close"], 20), df)

    def test_name(self):
        s = compute_ema(pd.Series([1.0] * 50), 10)
        assert s.name == "ema_10"


class TestSMA:
    def test_warmup_masked(self):
        df = make_ohlcv(100)
        result = compute_sma(df["close"], 20)
        assert result.iloc[:19].isna().all()
        assert not pd.isna(result.iloc[19])

    def test_constant_series(self):
        closes = pd.Series([50.0] * 100)
        result = compute_sma(closes, 20)
        assert result.iloc[20:].apply(lambda v: abs(v - 50.0) < 1e-9).all()

    def test_no_lookahead(self):
        df = make_ohlcv(200)
        assert_no_lookahead(lambda d, **kw: compute_sma(d["close"], 20), df)

    def test_name(self):
        s = compute_sma(pd.Series([1.0] * 50), 200)
        assert s.name == "sma_200"
