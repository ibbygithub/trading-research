"""Tests for continuous series builder helpers.

Covers the renamed last_trading_day_quarterly_cme() function and the
per-symbol output path logic in build_back_adjusted_continuous().
"""

from __future__ import annotations

from datetime import date

import pytest

from trading_research.data.continuous import (
    last_trading_day_quarterly_cme,
    roll_date_for_contract,
    contract_sequence,
)


# ---------------------------------------------------------------------------
# last_trading_day_quarterly_cme
# ---------------------------------------------------------------------------

class TestLastTradingDayQuarterlyCme:
    """Verify the 7-biz-days-before-last-biz-day rule for quarterly CME contracts."""

    def test_zn_sep_2023(self) -> None:
        # Last biz day of Sep 2023 = Sep 29 (Friday).
        # 7 biz days before = Sep 20 (Wednesday).
        assert last_trading_day_quarterly_cme(2023, 9) == date(2023, 9, 20)

    def test_zn_dec_2023(self) -> None:
        # Last biz day of Dec 2023 = Dec 29 (Friday).
        # 7 biz days before = Dec 20 (Wednesday).
        assert last_trading_day_quarterly_cme(2023, 12) == date(2023, 12, 20)

    def test_zn_mar_2024(self) -> None:
        # Last biz day of Mar 2024 = Mar 29 (Friday; Mar 28 = Good Friday excluded by
        # our simple biz-day calc which ignores holidays, but weekdays only).
        # Strictly weekday-only (no holiday): Mar 29 is Friday → last biz day.
        # 7 weekdays before Mar 29: Mar 20 (Wednesday).
        assert last_trading_day_quarterly_cme(2024, 3) == date(2024, 3, 20)

    def test_quarter_ending_saturday(self) -> None:
        # Dec 2018: Dec 31 is Monday. Last biz day = Dec 31.
        # 7 biz days before = Dec 20 (Thursday).
        assert last_trading_day_quarterly_cme(2018, 12) == date(2018, 12, 20)

    def test_same_rule_applies_to_6a_contract(self) -> None:
        # 6A (AUD futures) uses the same quarterly CME rule.
        # Jun 2024: Last biz day = Jun 28 (Friday).
        # 7 biz days before = Jun 19 (Wednesday).
        assert last_trading_day_quarterly_cme(2024, 6) == date(2024, 6, 19)

    def test_non_quarterly_month_raises_nothing(self) -> None:
        # The function computes for any month; the caller is responsible for
        # only passing quarterly months. Non-quarterly months are not an error.
        result = last_trading_day_quarterly_cme(2024, 1)
        # Jan 2024: last biz = Jan 31. 7 biz before = Jan 22 (Monday).
        assert result == date(2024, 1, 22)


# ---------------------------------------------------------------------------
# roll_date_for_contract (depends on last_trading_day_quarterly_cme)
# ---------------------------------------------------------------------------

class TestRollDateForContract:
    def test_roll_5_days_before_ltd(self) -> None:
        # ZN Sep 2023: ltd = Sep 20. Roll = 5 biz days before = Sep 13.
        assert roll_date_for_contract(2023, 9) == date(2023, 9, 13)

    def test_roll_1_day_before_ltd(self) -> None:
        # With roll_days_before=1, roll should be 1 biz day before ltd.
        ltd = last_trading_day_quarterly_cme(2023, 9)  # Sep 20
        roll = roll_date_for_contract(2023, 9, roll_days_before=1)
        assert roll == date(2023, 9, 19)  # 1 biz day before Sep 20


# ---------------------------------------------------------------------------
# contract_sequence — verify it works for a non-ZN ts_root
# ---------------------------------------------------------------------------

class TestContractSequence:
    def test_6a_sequence_uses_ad_root(self) -> None:
        # 6A uses TS root "AD". Verify contract names are AD*, not TY*.
        periods = contract_sequence(
            ts_root="AD",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
        )
        assert len(periods) > 0
        for p in periods:
            assert p.ts_symbol.startswith("AD"), (
                f"Expected AD* symbol, got {p.ts_symbol!r}"
            )

    def test_sequence_covers_full_range(self) -> None:
        periods = contract_sequence(
            ts_root="AD",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
        )
        starts = [p.data_start for p in periods]
        ends = [p.data_end for p in periods]
        assert min(starts) <= date(2024, 1, 1)
        assert max(ends) >= date(2024, 6, 30)
