"""Unit tests for the regime filter layer (session 31).

Covers:
- VolatilityRegimeFilter: construction, fit, is_tradeable, error cases
- RegimeFilterChain: AND-of-filters composition
- VWAPReversionV1 integration: regime_filters knob, signal gating
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from trading_research.core.instruments import Instrument
from trading_research.strategies.regime import (
    _FILTER_REGISTRY,
    RegimeFilter,
    RegimeFilterChain,
    build_filter,
)
from trading_research.strategies.regime.volatility_regime import VolatilityRegimeFilter
from trading_research.strategies.vwap_reversion_v1 import (
    VWAPReversionV1,
    VWAPReversionV1Knobs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_features_with_atr(
    atr_values: list[float],
    start: str = "2024-06-03 12:00",
    freq: str = "5min",
    close: float = 1.085,
    vwap: float = 1.085,
) -> pd.DataFrame:
    """Build a minimal features DataFrame with specified ATR values."""
    n = len(atr_values)
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": 1000,
            "vwap_session": vwap,
            "atr_14": atr_values,
        },
        index=idx,
    )


def _make_instrument_6e() -> Instrument:
    return Instrument(
        symbol="6E",
        tradestation_symbol="@EC",
        name="Euro FX",
        exchange="CME",
        asset_class="fx",
        tick_size=Decimal("0.00005"),
        tick_value_usd=Decimal("6.25"),
        contract_multiplier=Decimal("125000"),
        is_micro=False,
        commission_per_side_usd=Decimal("1.75"),
        intraday_initial_margin_usd=Decimal("500"),
        overnight_initial_margin_usd=None,
        session_open_et=time(18, 0),
        session_close_et=time(17, 0),
        rth_open_et=time(8, 0),
        rth_close_et=time(17, 0),
        calendar_name="CMEGlobex_FX",
        roll_method="panama",
    )


# ---------------------------------------------------------------------------
# VolatilityRegimeFilter unit tests
# ---------------------------------------------------------------------------


class TestVolatilityRegimeFilter:
    def test_registry_entry(self) -> None:
        assert "volatility-regime" in _FILTER_REGISTRY

    def test_satisfies_protocol(self) -> None:
        f = VolatilityRegimeFilter()
        assert isinstance(f, RegimeFilter)

    def test_default_percentile(self) -> None:
        f = VolatilityRegimeFilter()
        assert f._percentile == 75.0

    def test_invalid_percentile_below_50(self) -> None:
        with pytest.raises(ValueError, match="vol_percentile_threshold"):
            VolatilityRegimeFilter(vol_percentile_threshold=49.0)

    def test_invalid_percentile_above_95(self) -> None:
        with pytest.raises(ValueError, match="vol_percentile_threshold"):
            VolatilityRegimeFilter(vol_percentile_threshold=96.0)

    def test_is_tradeable_raises_before_fit(self) -> None:
        f = VolatilityRegimeFilter()
        features = _make_features_with_atr([0.001] * 10)
        with pytest.raises(RuntimeError, match="fit\\(\\) must be called"):
            f.is_tradeable(features, 0)

    def test_fit_computes_threshold(self) -> None:
        f = VolatilityRegimeFilter(vol_percentile_threshold=75.0)
        atr_values = list(range(1, 101))  # 1..100
        features = _make_features_with_atr([float(v) * 0.0001 for v in atr_values])
        f.fit(features)
        assert f.is_fitted
        # P75 of [0.0001, 0.0002, ..., 0.0100] = 0.0075 + epsilon
        expected_p75 = np.percentile([v * 0.0001 for v in atr_values], 75)
        assert f.fitted_threshold == pytest.approx(expected_p75, rel=1e-9)

    def test_fit_raises_on_missing_column(self) -> None:
        f = VolatilityRegimeFilter()
        features = pd.DataFrame({"close": [1.0, 2.0]})
        with pytest.raises(KeyError, match="atr_14"):
            f.fit(features)

    def test_fit_raises_on_all_nan(self) -> None:
        f = VolatilityRegimeFilter()
        features = _make_features_with_atr([float("nan")] * 5)
        with pytest.raises(ValueError, match="empty ATR"):
            f.fit(features)

    def test_low_atr_bar_is_tradeable(self) -> None:
        f = VolatilityRegimeFilter(vol_percentile_threshold=75.0)
        # ATR values: 10 low bars at 0.001, 10 high bars at 0.010
        atr_vals = [0.001] * 10 + [0.010] * 10
        train = _make_features_with_atr(atr_vals)
        f.fit(train)
        # A bar with ATR = 0.001 (well below P75) should be tradeable
        test = _make_features_with_atr([0.001] * 5)
        assert f.is_tradeable(test, 0) is True

    def test_high_atr_bar_is_blocked(self) -> None:
        f = VolatilityRegimeFilter(vol_percentile_threshold=75.0)
        # 25% of bars have very high ATR
        atr_vals = [0.001] * 75 + [0.020] * 25
        train = _make_features_with_atr(atr_vals)
        f.fit(train)
        # A bar with ATR = 0.020 (above P75) should be blocked
        test = _make_features_with_atr([0.020] * 5)
        assert f.is_tradeable(test, 0) is False

    def test_bar_at_threshold_is_tradeable(self) -> None:
        f = VolatilityRegimeFilter(vol_percentile_threshold=50.0)
        atr_vals = [0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.010]
        train = _make_features_with_atr(atr_vals)
        f.fit(train)
        threshold = f.fitted_threshold
        assert threshold is not None
        # Bar exactly AT threshold: should be tradeable (<= threshold)
        test = _make_features_with_atr([threshold] * 3)
        assert f.is_tradeable(test, 0) is True

    def test_zero_atr_bar_is_blocked(self) -> None:
        f = VolatilityRegimeFilter()
        atr_vals = [0.001] * 10
        train = _make_features_with_atr(atr_vals)
        f.fit(train)
        test = _make_features_with_atr([0.0] * 3)
        assert f.is_tradeable(test, 0) is False

    def test_nan_atr_bar_is_blocked(self) -> None:
        f = VolatilityRegimeFilter()
        train = _make_features_with_atr([0.001] * 10)
        f.fit(train)
        test = _make_features_with_atr([float("nan")] * 3)
        assert f.is_tradeable(test, 0) is False

    def test_fit_resets_threshold_on_second_call(self) -> None:
        f = VolatilityRegimeFilter(vol_percentile_threshold=50.0)
        train1 = _make_features_with_atr([0.001] * 10)
        train2 = _make_features_with_atr([0.010] * 10)
        f.fit(train1)
        threshold1 = f.fitted_threshold
        f.fit(train2)
        threshold2 = f.fitted_threshold
        assert threshold1 != threshold2
        assert threshold2 == pytest.approx(0.010, rel=1e-9)

    def test_build_filter_factory(self) -> None:
        f = build_filter("volatility-regime", vol_percentile_threshold=80.0)
        assert isinstance(f, VolatilityRegimeFilter)
        assert f._percentile == 80.0

    def test_build_filter_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown regime filter"):
            build_filter("nonexistent-filter")

    def test_name_includes_percentile(self) -> None:
        f = VolatilityRegimeFilter(vol_percentile_threshold=75.0)
        assert "75" in f.name
        assert "volatility" in f.name


# ---------------------------------------------------------------------------
# RegimeFilterChain unit tests
# ---------------------------------------------------------------------------


class TestRegimeFilterChain:
    def _fitted_chain(self, *percentiles: float) -> tuple[RegimeFilterChain, pd.DataFrame]:
        """Return a fitted chain and a reference training DataFrame."""
        atr_vals = list(np.linspace(0.001, 0.010, 100))
        train = _make_features_with_atr(atr_vals)
        filters = [VolatilityRegimeFilter(vol_percentile_threshold=p) for p in percentiles]
        chain = RegimeFilterChain(filters)
        chain.fit(train)
        return chain, train

    def test_empty_chain_always_tradeable(self) -> None:
        chain = RegimeFilterChain([])
        features = _make_features_with_atr([0.001] * 5)
        # Empty chain: no filters to reject, so always True
        assert chain.is_tradeable(features, 0) is True

    def test_single_filter_passes_through(self) -> None:
        chain, train = self._fitted_chain(75.0)
        # A very low ATR bar should pass a P75 gate
        test = _make_features_with_atr([0.001] * 5)
        assert chain.is_tradeable(test, 0) is True

    def test_single_filter_blocks(self) -> None:
        # P50 gate blocks the top half of ATR bars
        chain, train = self._fitted_chain(50.0)
        # ATR 0.010 is the max of linspace(0.001, 0.010, 100) → above P50
        test = _make_features_with_atr([0.010] * 5)
        assert chain.is_tradeable(test, 0) is False

    def test_two_filters_and_logic(self) -> None:
        # P75 gate + P50 gate: bar passes both only if ATR <= min(P75, P50) = P50
        chain, train = self._fitted_chain(75.0, 50.0)
        # A very low ATR bar should pass both
        test_low = _make_features_with_atr([0.001] * 5)
        assert chain.is_tradeable(test_low, 0) is True
        # A mid-range bar passes P75 but not P50 → chain rejects
        p50 = np.percentile(np.linspace(0.001, 0.010, 100), 50)
        above_p50 = p50 + 0.0005
        test_mid = _make_features_with_atr([above_p50] * 5)
        assert chain.is_tradeable(test_mid, 0) is False

    def test_fit_propagates_to_all_filters(self) -> None:
        atr_vals = list(np.linspace(0.001, 0.010, 100))
        train = _make_features_with_atr(atr_vals)
        f1 = VolatilityRegimeFilter(vol_percentile_threshold=75.0)
        f2 = VolatilityRegimeFilter(vol_percentile_threshold=50.0)
        chain = RegimeFilterChain([f1, f2])
        assert not f1.is_fitted
        assert not f2.is_fitted
        chain.fit(train)
        assert f1.is_fitted
        assert f2.is_fitted

    def test_chain_len(self) -> None:
        chain, _ = self._fitted_chain(50.0, 75.0, 90.0)
        assert len(chain) == 3

    def test_filter_names(self) -> None:
        chain, _ = self._fitted_chain(75.0)
        names = chain.filter_names
        assert len(names) == 1
        assert "75" in names[0]


# ---------------------------------------------------------------------------
# VWAPReversionV1 integration tests
# ---------------------------------------------------------------------------


class TestVWAPReversionV1RegimeIntegration:
    def _make_strategy_with_filter(
        self, percentile: float = 75.0
    ) -> VWAPReversionV1:
        knobs = VWAPReversionV1Knobs(
            regime_filters=["volatility-regime"],
            vol_percentile_threshold=percentile,
        )
        return VWAPReversionV1(knobs=knobs, template_name="vwap-reversion-v1")

    def _make_strategy_without_filter(self) -> VWAPReversionV1:
        knobs = VWAPReversionV1Knobs()
        return VWAPReversionV1(knobs=knobs, template_name="vwap-reversion-v1")

    def test_filter_chain_built_when_knob_set(self) -> None:
        strategy = self._make_strategy_with_filter()
        assert strategy._filter_chain is not None
        assert len(strategy._filter_chain) == 1

    def test_no_filter_chain_when_knob_empty(self) -> None:
        strategy = self._make_strategy_without_filter()
        assert strategy._filter_chain is None

    def test_generate_signals_raises_if_filter_not_fitted(
        self, instrument_6e: Instrument
    ) -> None:
        strategy = self._make_strategy_with_filter()
        # 60 bars at 12:00 UTC in entry window, spread well below threshold
        features = _make_features_with_atr(
            atr_values=[0.001] * 60,
            close=1.082,  # 2.2 ATR below vwap=1.085
        )
        features["close"] = 1.082
        with pytest.raises(RuntimeError, match="fit\\(\\) must be called"):
            strategy.generate_signals(features, features, instrument_6e)

    def test_generate_signals_respects_filter(
        self, instrument_6e: Instrument
    ) -> None:
        strategy = self._make_strategy_with_filter(percentile=50.0)
        # Half of ATR values are low, half are high
        low_atr = 0.0001
        high_atr = 0.010
        atr_train = [low_atr] * 50 + [high_atr] * 50
        atr_test = [low_atr] * 60  # all low-vol in test

        train_features = _make_features_with_atr(atr_train)
        test_features = _make_features_with_atr(
            atr_test,
            start="2024-06-03 12:05",
            close=1.082,  # below entry threshold
        )
        test_features["close"] = 1.082

        strategy.fit_filters(train_features)

        # Unfiltered strategy generates signals (spread = -3 ATR)
        unfiltered = self._make_strategy_without_filter()
        all_signals = unfiltered.generate_signals(test_features, test_features, instrument_6e)

        filtered_signals = strategy.generate_signals(test_features, test_features, instrument_6e)

        # With P50 filter and all-low-ATR test bars, filtered should == unfiltered
        # (all bars pass the filter because their ATR is below P50 of train data)
        assert len(filtered_signals) == len(all_signals)

    def test_generate_signals_blocked_when_all_high_vol(
        self, instrument_6e: Instrument
    ) -> None:
        strategy = self._make_strategy_with_filter(percentile=50.0)
        # Train: half low, half high
        atr_train = [0.0001] * 50 + [0.010] * 50
        train_features = _make_features_with_atr(atr_train)
        strategy.fit_filters(train_features)

        # Test: all high-ATR bars (above P50 of training) with spread deviation
        atr_test = [0.010] * 60
        test_features = _make_features_with_atr(
            atr_test,
            start="2024-06-03 12:05",
            close=1.082,
        )
        test_features["close"] = 1.082

        signals = strategy.generate_signals(test_features, test_features, instrument_6e)
        assert len(signals) == 0, "High-vol bars should all be blocked"

    def test_fit_filters_noop_when_no_filters(self) -> None:
        strategy = self._make_strategy_without_filter()
        features = _make_features_with_atr([0.001] * 10)
        strategy.fit_filters(features)  # Should not raise


@pytest.fixture()
def instrument_6e() -> Instrument:
    return _make_instrument_6e()
