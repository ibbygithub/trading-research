"""Unit tests for the ZN MACD pullback strategy signal logic.

All tests use synthetic DataFrames — no real parquets are read.
The 60m data loading is bypassed by injecting pre-computed htf columns
directly via monkeypatching.

Exit convention: zero-cross exit
---------------------------------
The strategy emits opposing signals on MACD zero-cross rather than a
price target. The engine's NaN-stop guard prevents these exit-only signals
from opening new positions. Tests verify both entry and exit signal logic.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from trading_research.strategies.zn_macd_pullback import generate_signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_index(n: int, freq: str = "5min") -> pd.DatetimeIndex:
    return pd.date_range("2024-01-10 14:00:00", periods=n, freq=freq, tz="UTC")


def _make_df(
    n: int,
    macd_hist: float | list,
    streak: int | list,
    daily_hist: float | list,
    atr: float = 0.25,
    vwap: float = 110.0,
    close: float = 110.0,
) -> pd.DataFrame:
    """Build a minimal 5m features DataFrame."""
    idx = _utc_index(n)

    def _expand(v, default):
        if isinstance(v, list):
            return v
        return [v] * n

    return pd.DataFrame(
        {
            "close":                    _expand(close, close),
            "macd_hist":                _expand(macd_hist, 0.0),
            "macd_hist_decline_streak": pd.array(_expand(streak, 0), dtype="Int64"),
            "daily_macd_hist":          _expand(daily_hist, 0.0),
            "atr_14":                   _expand(atr, atr),
            "vwap_session":             _expand(vwap, vwap),
        },
        index=idx,
    )


def _fake_60m(df: pd.DataFrame, hist_val: float, slope_val: float) -> pd.DataFrame:
    """Return a mock 60m HTF DataFrame already aligned to df's index."""
    return pd.DataFrame(
        {
            "timestamp_utc": df.index,
            "htf_60m_macd_hist": [hist_val] * len(df),
            "htf_60m_macd_hist_slope": [slope_val] * len(df),
        }
    )


def _run(df: pd.DataFrame, htf_60m_hist: float, htf_60m_slope: float, **kwargs) -> pd.DataFrame:
    """Run generate_signals with a mocked 60m loader."""
    mock_htf = _fake_60m(df, htf_60m_hist, htf_60m_slope)

    with patch(
        "trading_research.strategies.zn_macd_pullback._load_60m_macd",
        return_value=mock_htf,
    ):
        return generate_signals(df, **kwargs)


# ---------------------------------------------------------------------------
# Long entry tests
# ---------------------------------------------------------------------------

class TestLongEntry:
    def test_all_conditions_met_gives_long(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.002)
        assert (sigs["signal"] == 1).all()

    def test_daily_hist_zero_gives_flat(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.0,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 0).all()

    def test_daily_hist_negative_no_long_entry(self):
        # daily < 0 blocks long entry (c1_long fails).
        # short_exit fires (daily < 0 and macd_hist < 0) emitting signal=+1 with NaN stop.
        # Distinguish entry from exit by checking stop: entries always have finite stops.
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=-0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        # No long entry fired — all stops are NaN (only entry bars carry a finite stop).
        assert sigs["stop"].isna().all()

    def test_60m_hist_negative_gives_flat(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=-0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 0).all()

    def test_60m_declining_slope_gives_flat(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=-0.005)
        assert (sigs["signal"] == 0).all()

    def test_60m_flat_slope_gives_long(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.0)
        assert (sigs["signal"] == 1).all()

    def test_5m_hist_above_zero_emits_exit_signal(self):
        # macd_hist > 0: no long entry (c4_long fails).
        # long_exit fires because daily > 0 and macd_hist >= 0.
        df = _make_df(5, macd_hist=0.02, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == -1).all()

    def test_streak_of_two_gives_flat(self):
        # streak=-2, hist<0: neither entry nor exit fires
        # (long_exit requires hist >= 0; short_exit requires daily < 0)
        df = _make_df(5, macd_hist=-0.05, streak=-2, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 0).all()

    def test_streak_exactly_three_gives_long(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 1).all()

    def test_streak_of_four_gives_long(self):
        df = _make_df(5, macd_hist=-0.05, streak=-4, daily_hist=0.02,
                      close=110.0, vwap=111.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 1).all()


# ---------------------------------------------------------------------------
# Short entry tests
# ---------------------------------------------------------------------------

class TestShortEntry:
    def test_all_conditions_met_gives_short(self):
        df = _make_df(5, macd_hist=0.05, streak=-3, daily_hist=-0.02,
                      close=110.0, vwap=109.0)
        sigs = _run(df, htf_60m_hist=-0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == -1).all()

    def test_daily_positive_emits_exit_for_short_side(self):
        # daily > 0: no short entry (c1_short fails).
        # long_exit fires because daily > 0 and macd_hist > 0 (>= 0).
        df = _make_df(5, macd_hist=0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=109.0)
        sigs = _run(df, htf_60m_hist=-0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == -1).all()

    def test_60m_positive_gives_flat_for_short(self):
        # 60m > 0 blocks short entry (c2_short fails).
        # Neither exit fires: daily < 0 but hist > 0 so short_exit=False;
        # long_exit requires daily > 0 which is False here.
        df = _make_df(5, macd_hist=0.05, streak=-3, daily_hist=-0.02,
                      close=110.0, vwap=109.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 0).all()

    def test_60m_declining_gives_flat_for_short(self):
        df = _make_df(5, macd_hist=0.05, streak=-3, daily_hist=-0.02,
                      close=110.0, vwap=109.0)
        sigs = _run(df, htf_60m_hist=-0.01, htf_60m_slope=-0.005)
        assert (sigs["signal"] == 0).all()


# ---------------------------------------------------------------------------
# Zero-cross exit signal tests
# ---------------------------------------------------------------------------

class TestZeroCrossExit:
    def test_hist_crosses_zero_emits_long_exit(self):
        # daily > 0, 5m hist >= 0 — emit signal=-1 (close long)
        df = _make_df(5, macd_hist=0.01, streak=1, daily_hist=0.02,
                      close=110.0, vwap=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == -1).all()

    def test_hist_exactly_zero_emits_long_exit(self):
        # macd_hist=0.0 is >= 0, daily > 0 — exits the long
        df = _make_df(5, macd_hist=0.0, streak=0, daily_hist=0.02,
                      close=110.0, vwap=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == -1).all()

    def test_hist_crosses_zero_emits_short_exit(self):
        # daily < 0, 5m hist <= 0 — emit signal=+1 (close short)
        df = _make_df(5, macd_hist=-0.01, streak=-1, daily_hist=-0.02,
                      close=110.0, vwap=110.0)
        sigs = _run(df, htf_60m_hist=-0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 1).all()

    def test_no_exit_signal_when_hist_still_negative_long_context(self):
        # daily > 0, hist < 0, streak < -3 threshold not met — flat
        df = _make_df(5, macd_hist=-0.02, streak=-2, daily_hist=0.02,
                      close=110.0, vwap=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 0).all()

    def test_exit_signal_has_nan_stop(self):
        # Exit-only bar: hist>=0 in long context — stop must be NaN
        # so the engine guard does not open a phantom entry.
        df = _make_df(1, macd_hist=0.01, streak=1, daily_hist=0.02,
                      close=110.0, vwap=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert sigs.iloc[0]["signal"] == -1
        assert np.isnan(sigs.iloc[0]["stop"])

    def test_entry_overrides_exit_impossible_overlap(self):
        # valid_long requires hist < 0; long_exit requires hist >= 0.
        # They cannot fire on the same bar. Entry with hist=-0.05 should be +1.
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, vwap=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 1).all()


# ---------------------------------------------------------------------------
# Stop placement tests
# ---------------------------------------------------------------------------

class TestStopTarget:
    def test_long_stop_below_close(self):
        df = _make_df(1, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      close=110.0, atr=0.25, vwap=110.50)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001,
                    atr_stop_mult=2.0)
        assert sigs.iloc[0]["signal"] == 1
        # stop = 110.0 - 2.0 * 0.25 = 109.5
        assert abs(sigs.iloc[0]["stop"] - 109.5) < 1e-9
        # target is always NaN (zero-cross exit)
        assert np.isnan(sigs.iloc[0]["target"])

    def test_short_stop_above_close(self):
        df = _make_df(1, macd_hist=0.05, streak=-3, daily_hist=-0.02,
                      close=110.0, atr=0.25, vwap=109.50)
        sigs = _run(df, htf_60m_hist=-0.01, htf_60m_slope=0.001,
                    atr_stop_mult=2.0)
        assert sigs.iloc[0]["signal"] == -1
        # stop = 110.0 + 2.0 * 0.25 = 110.5
        assert abs(sigs.iloc[0]["stop"] - 110.5) < 1e-9
        # target is always NaN (zero-cross exit)
        assert np.isnan(sigs.iloc[0]["target"])

    def test_target_always_nan(self):
        # Regardless of conditions, target column should always be NaN.
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert sigs["target"].isna().all()


# ---------------------------------------------------------------------------
# NaN guard tests
# ---------------------------------------------------------------------------

class TestNaNGuards:
    def test_nan_atr_gives_flat(self):
        df = _make_df(1, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      atr=float("nan"), vwap=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert sigs.iloc[0]["signal"] == 0
        assert np.isnan(sigs.iloc[0]["stop"])

    def test_nan_vwap_does_not_affect_entry(self):
        # VWAP is not used in the zero-cross exit strategy.
        # A NaN VWAP should not suppress entry signals.
        df = _make_df(1, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      atr=0.25, vwap=float("nan"), close=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert sigs.iloc[0]["signal"] == 1

    def test_nan_daily_hist_gives_flat(self):
        df = _make_df(1, macd_hist=-0.05, streak=-3,
                      daily_hist=float("nan"))
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert sigs.iloc[0]["signal"] == 0

    def test_nan_60m_hist_gives_flat(self):
        df = _make_df(1, macd_hist=-0.05, streak=-3, daily_hist=0.02)
        sigs = _run(df, htf_60m_hist=float("nan"), htf_60m_slope=0.001)
        assert sigs.iloc[0]["signal"] == 0


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Event-day blackout filter tests
# ---------------------------------------------------------------------------


class TestEventBlackout:
    """Test that blackout_calendars suppresses entries on event days.

    Uses real FOMC dates from configs/calendars/fomc_dates.yaml.
    2024-01-31 is a known FOMC date; the test index starts at 14:00 UTC
    which is 9:00 AM ET — within the RTH session.

    Exit signals (NaN stop) must survive the blackout filter unchanged.
    """

    def _utc_index_on_fomc(self, n: int) -> pd.DatetimeIndex:
        # 2024-01-31 is an FOMC date; 14:00 UTC = 09:00 ET
        return pd.date_range("2024-01-31 14:00:00", periods=n, freq="5min", tz="UTC")

    def _make_fomc_df(self, n: int, macd_hist: float, streak: int,
                     daily_hist: float, atr: float = 0.25,
                     close: float = 110.0) -> pd.DataFrame:
        idx = self._utc_index_on_fomc(n)
        return pd.DataFrame(
            {
                "close":                    [close] * n,
                "macd_hist":                [macd_hist] * n,
                "macd_hist_decline_streak": pd.array([streak] * n, dtype="Int64"),
                "daily_macd_hist":          [daily_hist] * n,
                "atr_14":                   [atr] * n,
                "vwap_session":             [110.0] * n,
            },
            index=idx,
        )

    def _run_with_blackout(self, df: pd.DataFrame, htf_hist: float,
                           htf_slope: float, **kwargs) -> pd.DataFrame:
        mock_htf = _fake_60m(df, htf_hist, htf_slope)
        with patch(
            "trading_research.strategies.zn_macd_pullback._load_60m_macd",
            return_value=mock_htf,
        ):
            return generate_signals(df, **kwargs)

    def test_fomc_day_suppresses_long_entry(self) -> None:
        df = self._make_fomc_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02)
        sigs = self._run_with_blackout(
            df, htf_hist=0.01, htf_slope=0.001,
            blackout_calendars=["fomc"],
        )
        # All bars are on an FOMC day — entries must be suppressed
        assert (sigs["signal"] == 0).all()
        assert sigs["stop"].isna().all()

    def test_fomc_day_suppresses_short_entry(self) -> None:
        df = self._make_fomc_df(5, macd_hist=0.05, streak=-3, daily_hist=-0.02)
        sigs = self._run_with_blackout(
            df, htf_hist=-0.01, htf_slope=0.001,
            blackout_calendars=["fomc"],
        )
        assert (sigs["signal"] == 0).all()
        assert sigs["stop"].isna().all()

    def test_fomc_day_preserves_exit_signal(self) -> None:
        # long exit: daily > 0, macd_hist >= 0 — stop is NaN (exit-only bar)
        # Blackout must NOT suppress exit signals so open positions can close.
        df = self._make_fomc_df(5, macd_hist=0.02, streak=1, daily_hist=0.02)
        sigs = self._run_with_blackout(
            df, htf_hist=0.01, htf_slope=0.001,
            blackout_calendars=["fomc"],
        )
        # Exit signal (signal=-1, stop=NaN) must survive
        assert (sigs["signal"] == -1).all()
        assert sigs["stop"].isna().all()

    def test_no_blackout_gives_normal_signal(self) -> None:
        # Same FOMC day data but blackout_calendars=None — should fire normally
        df = self._make_fomc_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02)
        sigs = self._run_with_blackout(
            df, htf_hist=0.01, htf_slope=0.001,
            blackout_calendars=None,
        )
        assert (sigs["signal"] == 1).all()
        assert sigs["stop"].notna().all()

    def test_non_event_day_not_affected_by_blackout(self) -> None:
        # 2024-01-10 is not an FOMC, CPI, or NFP date
        idx = pd.date_range("2024-01-10 14:00:00", periods=5, freq="5min", tz="UTC")
        df = pd.DataFrame(
            {
                "close":                    [110.0] * 5,
                "macd_hist":                [-0.05] * 5,
                "macd_hist_decline_streak": pd.array([-3] * 5, dtype="Int64"),
                "daily_macd_hist":          [0.02] * 5,
                "atr_14":                   [0.25] * 5,
                "vwap_session":             [110.0] * 5,
            },
            index=idx,
        )
        mock_htf = _fake_60m(df, 0.01, 0.001)
        with patch(
            "trading_research.strategies.zn_macd_pullback._load_60m_macd",
            return_value=mock_htf,
        ):
            sigs = generate_signals(
                df,
                blackout_calendars=["fomc", "cpi", "nfp"],
            )
        # Entry should fire normally — 2024-01-10 is not an event day
        assert (sigs["signal"] == 1).all()
        assert sigs["stop"].notna().all()


class TestOutputSchema:
    def test_returns_correct_columns(self):
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert list(sigs.columns) == ["signal", "stop", "target"]

    def test_index_matches_input(self):
        df = _make_df(10, macd_hist=-0.05, streak=-3, daily_hist=0.02)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert sigs.index.equals(df.index)

    def test_flat_bars_have_nan_stop_target(self):
        # Streak of -2 → no entry signal, no exit signal → stop/target NaN
        df = _make_df(5, macd_hist=-0.05, streak=-2, daily_hist=0.02)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 0).all()
        assert sigs["stop"].isna().all()
        assert sigs["target"].isna().all()

    def test_entry_bars_have_finite_stop_nan_target(self):
        # Entry bars: stop is finite, target is NaN
        df = _make_df(5, macd_hist=-0.05, streak=-3, daily_hist=0.02,
                      atr=0.25, close=110.0)
        sigs = _run(df, htf_60m_hist=0.01, htf_60m_slope=0.001)
        assert (sigs["signal"] == 1).all()
        assert sigs["stop"].notna().all()
        assert sigs["target"].isna().all()
