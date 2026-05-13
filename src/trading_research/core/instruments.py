"""Typed instrument registry for the core model layer.

This module is the interface every session-23-and-beyond consumer should
import from. Strategy code, feature builders, and backtest infrastructure
should accept ``Instrument`` objects rather than bare symbol strings.

The backing store is ``configs/instruments_core.yaml`` (flat schema).
The legacy ``data.instruments`` module (nested schema) continues to serve
existing pipeline code until session 25 consolidates them.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "configs" / "instruments_core.yaml"


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    tradestation_symbol: str
    name: str
    exchange: str
    asset_class: Literal["rates", "fx", "equity_index", "commodity", "crypto"]

    # Contract specs — all Decimal to prevent float P&L rounding bugs.
    tick_size: Decimal
    tick_value_usd: Decimal
    contract_multiplier: Decimal
    is_micro: bool

    # Transaction costs confirmed by Ibby 2026-04-19.
    commission_per_side_usd: Decimal

    # Margins — intraday required; overnight nullable (not always published).
    intraday_initial_margin_usd: Decimal
    overnight_initial_margin_usd: Decimal | None

    # Session times — America/New_York.  For ZN the close (17:00) is next-day.
    session_open_et: time
    session_close_et: time
    rth_open_et: time
    rth_close_et: time
    timezone: str = "America/New_York"

    # Calendar and roll.
    calendar_name: str
    roll_method: Literal["panama", "ratio", "none"]

    # OU tradeable half-life bounds (bars) per timeframe — session 29.
    # Maps timeframe label → (lower, upper) inclusive range.
    # Defaults match the original ZN-calibrated module constants from
    # stationarity.py so existing ZN behaviour is preserved when an
    # instrument does not declare explicit bounds.
    tradeable_ou_bounds_bars: dict[str, tuple[float, float]] | None = None

    def get_ou_bounds(self, timeframe: str) -> tuple[float, float] | None:
        """Return (lower, upper) OU half-life bounds for *timeframe*.

        Returns None if no bounds are configured for this instrument+timeframe.
        Falls back to ZN-calibrated defaults when tradeable_ou_bounds_bars is
        not set on the instrument.
        """
        _DEFAULT_BOUNDS: dict[str, tuple[float, float]] = {
            "1m": (5.0, 60.0),
            "5m": (3.0, 24.0),
            "15m": (2.0, 8.0),
        }
        source = self.tradeable_ou_bounds_bars or _DEFAULT_BOUNDS
        return source.get(timeframe)

    @field_validator(
        "session_open_et",
        "session_close_et",
        "rth_open_et",
        "rth_close_et",
        mode="before",
    )
    @classmethod
    def _parse_time(cls, v: object) -> object:
        if isinstance(v, str):
            return time.fromisoformat(v)
        return v


class InstrumentRegistry:
    """Lazy-loading registry backed by ``configs/instruments_core.yaml``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PATH
        self._cache: dict[str, Instrument] | None = None

    def _load(self) -> dict[str, Instrument]:
        if self._cache is None:
            if not self._path.is_file():
                raise FileNotFoundError(
                    f"instruments_core.yaml not found at {self._path}"
                )
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
            self._cache = {
                symbol: Instrument.model_validate(spec)
                for symbol, spec in raw["instruments"].items()
            }
        return self._cache

    def get(self, symbol: str) -> Instrument:
        """Return the Instrument for *symbol*, raising KeyError if unknown."""
        instruments = self._load()
        try:
            return instruments[symbol]
        except KeyError as exc:
            known = ", ".join(sorted(instruments)) or "(none)"
            raise KeyError(
                f"Unknown instrument {symbol!r}. Known instruments: {known}"
            ) from exc

    def list(self) -> list[Instrument]:
        """Return all registered instruments in definition order."""
        return list(self._load().values())
