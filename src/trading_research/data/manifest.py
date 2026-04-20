"""Manifest sidecars for the three-layer data pipeline.

Every parquet file in data/raw/, data/clean/, and data/features/ has a
companion .manifest.json that records its provenance: sources, code commit,
parameters, and build time. This is what lets the pipeline answer "where
did this file come from and is it still fresh?" without human memory.

See docs/pipeline.md for the manifest schema spec and staleness rules.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_research.utils.logging import get_logger

logger = get_logger(__name__)


def manifest_path_for(parquet_path: Path) -> Path:
    """Return the path of the manifest sidecar for a parquet file."""
    return parquet_path.parent / (parquet_path.name + ".manifest.json")


def _current_commit() -> str:
    """Return the current git HEAD commit hash, or 'unknown' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _file_hash(path: Path) -> str:
    """Return the SHA-256 hash of a file (first 16 hex chars, enough to detect change)."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return "unavailable"


def _fast_parquet_stats(parquet_path: Path) -> tuple[int, dict[str, str]]:
    """Read row count and timestamp date range from parquet footer metadata only.

    Reads only the file footer (a few KB) — does not deserialise any row data.
    Falls back to a full column read if statistics are absent.
    """
    import pyarrow.parquet as pq

    try:
        meta = pq.read_metadata(parquet_path)
        row_count = meta.num_rows

        min_ts: Any = None
        max_ts: Any = None
        for rg_idx in range(meta.num_row_groups):
            rg = meta.row_group(rg_idx)
            for col_idx in range(rg.num_columns):
                col = rg.column(col_idx)
                if col.path_in_schema == "timestamp_utc":
                    stats = col.statistics
                    if stats is not None and stats.has_min_max:
                        if min_ts is None or stats.min < min_ts:
                            min_ts = stats.min
                        if max_ts is None or stats.max > max_ts:
                            max_ts = stats.max

        if min_ts is not None and max_ts is not None:
            # Statistics are Arrow timestamps; convert to ISO string
            import pandas as pd

            def _to_iso(v: Any) -> str:
                try:
                    return pd.Timestamp(v).isoformat()
                except Exception:
                    return str(v)

            return row_count, {"start": _to_iso(min_ts), "end": _to_iso(max_ts)}

        # Statistics absent — fall back to reading the column
        tbl = pq.read_table(parquet_path, columns=["timestamp_utc"])
        if tbl.num_rows == 0:
            return row_count, {}
        ts = tbl.column("timestamp_utc").to_pylist()
        ts_sorted = sorted(t for t in ts if t is not None)
        return row_count, {
            "start": ts_sorted[0].isoformat(),
            "end": ts_sorted[-1].isoformat(),
        }
    except Exception:
        return 0, {}


def write_manifest(parquet_path: Path, manifest: dict[str, Any]) -> Path:
    """Write a manifest sidecar JSON next to a parquet file.

    Parameters
    ----------
    parquet_path:
        Path to the parquet file. The manifest is written as
        ``{parquet_path}.manifest.json``.
    manifest:
        Dict conforming to the manifest schema (see docs/pipeline.md).
        ``built_at`` and ``code_commit`` are injected if missing.

    Returns
    -------
    Path of the written manifest file.
    """
    manifest = dict(manifest)
    manifest.setdefault("built_at", datetime.now(tz=timezone.utc).isoformat())
    manifest.setdefault("code_commit", _current_commit())
    manifest.setdefault("schema_version", 1)

    dest = manifest_path_for(parquet_path)
    dest.write_text(json.dumps(manifest, indent=2, default=str))
    logger.info("manifest_written", path=str(dest))
    return dest


def read_manifest(parquet_path: Path) -> dict[str, Any] | None:
    """Read the manifest sidecar for a parquet file.

    Returns None if no manifest exists.
    """
    mp = manifest_path_for(parquet_path)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text())
    except json.JSONDecodeError:
        logger.warning("manifest_invalid_json", path=str(mp))
        return None


def build_raw_manifest(
    parquet_path: Path,
    symbol: str,
    raw_type: str,
    description: str = "",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manifest dict for a RAW layer parquet.

    RAW files have no upstream sources — they are the source of truth.
    The manifest records the file's own stats for staleness detection
    of downstream files.

    Parameters
    ----------
    parquet_path:
        The RAW parquet being described.
    symbol:
        Instrument symbol (e.g., ``"6E"``, ``"EUH25"``).
    raw_type:
        Category string: ``"contract"``, ``"bulk_download"``, or ``"smoke"``.
    description:
        Optional human-readable note about the file's origin.
    parameters:
        Optional dict of acquisition parameters (e.g., date range).
    """
    row_count, date_range = _fast_parquet_stats(parquet_path)

    return {
        "schema_version": 1,
        "layer": "raw",
        "symbol": symbol,
        "raw_type": raw_type,
        "description": description,
        "row_count": row_count,
        "date_range": date_range,
        "sources": [],
        "parameters": parameters or {},
    }


def build_clean_manifest(
    parquet_path: Path,
    source_paths: list[Path],
    symbol: str,
    timeframe: str,
    adjustment: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Build a manifest dict for a CLEAN layer parquet.

    Parameters
    ----------
    parquet_path:
        The CLEAN parquet being described.
    source_paths:
        The RAW source file(s) this was built from.
    symbol:
        Instrument symbol (e.g., ``"6E"``).
    timeframe:
        Bar timeframe string (e.g., ``"5m"``, ``"1D"``).
    adjustment:
        Adjustment type (e.g., ``"backadjusted"``, ``"unadjusted"``).
    parameters:
        Dict of transformation parameters (e.g., ``{"freq": "5min"}``).
    """
    row_count, date_range = _fast_parquet_stats(parquet_path)

    sources = []
    for sp in source_paths:
        src_entry: dict[str, Any] = {"path": str(sp)}
        sm = read_manifest(sp)
        if sm:
            src_entry["built_at"] = sm.get("built_at", "unknown")
            src_entry["row_count"] = sm.get("row_count", "unknown")
        else:
            src_entry["file_hash"] = _file_hash(sp)
        sources.append(src_entry)

    return {
        "schema_version": 1,
        "layer": "clean",
        "symbol": symbol,
        "timeframe": timeframe,
        "adjustment": adjustment,
        "row_count": row_count,
        "date_range": date_range,
        "sources": sources,
        "parameters": parameters,
    }


def build_features_manifest(
    parquet_path: Path,
    source_paths: list[Path],
    symbol: str,
    timeframe: str,
    adjustment: str,
    feature_set_tag: str,
    feature_set_config: Path,
    indicators: list[dict[str, Any]],
    htf_projections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a manifest dict for a FEATURES layer parquet."""
    row_count, date_range = _fast_parquet_stats(parquet_path)

    sources = []
    for sp in source_paths:
        src_entry: dict[str, Any] = {"path": str(sp)}
        sm = read_manifest(sp)
        if sm:
            src_entry["built_at"] = sm.get("built_at", "unknown")
            src_entry["row_count"] = sm.get("row_count", "unknown")
        else:
            src_entry["file_hash"] = _file_hash(sp)
        sources.append(src_entry)

    return {
        "schema_version": 1,
        "layer": "features",
        "symbol": symbol,
        "timeframe": timeframe,
        "adjustment": adjustment,
        "row_count": row_count,
        "date_range": date_range,
        "sources": sources,
        "feature_set_tag": feature_set_tag,
        "feature_set_config": str(feature_set_config),
        "indicators": indicators,
        "htf_projections": htf_projections,
    }


def is_stale(parquet_path: Path) -> tuple[bool, list[str]]:
    """Check whether a parquet's manifest indicates it is stale.

    Returns
    -------
    (is_stale, reasons)
        True + list of reason strings if stale; False + [] if fresh.
        Returns (True, ["NO_MANIFEST"]) if no manifest exists.
    """
    manifest = read_manifest(parquet_path)
    if manifest is None:
        return True, ["NO_MANIFEST"]

    reasons: list[str] = []
    built_at_str = manifest.get("built_at")
    if not built_at_str:
        return True, ["manifest_missing_built_at"]

    try:
        built_at = datetime.fromisoformat(built_at_str)
    except ValueError:
        return True, ["manifest_invalid_built_at"]

    # Check each source
    for src in manifest.get("sources", []):
        src_path_str = src.get("path")
        if not src_path_str:
            continue
        sp = Path(src_path_str)
        if not sp.exists():
            reasons.append(f"source_missing: {sp}")
            continue
        # Check if source has a newer manifest
        src_manifest = read_manifest(sp)
        if src_manifest and src_manifest.get("built_at"):
            try:
                src_built = datetime.fromisoformat(src_manifest["built_at"])
                if src_built > built_at:
                    reasons.append(f"source_newer: {sp}")
            except ValueError:
                pass

    return len(reasons) > 0, reasons
