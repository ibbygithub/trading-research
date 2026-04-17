"""Resample 1-minute bars to higher timeframes (5m, 15m, etc.).

All higher timeframes are derived from the 1-minute base, never downloaded
separately.  This module is the authoritative resampler; everything that
needs a 5m or 15m view goes through here.

Session-boundary awareness
--------------------------
ZN Globex has a 1-hour maintenance halt (17:00–18:00 ET) every day.
Resampling naively could create an N-minute bar that straddles the halt:
e.g., a 15-minute bar that contains the 16:55 ET bar and the 18:00 ET bar
as if they were adjacent, collapsing 65 minutes of wall-clock time into one
bar.  That would be wrong.

The fix is simple: group by N-minute buckets aligned to clock time (UTC),
then drop any aggregate bar whose constituent 1-minute bars are not
*consecutive within that bucket*.  In practice a session break always
produces a gap of ≥60 consecutive missing minutes, so any bucket that
spans a break will have volume=0 (no 1-minute bars present), and we simply
drop zero-volume buckets.

Holiday and weekend gaps work the same way — no 1-minute bars → no output
bar — so they self-heal without requiring calendar awareness here.

Partial bars at session boundaries
------------------------------------
The first and last N-minute buckets of each session are often partial
(e.g., a 15-minute bucket starting at 17:15 ET contains only 15 one-minute
bars if the session opens at 17:15 ET on-the-dot, which ZN does — but if
the session opens at 18:00 ET and the bucket boundary is at 17:45/18:00/18:15
ET the first bar would be exactly 15 bars anyway).  We keep partial bars;
dropping them would silently lose real data near session opens/closes.

Usage
-----
    from trading_research.data.resample import resample_bars

    df_5m  = resample_bars(df_1m, freq="5min")
    df_15m = resample_bars(df_1m, freq="15min")

The returned DataFrame has the same column layout as the input (BAR_SCHEMA
columns) with ``timestamp_utc`` as the index and ``timestamp_ny`` computed
from it.

Output
------
Use ``write_resampled`` to write parquet files conforming to BAR_SCHEMA.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from trading_research.data.schema import BAR_SCHEMA
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

# Resample aggregation spec for each column.
# "first" / "last" / "max" / "min" / "sum" are pandas GroupBy agg names.
_OHLC_AGGS: dict[str, str] = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "buy_volume": "sum",
    "sell_volume": "sum",
    "up_ticks": "sum",
    "down_ticks": "sum",
    "total_ticks": "sum",
}

# Columns that are nullable integers in BAR_SCHEMA.
_NULLABLE_INT_COLS = frozenset(
    {"buy_volume", "sell_volume", "up_ticks", "down_ticks", "total_ticks"}
)


def resample_bars(
    df: pd.DataFrame,
    freq: str,
) -> pd.DataFrame:
    """Resample a 1-minute bar DataFrame to a higher timeframe.

    Parameters
    ----------
    df:
        DataFrame with a ``timestamp_utc`` column (tz-aware, UTC).
        Must include all BAR_SCHEMA columns; nullable-int columns may have
        NaN/None values.
    freq:
        Pandas offset alias for the target frequency (e.g. ``"5min"``,
        ``"15min"``, ``"30min"``).

    Returns
    -------
    DataFrame with the same column layout, indexed by ``timestamp_utc``
    (the bar-open timestamp of each N-minute bucket).  Zero-volume bars
    (gaps, halts, holidays) are dropped.  ``timestamp_ny`` is recomputed
    from ``timestamp_utc``.
    """
    if df.empty:
        return _empty_result()

    df = df.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.sort_values("timestamp_utc").set_index("timestamp_utc")

    # Build aggregation dict for non-nullable columns only.
    # Nullable int columns are handled separately with min_count=1 so that
    # buckets where all source values are NaN return NaN (not 0).
    non_nullable_agg = {
        col: fn
        for col, fn in _OHLC_AGGS.items()
        if col in df.columns and col not in _NULLABLE_INT_COLS
    }

    resampled = df.resample(freq, origin="epoch").agg(non_nullable_agg)

    # Nullable int columns: sum with min_count=1 preserves NaN when all are NaN.
    for col in _NULLABLE_INT_COLS:
        if col in df.columns:
            resampled[col] = (
                df[col].resample(freq, origin="epoch").sum(min_count=1)
            )

    # Drop buckets with no data (gap periods, maintenance halts, weekends).
    # A bucket with no contributing 1-minute bars will have close=NaN.
    resampled = resampled[resampled["close"].notna()].copy()

    # Convert nullable int columns to Int64 (nullable integer dtype).
    for col in _NULLABLE_INT_COLS:
        if col in resampled.columns:
            resampled[col] = resampled[col].astype("Int64")

    # Non-nullable ints: volume should always be an integer.
    if "volume" in resampled.columns:
        resampled["volume"] = resampled["volume"].fillna(0).astype("int64")

    # Recompute timestamp_ny from the UTC index.
    resampled["timestamp_ny"] = resampled.index.tz_convert("America/New_York")

    resampled = resampled.reset_index()

    logger.info(
        "resample_complete",
        freq=freq,
        input_rows=len(df),
        output_rows=len(resampled),
    )
    return resampled


def _empty_result() -> pd.DataFrame:
    """Return an empty DataFrame with the expected column layout."""
    cols = list(BAR_SCHEMA.names)
    return pd.DataFrame(columns=cols)


def write_resampled(
    df: pd.DataFrame,
    path: Path,
) -> None:
    """Write a resampled DataFrame to parquet conforming to BAR_SCHEMA.

    Nullable-int columns are cast to Int64 (pandas) before converting to
    pyarrow so null values survive the round-trip.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    out = df.copy()
    out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)
    out["timestamp_ny"] = pd.to_datetime(out["timestamp_ny"]).dt.tz_convert(
        "America/New_York"
    )

    for col in _NULLABLE_INT_COLS:
        if col in out.columns:
            out[col] = out[col].astype("Int64")

    # Keep only schema columns, in schema order.
    cols = [c for c in BAR_SCHEMA.names if c in out.columns]
    out = out[cols]

    tbl = pa.Table.from_pandas(out, schema=BAR_SCHEMA, preserve_index=False)
    pq.write_table(tbl, path)
    logger.info("resampled_written", path=str(path), rows=len(out))


def resample_daily(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 1-minute bars into daily bars using CME trade-date convention.

    A ZN "daily bar" is a Globex session, not a calendar day. The session runs
    from 18:00 ET (previous calendar day) to 17:00 ET, with a 1-hour maintenance
    halt. Matching TradeStation, TradingView, Bloomberg, and CME settlement.

    Implementation: shift timestamp_ny by +6 hours so that the 18:00 ET session
    open becomes midnight of the trade date. DST is handled correctly because
    timestamp_ny is tz-aware — no hard-coded UTC offsets needed.

    Parameters
    ----------
    df_1m:
        1-minute bar DataFrame with BAR_SCHEMA columns. ``timestamp_ny`` must
        be tz-aware (America/New_York).

    Returns
    -------
    DataFrame with one row per trading session. ``timestamp_utc`` is the first
    1-minute bar's open time in that session. Nullable-int columns keep NaN
    when all source bars are null.
    """
    if df_1m.empty:
        return _empty_result()

    df = df_1m.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = pd.to_datetime(df["timestamp_ny"]).dt.tz_convert(
        "America/New_York"
    )
    df = df.sort_values("timestamp_utc")

    # +6h shifts 18:00 ET session open to midnight → all bars in the same
    # Globex session share a single trade_date.
    df["_trade_date"] = (df["timestamp_ny"] + pd.Timedelta(hours=6)).dt.date

    # Aggregate OHLCV; nullable ints use min_count=1 so all-NaN → NaN (not 0).
    non_nullable_agg: dict[str, str] = {
        col: fn for col, fn in _OHLC_AGGS.items() if col not in _NULLABLE_INT_COLS
    }
    daily = df.groupby("_trade_date", sort=True).agg(non_nullable_agg)

    for col in _NULLABLE_INT_COLS:
        if col in df.columns:
            daily[col] = df.groupby("_trade_date")[col].sum(min_count=1).astype("Int64")

    # Attach open-of-session timestamps.
    daily["timestamp_utc"] = df.groupby("_trade_date")["timestamp_utc"].first()
    daily["timestamp_ny"] = daily["timestamp_utc"].dt.tz_convert("America/New_York")

    daily = daily.reset_index(drop=True)
    if "volume" in daily.columns:
        daily["volume"] = daily["volume"].fillna(0).astype("int64")

    logger.info(
        "resample_daily_complete",
        input_rows=len(df_1m),
        output_rows=len(daily),
    )
    return daily


def resample_and_write(
    source_path: Path,
    output_dir: Path,
    freqs: list[str],
    symbol: str,
) -> dict[str, Path]:
    """Load a 1-minute parquet file, resample to each requested frequency,
    and write the results to ``output_dir``.

    File naming convention: ``{symbol}_{freq}_{date_range}.parquet``
    where ``freq`` is the frequency string with 'min' replaced by 'm'
    (e.g. '5min' → '5m').

    Parameters
    ----------
    source_path:
        Path to the 1-minute base parquet file.
    output_dir:
        Directory for output parquet files.
    freqs:
        List of pandas offset alias strings (e.g. ``["5min", "15min"]``).
    symbol:
        Base symbol name for output file naming (e.g. ``"ZN"``).

    Returns
    -------
    Dict mapping frequency string → output Path.
    """
    tbl = pq.read_table(source_path)
    df = tbl.to_pandas()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    # Extract date range from data for file naming.
    start_str = df["timestamp_utc"].min().strftime("%Y-%m-%d")
    end_str = df["timestamp_utc"].max().strftime("%Y-%m-%d")

    output_paths: dict[str, Path] = {}
    for freq in freqs:
        label = freq.replace("min", "m")
        out_name = f"{symbol}_{label}_{start_str}_{end_str}.parquet"
        out_path = output_dir / out_name

        resampled = resample_bars(df, freq)
        write_resampled(resampled, out_path)

        output_paths[freq] = out_path
        logger.info(
            "resample_written",
            symbol=symbol,
            freq=freq,
            rows=len(resampled),
            path=str(out_path),
        )

    return output_paths
