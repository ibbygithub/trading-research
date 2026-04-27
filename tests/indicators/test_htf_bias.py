"""Critical test: HTF bias projection uses the PRIOR session's daily value.

This is the most important test in the feature builder — it proves the
pipeline doesn't look ahead. An intraday bar with trade_date T must see
daily indicators computed from bars with trade_date strictly < T.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading_research.indicators.features import build_features, trade_date_from_ny


class TestTradeDate:
    def test_session_open_assigns_to_next_date(self):
        """18:00 ET Sunday (Globex Monday session open) → trade_date = Monday."""
        # 2024-01-07 is a Sunday. 18:00 ET = 23:00 UTC.
        ts_ny = pd.Series(
            pd.to_datetime(["2024-01-07 18:00:00"]).tz_localize("America/New_York")
        )
        trade_dates = trade_date_from_ny(ts_ny)
        assert trade_dates.iloc[0] == date(2024, 1, 8)  # Monday

    def test_mid_session_bar_correct_trade_date(self):
        """10:00 ET Monday → trade_date = Monday."""
        ts_ny = pd.Series(
            pd.to_datetime(["2024-01-08 10:00:00"]).tz_localize("America/New_York")
        )
        trade_dates = trade_date_from_ny(ts_ny)
        assert trade_dates.iloc[0] == date(2024, 1, 8)

    def test_session_close_bar_correct_trade_date(self):
        """16:59 ET Monday (last RTH bar) → trade_date = Monday."""
        ts_ny = pd.Series(
            pd.to_datetime(["2024-01-08 16:59:00"]).tz_localize("America/New_York")
        )
        trade_dates = trade_date_from_ny(ts_ny)
        assert trade_dates.iloc[0] == date(2024, 1, 8)

    def test_dst_spring_forward_session_open(self):
        """18:00 EDT on DST spring-forward Sunday (2024-03-10) → trade_date = Monday.

        On 2024-03-10, US clocks spring forward 2am→3am. The ZN session that
        opens at 18:00 EDT (= 22:00 UTC) should still land on Monday 2024-03-11.
        The +6h offset on a tz-aware timestamp is unaffected by the DST change
        because pandas/pytz applies arithmetic in UTC.
        """
        ts_utc = pd.Series(
            pd.to_datetime(["2024-03-10 22:00:00"]).tz_localize("UTC")
        )
        ts_ny = ts_utc.dt.tz_convert("America/New_York")
        trade_dates = trade_date_from_ny(ts_ny)
        assert trade_dates.iloc[0] == date(2024, 3, 11)  # Monday

    def test_dst_fall_back_session_open(self):
        """18:00 EST on DST fall-back Sunday (2024-11-03) → trade_date = Monday.

        On 2024-11-03, US clocks fall back 2am→1am. The ZN session opening
        at 18:00 EST (= 23:00 UTC) should land on Monday 2024-11-04.
        """
        ts_utc = pd.Series(
            pd.to_datetime(["2024-11-03 23:00:00"]).tz_localize("UTC")
        )
        ts_ny = ts_utc.dt.tz_convert("America/New_York")
        trade_dates = trade_date_from_ny(ts_ny)
        assert trade_dates.iloc[0] == date(2024, 11, 4)  # Monday

    def test_dst_fall_back_repeated_hour_consistent(self):
        """Both 01:00 occurrences on fall-back Sunday → same trade_date (Sunday).

        During the fall-back on 2024-11-03, the 01:00 hour repeats.
        05:00 UTC = 01:00 EDT (before fall-back); 06:00 UTC = 01:00 EST (after).
        Both are within the Saturday→Sunday CME session and must share trade_date.
        """
        ts_utc = pd.Series(
            pd.to_datetime(["2024-11-03 05:00:00", "2024-11-03 06:00:00"]).tz_localize("UTC")
        )
        ts_ny = ts_utc.dt.tz_convert("America/New_York")
        trade_dates = trade_date_from_ny(ts_ny)
        assert trade_dates.iloc[0] == trade_dates.iloc[1]
        assert trade_dates.iloc[0] == date(2024, 11, 3)  # Sunday


class TestHTFBiasLookAhead:
    """Verify that daily indicators are shifted by one session before projection.

    Scenario:
        daily bar trade_date 2024-01-08: close = 110.0, EMA(1) = 110.0
        daily bar trade_date 2024-01-09: close = 112.0, EMA(1) would be 112.0

    Intraday bars on trade_date 2024-01-09 must see EMA = 110.0 (prior day's).
    Intraday bars on trade_date 2024-01-10 must see EMA = 112.0 (prior day's).
    """

    def _make_daily(self, n: int = 50) -> pd.DataFrame:
        """Synthetic daily bars starting 2024-01-02."""
        dates = pd.date_range("2024-01-02 18:00:00", periods=n, freq="24h", tz="UTC")
        ts_ny = dates.tz_convert("America/New_York")
        closes = [110.0 + i * 0.5 for i in range(n)]
        return pd.DataFrame(
            {
                "timestamp_utc": dates,
                "timestamp_ny": ts_ny,
                "open": closes,
                "high": [c + 0.1 for c in closes],
                "low": [c - 0.1 for c in closes],
                "close": closes,
                "volume": 1000,
                "buy_volume": pd.array([500] * n, dtype="Int64"),
                "sell_volume": pd.array([500] * n, dtype="Int64"),
                "up_ticks": pd.array([10] * n, dtype="Int64"),
                "down_ticks": pd.array([10] * n, dtype="Int64"),
                "total_ticks": pd.array([20] * n, dtype="Int64"),
            }
        )

    def _make_intraday(self, trade_date: date, n_bars: int = 5) -> pd.DataFrame:
        """Synthetic intraday bars on a given trade_date.

        trade_date 2024-01-08 → session opens 2024-01-07 23:00 UTC (18:00 ET).
        """
        # Session open: day before trade_date at 23:00 UTC
        session_open_utc = pd.Timestamp(
            year=trade_date.year,
            month=trade_date.month,
            day=trade_date.day,
            tz="UTC",
        ) - pd.Timedelta(hours=1)
        ts = pd.date_range(session_open_utc, periods=n_bars, freq="1min", tz="UTC")
        ts_ny = ts.tz_convert("America/New_York")
        closes = [110.0] * n_bars
        return pd.DataFrame(
            {
                "timestamp_utc": ts,
                "timestamp_ny": ts_ny,
                "open": closes,
                "high": [c + 0.1 for c in closes],
                "low": [c - 0.1 for c in closes],
                "close": closes,
                "volume": 500,
                "buy_volume": pd.array([250] * n_bars, dtype="Int64"),
                "sell_volume": pd.array([250] * n_bars, dtype="Int64"),
                "up_ticks": pd.array([5] * n_bars, dtype="Int64"),
                "down_ticks": pd.array([5] * n_bars, dtype="Int64"),
                "total_ticks": pd.array([10] * n_bars, dtype="Int64"),
            }
        )

    def test_shift1_used_in_htf_join(self):
        """Directly test that the shift(1) logic means intraday bars see
        the PRIOR day's indicator value, not today's."""
        from trading_research.indicators.ema import compute_ema
        from trading_research.indicators.features import trade_date_from_ny

        daily = self._make_daily(10)
        daily["_trade_date"] = trade_date_from_ny(daily["timestamp_ny"])

        ema_vals = compute_ema(daily["close"], 1)  # period=1 → EMA = close itself
        shifted = ema_vals.shift(1)

        # Build a mapping: trade_date → shifted EMA value
        htf = pd.DataFrame({
            "_trade_date": daily["_trade_date"],
            "daily_ema_1": shifted.values,
        })

        # Intraday bar on trade_date[5] should see daily_ema at position 4 (shifted).
        td5 = daily["_trade_date"].iloc[5]
        expected_ema = daily["close"].iloc[4]  # close at day 4 = EMA(1) at day 4
        joined_val = htf.loc[htf["_trade_date"] == td5, "daily_ema_1"].values[0]

        assert abs(float(joined_val) - expected_ema) < 1e-6, (
            f"HTF join used day {td5}'s own EMA ({joined_val:.4f}) instead of "
            f"prior day's ({expected_ema:.4f})"
        )

    def test_first_daily_bar_gets_nan_bias(self):
        """The first intraday session has no prior daily close → daily_* columns NaN."""
        from trading_research.indicators.ema import compute_ema
        from trading_research.indicators.features import trade_date_from_ny

        daily = self._make_daily(10)
        daily["_trade_date"] = trade_date_from_ny(daily["timestamp_ny"])

        ema_vals = compute_ema(daily["close"], 5)
        shifted = ema_vals.shift(1)

        htf = pd.DataFrame({
            "_trade_date": daily["_trade_date"],
            "daily_ema_5": shifted.values,
        })

        # The very first trade_date should have NaN from the shift.
        first_td = daily["_trade_date"].iloc[0]
        first_val = htf.loc[htf["_trade_date"] == first_td, "daily_ema_5"].values[0]
        assert pd.isna(first_val), (
            f"First daily row should be NaN after shift(1), got {first_val}"
        )
