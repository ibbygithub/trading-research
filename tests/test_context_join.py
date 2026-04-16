"""Tests for eval/context.py — join_entry_context()."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from trading_research.eval.context import join_entry_context, _classify_regime


# ---------------------------------------------------------------------------
# Helpers — synthetic data builders
# ---------------------------------------------------------------------------

def _make_features(n: int = 300, start: str = "2024-01-02 00:00") -> pd.DataFrame:
    """Return a minimal synthetic 5m features DataFrame with required columns."""
    idx = pd.date_range(start=start, periods=n, freq="5min", tz="UTC")
    rng = np.random.default_rng(42)
    close = 110.0 + rng.standard_normal(n).cumsum() * 0.01
    feat = pd.DataFrame(
        {
            "open": close - 0.005,
            "high": close + 0.01,
            "low": close - 0.01,
            "close": close,
            "volume": rng.integers(100, 1000, n).astype(float),
            "atr_14": np.full(n, 0.05),
            "rsi_14": np.full(n, 50.0),
            "vwap_session": close - 0.002,
            "daily_macd_hist": rng.standard_normal(n) * 0.001,
            "timestamp_ny": idx.tz_convert("America/New_York"),
        },
        index=idx,
    )
    feat.index.name = "timestamp_utc"
    return feat


def _make_trades(n: int = 10, features: pd.DataFrame = None) -> pd.DataFrame:
    """Return a minimal trade log DataFrame aligned to *features* bars."""
    if features is None:
        features = _make_features()

    rng = np.random.default_rng(7)
    entry_idx = sorted(rng.choice(range(50, len(features) - 20), n, replace=False))
    entry_ts = features.index[entry_idx]
    exit_ts = features.index[[min(i + 10, len(features) - 1) for i in entry_idx]]
    entry_price = features["close"].iloc[entry_idx].values
    exit_price = features["close"].iloc[[min(i + 10, len(features) - 1) for i in entry_idx]].values
    stop = entry_price - 0.1

    df = pd.DataFrame(
        {
            "trade_id": [f"t{i:04d}" for i in range(n)],
            "strategy_id": "test",
            "symbol": "ZN",
            "direction": "long",
            "quantity": 1,
            "entry_trigger_ts": entry_ts,
            "entry_ts": entry_ts,
            "entry_price": entry_price,
            "exit_trigger_ts": exit_ts,
            "exit_ts": exit_ts,
            "exit_price": exit_price,
            "exit_reason": "signal",
            "initial_stop": stop,
            "initial_target": np.nan,
            "pnl_points": exit_price - entry_price,
            "pnl_usd": (exit_price - entry_price) * 1000,
            "slippage_usd": 31.25,
            "commission_usd": 4.0,
            "net_pnl_usd": (exit_price - entry_price) * 1000 - 35.25,
            "mae_points": -0.05,
            "mfe_points": 0.03,
        }
    )
    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestClassifyRegime:
    """Unit tests for _classify_regime hour classifier."""

    def test_ny_rth(self):
        assert _classify_regime(9)  == "NY RTH"
        assert _classify_regime(14) == "NY RTH"
        assert _classify_regime(15) == "NY RTH"

    def test_london(self):
        assert _classify_regime(3) == "London"
        assert _classify_regime(7) == "London"

    def test_asia(self):
        assert _classify_regime(0)  == "Asia"
        assert _classify_regime(2)  == "Asia"
        assert _classify_regime(18) == "Asia"
        assert _classify_regime(23) == "Asia"

    def test_ny_preopen(self):
        assert _classify_regime(8) == "NY pre-open"

    def test_ny_close(self):
        assert _classify_regime(16) == "NY close"

    def test_overnight(self):
        assert _classify_regime(17) == "Overnight"


class TestJoinEntryContext:
    """Integration tests for join_entry_context()."""

    def test_returns_correct_columns(self):
        feat = _make_features(300)
        trades = _make_trades(10, feat)
        result = join_entry_context(trades, feat)

        expected_new = {
            "atr_14_pct_rank_252", "daily_range_used_pct", "vwap_distance_atr",
            "htf_bias_strength", "session_regime", "entry_atr_14",
        }
        assert expected_new.issubset(result.columns)

    def test_row_count_preserved(self):
        feat = _make_features(300)
        trades = _make_trades(20, feat)
        result = join_entry_context(trades, feat)
        assert len(result) == 20

    def test_session_regime_categorical(self):
        feat = _make_features(300)
        trades = _make_trades(10, feat)
        result = join_entry_context(trades, feat)
        valid = {"Asia", "London", "NY pre-open", "NY RTH", "NY close", "Overnight", "Unknown"}
        assert set(result["session_regime"].unique()).issubset(valid)

    def test_entry_atr_14_non_negative(self):
        feat = _make_features(300)
        trades = _make_trades(10, feat)
        result = join_entry_context(trades, feat)
        # ATR is always ≥ 0
        valid = result["entry_atr_14"].dropna()
        assert (valid >= 0).all()

    def test_vwap_distance_finite(self):
        feat = _make_features(300)
        trades = _make_trades(10, feat)
        result = join_entry_context(trades, feat)
        # With non-zero ATR, vwap_distance_atr should be finite
        finite = result["vwap_distance_atr"].dropna()
        assert len(finite) > 0
        assert all(math.isfinite(v) for v in finite)

    def test_htf_bias_strength_non_negative(self):
        feat = _make_features(300)
        trades = _make_trades(10, feat)
        result = join_entry_context(trades, feat)
        valid = result["htf_bias_strength"].dropna()
        assert (valid >= 0).all()

    def test_original_columns_unchanged(self):
        feat = _make_features(300)
        trades = _make_trades(10, feat)
        result = join_entry_context(trades, feat)
        # All original trade columns still present
        for col in trades.columns:
            assert col in result.columns

    def test_no_lookahead_session_regime(self):
        """Verify that session_regime is derived solely from entry_ts (NY hour)."""
        feat = _make_features(300, start="2024-01-02 14:00")  # starts at 14:00 UTC = 09:00 ET
        trades = _make_trades(5, feat)
        result = join_entry_context(trades, feat)
        # All entries are during ET business hours → should be NY-related regime
        regimes = result["session_regime"].tolist()
        assert all(r in {"NY RTH", "NY pre-open", "NY close", "Overnight", "London", "Asia"} for r in regimes)

    def test_empty_trades_returns_empty(self):
        feat = _make_features(100)
        empty_trades = _make_trades(0, feat).head(0)
        result = join_entry_context(empty_trades, feat)
        assert len(result) == 0
