"""Unit tests for the ZN VWAP session mean-reversion strategy (v2).

All tests use synthetic DataFrames — no real parquets are read.
Tests verify both entry and exit signal logic, RTH filtering, blackout
suppression, and look-ahead constraints (band values use only session data
available at bar T, so we verify index alignment only — the look-ahead
guarantee lives in vwap.py and features.py).
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from trading_research.strategies.zn_vwap_reversion import generate_signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rth_index(n: int, start: str = "2024-01-10 14:00:00") -> pd.DatetimeIndex:
    """RTH timestamps (14:00 UTC = 09:00 ET, well within 13:20–20:00 UTC)."""
    return pd.date_range(start, periods=n, freq="5min", tz="UTC")


def _globex_index(n: int) -> pd.DatetimeIndex:
    """Globex timestamps (02:00 UTC = 21:00 ET previous day — outside RTH)."""
    return pd.date_range("2024-01-10 02:00:00", periods=n, freq="5min", tz="UTC")


def _make_df(
    n: int,
    *,
    close: float | list,
    vwap: float | list,
    vwap_std_2: float | list,
    daily_hist: float | list,
    atr: float = 0.25,
    index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    idx = index if index is not None else _rth_index(n)

    def _expand(v):
        return v if isinstance(v, list) else [v] * n

    return pd.DataFrame(
        {
            "close":                 _expand(close),
            "vwap_session":          _expand(vwap),
            "vwap_session_std_2_0":  _expand(vwap_std_2),
            "daily_macd_hist":       _expand(daily_hist),
            "atr_14":                _expand(atr),
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# Long entry
# ---------------------------------------------------------------------------

class TestLongEntry:
    def test_fires_below_lower_band_with_bullish_daily(self):
        # close=109.0, vwap=110.0, std_2=0.75 → lower band=109.25 → close < band
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 1
        assert np.isfinite(out["stop"].iloc[0])

    def test_stop_is_close_minus_2atr(self):
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05, atr=0.20)
        out = generate_signals(df, atr_stop_mult=2.0)
        expected_stop = 109.0 - 2.0 * 0.20
        assert out["stop"].iloc[0] == pytest.approx(expected_stop)

    def test_does_not_fire_above_lower_band(self):
        # close=109.5 > lower_band=109.25 → no entry
        df = _make_df(1, close=109.5, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 0

    def test_does_not_fire_with_bearish_daily(self):
        # close below band but daily MACD bearish → no long entry (stop must be NaN)
        # Note: a short-exit signal (signal=+1, NaN stop) may still fire if close<=vwap.
        # The entry guard is the stop: NaN stop = no position opened.
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=-0.05)
        out = generate_signals(df)
        assert not np.isfinite(out["stop"].iloc[0])

    def test_does_not_fire_with_neutral_daily(self):
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.0)
        out = generate_signals(df)
        assert not np.isfinite(out["stop"].iloc[0])


# ---------------------------------------------------------------------------
# Short entry
# ---------------------------------------------------------------------------

class TestShortEntry:
    def test_fires_above_upper_band_with_bearish_daily(self):
        # close=111.0, vwap=110.0, std_2=0.75 → upper band=110.75 → close > band
        df = _make_df(1, close=111.0, vwap=110.0, vwap_std_2=0.75, daily_hist=-0.05)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == -1
        assert np.isfinite(out["stop"].iloc[0])

    def test_stop_is_close_plus_2atr(self):
        df = _make_df(1, close=111.0, vwap=110.0, vwap_std_2=0.75, daily_hist=-0.05, atr=0.20)
        out = generate_signals(df, atr_stop_mult=2.0)
        expected_stop = 111.0 + 2.0 * 0.20
        assert out["stop"].iloc[0] == pytest.approx(expected_stop)

    def test_does_not_fire_below_upper_band(self):
        df = _make_df(1, close=110.5, vwap=110.0, vwap_std_2=0.75, daily_hist=-0.05)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 0

    def test_does_not_fire_with_bullish_daily(self):
        # No short entry when daily is bullish — stop must be NaN.
        # A long-exit signal (signal=-1, NaN stop) may fire if close>=vwap.
        df = _make_df(1, close=111.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert not np.isfinite(out["stop"].iloc[0])


# ---------------------------------------------------------------------------
# RTH filter
# ---------------------------------------------------------------------------

class TestRTHFilter:
    def test_globex_bar_suppressed(self):
        # 02:00 UTC is deep Globex — no entry allowed
        df = _make_df(
            1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05,
            index=_globex_index(1),
        )
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 0
        assert not np.isfinite(out["stop"].iloc[0])

    def test_rth_boundary_start_fires(self):
        # 13:20 UTC = exactly 08:20 ET — first valid RTH bar
        idx = pd.DatetimeIndex(["2024-01-10 13:20:00+00:00"])
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05, index=idx)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 1

    def test_rth_boundary_end_suppressed(self):
        # 20:00 UTC = 15:00 ET — not in [13:20, 20:00) — suppressed
        idx = pd.DatetimeIndex(["2024-01-10 20:00:00+00:00"])
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05, index=idx)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 0

    def test_mixed_rth_and_globex(self):
        rth_idx = pd.DatetimeIndex(["2024-01-10 14:00:00+00:00"])
        glob_idx = pd.DatetimeIndex(["2024-01-10 02:00:00+00:00"])
        idx = rth_idx.append(glob_idx).sort_values()
        close = [109.0, 109.0]
        df = _make_df(2, close=close, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05, index=idx)
        out = generate_signals(df)
        # RTH bar fires, Globex bar does not
        rth_row = out.loc["2024-01-10 14:00:00+00:00"]
        glob_row = out.loc["2024-01-10 02:00:00+00:00"]
        assert rth_row["signal"] == 1
        assert glob_row["signal"] == 0


# ---------------------------------------------------------------------------
# VWAP-crossing exit signals
# ---------------------------------------------------------------------------

class TestVWAPExit:
    def test_long_exit_when_price_reaches_vwap(self):
        # Bar 0: entry (close below band). Bar 1: close >= vwap → exit.
        idx = _rth_index(2)
        df = pd.DataFrame(
            {
                "close":                [109.0, 110.0],
                "vwap_session":         [110.0, 110.0],
                "vwap_session_std_2_0": [0.75,  0.75],
                "daily_macd_hist":      [0.05,  0.05],
                "atr_14":               [0.25,  0.25],
            },
            index=idx,
        )
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 1         # entry
        assert out["signal"].iloc[1] == -1        # exit
        assert not np.isfinite(out["stop"].iloc[1])  # exit has NaN stop

    def test_short_exit_when_price_reaches_vwap(self):
        idx = _rth_index(2)
        df = pd.DataFrame(
            {
                "close":                [111.0, 110.0],
                "vwap_session":         [110.0, 110.0],
                "vwap_session_std_2_0": [0.75,  0.75],
                "daily_macd_hist":      [-0.05, -0.05],
                "atr_14":               [0.25,  0.25],
            },
            index=idx,
        )
        out = generate_signals(df)
        assert out["signal"].iloc[0] == -1        # entry
        assert out["signal"].iloc[1] == 1         # exit
        assert not np.isfinite(out["stop"].iloc[1])

    def test_exit_has_nan_stop(self):
        """NaN stop on exit bars prevents the engine from opening a new position."""
        df = _make_df(1, close=110.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        # close == vwap → long exit bar only (not an entry since close is not < lower band)
        assert out["signal"].iloc[0] == -1
        assert not np.isfinite(out["stop"].iloc[0])


# ---------------------------------------------------------------------------
# Entry/exit mutual exclusivity
# ---------------------------------------------------------------------------

class TestMutualExclusivity:
    def test_long_entry_cannot_also_be_long_exit(self):
        # Entry requires close < vwap - std (< vwap). Exit requires close >= vwap.
        # These are structurally impossible on the same bar.
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 1   # entry, not exit

    def test_no_conflict_when_both_daily_conditions_false(self):
        df = _make_df(1, close=110.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.0)
        out = generate_signals(df)
        assert out["signal"].iloc[0] == 0


# ---------------------------------------------------------------------------
# Blackout filter
# ---------------------------------------------------------------------------

class TestBlackout:
    def _run_with_blackout(self, df: pd.DataFrame) -> pd.DataFrame:
        blackout_date = df.index[0].tz_convert("America/New_York").date()
        # load_blackout_dates is a late import inside generate_signals; patch at source.
        with patch(
            "trading_research.strategies.event_blackout.load_blackout_dates",
            return_value={blackout_date},
        ):
            return generate_signals(df, blackout_calendars=["fomc"])

    def test_entry_suppressed_on_blackout_date(self):
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = self._run_with_blackout(df)
        assert out["signal"].iloc[0] == 0
        assert not np.isfinite(out["stop"].iloc[0])

    def test_exit_preserved_on_blackout_date(self):
        # Bar where close >= vwap → exit signal (NaN stop). Blackout must not zero it.
        df = _make_df(1, close=110.5, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = self._run_with_blackout(df)
        # stop is NaN (exit bar) → blackout predicate `np.isfinite(stop_arr)` is False
        # → blackout does NOT touch exit signals
        assert out["signal"].iloc[0] == -1   # exit preserved
        assert not np.isfinite(out["stop"].iloc[0])

    def test_no_blackout_calendars_leaves_entry_intact(self):
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df, blackout_calendars=None)
        assert out["signal"].iloc[0] == 1


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class TestOutputSchema:
    def test_output_columns(self):
        df = _make_df(3, close=110.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert set(out.columns) == {"signal", "stop", "target"}

    def test_output_index_matches_input(self):
        df = _make_df(5, close=110.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert out.index.equals(df.index)

    def test_signal_dtype_is_int8(self):
        df = _make_df(3, close=110.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert out["signal"].dtype == np.int8

    def test_target_always_nan(self):
        # Exit is VWAP crossing; there is no fixed price target.
        df = _make_df(5, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        out = generate_signals(df)
        assert out["target"].isna().all()

    def test_missing_column_raises_key_error(self):
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        df = df.drop(columns=["atr_14"])
        with pytest.raises(KeyError, match="atr_14"):
            generate_signals(df)

    def test_invalid_sigma_raises_value_error(self):
        df = _make_df(1, close=109.0, vwap=110.0, vwap_std_2=0.75, daily_hist=0.05)
        df = df.rename(columns={"vwap_session_std_2_0": "vwap_session_std_2_5"})
        with pytest.raises(ValueError, match="vwap_band_sigma"):
            generate_signals(df, vwap_band_sigma=2.5)
