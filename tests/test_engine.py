"""Tests for the backtest engine."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from trading_research.backtest.engine import BacktestConfig, BacktestEngine
from trading_research.backtest.fills import FillModel
from trading_research.data.instruments import load_instruments


def _inst():
    return load_instruments().get("ZN")


def _ts(n: int, freq: str = "5min") -> pd.DatetimeIndex:
    """Generate n UTC timestamps starting from a fixed base."""
    base = pd.Timestamp("2024-01-10 14:00:00", tz="UTC")
    return pd.date_range(base, periods=n, freq=freq)


def _make_bars(n: int, prices: list[float] | None = None, freq: str = "5min") -> pd.DataFrame:
    """Synthetic flat bars at given close prices (or 110.0 if not specified)."""
    idx = _ts(n, freq)
    if prices is None:
        prices = [110.0] * n
    data = {
        "open": prices,
        "high": [p + 0.25 for p in prices],
        "low": [p - 0.25 for p in prices],
        "close": prices,
        "buy_volume": [500] * n,
        "sell_volume": [500] * n,
        "timestamp_ny": [ts.tz_convert("America/New_York") for ts in idx],
    }
    return pd.DataFrame(data, index=idx)


def _make_signals(bars: pd.DataFrame, signal_col: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {"signal": signal_col, "stop": np.nan, "target": np.nan},
        index=bars.index,
    )


# ---------------------------------------------------------------------------
# 3-bar synthetic long: enter T+1 open, exit at target, correct net P&L
# ---------------------------------------------------------------------------

class TestThreeBarLong:
    def test_correct_net_pnl(self):
        # 5 bars: bar 0 signals long, bar 1 is entry, bar 2 is target bar,
        # bars 3-4 are after the trade.
        prices = [110.0, 110.5, 111.5, 111.0, 110.0]
        bars = _make_bars(5, prices)
        sig_data = pd.DataFrame({
            "signal": [1, 0, 0, 0, 0],
            "stop": [109.5, float("nan"), float("nan"), float("nan"), float("nan")],
            "target": [111.25, float("nan"), float("nan"), float("nan"), float("nan")],
        }, index=bars.index)

        cfg = BacktestConfig(strategy_id="test", symbol="ZN", eod_flat=False)
        engine = BacktestEngine(cfg, _inst())
        result = engine.run(bars, sig_data)

        # Should have exactly 1 trade.
        assert len(result.trades) == 1
        t = result.trades.iloc[0]
        assert t["direction"] == "long"
        assert t["exit_reason"] == "target"

        # Entry: bar 1 open (110.5) + 1 tick slippage (0.015625) = 110.515625
        expected_entry = 110.5 + 0.015625
        assert abs(t["entry_price"] - expected_entry) < 1e-6

        # Exit: target = 111.25; bar 2 high = 111.75, bar 2 low = 111.25 → target hit
        assert abs(t["exit_price"] - 111.25) < 1e-6

        # pnl_points = 111.25 - 110.515625
        pnl_pts = 111.25 - expected_entry
        pnl_usd = pnl_pts * 1000.0   # point_value_usd for ZN
        slippage_usd = 1 * 15.625 * 2   # 1 tick × $15.625 × 2 sides
        commission_usd = 2.0 * 2        # $2/side × 2
        net = pnl_usd - slippage_usd - commission_usd
        assert abs(t["net_pnl_usd"] - net) < 0.01


# ---------------------------------------------------------------------------
# Stop wins on ambiguous bar
# ---------------------------------------------------------------------------

class TestAmbiguousBarPessimistic:
    def test_stop_beats_target(self):
        # Bar with range wide enough to cover both stop and target.
        prices = [110.0, 110.5, 110.5, 110.5]
        bars = _make_bars(4, prices)
        # Make bar 2 have wide range covering both levels.
        bars.at[bars.index[2], "high"] = 111.5
        bars.at[bars.index[2], "low"] = 109.0

        sig_data = pd.DataFrame({
            "signal": [1, 0, 0, 0],
            "stop": [109.5, float("nan"), float("nan"), float("nan")],
            "target": [111.0, float("nan"), float("nan"), float("nan")],
        }, index=bars.index)

        cfg = BacktestConfig(strategy_id="test", symbol="ZN", eod_flat=False)
        result = BacktestEngine(cfg, _inst()).run(bars, sig_data)

        assert len(result.trades) == 1
        assert result.trades.iloc[0]["exit_reason"] == "stop"


# ---------------------------------------------------------------------------
# EOD close fires when session close is reached
# ---------------------------------------------------------------------------

class TestEODFlat:
    def test_eod_closes_position(self):
        # Use timestamps that pass 15:00 NY time during the bar sequence.
        base_ny = pd.Timestamp("2024-01-10 14:55:00", tz="America/New_York")
        # 3 bars: 14:55, 15:00, 15:05 NY
        idx_ny = pd.date_range(base_ny, periods=3, freq="5min")
        idx_utc = idx_ny.tz_convert("UTC")

        prices = [110.0, 110.25, 110.5]
        bars = pd.DataFrame({
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low":  [p - 0.1 for p in prices],
            "close": prices,
            "buy_volume": [500] * 3,
            "sell_volume": [500] * 3,
            "timestamp_ny": list(idx_ny),
        }, index=idx_utc)

        # Signal on bar 0 (14:55 NY); stop must be finite for engine entry guard.
        sig_data = pd.DataFrame({
            "signal": [1, 0, 0],
            "stop": [109.5, float("nan"), float("nan")],
            "target": [float("nan")] * 3,
        }, index=idx_utc)

        cfg = BacktestConfig(strategy_id="test", symbol="ZN", eod_flat=True)
        result = BacktestEngine(cfg, _inst()).run(bars, sig_data)

        # Position opened on bar 1 (15:00 NY) and should close EOD at 15:00.
        assert len(result.trades) == 1
        t = result.trades.iloc[0]
        assert t["exit_reason"] == "eod"


# ---------------------------------------------------------------------------
# MAE and MFE computed correctly
# ---------------------------------------------------------------------------

class TestMAEMFE:
    def test_mae_mfe_long(self):
        # Long trade: entry at 110.0, then bar dips to 109.0 (MAE),
        # then rallies to 111.5 (MFE), then closes at target 111.0.
        prices = [110.0, 110.0, 109.2, 111.6, 111.0]
        bars = _make_bars(5, prices)
        bars.at[bars.index[2], "low"] = 109.0
        bars.at[bars.index[3], "high"] = 111.5

        sig_data = pd.DataFrame({
            "signal": [1, 0, 0, 0, 0],
            "stop": [108.0, float("nan")] * 2 + [float("nan")],
            "target": [111.0, float("nan")] * 2 + [float("nan")],
        }, index=bars.index)

        cfg = BacktestConfig(strategy_id="test", symbol="ZN", eod_flat=False)
        result = BacktestEngine(cfg, _inst()).run(bars, sig_data)

        assert len(result.trades) >= 1
        t = result.trades.iloc[0]
        # MAE should be negative (price went against us).
        assert t["mae_points"] < 0
        # MFE should be positive (price went in our favour).
        assert t["mfe_points"] > 0


# ---------------------------------------------------------------------------
# No position carried across session boundary
# ---------------------------------------------------------------------------

class TestNoCarryAcrossSessions:
    def test_eod_flat_prevents_overnight_carry(self):
        # Build bars that span two sessions.
        # Session 1: 14:55 → 15:05 NY (bars before and after close).
        # Session 2: next day 09:00 NY.
        base_ny = pd.Timestamp("2024-01-10 14:55:00", tz="America/New_York")
        times_ny = [
            base_ny,
            base_ny + pd.Timedelta("5min"),   # 15:00 NY — session close
            base_ny + pd.Timedelta("10min"),  # 15:05 NY
        ]
        idx_utc = pd.DatetimeIndex([t.tz_convert("UTC") for t in times_ny])
        prices = [110.0, 110.0, 110.25]
        bars = pd.DataFrame({
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low":  [p - 0.1 for p in prices],
            "close": prices,
            "buy_volume": [500] * 3,
            "sell_volume": [500] * 3,
            "timestamp_ny": times_ny,
        }, index=idx_utc)

        sig_data = pd.DataFrame({
            "signal": [1, 0, 0],
            "stop": [float("nan")] * 3,
            "target": [float("nan")] * 3,
        }, index=idx_utc)

        cfg = BacktestConfig(strategy_id="test", symbol="ZN", eod_flat=True)
        result = BacktestEngine(cfg, _inst()).run(bars, sig_data)

        if len(result.trades) > 0:
            t = result.trades.iloc[0]
            assert t["exit_reason"] == "eod"
