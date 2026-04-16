"""Canonical 1-minute bar schema.

Every dataset in ``data/clean/`` and ``data/features/`` conforms to this schema.
Raw downloads in ``data/raw/`` should conform too, but the validation happens
in ``data-management`` before a dataset is promoted to clean.

The schema is expressed twice: once as a pyarrow schema (authoritative for
parquet IO) and once as a pydantic model (convenient for row-level validation
in tests and at API boundaries). Keep them in sync.

Fields:

``timestamp_utc``
    UTC bar-open timestamp, nanosecond precision, tz-aware, non-null.

``timestamp_ny``
    America/New_York bar-open timestamp, nanosecond precision, tz-aware,
    non-null. Derived from ``timestamp_utc`` at write time. Stored alongside
    so display code never has to convert and never has to guess the tz.

``open``, ``high``, ``low``, ``close``
    Float64, non-null.

``volume``
    Int64, non-null. Total contracts traded in the bar.

``buy_volume``, ``sell_volume``
    Int64, **nullable**. Order-flow attribution from TradeStation's
    UpVolume/DownVolume fields. Nullable because some historical windows
    omit it. Strategies that use order flow MUST handle the null case
    explicitly.

``up_ticks``, ``down_ticks``, ``total_ticks``
    Int64, nullable. Tick-level attribution, same provenance caveat.

The schema version is written into parquet metadata so future readers can
detect and refuse to read schemas they don't understand.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "bar-1m.v1"

_TS_UTC = pa.timestamp("ns", tz="UTC")
_TS_NY = pa.timestamp("ns", tz="America/New_York")

BAR_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("timestamp_utc", _TS_UTC, nullable=False),
        pa.field("timestamp_ny", _TS_NY, nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.int64(), nullable=False),
        pa.field("buy_volume", pa.int64(), nullable=True),
        pa.field("sell_volume", pa.int64(), nullable=True),
        pa.field("up_ticks", pa.int64(), nullable=True),
        pa.field("down_ticks", pa.int64(), nullable=True),
        pa.field("total_ticks", pa.int64(), nullable=True),
    ],
    metadata={b"schema_version": SCHEMA_VERSION.encode()},
)


BAR_COLUMN_ORDER: tuple[str, ...] = tuple(f.name for f in BAR_SCHEMA)


class Bar(BaseModel):
    """One 1-minute bar. Pydantic mirror of ``BAR_SCHEMA`` for row-level use."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_utc: datetime
    timestamp_ny: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Annotated[int, Field(ge=0)]
    buy_volume: Annotated[int | None, Field(ge=0)] = None
    sell_volume: Annotated[int | None, Field(ge=0)] = None
    up_ticks: Annotated[int | None, Field(ge=0)] = None
    down_ticks: Annotated[int | None, Field(ge=0)] = None
    total_ticks: Annotated[int | None, Field(ge=0)] = None


def empty_bar_table() -> pa.Table:
    """Return an empty table with the canonical schema. Useful as a fallback."""
    return pa.Table.from_pylist([], schema=BAR_SCHEMA)


# ---------------------------------------------------------------------------
# Trade log schema — written by the backtest engine to runs/<strategy>/<ts>/
# ---------------------------------------------------------------------------

TRADE_SCHEMA_VERSION = "trade.v1"

_TS_UTC = pa.timestamp("ns", tz="UTC")

TRADE_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("trade_id", pa.string(), nullable=False),
        pa.field("strategy_id", pa.string(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("direction", pa.string(), nullable=False),           # "long" | "short"
        pa.field("quantity", pa.int64(), nullable=False),
        pa.field("entry_trigger_ts", _TS_UTC, nullable=False),       # bar T close — signal fired
        pa.field("entry_ts", _TS_UTC, nullable=False),               # bar T+1 open — fill executed
        pa.field("entry_price", pa.float64(), nullable=False),
        pa.field("exit_trigger_ts", _TS_UTC, nullable=False),        # bar when exit condition met
        pa.field("exit_ts", _TS_UTC, nullable=False),                # bar when fill executed
        pa.field("exit_price", pa.float64(), nullable=False),
        pa.field("exit_reason", pa.string(), nullable=False),        # target|stop|signal|eod|time_limit
        pa.field("initial_stop", pa.float64(), nullable=True),
        pa.field("initial_target", pa.float64(), nullable=True),
        pa.field("pnl_points", pa.float64(), nullable=False),
        pa.field("pnl_usd", pa.float64(), nullable=False),
        pa.field("slippage_usd", pa.float64(), nullable=False),
        pa.field("commission_usd", pa.float64(), nullable=False),
        pa.field("net_pnl_usd", pa.float64(), nullable=False),
        pa.field("mae_points", pa.float64(), nullable=True),         # max adverse excursion
        pa.field("mfe_points", pa.float64(), nullable=True),         # max favourable excursion
    ],
    metadata={b"schema_version": TRADE_SCHEMA_VERSION.encode()},
)

TRADE_COLUMN_ORDER: tuple[str, ...] = tuple(f.name for f in TRADE_SCHEMA)


class Trade(BaseModel):
    """One completed trade. Pydantic mirror of ``TRADE_SCHEMA`` for row-level use."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trade_id: str
    strategy_id: str
    symbol: str
    direction: str                   # "long" or "short"
    quantity: Annotated[int, Field(gt=0)]
    entry_trigger_ts: datetime
    entry_ts: datetime
    entry_price: float
    exit_trigger_ts: datetime
    exit_ts: datetime
    exit_price: float
    exit_reason: str                 # target|stop|signal|eod|time_limit
    initial_stop: float | None = None
    initial_target: float | None = None
    pnl_points: float = 0.0
    pnl_usd: float = 0.0
    slippage_usd: float = 0.0
    commission_usd: float = 0.0
    net_pnl_usd: float = 0.0
    mae_points: float | None = None
    mfe_points: float | None = None


def empty_trade_table() -> pa.Table:
    """Return an empty table with the canonical trade schema."""
    return pa.Table.from_pylist([], schema=TRADE_SCHEMA)
