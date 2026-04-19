"""Event-day blackout filter for strategy entry gating.

A blackout date is any date on which a high-impact economic release occurs:
FOMC policy statement, CPI, or NFP. On these days the microstructure of
ZN (and most bond/FX instruments) is structurally different — wider spreads,
fat-tail moves, and price action that is explicitly non-mean-reverting.

This module is calendar-only. It has no market data dependency and can be
tested in isolation with synthetic YAML files.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

import yaml

_CALENDAR_DIR = Path(__file__).resolve().parents[3] / "configs" / "calendars"

_CALENDAR_FILES: dict[str, tuple[str, str]] = {
    "fomc": ("fomc_dates.yaml", "fomc_dates"),
    "cpi":  ("cpi_dates.yaml",  "cpi_dates"),
    "nfp":  ("nfp_dates.yaml",  "nfp_dates"),
}


def load_blackout_dates(
    calendars: Iterable[str],
    calendar_dir: Path | None = None,
) -> frozenset[date]:
    """Load one or more named event calendars and return all dates as a frozen set.

    Parameters
    ----------
    calendars:
        Names to load — any combination of ``"fomc"``, ``"cpi"``, ``"nfp"``.
    calendar_dir:
        Override for the ``configs/calendars/`` directory. Used in tests.

    Returns
    -------
    frozenset[date]
        All dates across all requested calendars.

    Raises
    ------
    ValueError
        Unknown calendar name.
    FileNotFoundError
        Calendar YAML file not found.
    """
    cal_dir = calendar_dir or _CALENDAR_DIR
    all_dates: set[date] = set()

    for name in calendars:
        if name not in _CALENDAR_FILES:
            raise ValueError(
                f"Unknown calendar '{name}'. Valid: {sorted(_CALENDAR_FILES)}"
            )
        filename, key = _CALENDAR_FILES[name]
        path = cal_dir / filename
        data = yaml.safe_load(path.read_text())
        for d in data[key]:
            all_dates.add(date.fromisoformat(str(d)))

    return frozenset(all_dates)


def is_blackout(trade_date: date, blackout_set: frozenset[date]) -> bool:
    """Return True if *trade_date* falls on a blacked-out event day."""
    return trade_date in blackout_set
