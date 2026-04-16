"""Convert raw TradeStation Bars payloads into the canonical bar schema.

TradeStation returns a list of dicts like::

    {
      "High": "110.75", "Low": "110.25", "Open": "110.50", "Close": "110.5625",
      "TimeStamp": "2024-01-02T14:30:00Z",
      "TotalVolume": "1234",
      "UpTicks": 50, "DownTicks": 45, "TotalTicks": 95,
      "UpVolume": 700, "DownVolume": 534,
      "IsRealtime": false, "IsEndOfHistory": false, "Epoch": 1704206400000,
      ...
    }

Numeric fields are sometimes strings, sometimes numbers, occasionally missing.
Order-flow fields (UpVolume/DownVolume, tick counts) may be absent on older
windows — they are mapped to NULL, never to zero. Mapping zero onto a missing
field would silently corrupt downstream order-flow analysis.

The output is a pyarrow Table conforming to ``BAR_SCHEMA``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import pyarrow as pa

from trading_research.data.schema import BAR_SCHEMA, empty_bar_table

_NY_TZ = "America/New_York"


def _to_int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(float(s))
        except ValueError:
            return None
    return None


def _to_float(v: Any) -> float:
    if v is None:
        raise ValueError("required OHLC field is missing")
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).strip())


def _parse_timestamp(ts: Any) -> datetime:
    if ts is None:
        raise ValueError("TimeStamp field missing")
    # Pandas handles the 'Z' suffix and trailing fractional seconds.
    out = pd.to_datetime(ts, utc=True, errors="raise")
    if isinstance(out, pd.Timestamp):
        return out.to_pydatetime()
    raise ValueError(f"Unparseable timestamp: {ts!r}")


def bars_json_to_table(bars: list[dict[str, Any]]) -> pa.Table:
    """Convert a TradeStation ``Bars`` list into a canonical-schema table.

    Returns an empty table if ``bars`` is empty. Raises ``ValueError`` if a
    row is missing a required field (OHLC, volume, timestamp).
    """
    if not bars:
        return empty_bar_table()

    rows: list[dict[str, Any]] = []
    for raw in bars:
        ts_utc = _parse_timestamp(raw.get("TimeStamp"))

        volume = _to_int_or_none(raw.get("TotalVolume"))
        if volume is None:
            # TradeStation occasionally names this field differently.
            volume = _to_int_or_none(raw.get("Volume"))
        if volume is None:
            raise ValueError(f"bar at {ts_utc.isoformat()} missing volume")

        rows.append(
            {
                "timestamp_utc": ts_utc,
                "timestamp_ny": ts_utc,  # converted to NY tz after the fact below
                "open": _to_float(raw.get("Open")),
                "high": _to_float(raw.get("High")),
                "low": _to_float(raw.get("Low")),
                "close": _to_float(raw.get("Close")),
                "volume": int(volume),
                "buy_volume": _to_int_or_none(raw.get("UpVolume")),
                "sell_volume": _to_int_or_none(raw.get("DownVolume")),
                "up_ticks": _to_int_or_none(raw.get("UpTicks")),
                "down_ticks": _to_int_or_none(raw.get("DownTicks")),
                "total_ticks": _to_int_or_none(raw.get("TotalTicks")),
            }
        )

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = df["timestamp_utc"].dt.tz_convert(_NY_TZ)

    return pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)
