"""Tests for YAML-defined strategy authoring (session 36).

Verifies:
1. ExprEvaluator handles all supported expression types.
2. YAMLStrategy.generate_signals_df produces correct output.
3. Parity between YAMLStrategy and the Python module for the two
   directly-portable strategies (6A VWAP MR and 6C Donchian Breakout).
4. Time-window filter, shift(), conflict resolution, stop/target computation.
5. CLI dispatch detection smoke tests.
6. YAML config files load and validate without error.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from trading_research.strategies.template import (
    ExprEvaluator,
    YAMLStrategy,
    load_yaml_strategy,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CONFIGS_DIR = Path(__file__).parents[1] / "configs" / "strategies"
_UTC = UTC


def _make_index(n: int, start: str = "2024-01-02 12:30:00") -> pd.DatetimeIndex:
    """UTC DatetimeIndex with 15-minute spacing."""
    return pd.date_range(start=start, periods=n, freq="15min", tz="UTC")


def _make_6a_fixture(
    *,
    n: int = 10,
    entry_atr_mult: float = 1.5,
    stop_atr_mult: float = 1.5,
    adx_max: float = 22.0,
) -> pd.DataFrame:
    """Synthetic 6A features fixture with known signal bars.

    Bar layout (0-indexed):
    - Row 2: long signal  — close below lower band, adx < adx_max, in window
    - Row 4: NO signal    — close below band but adx >= adx_max (trending)
    - Row 6: short signal — close above upper band, adx < adx_max, in window
    - Row 8: NO signal    — below band but outside time window (18:30 UTC)
    """
    idx = _make_index(n, start="2024-01-02 12:30:00")  # 12:30–14:45 UTC, all in window
    vwap = np.full(n, 0.6500)
    atr = np.full(n, 0.0010)
    adx = np.full(n, 18.0)  # range-bound by default
    close = vwap.copy()     # neutral by default

    # Row 2: long — close far below lower band
    close[2] = vwap[2] - (entry_atr_mult + 0.1) * atr[2]
    # Row 4: adx >= adx_max — entry blocked
    close[4] = vwap[4] - (entry_atr_mult + 0.1) * atr[4]
    adx[4] = adx_max + 1.0
    # Row 6: short — close far above upper band
    close[6] = vwap[6] + (entry_atr_mult + 0.1) * atr[6]

    # Row 8: outside time window — use an index with a later hour
    out_of_window_idx = pd.DatetimeIndex(
        [idx[i] if i != 8 else pd.Timestamp("2024-01-02 18:30:00", tz="UTC") for i in range(n)]
    )
    close[8] = vwap[8] - (entry_atr_mult + 0.1) * atr[8]

    return pd.DataFrame(
        {"close": close, "vwap_session": vwap, "atr_14": atr, "adx_14": adx},
        index=out_of_window_idx,
    )


def _make_6c_fixture(n: int = 10) -> pd.DataFrame:
    """Synthetic 6C features fixture for Donchian breakout tests.

    Bar layout:
    - Row 2: long signal  — close > donchian_upper[prev_bar], ema_fast > ema_slow
    - Row 5: short signal — close < donchian_lower[prev_bar], ema_fast < ema_slow
    - Row 7: NO signal    — breakout but trend opposes direction
    """
    idx = pd.date_range("2024-01-02 00:00:00", periods=n, freq="60min", tz="UTC")
    close = np.full(n, 0.7400)
    donchian_upper = np.full(n, 0.7410)
    donchian_lower = np.full(n, 0.7390)
    atr = np.full(n, 0.0005)
    ema_fast = np.full(n, 0.7405)
    ema_slow = np.full(n, 0.7400)  # fast > slow → trend up

    # Row 2: close > donchian_upper_prev = donchian_upper[1] = 0.7410
    close[2] = 0.7415
    # Row 5: close < donchian_lower_prev, trend DOWN
    close[5] = 0.7385
    ema_fast[5] = 0.7395
    ema_slow[5] = 0.7400  # fast < slow → trend down
    # Row 7: breakout up but ema_fast < ema_slow (trend opposes)
    close[7] = 0.7415
    ema_fast[7] = 0.7395
    ema_slow[7] = 0.7400

    return pd.DataFrame(
        {
            "close": close,
            "donchian_upper": donchian_upper,
            "donchian_lower": donchian_lower,
            "atr_14": atr,
            "daily_ema_50": ema_fast,
            "daily_ema_200": ema_slow,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# ExprEvaluator tests
# ---------------------------------------------------------------------------


class TestExprEvaluator:
    def _make_ev(self, df: pd.DataFrame, knobs: dict) -> ExprEvaluator:
        return ExprEvaluator(df, knobs)

    def _simple_df(self, n: int = 5) -> tuple[pd.DataFrame, ExprEvaluator]:
        idx = _make_index(n)
        df = pd.DataFrame({"close": np.arange(n, dtype=float), "atr": np.ones(n)}, index=idx)
        ev = self._make_ev(df, {"mult": 2.0, "threshold": 3.0})
        return df, ev

    def test_numeric_literal(self) -> None:
        _, ev = self._simple_df()
        assert ev.eval("42.0") == pytest.approx(42.0)

    def test_column_reference(self) -> None:
        df, ev = self._simple_df()
        result = ev.eval("close")
        pd.testing.assert_series_equal(result, df["close"].astype(float), check_names=False)

    def test_knob_reference(self) -> None:
        _, ev = self._simple_df()
        assert ev.eval("mult") == pytest.approx(2.0)

    def test_arithmetic(self) -> None:
        df, ev = self._simple_df()
        result = ev.eval("close + mult * atr")
        expected = df["close"] + 2.0 * df["atr"]
        pd.testing.assert_series_equal(result, expected.astype(float), check_names=False)

    def test_comparison_returns_bool_series(self) -> None:
        df, ev = self._simple_df()
        result = ev.eval("close > threshold")
        assert isinstance(result, pd.Series)
        # close values: 0,1,2,3,4 — only rows 3,4 are > 3.0
        np.testing.assert_array_equal(result.to_numpy(), [False, False, False, False, True])

    def test_shift(self) -> None:
        df, ev = self._simple_df()
        result = ev.eval("shift(close, 1)")
        assert isinstance(result, pd.Series)
        # Shifted by 1: first row is NaN, rest are [0,1,2,3]
        assert np.isnan(result.iloc[0])
        np.testing.assert_array_equal(result.iloc[1:].to_numpy(), [0.0, 1.0, 2.0, 3.0])

    def test_nan_in_comparison_produces_false(self) -> None:
        idx = _make_index(3)
        df = pd.DataFrame({"close": [1.0, np.nan, 3.0], "threshold": [2.0, 2.0, 2.0]}, index=idx)
        ev = self._make_ev(df, {})
        result = ev.eval("close > 2.0")
        assert result.iloc[1] == False  # noqa: E712  — NaN comparison → False

    def test_unary_minus(self) -> None:
        _, ev = self._simple_df()
        assert ev.eval("-mult") == pytest.approx(-2.0)

    def test_parentheses(self) -> None:
        df, ev = self._simple_df()
        result_with = ev.eval("(close + 1) * mult")
        result_without = ev.eval("close + 1 * mult")
        # with parentheses: (close+1)*2; without: close + 2
        pd.testing.assert_series_equal(
            result_with, ((df["close"] + 1) * 2).astype(float), check_names=False
        )
        pd.testing.assert_series_equal(
            result_without, (df["close"] + 2).astype(float), check_names=False
        )

    def test_unknown_name_raises(self) -> None:
        _, ev = self._simple_df()
        with pytest.raises(ValueError, match="not a column"):
            ev.eval("does_not_exist")

    def test_unsupported_function_raises(self) -> None:
        _, ev = self._simple_df()
        with pytest.raises(ValueError, match="Unknown function"):
            ev.eval("abs(close)")

    def test_chained_comparison_raises(self) -> None:
        _, ev = self._simple_df()
        with pytest.raises(ValueError, match="Chained comparisons"):
            ev.eval("1 < close < 3")


# ---------------------------------------------------------------------------
# YAMLStrategy construction and signal generation
# ---------------------------------------------------------------------------


class TestYAMLStrategyConstruction:
    def test_from_config_requires_entry_block(self) -> None:
        with pytest.raises(ValueError, match="'entry' block"):
            YAMLStrategy.from_config({"strategy_id": "x", "signal_module": "some.module"})

    def test_load_yaml_strategy_rejects_signal_module(self) -> None:
        with pytest.raises(ValueError, match="signal_module"):
            load_yaml_strategy({"strategy_id": "x", "signal_module": "mod", "entry": {}})

    def test_properties(self) -> None:
        config = {
            "strategy_id": "my-strat",
            "knobs": {"a": 1.5},
            "entry": {"long": {"all": ["close > 0.0"]}},
        }
        strat = YAMLStrategy.from_config(config)
        assert strat.name == "my-strat"
        assert strat.template_name == "yaml-template"
        assert strat.knobs == {"a": 1.5}

    def test_raises_on_non_tz_aware_index(self) -> None:
        config = {"strategy_id": "x", "entry": {"long": {"all": ["close > 0.0"]}}}
        strat = YAMLStrategy.from_config(config)
        df = pd.DataFrame({"close": [1.0, 2.0]}, index=pd.date_range("2024-01-01", periods=2, freq="5min"))
        with pytest.raises(ValueError, match="tz-aware"):
            strat.generate_signals_df(df)


class TestYAMLStrategySignals:
    """Core signal generation correctness."""

    def _make_simple_strat(
        self, long_cond: str, short_cond: str = "", stop_long: str = "0.0", target_long: str = "0.0"
    ) -> YAMLStrategy:
        cfg: dict = {
            "strategy_id": "test",
            "knobs": {"thresh": 2.0},
            "entry": {"long": {"all": [long_cond]}},
            "exits": {
                "stop": {"long": stop_long, "short": stop_long},
                "target": {"long": target_long, "short": target_long},
            },
        }
        if short_cond:
            cfg["entry"]["short"] = {"all": [short_cond]}
        return YAMLStrategy.from_config(cfg)

    def test_no_signals_when_condition_never_met(self) -> None:
        idx = _make_index(5)
        df = pd.DataFrame({"close": np.zeros(5), "vwap": np.ones(5)}, index=idx)
        strat = self._make_simple_strat("close > vwap")
        result = strat.generate_signals_df(df)
        assert (result["signal"] == 0).all()

    def test_long_signal_fires_correctly(self) -> None:
        idx = _make_index(5)
        close = np.array([0.0, 0.0, 5.0, 0.0, 0.0])
        df = pd.DataFrame(
            {"close": close, "atr": np.ones(5)},
            index=idx,
        )
        strat = self._make_simple_strat(
            long_cond="close > thresh",
            stop_long="close - atr",
            target_long="close + atr",
        )
        result = strat.generate_signals_df(df)
        assert result.loc[idx[2], "signal"] == 1
        assert result.loc[idx[2], "stop"] == pytest.approx(5.0 - 1.0)
        assert result.loc[idx[2], "target"] == pytest.approx(5.0 + 1.0)
        assert (result["signal"].drop(idx[2]) == 0).all()

    def test_conflict_resolution_neither_fires(self) -> None:
        """When both long and short conditions are true, neither fires."""
        idx = _make_index(3)
        df = pd.DataFrame({"close": [1.0, 1.0, 1.0]}, index=idx)
        cfg = {
            "strategy_id": "conflict-test",
            "knobs": {},
            "entry": {
                "long": {"all": ["close > 0.5"]},
                "short": {"all": ["close > 0.5"]},  # same condition → always conflicts
            },
            "exits": {
                "stop": {"long": "close", "short": "close"},
                "target": {"long": "close", "short": "close"},
            },
        }
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        assert (result["signal"] == 0).all(), "conflict should suppress both signals"

    def test_time_window_filter(self) -> None:
        """Bars outside the UTC time window get no signal."""
        n = 6
        # Mix of bars: rows 0-3 in 12:00-17:00, rows 4-5 outside
        idx = pd.DatetimeIndex([
            "2024-01-02 12:00", "2024-01-02 13:00",
            "2024-01-02 16:59", "2024-01-02 14:00",
            "2024-01-02 11:59", "2024-01-02 17:00",  # both outside
        ], tz="UTC")
        df = pd.DataFrame(
            {"close": np.ones(n), "atr": np.ones(n)},
            index=idx,
        )
        cfg = {
            "strategy_id": "tw-test",
            "knobs": {},
            "entry": {
                "long": {"all": ["close > 0.5"]},
                "time_window": {"start_utc": "12:00", "end_utc": "17:00"},
            },
            "exits": {
                "stop": {"long": "close - atr"},
                "target": {"long": "close"},
            },
        }
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        # Rows 0-3 should be in window (12:00 ≤ t < 17:00)
        assert result.iloc[0]["signal"] == 1
        assert result.iloc[1]["signal"] == 1
        assert result.iloc[2]["signal"] == 1
        assert result.iloc[3]["signal"] == 1
        # Rows 4-5 outside window
        assert result.iloc[4]["signal"] == 0
        assert result.iloc[5]["signal"] == 0

    def test_nan_stop_suppresses_signal(self) -> None:
        """A signal with NaN stop is suppressed (indicator warm-up)."""
        idx = _make_index(3)
        df = pd.DataFrame(
            {"close": [1.0, 1.0, 1.0], "atr": [np.nan, np.nan, 1.0]},
            index=idx,
        )
        strat = self._make_simple_strat(
            long_cond="close > 0.5",
            stop_long="close - atr",  # NaN for first two rows
            target_long="close",
        )
        result = strat.generate_signals_df(df)
        assert result.iloc[0]["signal"] == 0  # NaN stop → suppressed
        assert result.iloc[1]["signal"] == 0
        assert result.iloc[2]["signal"] == 1  # atr finite → fires

    def test_any_composition(self) -> None:
        """'any' conditions use OR logic."""
        idx = _make_index(4)
        df = pd.DataFrame(
            {"a": [0.0, 1.0, 0.0, 1.0], "b": [0.0, 0.0, 1.0, 1.0]},
            index=idx,
        )
        cfg = {
            "strategy_id": "any-test",
            "knobs": {},
            "entry": {
                "long": {
                    "any": ["a > 0.5", "b > 0.5"],
                }
            },
            "exits": {"stop": {"long": "0.0"}, "target": {"long": "1.0"}},
        }
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        np.testing.assert_array_equal(
            result["signal"].to_numpy(),
            [0, 1, 1, 1],  # row 0: neither; rows 1,2,3: at least one
        )

    def test_shift_in_condition(self) -> None:
        """shift(col, 1) in a condition uses the prior bar's value."""
        idx = _make_index(5)
        vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        df = pd.DataFrame({"close": vals, "prev": vals}, index=idx)
        # Signal fires when close > shift(close, 1), i.e. close is rising bar-over-bar
        cfg = {
            "strategy_id": "shift-test",
            "knobs": {},
            "entry": {"long": {"all": ["close > shift(close, 1)"]}},
            "exits": {"stop": {"long": "0.0"}, "target": {"long": "1.0"}},
        }
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        # Row 0: prev is NaN → False; rows 1-4: rising → True
        assert result.iloc[0]["signal"] == 0
        for i in range(1, 5):
            assert result.iloc[i]["signal"] == 1


# ---------------------------------------------------------------------------
# Parity tests: YAML vs Python module
# ---------------------------------------------------------------------------


class TestParityWithPythonModules:
    """Verify YAML templates produce signals identical to their Python equivalents."""

    def test_6a_vwap_mr_adx_parity(self) -> None:
        """YAMLStrategy matches fx_vwap_reversion_adx.generate_signals on fixture."""
        from trading_research.strategies.fx_vwap_reversion_adx import (
            generate_signals as py_generate,
        )

        df = _make_6a_fixture(entry_atr_mult=1.5, stop_atr_mult=1.5, adx_max=22.0)

        # Python module signals
        py_signals = py_generate(
            df,
            entry_atr_mult=1.5,
            stop_atr_mult=1.5,
            adx_max=22.0,
            overlap_start_utc="12:00",
            overlap_end_utc="17:00",
        )

        # YAML strategy signals
        cfg = yaml.safe_load(
            (_CONFIGS_DIR / "6a-vwap-reversion-adx-yaml-v1.yaml").read_text(encoding="utf-8")
        )
        strat = YAMLStrategy.from_config(cfg)
        yaml_signals = strat.generate_signals_df(df)

        # Signals and stops must match exactly; targets may have float rounding
        np.testing.assert_array_equal(
            py_signals["signal"].to_numpy(), yaml_signals["signal"].to_numpy()
        )
        np.testing.assert_allclose(
            py_signals["stop"].to_numpy(na_value=np.nan),
            yaml_signals["stop"].to_numpy(na_value=np.nan),
            rtol=1e-9,
            equal_nan=True,
        )
        np.testing.assert_allclose(
            py_signals["target"].to_numpy(na_value=np.nan),
            yaml_signals["target"].to_numpy(na_value=np.nan),
            rtol=1e-9,
            equal_nan=True,
        )

    def test_6c_donchian_breakout_parity(self) -> None:
        """YAMLStrategy matches fx_donchian_breakout.generate_signals on fixture."""
        from trading_research.strategies.fx_donchian_breakout import (
            generate_signals as py_generate,
        )

        df = _make_6c_fixture()

        py_signals = py_generate(df, target_atr_mult=3.0, stop_atr_mult=1.5)

        cfg = yaml.safe_load(
            (_CONFIGS_DIR / "6c-donchian-breakout-yaml-v1.yaml").read_text(encoding="utf-8")
        )
        strat = YAMLStrategy.from_config(cfg)
        yaml_signals = strat.generate_signals_df(df)

        np.testing.assert_array_equal(
            py_signals["signal"].to_numpy(), yaml_signals["signal"].to_numpy()
        )
        np.testing.assert_allclose(
            py_signals["stop"].to_numpy(na_value=np.nan),
            yaml_signals["stop"].to_numpy(na_value=np.nan),
            rtol=1e-9,
            equal_nan=True,
        )
        np.testing.assert_allclose(
            py_signals["target"].to_numpy(na_value=np.nan),
            yaml_signals["target"].to_numpy(na_value=np.nan),
            rtol=1e-9,
            equal_nan=True,
        )


# ---------------------------------------------------------------------------
# ZN YAML template: entry-condition correctness
# ---------------------------------------------------------------------------


class TestZNVWAPReversionYAML:
    """Verify zn-vwap-reversion-yaml-v1 entry conditions fire correctly."""

    def _make_zn_fixture(self, n: int = 12) -> pd.DataFrame:
        """Synthetic ZN fixture with vwap_session_std_2_0 and daily_macd_hist."""
        # RTH window: 13:20-20:00 UTC; use 14:00 UTC for in-window bars
        idx = pd.date_range("2024-01-02 14:00", periods=n, freq="5min", tz="UTC")
        vwap = np.full(n, 110.0)
        std_2sigma = np.full(n, 0.20)   # 2-sigma band width
        atr = np.full(n, 0.10)
        daily_macd_hist = np.full(n, 0.01)  # bullish by default
        close = vwap.copy()

        # Row 2: long signal — below lower band AND bullish MACD
        close[2] = vwap[2] - std_2sigma[2] - 0.05

        # Row 5: short signal — above upper band AND bearish MACD
        close[5] = vwap[5] + std_2sigma[5] + 0.05
        daily_macd_hist[5] = -0.01

        # Row 8: below band but bearish MACD → no long signal
        close[8] = vwap[8] - std_2sigma[8] - 0.05
        daily_macd_hist[8] = -0.01

        return pd.DataFrame(
            {
                "close": close,
                "vwap_session": vwap,
                "vwap_session_std_2_0": std_2sigma,
                "daily_macd_hist": daily_macd_hist,
                "atr_14": atr,
            },
            index=idx,
        )

    def test_long_signal_fires(self) -> None:
        df = self._make_zn_fixture()
        cfg = yaml.safe_load(
            (_CONFIGS_DIR / "zn-vwap-reversion-yaml-v1.yaml").read_text(encoding="utf-8")
        )
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        assert result.iloc[2]["signal"] == 1, "row 2 should be long"

    def test_short_signal_fires(self) -> None:
        df = self._make_zn_fixture()
        cfg = yaml.safe_load(
            (_CONFIGS_DIR / "zn-vwap-reversion-yaml-v1.yaml").read_text(encoding="utf-8")
        )
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        assert result.iloc[5]["signal"] == -1, "row 5 should be short"

    def test_macd_filter_suppresses_entry(self) -> None:
        """Row 8: below band but bearish MACD → no long."""
        df = self._make_zn_fixture()
        cfg = yaml.safe_load(
            (_CONFIGS_DIR / "zn-vwap-reversion-yaml-v1.yaml").read_text(encoding="utf-8")
        )
        strat = YAMLStrategy.from_config(cfg)
        result = strat.generate_signals_df(df)
        assert result.iloc[8]["signal"] == 0, "bearish MACD should block long"


# ---------------------------------------------------------------------------
# YAML config file load and structural validation
# ---------------------------------------------------------------------------


class TestYAMLConfigFiles:
    """Ensure all three YAML template configs are well-formed."""

    @pytest.mark.parametrize(
        "config_file",
        [
            "6a-vwap-reversion-adx-yaml-v1.yaml",
            "6c-donchian-breakout-yaml-v1.yaml",
            "zn-vwap-reversion-yaml-v1.yaml",
        ],
    )
    def test_config_loads_as_yaml_strategy(self, config_file: str) -> None:
        path = _CONFIGS_DIR / config_file
        assert path.is_file(), f"Config file missing: {path}"
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        strat = YAMLStrategy.from_config(cfg)
        assert strat.name == cfg["strategy_id"]
        assert strat.template_name == "yaml-template"
        assert isinstance(strat.knobs, dict)

    @pytest.mark.parametrize(
        "config_file",
        [
            "6a-vwap-reversion-adx-yaml-v1.yaml",
            "6c-donchian-breakout-yaml-v1.yaml",
            "zn-vwap-reversion-yaml-v1.yaml",
        ],
    )
    def test_config_has_required_fields(self, config_file: str) -> None:
        path = _CONFIGS_DIR / config_file
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "strategy_id" in cfg
        assert "symbol" in cfg
        assert "timeframe" in cfg
        assert "entry" in cfg
        assert "exits" in cfg
        assert "backtest" in cfg


# ---------------------------------------------------------------------------
# Dispatch detection helpers (walkforward + backtest)
# ---------------------------------------------------------------------------


class TestDispatchDetection:
    """Verify the dispatch key logic used in CLI and walkforward."""

    def test_entry_key_triggers_yaml_strategy(self) -> None:
        cfg = {
            "strategy_id": "test",
            "entry": {"long": {"all": ["close > 0.0"]}},
            "exits": {"stop": {"long": "0.0"}, "target": {"long": "1.0"}},
        }
        strat = YAMLStrategy.from_config(cfg)
        assert strat.template_name == "yaml-template"

    def test_signal_module_key_not_accepted_by_load_yaml(self) -> None:
        cfg = {
            "strategy_id": "test",
            "signal_module": "some.module",
            "entry": {"long": {"all": ["close > 0.0"]}},
        }
        with pytest.raises(ValueError):
            load_yaml_strategy(cfg)

    def test_template_key_not_accepted_by_load_yaml(self) -> None:
        cfg = {
            "strategy_id": "test",
            "template": "some-template",
            "entry": {"long": {"all": ["close > 0.0"]}},
        }
        with pytest.raises(ValueError):
            load_yaml_strategy(cfg)


# ---------------------------------------------------------------------------
# Strategy Protocol compliance
# ---------------------------------------------------------------------------


class TestStrategyProtocolCompliance:
    """YAMLStrategy satisfies the Strategy Protocol duck-type requirements."""

    def _make_strat(self) -> YAMLStrategy:
        return YAMLStrategy.from_config(
            {
                "strategy_id": "proto-test",
                "knobs": {"k": 1.0},
                "entry": {"long": {"all": ["close > 0.0"]}},
                "exits": {"stop": {"long": "0.0"}, "target": {"long": "1.0"}},
            }
        )

    def test_has_name_property(self) -> None:
        assert isinstance(self._make_strat().name, str)

    def test_has_template_name_property(self) -> None:
        assert isinstance(self._make_strat().template_name, str)

    def test_has_knobs_property(self) -> None:
        assert isinstance(self._make_strat().knobs, dict)

    def test_size_position_returns_int(self) -> None:
        from decimal import Decimal

        from trading_research.core.strategies import PortfolioContext, Signal

        strat = self._make_strat()
        sig = Signal(
            timestamp=pd.Timestamp("2024-01-02 12:00", tz="UTC").to_pydatetime(),
            direction="long",
            strength=1.0,
        )
        ctx = PortfolioContext(open_positions=[], account_equity=Decimal("10000"), daily_pnl=Decimal("0"))
        qty = strat.size_position(sig, ctx, None)  # type: ignore[arg-type]
        assert isinstance(qty, int)
        assert qty >= 0

    def test_exit_rules_returns_hold(self) -> None:
        from trading_research.core.strategies import ExitDecision

        strat = self._make_strat()
        decision = strat.exit_rules(None, None, None)  # type: ignore[arg-type]
        assert isinstance(decision, ExitDecision)
        assert decision.action == "hold"

    def test_is_runtime_checkable_strategy(self) -> None:
        from trading_research.core.strategies import Strategy

        strat = self._make_strat()
        assert isinstance(strat, Strategy)
