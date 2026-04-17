"""Tests for the fill model and TP/SL resolver."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from trading_research.backtest.fills import FillModel, apply_fill, resolve_exit


def _bar(open_=110.0, high=110.5, low=109.5, close=110.25,
         buy_volume=None, sell_volume=None) -> pd.Series:
    return pd.Series({
        "open": open_, "high": high, "low": low, "close": close,
        "buy_volume": buy_volume, "sell_volume": sell_volume,
    })


# ---------------------------------------------------------------------------
# apply_fill
# ---------------------------------------------------------------------------

class TestApplyFill:
    def test_long_next_bar_open_adds_slippage(self):
        signal = _bar(close=110.0)
        next_b = _bar(open_=110.1)
        price = apply_fill(signal, next_b, FillModel.NEXT_BAR_OPEN, +1, 1, 0.015625)
        # long: fills higher by 1 tick
        assert abs(price - (110.1 + 0.015625)) < 1e-9

    def test_short_next_bar_open_subtracts_slippage(self):
        signal = _bar(close=110.0)
        next_b = _bar(open_=110.1)
        price = apply_fill(signal, next_b, FillModel.NEXT_BAR_OPEN, -1, 1, 0.015625)
        # short: fills lower by 1 tick
        assert abs(price - (110.1 - 0.015625)) < 1e-9

    def test_same_bar_uses_signal_close(self):
        signal = _bar(close=110.5)
        next_b = _bar(open_=111.0)  # irrelevant
        price = apply_fill(signal, next_b, FillModel.SAME_BAR, +1, 0, 0.015625)
        assert abs(price - 110.5) < 1e-9

    def test_zero_slippage(self):
        signal = _bar(close=110.0)
        next_b = _bar(open_=110.2)
        price = apply_fill(signal, next_b, FillModel.NEXT_BAR_OPEN, +1, 0, 0.015625)
        assert abs(price - 110.2) < 1e-9


# ---------------------------------------------------------------------------
# resolve_exit
# ---------------------------------------------------------------------------

class TestResolveExit:
    def test_no_levels_returns_open(self):
        bar = _bar(open_=110.0, high=110.5, low=109.5)
        reason, price = resolve_exit(bar, +1, float("nan"), float("nan"))
        assert reason == "open"
        assert abs(price - 110.0) < 1e-9

    def test_target_only_inside_range_long(self):
        bar = _bar(high=111.0, low=109.5)
        reason, price = resolve_exit(bar, +1, float("nan"), 110.75)
        assert reason == "target"
        assert abs(price - 110.75) < 1e-9

    def test_stop_only_inside_range_long(self):
        bar = _bar(high=110.5, low=109.5)
        reason, price = resolve_exit(bar, +1, 109.75, float("nan"))
        assert reason == "stop"
        assert abs(price - 109.75) < 1e-9

    def test_both_inside_range_stop_wins_pessimistic(self):
        # Bar range covers both stop (109.75) and target (110.75).
        bar = _bar(high=111.0, low=109.5)
        reason, price = resolve_exit(bar, +1, 109.75, 110.75)
        assert reason == "stop"
        assert abs(price - 109.75) < 1e-9

    def test_neither_inside_range(self):
        # Target is above the bar high; stop is below the bar low.
        bar = _bar(high=110.5, low=109.8)
        reason, price = resolve_exit(bar, +1, 109.5, 111.0)
        assert reason == "open"
        assert math.isnan(price)

    def test_short_target_inside_range(self):
        bar = _bar(high=110.5, low=109.0)
        # Short: target is below entry; stop is above entry.
        reason, price = resolve_exit(bar, -1, 111.0, 109.25)
        assert reason == "target"
        assert abs(price - 109.25) < 1e-9

    def test_short_both_inside_stop_wins(self):
        bar = _bar(high=111.5, low=108.5)
        reason, price = resolve_exit(bar, -1, 111.0, 109.0)
        assert reason == "stop"
        assert abs(price - 111.0) < 1e-9

    def test_ofi_fallback_when_no_volume(self):
        bar = _bar(high=111.0, low=109.5, buy_volume=None, sell_volume=None)
        reason, price = resolve_exit(bar, +1, 109.75, 110.75, use_ofi=True)
        # No OFI data → falls back to pessimistic → stop wins.
        assert reason == "stop"

    def test_ofi_buying_dominant_target_wins_long(self):
        # buy_volume >> sell_volume → ofi > 0 → target wins for long.
        bar = _bar(high=111.0, low=109.5, buy_volume=900, sell_volume=100)
        reason, price = resolve_exit(bar, +1, 109.75, 110.75, use_ofi=True)
        assert reason == "target"
