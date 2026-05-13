"""Tests for session-37 additions: multi-TF join and composable regime filters.

Covers:
1. join_htf — look-ahead prevention (the core correctness guarantee)
2. join_htf — column prefixing and DataFrame shape
3. YAMLStrategy — higher_timeframes field parsed from config
4. YAMLStrategy — expressions reference HTF columns after join
5. YAMLStrategy — regime_filter inline spec parsed and applied
6. YAMLStrategy — regime_filter include: reference resolved from temp dir
7. YAMLStrategy — regime_filters list (multiple filters)
8. YAMLStrategy — fit_filters called before generate_signals_df
9. YAMLStrategy — auto-fit when fit_filters not called (non-rolling mode)
10. VolatilityRegimeFilter — atr_column property and vectorized_mask
11. MTF strategy config file loads without error
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from trading_research.backtest.multiframe import join_htf, safe_prefix
from trading_research.strategies.regime.volatility_regime import VolatilityRegimeFilter
from trading_research.strategies.template import YAMLStrategy

# ---------------------------------------------------------------------------
# Test fixtures — synthetic DataFrames
# ---------------------------------------------------------------------------

_UTC = "UTC"


def _make_5m(n: int, start: str = "2024-01-02 12:00:00") -> pd.DataFrame:
    """Synthetic 5-minute bars."""
    idx = pd.date_range(start=start, periods=n, freq="5min", tz=_UTC)
    idx.name = "timestamp_utc"
    return pd.DataFrame(
        {
            "close": np.linspace(1.0, 1.0 + n * 0.001, n),
            "atr_14": np.full(n, 0.001),
            "vwap_session": np.full(n, 1.003),
        },
        index=idx,
    )


def _make_60m(n: int, start: str = "2024-01-02 11:00:00") -> pd.DataFrame:
    """Synthetic 60-minute bars with EMA columns."""
    idx = pd.date_range(start=start, periods=n, freq="60min", tz=_UTC)
    idx.name = "timestamp_utc"
    ema_20 = np.linspace(1.0, 1.0 + n * 0.01, n)
    ema_50 = np.linspace(0.99, 0.99 + n * 0.008, n)
    return pd.DataFrame(
        {
            "close": np.linspace(1.0, 1.0 + n * 0.01, n),
            "ema_20": ema_20,
            "ema_50": ema_50,
            "atr_14": np.full(n, 0.002),
            "timestamp_ny": np.full(n, "07:00"),   # metadata — should be skipped
            "trade_date": np.full(n, "2024-01-02"),  # metadata — should be skipped
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# 1–2. join_htf correctness tests
# ---------------------------------------------------------------------------


class TestJoinHtf:
    def test_no_lookahead_5m_bars_cannot_see_open_60m_bar(self) -> None:
        """5m bars within an open 60m bar must NOT see that 60m bar's data.

        Scenario:
        - 60m bar opens at 12:00 UTC (index value 12:00).
        - 5m bars at 12:00, 12:05, …, 12:55 are WITHIN that 60m bar.
        - Those 5m bars should see the PRIOR 60m bar (11:00), not the
          current open one (12:00).

        After shift(1), the 60m entry at 12:00 shows the data from 11:00.
        The 60m entry at 13:00 shows the data from 12:00.
        A 5m bar at 12:05 gets the 60m entry at 12:00 (i.e. prior bar's data).
        """
        primary = _make_5m(25, "2024-01-02 12:00:00")  # 12:00–14:00
        htf = _make_60m(5, "2024-01-02 11:00:00")      # 11:00–15:00

        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        # The 60m bar at 11:00 had ema_20 = first value of the linspace.
        # After shift(1), it appears at 12:00.
        # 5m bars at 12:00–12:55 should all see this value.
        ema_at_11h = htf["ema_20"].iloc[0]  # 11:00 bar value
        shifted_at_12h = float(result["tf60m_ema_20"].iloc[0])   # first 5m bar (12:00)
        assert shifted_at_12h == pytest.approx(ema_at_11h), (
            "5m bar at 12:00 saw the 12:00 60m bar instead of the prior 11:00 bar"
        )

    def test_5m_bars_after_60m_close_see_correct_value(self) -> None:
        """5m bars at T+60m see the 60m bar that closed at T."""
        primary = _make_5m(25, "2024-01-02 12:00:00")  # 12:00–14:00
        htf = _make_60m(5, "2024-01-02 11:00:00")      # 11:00–15:00

        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        # 60m bar at 12:00 closed at 13:00 → visible from 13:00 onwards.
        # After shift(1) it appears at 13:00.
        ema_at_12h = htf["ema_20"].iloc[1]   # 12:00 bar value
        # 5m bar at 13:00 = index position 12 in a 12:00-start 5m series
        bar_at_13h = primary.index.get_loc(pd.Timestamp("2024-01-02 13:00:00", tz="UTC"))
        result_val = float(result["tf60m_ema_20"].iloc[bar_at_13h])
        assert result_val == pytest.approx(ema_at_12h), (
            "5m bar at 13:00 did not see the 60m bar that closed at 13:00 (started at 12:00)"
        )

    def test_column_prefix_applied(self) -> None:
        primary = _make_5m(12, "2024-01-02 12:00:00")
        htf = _make_60m(3, "2024-01-02 11:00:00")
        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        assert "tf60m_close" in result.columns
        assert "tf60m_ema_20" in result.columns
        assert "tf60m_ema_50" in result.columns
        assert "tf60m_atr_14" in result.columns

    def test_metadata_columns_excluded(self) -> None:
        primary = _make_5m(12, "2024-01-02 12:00:00")
        htf = _make_60m(3, "2024-01-02 11:00:00")
        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        assert "tf60m_timestamp_ny" not in result.columns
        assert "tf60m_trade_date" not in result.columns

    def test_primary_columns_preserved(self) -> None:
        primary = _make_5m(12, "2024-01-02 12:00:00")
        htf = _make_60m(3, "2024-01-02 11:00:00")
        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        for col in primary.columns:
            assert col in result.columns

    def test_index_shape_preserved(self) -> None:
        primary = _make_5m(12, "2024-01-02 12:00:00")
        htf = _make_60m(3, "2024-01-02 11:00:00")
        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        assert len(result) == len(primary)
        assert result.index.tz is not None

    def test_naive_index_raises(self) -> None:
        primary = _make_5m(5)
        htf = _make_60m(2)
        # Strip timezone from primary
        primary_naive = primary.copy()
        primary_naive.index = primary_naive.index.tz_localize(None)
        with pytest.raises(ValueError, match="tz-aware"):
            join_htf(primary_naive, htf, prefix=safe_prefix("60m"))

    def test_pre_htf_bars_are_nan(self) -> None:
        """5m bars before the first HTF bar should have NaN in HTF columns."""
        # HTF starts at 13:00, primary starts at 12:00 → early bars have no HTF data
        primary = _make_5m(24, "2024-01-02 12:00:00")
        htf = _make_60m(2, "2024-01-02 13:00:00")
        result = join_htf(primary, htf, prefix=safe_prefix("60m"))

        # After shift(1), the 13:00 HTF bar shows as NaN (prior shifted row is None),
        # so all 5m bars before 14:00 see NaN.
        bar_at_12h = primary.index.get_loc(pd.Timestamp("2024-01-02 12:00:00", tz="UTC"))
        assert pd.isna(result["tf60m_ema_20"].iloc[bar_at_12h])


# ---------------------------------------------------------------------------
# 3–4. YAMLStrategy — higher_timeframes field and HTF column expressions
# ---------------------------------------------------------------------------


def _make_yaml_strat(config_text: str) -> YAMLStrategy:
    cfg = yaml.safe_load(textwrap.dedent(config_text))
    return YAMLStrategy.from_config(cfg)


class TestYAMLStrategyMTF:
    def test_higher_timeframes_parsed(self) -> None:
        strat = _make_yaml_strat("""
            strategy_id: test-mtf
            symbol: 6A
            higher_timeframes: [60m, 240m]
            entry:
              long:
                all: ["close < vwap_session"]
            exits: {}
        """)
        assert strat.higher_timeframes == ["60m", "240m"]

    def test_higher_timeframes_default_empty(self) -> None:
        strat = _make_yaml_strat("""
            strategy_id: test-stf
            symbol: 6A
            entry:
              long:
                all: ["close < vwap_session"]
            exits: {}
        """)
        assert strat.higher_timeframes == []

    def test_htf_column_reference_in_expression(self) -> None:
        """After join_htf, the strategy can evaluate expressions using HTF columns."""
        primary = _make_5m(10, "2024-01-02 12:00:00")
        htf = _make_60m(4, "2024-01-02 11:00:00")
        joined = join_htf(primary, htf, prefix=safe_prefix("60m"))

        strat = _make_yaml_strat("""
            strategy_id: test-htf-expr
            symbol: 6A
            higher_timeframes: [60m]
            entry:
              long:
                all:
                  - "tf60m_ema_20 > tf60m_ema_50"
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """)

        signals = strat.generate_signals_df(joined)
        assert "signal" in signals.columns
        # Some bars should have long=1 where tf60m_ema_20 > tf60m_ema_50
        # The fixture is constructed so ema_20 > ema_50 everywhere (both increase
        # linearly with ema_20 starting higher).
        assert (signals["signal"] == 1).any()


# ---------------------------------------------------------------------------
# 5–9. YAMLStrategy — regime_filter support
# ---------------------------------------------------------------------------


def _make_df_with_atr(n: int, low_atr_rows: list[int]) -> pd.DataFrame:
    """Synthetic DataFrame where specified rows have low ATR and others have high."""
    idx = pd.date_range("2024-01-02 12:00", periods=n, freq="5min", tz="UTC")
    idx.name = "timestamp_utc"
    atr = np.full(n, 0.010)   # default: high ATR (above any P75 threshold)
    for i in low_atr_rows:
        atr[i] = 0.001        # low ATR (below threshold)
    vwap = np.full(n, 1.0)
    close = np.full(n, 0.990)  # always below vwap → would fire long without filter
    return pd.DataFrame({"close": close, "vwap_session": vwap, "atr_14": atr}, index=idx)


class TestYAMLStrategyRegimeFilter:
    def test_inline_regime_filter_parsed(self) -> None:
        strat = _make_yaml_strat("""
            strategy_id: test-rf
            symbol: 6A
            regime_filter:
              type: volatility-regime
              vol_percentile_threshold: 75
              atr_column: atr_14
            entry:
              long:
                all: ["close < vwap_session"]
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """)
        assert len(strat._regime_filters) == 1
        assert isinstance(strat._regime_filters[0], VolatilityRegimeFilter)

    def test_regime_filter_suppresses_high_atr_bars(self) -> None:
        """Bars with ATR above the fitted threshold must be suppressed.

        Fit on uniform training data (ATR=0.004 → P75=0.004), then test
        against bars where rows 2 and 4 have ATR=0.001 (below threshold)
        and all others have ATR=0.010 (above threshold).  Only rows 2 and 4
        should generate a signal.
        """
        strat = _make_yaml_strat("""
            strategy_id: test-rf-suppress
            symbol: 6A
            regime_filter:
              type: volatility-regime
              vol_percentile_threshold: 75
              atr_column: atr_14
            entry:
              long:
                all: ["close < vwap_session"]
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """)

        # Fit on training data with uniform ATR=0.004 → P75 threshold = 0.004.
        train = _make_df_with_atr(n=20, low_atr_rows=[])
        train["atr_14"] = 0.004
        strat.fit_filters(train)

        # Test data: rows 2 and 4 have ATR=0.001 (≤ 0.004 → pass),
        # all others have ATR=0.010 (> 0.004 → blocked).
        df = _make_df_with_atr(n=10, low_atr_rows=[2, 4])
        signals = strat.generate_signals_df(df)
        signal_rows = list(np.where(signals["signal"].to_numpy() == 1)[0])
        assert signal_rows == [2, 4], (
            f"Expected signals only at rows [2, 4], got {signal_rows}"
        )

    def test_no_regime_filter_all_bars_fire(self) -> None:
        """Without regime filter, all rows where close < vwap should fire."""
        df = _make_df_with_atr(n=5, low_atr_rows=[])  # all bars have high ATR

        strat = _make_yaml_strat("""
            strategy_id: test-no-rf
            symbol: 6A
            entry:
              long:
                all: ["close < vwap_session"]
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """)
        signals = strat.generate_signals_df(df)
        assert (signals["signal"] == 1).all()

    def test_fit_filters_used_for_threshold(self) -> None:
        """fit_filters on train data must set the ATR threshold used in test data."""
        train = _make_df_with_atr(10, [])   # all high ATR → P75 threshold is high
        # Force a known threshold by making train ATR uniformly 0.005
        train["atr_14"] = 0.005

        test = _make_df_with_atr(10, [0, 1, 2])  # low-ATR rows among high-ATR
        test["atr_14"] = np.where(
            np.arange(10) < 3, 0.001, 0.010
        )

        strat = _make_yaml_strat("""
            strategy_id: test-fit
            symbol: 6A
            regime_filter:
              type: volatility-regime
              vol_percentile_threshold: 75
              atr_column: atr_14
            entry:
              long:
                all: ["close < vwap_session"]
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """)
        # train P75(atr_14=0.005) = 0.005 → threshold = 0.005
        strat.fit_filters(train)
        assert strat._regime_filters[0].fitted_threshold == pytest.approx(0.005)

        signals = strat.generate_signals_df(test)
        # Only rows 0, 1, 2 have atr=0.001 ≤ 0.005 → should fire
        signal_rows = list(np.where(signals["signal"].to_numpy() == 1)[0])
        assert signal_rows == [0, 1, 2]

    def test_regime_filters_list(self) -> None:
        """regime_filters: (list) is parsed and all filters applied."""
        strat = _make_yaml_strat("""
            strategy_id: test-rf-list
            symbol: 6A
            regime_filters:
              - type: volatility-regime
                vol_percentile_threshold: 75
                atr_column: atr_14
              - type: volatility-regime
                vol_percentile_threshold: 90
                atr_column: atr_14
            entry:
              long:
                all: ["close < vwap_session"]
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """)
        assert len(strat._regime_filters) == 2

    def test_include_regime_filter(self, tmp_path: Path) -> None:
        """include: loads a shared regime filter from configs/regimes/."""
        regime_cfg = tmp_path / "my-filter.yaml"
        regime_cfg.write_text(
            "type: volatility-regime\nvol_percentile_threshold: 75\natr_column: atr_14\n"
        )

        cfg = yaml.safe_load(textwrap.dedent("""
            strategy_id: test-include
            symbol: 6A
            regime_filter:
              include: my-filter
            entry:
              long:
                all: ["close < vwap_session"]
            exits:
              stop:
                long: "close - 0.001"
              target:
                long: "vwap_session"
        """))
        strat = YAMLStrategy.from_config(cfg, regimes_dir=tmp_path)
        assert len(strat._regime_filters) == 1
        flt = strat._regime_filters[0]
        assert isinstance(flt, VolatilityRegimeFilter)
        assert flt._percentile == 75.0

    def test_include_not_found_raises(self, tmp_path: Path) -> None:
        cfg = yaml.safe_load(textwrap.dedent("""
            strategy_id: test-include-missing
            symbol: 6A
            regime_filter:
              include: does-not-exist
            entry:
              long:
                all: ["close < vwap_session"]
            exits: {}
        """))
        with pytest.raises(ValueError, match="not found"):
            YAMLStrategy.from_config(cfg, regimes_dir=tmp_path)


# ---------------------------------------------------------------------------
# 10. VolatilityRegimeFilter — new public API
# ---------------------------------------------------------------------------


class TestVolatilityRegimeFilterExtensions:
    def test_atr_column_property(self) -> None:
        flt = VolatilityRegimeFilter(atr_column="atr_14")
        assert flt.atr_column == "atr_14"

    def test_vectorized_mask_fitted(self) -> None:
        df = pd.DataFrame(
            {"atr_14": [0.001, 0.002, 0.005, 0.010, 0.050]},
            index=pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC"),
        )
        flt = VolatilityRegimeFilter(vol_percentile_threshold=75)
        flt.fit(df)
        mask = flt.vectorized_mask(df)
        assert mask.dtype == bool
        # P75 of [0.001, 0.002, 0.005, 0.010, 0.050] = 0.010 (index 3 of 5)
        # Tradeable: rows where atr <= 0.010 → all except last (0.050)
        assert mask.tolist() == [True, True, True, True, False]

    def test_vectorized_mask_autofits_when_not_fitted(self) -> None:
        df = pd.DataFrame(
            {"atr_14": [0.001, 0.001, 0.010, 0.010]},
            index=pd.date_range("2024-01-01", periods=4, freq="5min", tz="UTC"),
        )
        flt = VolatilityRegimeFilter(vol_percentile_threshold=75)
        # Not fitted — should auto-fit and return a mask without raising
        mask = flt.vectorized_mask(df)
        assert len(mask) == 4
        assert flt.is_fitted

    def test_vectorized_mask_zeros_for_nonfinite_atr(self) -> None:
        df = pd.DataFrame(
            {"atr_14": [np.nan, 0.001, -1.0, 0.002]},
            index=pd.date_range("2024-01-01", periods=4, freq="5min", tz="UTC"),
        )
        flt = VolatilityRegimeFilter(vol_percentile_threshold=75)
        flt.fit(df.dropna())
        mask = flt.vectorized_mask(df)
        # nan row and negative-ATR row must be False
        assert not mask[0]   # NaN
        assert not mask[2]   # negative


# ---------------------------------------------------------------------------
# 11. MTF strategy config file round-trip
# ---------------------------------------------------------------------------


class TestMTFConfigFile:
    _CONFIG = Path(__file__).parents[1] / "configs" / "strategies" / "6a-vwap-reversion-mtf-v1.yaml"
    _REGIMES = Path(__file__).parents[1] / "configs" / "regimes"

    def test_config_file_loads(self) -> None:
        assert self._CONFIG.exists(), f"MTF config not found: {self._CONFIG}"
        cfg = yaml.safe_load(self._CONFIG.read_text())
        assert cfg["strategy_id"] == "6a-vwap-reversion-mtf-v1"
        assert cfg["symbol"] == "6A"
        assert "higher_timeframes" in cfg
        assert "60m" in cfg["higher_timeframes"]
        assert "regime_filter" in cfg

    def test_yaml_strategy_instantiates_from_config(self) -> None:
        cfg = yaml.safe_load(self._CONFIG.read_text())
        strat = YAMLStrategy.from_config(cfg, regimes_dir=self._REGIMES)
        assert strat.name == "6a-vwap-reversion-mtf-v1"
        assert strat.higher_timeframes == ["60m"]
        assert len(strat._regime_filters) == 1

    def test_yaml_strategy_generates_signals_on_synthetic_data(self) -> None:
        """End-to-end: join HTF, generate signals, verify no crash and output shape."""
        cfg = yaml.safe_load(self._CONFIG.read_text())
        strat = YAMLStrategy.from_config(cfg, regimes_dir=self._REGIMES)

        # Synthetic 15m primary bars
        n = 20
        idx = pd.date_range("2024-01-02 12:00", periods=n, freq="15min", tz="UTC")
        idx.name = "timestamp_utc"
        primary = pd.DataFrame(
            {
                "close": np.full(n, 0.6450),
                "vwap_session": np.full(n, 0.6500),
                "atr_14": np.full(n, 0.0008),
                "adx_14": np.full(n, 15.0),
            },
            index=idx,
        )

        # Synthetic 60m HTF bars
        htf_n = 6
        htf_idx = pd.date_range("2024-01-02 10:00", periods=htf_n, freq="60min", tz="UTC")
        htf_idx.name = "timestamp_utc"
        htf = pd.DataFrame(
            {
                "close": np.full(htf_n, 0.6480),
                "ema_20": np.full(htf_n, 0.6490),   # ema_20 > ema_50 → uptrend
                "ema_50": np.full(htf_n, 0.6470),
                "atr_14": np.full(htf_n, 0.001),
            },
            index=htf_idx,
        )

        joined = join_htf(primary, htf, prefix=safe_prefix("60m"))
        signals = strat.generate_signals_df(joined)

        assert list(signals.columns) == ["signal", "stop", "target"]
        assert len(signals) == n
