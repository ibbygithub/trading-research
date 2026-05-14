"""Inventory: print a human-readable table of all data files."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from trading_research.data.manifest import manifest_path_for, read_manifest, is_stale
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

_DATA_ROOT = Path(__file__).parents[3] / "data"

_TF_ORDER = {"1m": 0, "5m": 1, "15m": 2, "60m": 3, "240m": 4, "1D": 5}


def _size_mb(path: Path) -> str:
    try:
        return f"{path.stat().st_size / 1_048_576:.1f} MB"
    except OSError:
        return "?"


def _row_count(path: Path, manifest: dict | None) -> str:
    if manifest and manifest.get("row_count"):
        return f"{manifest['row_count']:,}"
    try:
        return f"{pq.read_metadata(path).num_rows:,}"
    except Exception:
        return "?"


def _date_range(manifest: dict | None) -> str:
    if not manifest:
        return "?"
    dr = manifest.get("date_range", {})
    start = dr.get("start", "?")[:10] if dr.get("start") else "?"
    end = dr.get("end", "?")[:10] if dr.get("end") else "?"
    return f"{start} .. {end}"


def _manifest_status(path: Path) -> tuple[str, str]:
    mp = manifest_path_for(path)
    if not mp.exists():
        return "MISSING", "yes"
    stale, reasons = is_stale(path)
    status = "backfilled" if read_manifest(path) and read_manifest(path).get("backfilled") else "OK"
    stale_str = ", ".join(reasons) if stale else "no"
    return status, stale_str


def _parse_filename(path: Path, layer: str) -> tuple[str, str, str]:
    """Extract (symbol, timeframe, adjustment) from filename heuristically."""
    stem = path.stem
    parts = stem.split("_")

    # FEATURES: ZN_backadjusted_5m_features_base-v1_...
    if layer == "FEATURES":
        try:
            tf_idx = next(i for i, p in enumerate(parts) if "m" in p or p == "1D")
            symbol = parts[0]
            adjustment = parts[1] if len(parts) > 1 else "?"
            timeframe = parts[tf_idx]
            return symbol, timeframe, adjustment
        except StopIteration:
            return parts[0], "?", "?"

    # CLEAN: ZN_1m_backadjusted_... or ZN_backadjusted_5m_...
    if layer == "CLEAN":
        if len(parts) >= 3 and (parts[1].endswith("m") or parts[1] == "1D"):
            return parts[0], parts[1], parts[2] if len(parts) > 2 else "?"
        elif len(parts) >= 3:
            return parts[0], parts[2] if len(parts) > 2 else "?", parts[1]
        return parts[0], "?", "?"

    # RAW contracts: TYH10_1m_... or ZN_1m_...
    if len(parts) >= 2:
        return parts[0], parts[1] if len(parts) > 1 else "?", "raw"
    return parts[0], "?", "raw"


def print_inventory(data_root: Path = _DATA_ROOT) -> None:
    """Print a table of all parquet files in the three-layer data store."""
    logger.info("inventory_start", stage="inventory", action="start", outcome="ok")
    header = f"{'Layer':<10} {'Symbol':<20} {'TF':<6} {'Adjust':<12} {'Rows':>12} {'Range':<26} {'Size':>8} {'Manifest':<12} {'Stale'}"
    print(header)
    print("-" * len(header))

    total_files = 0
    for layer_name, subdir in [("RAW", "raw"), ("CLEAN", "clean"), ("FEATURES", "features")]:
        layer_dir = data_root / subdir
        if not layer_dir.exists():
            continue

        for path in sorted(layer_dir.rglob("*.parquet")):
            manifest = read_manifest(path)
            symbol, tf, adj = _parse_filename(path, layer_name)
            rows = _row_count(path, manifest)
            date_rng = _date_range(manifest)
            size = _size_mb(path)
            mstatus, stale_str = _manifest_status(path)

            print(
                f"{layer_name:<10} {symbol:<20} {tf:<6} {adj:<12} {rows:>12} {date_rng:<26} {size:>8} {mstatus:<12} {stale_str}"
            )
            total_files += 1
    logger.info(
        "inventory_complete",
        stage="inventory",
        action="finish",
        outcome="ok",
        files=total_files,
    )
