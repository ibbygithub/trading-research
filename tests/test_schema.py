"""Tests for the canonical bar schema."""

from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trading_research.data.schema import (
    BAR_COLUMN_ORDER,
    BAR_SCHEMA,
    SCHEMA_VERSION,
    Bar,
    empty_bar_table,
)


def test_schema_version_in_metadata():
    assert BAR_SCHEMA.metadata[b"schema_version"].decode() == SCHEMA_VERSION


def test_column_order_is_canonical():
    assert BAR_COLUMN_ORDER[:7] == (
        "timestamp_utc",
        "timestamp_ny",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


def test_orderflow_fields_are_nullable():
    for name in ("buy_volume", "sell_volume", "up_ticks", "down_ticks", "total_ticks"):
        assert BAR_SCHEMA.field(name).nullable, f"{name} must be nullable"


def test_ohlc_and_volume_are_non_nullable():
    for name in ("timestamp_utc", "timestamp_ny", "open", "high", "low", "close", "volume"):
        assert not BAR_SCHEMA.field(name).nullable, f"{name} must be non-null"


def test_empty_table_has_canonical_schema():
    t = empty_bar_table()
    assert t.num_rows == 0
    assert t.schema.equals(BAR_SCHEMA, check_metadata=False)


def test_parquet_roundtrip_preserves_schema(tmp_path):
    ts_utc = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    ts_ny = ts_utc.astimezone()
    row = {
        "timestamp_utc": ts_utc,
        "timestamp_ny": ts_ny,
        "open": 110.5,
        "high": 110.75,
        "low": 110.25,
        "close": 110.5625,
        "volume": 1234,
        "buy_volume": 700,
        "sell_volume": 534,
        "up_ticks": 50,
        "down_ticks": 45,
        "total_ticks": 95,
    }
    table = pa.Table.from_pylist([row], schema=BAR_SCHEMA)
    path = tmp_path / "bars.parquet"
    pq.write_table(table, path)
    read_back = pq.read_table(path)
    assert read_back.schema.equals(BAR_SCHEMA, check_metadata=False)
    assert read_back.num_rows == 1


def test_pydantic_bar_roundtrip():
    b = Bar(
        timestamp_utc=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        timestamp_ny=datetime(2024, 1, 2, 9, 30, tzinfo=UTC),
        open=110.5,
        high=110.75,
        low=110.25,
        close=110.5625,
        volume=1234,
    )
    assert b.buy_volume is None
    assert b.volume == 1234


def test_pydantic_bar_rejects_negative_volume():
    with pytest.raises(ValueError):
        Bar(
            timestamp_utc=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
            timestamp_ny=datetime(2024, 1, 2, 9, 30, tzinfo=UTC),
            open=110.5,
            high=110.75,
            low=110.25,
            close=110.5625,
            volume=-1,
        )
