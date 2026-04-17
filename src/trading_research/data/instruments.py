"""Typed loader for ``configs/instruments.yaml``.

Fail loudly if the file is missing, malformed, or missing a field for an
instrument we ask about. This module is the single source of truth for
instrument specs — strategy code never reads the YAML directly.
"""

from __future__ import annotations

from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_INSTRUMENTS_PATH = Path(__file__).resolve().parents[3] / "configs" / "instruments.yaml"


class SessionWindow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    open: time
    close: time

    @field_validator("open", "close", mode="before")
    @classmethod
    def _parse_hhmm(cls, v: object) -> object:
        if isinstance(v, str):
            return time.fromisoformat(v)
        return v


class Session(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timezone: str
    globex: SessionWindow
    rth: SessionWindow


class RollConvention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    convention: str
    notes: str | None = None


class DataSourceSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_timeframe: str
    historical_source: str
    tradestation_session_template: str | None = None
    calendar: str | None = None  # pandas-market-calendars name for session validation


class BacktestDefaults(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slippage_ticks: Annotated[int, Field(ge=0)] = 1    # per side
    commission_usd: Annotated[float, Field(ge=0)] = 2.00   # per side


class InstrumentSpec(BaseModel):
    """Everything we need to know about a tradeable contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_symbol: str
    continuous_symbol: str
    description: str
    exchange: str
    asset_class: str
    currency: str
    tick_size: Annotated[float, Field(gt=0)]
    tick_value_usd: Annotated[float, Field(gt=0)]
    point_value_usd: Annotated[float, Field(gt=0)]
    contract_size_face_value: Annotated[int, Field(gt=0)]
    session: Session
    roll: RollConvention
    data: DataSourceSpec
    backtest_defaults: BacktestDefaults = BacktestDefaults()


class InstrumentRegistry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instruments: dict[str, InstrumentSpec]

    def get(self, symbol: str) -> InstrumentSpec:
        try:
            return self.instruments[symbol]
        except KeyError as exc:
            known = ", ".join(sorted(self.instruments)) or "(none)"
            raise KeyError(
                f"Unknown instrument {symbol!r}. Known instruments: {known}"
            ) from exc


def load_instruments(path: Path | None = None) -> InstrumentRegistry:
    """Load and validate the instrument registry."""
    p = path or DEFAULT_INSTRUMENTS_PATH
    if not p.is_file():
        raise FileNotFoundError(f"instruments.yaml not found at {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return InstrumentRegistry.model_validate(raw)


@lru_cache(maxsize=1)
def default_registry() -> InstrumentRegistry:
    """Cached accessor for the default registry. Use this in app code."""
    return load_instruments()


def load_instrument(symbol: str, path: Path | None = None) -> InstrumentSpec:
    """Return the InstrumentSpec for *symbol*.

    Raises KeyError if the symbol is not registered.
    """
    registry = load_instruments(path) if path else default_registry()
    return registry.get(symbol)


def get_cost_per_trade(symbol: str, path: Path | None = None) -> tuple[float, float]:
    """Return (slippage_usd_round_trip, commission_usd_round_trip) for *symbol*.

    Values come from ``backtest_defaults`` in instruments.yaml.
    Slippage is: slippage_ticks × tick_value_usd × 2 (entry + exit).
    Commission is: commission_usd × 2 (entry + exit).
    """
    spec = load_instrument(symbol, path)
    bd = spec.backtest_defaults
    slippage_rt = bd.slippage_ticks * spec.tick_value_usd * 2
    commission_rt = bd.commission_usd * 2
    return slippage_rt, commission_rt
