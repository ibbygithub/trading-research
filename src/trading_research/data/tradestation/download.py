"""Resumable, paginated historical bar download.

Pagination unit: 30 calendar days per window. Well under every documented
limit (57,600 bars per request, 500,000 barsback minutes, 3 calendar years
per date-range request). Tuning this up or down is possible but not done
automatically — the default is conservative on purpose.

Resumability: each window's normalized bars are written to a temporary
parquet under ``data/raw/.in_progress/<run_id>/window_<index>.parquet`` as
they complete. If a run dies mid-pull, re-running with the same parameters
picks the same run_id (a hash of symbol+range) and skips windows already on
disk. After the final stitched parquet is written successfully, the
``.in_progress`` directory is cleaned up.

Output layout (one run, per ``historical-bars`` skill):

    data/raw/
    ├── ZN_1m_2024-01-01_2024-01-31.parquet
    └── ZN_1m_2024-01-01_2024-01-31.metadata.json

The metadata JSON is the provenance trail. Everything the data-management
skill needs to validate the file later, and everything a human needs to
answer "what exactly did we download and when?", lives in that JSON.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from trading_research.data.instruments import InstrumentSpec, default_registry
from trading_research.data.schema import BAR_SCHEMA, empty_bar_table
from trading_research.utils.logging import get_logger

from .auth import TradeStationAuth
from .client import TradeStationClient
from .errors import IncompleteDownloadError, RateLimitError, TradeStationError
from .normalize import bars_json_to_table

logger = get_logger(__name__)

DEFAULT_WINDOW_DAYS = 30
DEFAULT_RAW_DIR = Path("data/raw")


@dataclass
class DownloadResult:
    parquet_path: Path
    metadata_path: Path
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    rows_downloaded: int
    expected_row_count_naive: int
    api_calls_made: int
    rate_limit_hits: int
    duration_seconds: float
    continuous_method: str
    api_version: str
    download_timestamp_utc: datetime
    window_days: int
    request_params: dict[str, Any]
    naive_gap_analysis: dict[str, Any]
    largest_gaps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["parquet_path"] = str(self.parquet_path)
        d["metadata_path"] = str(self.metadata_path)
        d["start_date"] = self.start_date.isoformat()
        d["end_date"] = self.end_date.isoformat()
        d["download_timestamp_utc"] = self.download_timestamp_utc.isoformat()
        return d


def _iter_windows(
    start: datetime, end: datetime, window_days: int
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=window_days), end)
        out.append((cur, nxt))
        if nxt == end:
            break
        cur = nxt + timedelta(seconds=1)
    return out


def _run_id(symbol: str, start: date, end: date, window_days: int) -> str:
    key = f"{symbol}|{start.isoformat()}|{end.isoformat()}|w{window_days}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _naive_expected_bars(start: date, end: date) -> int:
    # Rough: CME Globex ~23 hours/day * 5 days/week minus holidays.
    # This is intentionally naive — the real gap analysis happens in
    # data-management with pandas-market-calendars. Here we just want an
    # order-of-magnitude sanity check.
    days = (end - start).days + 1
    weeks = days / 7.0
    trading_days = weeks * 5
    return int(trading_days * 60 * 23)


def _largest_gaps(bars_table: pa.Table, top_n: int = 5) -> list[dict[str, Any]]:
    if bars_table.num_rows < 2:
        return []
    ts = bars_table.column("timestamp_utc").to_pylist()
    gaps: list[tuple[float, datetime, datetime]] = []
    for a, b in zip(ts, ts[1:], strict=False):
        delta = (b - a).total_seconds()
        if delta > 60:
            gaps.append((delta, a, b))
    gaps.sort(reverse=True, key=lambda t: t[0])
    return [
        {
            "start": a.isoformat(),
            "end": b.isoformat(),
            "duration_hours": round(delta / 3600.0, 2),
        }
        for delta, a, b in gaps[:top_n]
    ]


def _resolve_symbol(root_symbol: str) -> tuple[str, InstrumentSpec]:
    spec = default_registry().get(root_symbol)
    return spec.continuous_symbol, spec


def download_historical_bars(
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    auth: TradeStationAuth | None = None,
    client: TradeStationClient | None = None,
    output_dir: Path = DEFAULT_RAW_DIR,
    window_days: int = DEFAULT_WINDOW_DAYS,
    continuous_method: str = "tradestation_continuous",
) -> DownloadResult:
    """Download 1-minute bars for ``symbol`` over ``[start_date, end_date]``.

    ``symbol`` is the *root* (e.g. ``"6E"``); the instrument registry is
    consulted for the actual TradeStation symbol (``"@EU"``) and the data
    source settings.

    Currently supported ``continuous_method``: ``"tradestation_continuous"``
    (use TradeStation's ``@SYMBOL`` continuous contract). Multi-contract
    back-adjusted stitching is a session-03 deliverable.

    Writes one parquet and one metadata JSON to ``output_dir``. Returns a
    ``DownloadResult`` describing what was written.
    """
    if continuous_method != "tradestation_continuous":
        raise NotImplementedError(
            "Multi-contract back-adjusted stitching is not implemented yet. "
            "Use continuous_method='tradestation_continuous' for now."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_symbol, spec = _resolve_symbol(symbol)

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC).replace(
        microsecond=0
    )

    windows = _iter_windows(start_dt, end_dt, window_days)
    run_id = _run_id(symbol, start_date, end_date, window_days)
    in_progress_dir = output_dir / ".in_progress" / run_id
    in_progress_dir.mkdir(parents=True, exist_ok=True)

    own_client = False
    own_auth = False
    if client is None:
        if auth is None:
            auth = TradeStationAuth()
            own_auth = True
        client = TradeStationClient(auth)
        own_client = True

    api_calls = 0
    rate_limit_hits = 0
    t0 = time.time()

    try:
        for i, (lo, hi) in enumerate(windows):
            window_file = in_progress_dir / f"window_{i:04d}.parquet"
            if window_file.exists():
                logger.info(
                    "tradestation_window_skip_existing",
                    index=i,
                    path=str(window_file),
                )
                continue

            logger.info(
                "tradestation_window_fetch",
                index=i,
                total=len(windows),
                firstdate=lo.isoformat(),
                lastdate=hi.isoformat(),
            )
            attempt_start_calls = api_calls
            try:
                bars = client.fetch_bar_window(ts_symbol, lo, hi)
            except RateLimitError:
                rate_limit_hits += 1
                raise
            except TradeStationError:
                raise
            finally:
                api_calls = attempt_start_calls + 1

            table = bars_json_to_table(bars)
            pq.write_table(table, window_file)

        # Stitch windows.
        window_tables: list[pa.Table] = []
        for i in range(len(windows)):
            window_file = in_progress_dir / f"window_{i:04d}.parquet"
            if not window_file.exists():
                raise IncompleteDownloadError(
                    f"missing window file for index {i}: {window_file}"
                )
            window_tables.append(pq.read_table(window_file))

        combined = (
            pa.concat_tables(window_tables) if window_tables else empty_bar_table()
        )
        if combined.num_rows > 0:
            df = combined.to_pandas()
            df = df.sort_values("timestamp_utc").drop_duplicates(
                subset=["timestamp_utc"], keep="last"
            )
            combined = pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)

        parquet_name = f"{symbol}_1m_{start_date.isoformat()}_{end_date.isoformat()}.parquet"
        metadata_name = f"{symbol}_1m_{start_date.isoformat()}_{end_date.isoformat()}.metadata.json"
        parquet_path = output_dir / parquet_name
        metadata_path = output_dir / metadata_name

        pq.write_table(combined, parquet_path)

        expected_naive = _naive_expected_bars(start_date, end_date)
        result = DownloadResult(
            parquet_path=parquet_path,
            metadata_path=metadata_path,
            symbol=symbol,
            timeframe="1m",
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=combined.num_rows,
            expected_row_count_naive=expected_naive,
            api_calls_made=api_calls,
            rate_limit_hits=rate_limit_hits,
            duration_seconds=round(time.time() - t0, 3),
            continuous_method=continuous_method,
            api_version="v3",
            download_timestamp_utc=datetime.now(UTC),
            window_days=window_days,
            request_params={
                "symbol_tradestation": ts_symbol,
                "interval": 1,
                "unit": "Minute",
                "session_template": spec.data.tradestation_session_template,
            },
            naive_gap_analysis={
                "expected_bars_naive": expected_naive,
                "actual_bars": combined.num_rows,
                "missing_bars_naive": max(0, expected_naive - combined.num_rows),
            },
            largest_gaps=_largest_gaps(combined),
        )
        metadata_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

        # Successful completion -> clean up in_progress dir.
        shutil.rmtree(in_progress_dir, ignore_errors=True)

        logger.info(
            "tradestation_download_complete",
            symbol=symbol,
            rows=combined.num_rows,
            api_calls=api_calls,
            rate_limit_hits=rate_limit_hits,
            duration_sec=result.duration_seconds,
        )
        return result
    finally:
        if own_client and client is not None:
            client.close()
        _ = own_auth  # auth has no close
