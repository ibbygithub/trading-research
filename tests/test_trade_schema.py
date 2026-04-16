"""Round-trip test: Trade → dict → PyArrow table → parquet → Trade."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trading_research.data.schema import TRADE_SCHEMA, Trade, empty_trade_table


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_trade() -> Trade:
    now = _utcnow()
    return Trade(
        trade_id="abc-123",
        strategy_id="test-strat",
        symbol="ZN",
        direction="long",
        quantity=1,
        entry_trigger_ts=now,
        entry_ts=now,
        entry_price=110.5,
        exit_trigger_ts=now,
        exit_ts=now,
        exit_price=110.75,
        exit_reason="target",
        initial_stop=110.25,
        initial_target=110.75,
        pnl_points=0.25,
        pnl_usd=250.0,
        slippage_usd=31.25,
        commission_usd=4.0,
        net_pnl_usd=214.75,
        mae_points=-0.0625,
        mfe_points=0.25,
    )


def test_round_trip_parquet(tmp_path):
    trade = _make_trade()

    # Trade → dict → PyArrow table.
    row = trade.model_dump()
    # PyArrow timestamps need pandas-compatible objects.
    import pandas as pd
    for col in ("entry_trigger_ts", "entry_ts", "exit_trigger_ts", "exit_ts"):
        row[col] = pd.Timestamp(row[col])

    table = pa.Table.from_pylist([row], schema=TRADE_SCHEMA)

    # Write to parquet.
    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)

    # Read back.
    table2 = pq.read_table(buf)

    assert table2.num_rows == 1
    row2 = table2.to_pydict()

    assert row2["trade_id"][0] == "abc-123"
    assert row2["strategy_id"][0] == "test-strat"
    assert row2["symbol"][0] == "ZN"
    assert row2["direction"][0] == "long"
    assert row2["quantity"][0] == 1
    assert row2["exit_reason"][0] == "target"
    assert abs(row2["net_pnl_usd"][0] - 214.75) < 1e-6
    assert abs(row2["mae_points"][0] - (-0.0625)) < 1e-9
    assert abs(row2["mfe_points"][0] - 0.25) < 1e-9


def test_schema_version_in_metadata():
    assert TRADE_SCHEMA.metadata[b"schema_version"] == b"trade.v1"


def test_empty_trade_table():
    t = empty_trade_table()
    assert t.num_rows == 0
    assert t.schema.equals(TRADE_SCHEMA)


def test_trade_direction_validation():
    """Trade does not enforce direction values — that's the engine's job.
    Just verify the model accepts valid strings."""
    now = _utcnow()
    t = Trade(
        trade_id="x",
        strategy_id="s",
        symbol="ZN",
        direction="short",
        quantity=2,
        entry_trigger_ts=now,
        entry_ts=now,
        entry_price=110.0,
        exit_trigger_ts=now,
        exit_ts=now,
        exit_price=109.75,
        exit_reason="stop",
    )
    assert t.direction == "short"
    assert t.quantity == 2
