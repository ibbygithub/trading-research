"""Data loading for the replay cockpit.

Provides `load_window()` which returns a dict of DataFrames keyed by timeframe.
5m/15m data comes from FEATURES parquets (already has indicators).
60m/1D comes from CLEAN parquets; SMA(200) is computed on the fly.

All returned DataFrames have a tz-aware UTC DatetimeIndex.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

_DATA_ROOT = Path(__file__).parents[3] / "data"


class DataNotFoundError(Exception):
    """Raised when a required parquet file cannot be found."""


def _to_utc(dt: datetime) -> pd.Timestamp:
    """Normalise a datetime to a tz-aware UTC Timestamp."""
    ts = pd.Timestamp(dt)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _find_parquet(directory: Path, pattern: str) -> Path:
    """Return the most-recently-named file matching *pattern* in *directory*.

    Uses lexicographic sort on filenames; files with date-range suffixes sort
    correctly by this rule.

    Raises DataNotFoundError if no match is found.
    """
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise DataNotFoundError(
            f"No parquet found matching '{pattern}' in {directory}. "
            "Run 'uv run trading-research rebuild' to generate missing files."
        )
    return matches[-1]


def load_window(
    symbol: str,
    from_dt: datetime,
    to_dt: datetime,
    data_root: Path | None = None,
    feature_set: str = "base-v1",
) -> dict[str, pd.DataFrame]:
    """Load data for all four timeframes within [from_dt, to_dt].

    Returns a dict keyed by timeframe label:
        {"5m": df, "15m": df, "60m": df, "1D": df}

    All DataFrames have:
    - A tz-aware UTC DatetimeIndex (timestamp_utc set as index)
    - Rows strictly within [from_dt, to_dt]

    5m and 15m include all indicator columns from the FEATURES parquet.
    60m and 1D include OHLCV + buy/sell volume + sma_200 (computed on the fly
    from the full history, then filtered, so no warm-up NaN at window start).

    Raises:
        DataNotFoundError: if any parquet file for the symbol is missing.
    """
    root = data_root or _DATA_ROOT
    from_ts = _to_utc(from_dt)
    to_ts = _to_utc(to_dt)

    result: dict[str, pd.DataFrame] = {}

    # --- 5m and 15m: load from FEATURES ---
    for tf in ("5m", "15m"):
        path = _find_parquet(
            root / "features",
            f"{symbol}_backadjusted_{tf}_features_{feature_set}_*.parquet",
        )
        df = pd.read_parquet(path, engine="pyarrow")
        df = df.set_index("timestamp_utc")
        df.index = pd.DatetimeIndex(df.index, tz="UTC")
        df = df.sort_index()
        result[tf] = df.loc[from_ts:to_ts]

    # --- 60m and 1D: load from CLEAN, compute SMA(200) on full history ---
    for tf in ("60m", "1D"):
        path = _find_parquet(
            root / "clean",
            f"{symbol}_backadjusted_{tf}_*.parquet",
        )
        df = pd.read_parquet(path, engine="pyarrow")
        df = df.set_index("timestamp_utc")
        df.index = pd.DatetimeIndex(df.index, tz="UTC")
        df = df.sort_index()
        # Compute SMA(200) on the full dataset so the window start has valid values.
        df["sma_200"] = df["close"].rolling(200).mean()
        result[tf] = df.loc[from_ts:to_ts]

    return result


def load_trades(path: Path) -> pd.DataFrame:
    """Load a trade log parquet written by the backtest engine.

    Returns a DataFrame with at minimum these columns (all may be present):
        entry_ts, exit_ts, entry_price, exit_price,
        direction, exit_reason, net_pnl_usd

    Timestamps are returned as tz-aware UTC Timestamps.

    Raises DataNotFoundError if the file does not exist.
    """
    path = Path(path)
    if not path.is_file():
        raise DataNotFoundError(f"Trades file not found: {path}")

    df = pd.read_parquet(path, engine="pyarrow")

    # Normalise timestamp columns to tz-aware UTC.
    for col in ("entry_ts", "exit_ts", "entry_trigger_ts", "exit_trigger_ts"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)

    return df
