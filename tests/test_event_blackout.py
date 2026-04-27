"""Tests for the event_blackout module.

Uses temporary YAML files (via tmp_path) so tests have no dependency on the
real calendar files and remain fast regardless of calendar updates.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from trading_research.strategies.event_blackout import (
    is_blackout,
    load_blackout_dates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def calendar_dir(tmp_path: Path) -> Path:
    """Write minimal YAML calendars to a temp directory."""
    fomc = {"fomc_dates": ["2023-02-01", "2023-03-22", "2023-05-03"]}
    cpi = {"cpi_dates": ["2023-02-14", "2023-03-14"]}
    nfp = {"nfp_dates": ["2023-02-03", "2023-03-10"]}

    (tmp_path / "fomc_dates.yaml").write_text(yaml.dump(fomc))
    (tmp_path / "cpi_dates.yaml").write_text(yaml.dump(cpi))
    (tmp_path / "nfp_dates.yaml").write_text(yaml.dump(nfp))
    return tmp_path


# ---------------------------------------------------------------------------
# load_blackout_dates
# ---------------------------------------------------------------------------


class TestLoadBlackoutDates:
    def test_fomc_only(self, calendar_dir: Path) -> None:
        result = load_blackout_dates(["fomc"], calendar_dir=calendar_dir)
        assert date(2023, 2, 1) in result
        assert date(2023, 3, 22) in result
        assert date(2023, 5, 3) in result
        # CPI date should NOT be present
        assert date(2023, 2, 14) not in result

    def test_cpi_only(self, calendar_dir: Path) -> None:
        result = load_blackout_dates(["cpi"], calendar_dir=calendar_dir)
        assert date(2023, 2, 14) in result
        assert date(2023, 3, 14) in result
        assert date(2023, 2, 1) not in result  # FOMC date, not in this set

    def test_nfp_only(self, calendar_dir: Path) -> None:
        result = load_blackout_dates(["nfp"], calendar_dir=calendar_dir)
        assert date(2023, 2, 3) in result
        assert date(2023, 3, 10) in result

    def test_all_three_combined(self, calendar_dir: Path) -> None:
        result = load_blackout_dates(["fomc", "cpi", "nfp"], calendar_dir=calendar_dir)
        # FOMC
        assert date(2023, 2, 1) in result
        # CPI
        assert date(2023, 2, 14) in result
        # NFP
        assert date(2023, 2, 3) in result
        # Total unique dates across all three calendars
        assert len(result) == 7  # 3 FOMC + 2 CPI + 2 NFP, all distinct

    def test_empty_calendars_returns_empty_set(self, calendar_dir: Path) -> None:
        result = load_blackout_dates([], calendar_dir=calendar_dir)
        assert result == frozenset()

    def test_unknown_calendar_raises(self, calendar_dir: Path) -> None:
        with pytest.raises(ValueError, match="Unknown calendar"):
            load_blackout_dates(["unknown"], calendar_dir=calendar_dir)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        # tmp_path has no YAML files in it
        with pytest.raises((FileNotFoundError, OSError)):
            load_blackout_dates(["fomc"], calendar_dir=tmp_path)

    def test_returns_frozenset(self, calendar_dir: Path) -> None:
        result = load_blackout_dates(["fomc"], calendar_dir=calendar_dir)
        assert isinstance(result, frozenset)

    def test_dates_are_date_objects(self, calendar_dir: Path) -> None:
        result = load_blackout_dates(["fomc"], calendar_dir=calendar_dir)
        for d in result:
            assert isinstance(d, date)

    def test_duplicate_dates_across_calendars_are_deduplicated(
        self, tmp_path: Path
    ) -> None:
        """If FOMC and CPI happen to fall on the same day, count it once."""
        shared_date = "2023-03-22"
        (tmp_path / "fomc_dates.yaml").write_text(
            yaml.dump({"fomc_dates": [shared_date]})
        )
        (tmp_path / "cpi_dates.yaml").write_text(
            yaml.dump({"cpi_dates": [shared_date]})
        )
        (tmp_path / "nfp_dates.yaml").write_text(yaml.dump({"nfp_dates": []}))

        result = load_blackout_dates(["fomc", "cpi"], calendar_dir=tmp_path)
        assert len(result) == 1

    def test_real_fomc_calendar_loads(self) -> None:
        """Smoke test: real configs/calendars/fomc_dates.yaml parses cleanly."""
        result = load_blackout_dates(["fomc"])
        # FOMC 2020-03-03 was an emergency inter-meeting cut
        assert date(2020, 3, 3) in result
        # Jan 2025 meeting
        assert date(2025, 1, 29) in result
        assert len(result) >= 120  # ~8 meetings/year × 15+ years

    def test_real_cpi_calendar_loads(self) -> None:
        result = load_blackout_dates(["cpi"])
        assert date(2023, 6, 13) in result
        assert len(result) >= 190  # 12 per year × 16 years

    def test_real_nfp_calendar_loads(self) -> None:
        result = load_blackout_dates(["nfp"])
        assert date(2023, 6, 2) in result
        assert len(result) >= 190


# ---------------------------------------------------------------------------
# is_blackout
# ---------------------------------------------------------------------------


class TestIsBlackout:
    def test_date_in_set_returns_true(self) -> None:
        blackout_set = frozenset([date(2023, 2, 1), date(2023, 3, 22)])
        assert is_blackout(date(2023, 2, 1), blackout_set) is True

    def test_date_not_in_set_returns_false(self) -> None:
        blackout_set = frozenset([date(2023, 2, 1)])
        assert is_blackout(date(2023, 2, 2), blackout_set) is False

    def test_empty_set_always_false(self) -> None:
        assert is_blackout(date(2023, 1, 1), frozenset()) is False
