"""Tests for TradeStation -> canonical schema normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_research.data.schema import BAR_SCHEMA
from trading_research.data.tradestation.normalize import bars_json_to_table

FIXTURE = Path(__file__).parent / "fixtures" / "tradestation_zn_sample.json"


def _load_fixture() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["Bars"]


def test_empty_bars_returns_empty_canonical_table():
    t = bars_json_to_table([])
    assert t.num_rows == 0
    assert t.schema.equals(BAR_SCHEMA, check_metadata=False)


def test_fixture_roundtrip_has_canonical_schema():
    bars = _load_fixture()
    t = bars_json_to_table(bars)
    assert t.num_rows == 3
    assert t.schema.equals(BAR_SCHEMA, check_metadata=False)


def test_orderflow_nulls_propagate_not_zero():
    # Third bar in the fixture omits UpVolume/DownVolume/UpTicks/DownTicks/TotalTicks.
    # These must be NULL, not zero — mapping null to zero would silently corrupt
    # downstream order-flow analysis.
    bars = _load_fixture()
    t = bars_json_to_table(bars)
    df = t.to_pandas()
    third = df.iloc[2]
    assert third["buy_volume"] is None or third["buy_volume"] != third["buy_volume"]  # NaN/None
    assert third["sell_volume"] is None or third["sell_volume"] != third["sell_volume"]
    assert third["up_ticks"] is None or third["up_ticks"] != third["up_ticks"]
    # The first two bars have the values populated.
    assert int(df.iloc[0]["buy_volume"]) == 700
    assert int(df.iloc[0]["sell_volume"]) == 534
    assert int(df.iloc[1]["buy_volume"]) == 523


def test_timestamps_are_utc_and_ny_paired():
    bars = _load_fixture()
    t = bars_json_to_table(bars)
    utc_col = t.column("timestamp_utc")
    ny_col = t.column("timestamp_ny")
    # Types match schema: tz-aware, non-null.
    assert str(utc_col.type) == "timestamp[ns, tz=UTC]"
    assert str(ny_col.type) == "timestamp[ns, tz=America/New_York]"
    # All rows present.
    assert utc_col.null_count == 0
    assert ny_col.null_count == 0


def test_missing_volume_raises():
    with pytest.raises(ValueError, match="missing volume"):
        bars_json_to_table(
            [
                {
                    "Open": "1",
                    "High": "1",
                    "Low": "1",
                    "Close": "1",
                    "TimeStamp": "2024-01-02T14:30:00Z",
                }
            ]
        )


def test_numeric_strings_and_numbers_both_accepted():
    bars = [
        {
            "Open": 100.0,
            "High": "101",
            "Low": "99",
            "Close": 100.5,
            "TotalVolume": 500,
            "TimeStamp": "2024-01-02T14:30:00Z",
            "UpVolume": "300",
            "DownVolume": 200,
        }
    ]
    t = bars_json_to_table(bars)
    df = t.to_pandas()
    assert df.iloc[0]["open"] == 100.0
    assert df.iloc[0]["high"] == 101.0
    assert int(df.iloc[0]["buy_volume"]) == 300
    assert int(df.iloc[0]["sell_volume"]) == 200
