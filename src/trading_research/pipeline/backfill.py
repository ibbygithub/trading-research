"""Backfill manifests for parquet files that predate the manifest convention.

These files were built in sessions 02-04 before manifest writing was standard.
The backfilled manifests use file mtime as built_at and mark themselves
``"backfilled": true`` so downstream staleness checks know the provenance
was reconstructed, not recorded at build time.

Backfill order matters: RAW contracts first, then CLEAN 1m, then CLEAN resamples.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from trading_research.data.manifest import (
    build_clean_manifest,
    build_raw_manifest,
    manifest_path_for,
    write_manifest,
)
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

_DATA_ROOT = Path(__file__).parents[3] / "data"


def _mtime_utc(path: Path) -> str:
    """Return file mtime as a UTC ISO-8601 string."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _needs_backfill(path: Path) -> bool:
    return not manifest_path_for(path).exists()


# ---------------------------------------------------------------------------
# RAW layer
# ---------------------------------------------------------------------------


def backfill_raw_contract(path: Path, dry_run: bool = False) -> dict | None:
    """Write a manifest for a single TY*.parquet contract file in data/raw/contracts/."""
    if not _needs_backfill(path):
        return None

    # Extract symbol from filename: TYH10_1m_... → "TYH10"
    symbol = path.stem.split("_")[0]
    manifest = build_raw_manifest(
        parquet_path=path,
        symbol=symbol,
        raw_type="contract",
        description=f"Per-contract cache downloaded in session 04. Backfilled manifest.",
        parameters={"source": "TradeStation API"},
    )
    manifest["built_at"] = _mtime_utc(path)
    manifest["backfilled"] = True

    if dry_run:
        logger.info("backfill_dry_run", path=str(path), layer="raw/contract")
        return manifest

    write_manifest(path, manifest)
    return manifest


def backfill_raw_bulk(path: Path, dry_run: bool = False) -> dict | None:
    """Write a manifest for a bulk raw download file (ZN_1m_*, 6A_*, etc.)."""
    if not _needs_backfill(path):
        return None

    # Extract symbol: ZN_1m_2010-01-01_... → "ZN"
    symbol = path.stem.split("_")[0]
    manifest = build_raw_manifest(
        parquet_path=path,
        symbol=symbol,
        raw_type="bulk_download",
        description="Full historical bulk download. Backfilled manifest.",
        parameters={"source": "TradeStation API"},
    )
    manifest["built_at"] = _mtime_utc(path)
    manifest["backfilled"] = True

    if dry_run:
        logger.info("backfill_dry_run", path=str(path), layer="raw/bulk")
        return manifest

    write_manifest(path, manifest)
    return manifest


# ---------------------------------------------------------------------------
# CLEAN layer
# ---------------------------------------------------------------------------

# Pattern: ZN_1m_backadjusted_... or ZN_1m_unadjusted_...
_CLEAN_1M_PATTERN = re.compile(
    r"ZN_1m_(backadjusted|unadjusted)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.parquet$"
)

# Pattern: ZN_backadjusted_{tf}_... where tf is 5m, 15m, etc.
_CLEAN_RESAMPLE_PATTERN = re.compile(
    r"ZN_(backadjusted)_(\d+m|1D|240m)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.parquet$"
)


def backfill_clean_1m(path: Path, contracts_dir: Path, dry_run: bool = False) -> dict | None:
    """Write a manifest for ZN_1m_backadjusted or ZN_1m_unadjusted."""
    if not _needs_backfill(path):
        return None

    m = _CLEAN_1M_PATTERN.match(path.name)
    if not m:
        logger.warning("backfill_clean_1m_unrecognised", path=str(path))
        return None

    adjustment = m.group(1)
    source_paths = sorted(contracts_dir.glob("TY*.parquet"))

    manifest = build_clean_manifest(
        parquet_path=path,
        source_paths=source_paths,
        symbol="ZN",
        timeframe="1m",
        adjustment=adjustment,
        parameters={
            "method": "back_adjusted_continuous" if adjustment == "backadjusted" else "stitched_unadjusted",
            "roll_days_before": 5,
        },
    )
    manifest["built_at"] = _mtime_utc(path)
    manifest["backfilled"] = True

    if dry_run:
        logger.info("backfill_dry_run", path=str(path), layer="clean/1m")
        return manifest

    write_manifest(path, manifest)
    return manifest


def backfill_clean_resample(path: Path, clean_dir: Path, dry_run: bool = False) -> dict | None:
    """Write a manifest for a resampled CLEAN file (5m, 15m, etc.)."""
    if not _needs_backfill(path):
        return None

    m = _CLEAN_RESAMPLE_PATTERN.match(path.name)
    if not m:
        logger.warning("backfill_clean_resample_unrecognised", path=str(path))
        return None

    adjustment = m.group(1)
    timeframe = m.group(2)

    # Source is the 1m backadjusted file
    source_candidates = sorted(clean_dir.glob("ZN_1m_backadjusted_*.parquet"))
    source_paths = source_candidates[:1] if source_candidates else []

    manifest = build_clean_manifest(
        parquet_path=path,
        source_paths=source_paths,
        symbol="ZN",
        timeframe=timeframe,
        adjustment=adjustment,
        parameters={"freq": timeframe.replace("m", "min") if timeframe != "1D" else "1D"},
    )
    manifest["built_at"] = _mtime_utc(path)
    manifest["backfilled"] = True

    if dry_run:
        logger.info("backfill_dry_run", path=str(path), layer=f"clean/{timeframe}")
        return manifest

    write_manifest(path, manifest)
    return manifest


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def backfill_all(data_root: Path = _DATA_ROOT, dry_run: bool = False) -> int:
    """Write manifests for all pre-convention files that lack them.

    Returns the number of manifests written (or that would be written in dry_run).
    """
    count = 0
    contracts_dir = data_root / "raw" / "contracts"
    clean_dir = data_root / "clean"

    # 1. RAW contracts (must go first — CLEAN manifests reference them as sources)
    for path in sorted(contracts_dir.glob("*.parquet")):
        result = backfill_raw_contract(path, dry_run=dry_run)
        if result is not None:
            count += 1
            logger.info("backfilled", path=str(path), dry_run=dry_run)

    # 2. Other RAW files in data/raw/ (bulk downloads, smoke pulls)
    for path in sorted((data_root / "raw").glob("*.parquet")):
        result = backfill_raw_bulk(path, dry_run=dry_run)
        if result is not None:
            count += 1
            logger.info("backfilled", path=str(path), dry_run=dry_run)

    # 3. CLEAN 1m files (must go before resamples)
    for path in sorted(clean_dir.glob("ZN_1m_*.parquet")):
        result = backfill_clean_1m(path, contracts_dir=contracts_dir, dry_run=dry_run)
        if result is not None:
            count += 1
            logger.info("backfilled", path=str(path), dry_run=dry_run)

    # 4. CLEAN resampled files (5m, 15m — 60m/240m/1D already have manifests from session 05)
    for path in sorted(clean_dir.glob("ZN_backadjusted_*.parquet")):
        result = backfill_clean_resample(path, clean_dir=clean_dir, dry_run=dry_run)
        if result is not None:
            count += 1
            logger.info("backfilled", path=str(path), dry_run=dry_run)

    return count
