"""
prep_migration_samples.py

Build a tiny, reviewable migration sample set from the trading-research data
layers. For every .csv or .parquet found under the configured scan roots,
copy the *schema* (column names) plus the first 100 rows into a mirrored
path under ./migration_samples/.

Design goals
------------
- Non-destructive: reads only, never modifies source data.
- Deterministic: same inputs → same outputs.
- Honest about what it dropped: writes migration_samples/MANIFEST.json with
  one entry per source file (path, row count sampled, total row count where
  cheaply known, schema).
- Self-contained: no hard dependency on the trading_research package. Uses
  pandas / pyarrow which are already in pyproject.toml.

Usage
-----
    uv run python prep_migration_samples.py
    uv run python prep_migration_samples.py --rows 200
    uv run python prep_migration_samples.py --root data/clean --root data/features

The output directory is wiped at the start of each run so stale samples do
not accumulate. Pass --no-clean to disable that behavior.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

# Default roots to scan. Order matters only for readability in the manifest.
DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "data/raw",
    "data/clean",
    "data/features",
    "runs",
)

OUTPUT_DIR_NAME = "migration_samples"
DEFAULT_ROW_COUNT = 100
SUPPORTED_SUFFIXES = {".csv", ".parquet"}


# -----------------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------------


@dataclass
class SampleRecord:
    """One entry in the output manifest."""

    source: str           # path relative to project root
    destination: str      # path relative to project root
    suffix: str
    rows_sampled: int
    total_rows: int | None  # None when computing full count would be expensive
    columns: list[str]
    dtypes: dict[str, str]
    error: str | None = None


# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------


def iter_source_files(roots: Iterable[Path]) -> list[Path]:
    """Yield every .csv or .parquet under the given roots, sorted."""

    found: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"[skip] scan root missing: {root}", file=sys.stderr)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            found.append(path)
    # Stable ordering — makes the manifest diffable across runs.
    found.sort()
    return found


def sample_csv(source: Path, n_rows: int) -> tuple[pd.DataFrame, int | None]:
    """Read the first n_rows of a CSV. Total row count is not computed (costly
    on large CSVs); returned as None."""

    df = pd.read_csv(source, nrows=n_rows)
    return df, None


def sample_parquet(source: Path, n_rows: int) -> tuple[pd.DataFrame, int | None]:
    """Read the first n_rows of a parquet file. Parquet metadata carries the
    total row count cheaply, so we return it."""

    import pyarrow.parquet as pq

    pf = pq.ParquetFile(source)
    total_rows = pf.metadata.num_rows if pf.metadata is not None else None

    # Read only as many row groups as we need to satisfy n_rows.
    collected: list[pd.DataFrame] = []
    rows_so_far = 0
    for rg_index in range(pf.num_row_groups):
        rg_df = pf.read_row_group(rg_index).to_pandas()
        collected.append(rg_df)
        rows_so_far += len(rg_df)
        if rows_so_far >= n_rows:
            break

    if not collected:
        return pd.DataFrame(), total_rows

    df = pd.concat(collected, ignore_index=True).head(n_rows)
    return df, total_rows


def write_sample(df: pd.DataFrame, destination: Path) -> None:
    """Write the sampled frame back out in the same format as the source."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() == ".csv":
        df.to_csv(destination, index=False)
    elif destination.suffix.lower() == ".parquet":
        # Use pyarrow implicitly via pandas. Keep it simple — these files are
        # meant to be human-inspectable samples, not performance-tuned.
        df.to_parquet(destination, index=False)
    else:  # pragma: no cover — guarded by SUPPORTED_SUFFIXES
        raise ValueError(f"unsupported suffix: {destination.suffix}")


def process_file(source: Path, output_root: Path, n_rows: int) -> SampleRecord:
    """Sample one source file. Errors are caught and recorded in the manifest
    so a single unreadable file does not abort the whole run."""

    rel = source.relative_to(PROJECT_ROOT)
    destination = output_root / rel

    try:
        if source.suffix.lower() == ".csv":
            df, total = sample_csv(source, n_rows)
        else:
            df, total = sample_parquet(source, n_rows)

        write_sample(df, destination)

        return SampleRecord(
            source=rel.as_posix(),
            destination=destination.relative_to(PROJECT_ROOT).as_posix(),
            suffix=source.suffix.lower(),
            rows_sampled=len(df),
            total_rows=total,
            columns=list(df.columns),
            dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — we intentionally record any failure
        return SampleRecord(
            source=rel.as_posix(),
            destination=destination.relative_to(PROJECT_ROOT).as_posix(),
            suffix=source.suffix.lower(),
            rows_sampled=0,
            total_rows=None,
            columns=[],
            dtypes={},
            error=f"{type(exc).__name__}: {exc}",
        )


def write_manifest(records: list[SampleRecord], output_root: Path, n_rows: int) -> Path:
    """Emit migration_samples/MANIFEST.json summarizing the sample run."""

    manifest_path = output_root / "MANIFEST.json"
    manifest = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "rows_per_file": n_rows,
        "file_count": len(records),
        "ok_count": sum(1 for r in records if r.error is None),
        "error_count": sum(1 for r in records if r.error is not None),
        "files": [asdict(r) for r in records],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a header + first-N-rows sample set from trading-research "
            "data layers for migration review."
        )
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROW_COUNT,
        help=f"rows to sample per file (default: {DEFAULT_ROW_COUNT})",
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        help=(
            "scan root (relative to project). May be repeated. "
            f"Default: {', '.join(DEFAULT_SCAN_ROOTS)}"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_DIR_NAME,
        help=f"output directory name (default: {OUTPUT_DIR_NAME})",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="do not wipe the output directory at the start of the run",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    scan_roots = [PROJECT_ROOT / r for r in (args.roots or DEFAULT_SCAN_ROOTS)]
    output_root = PROJECT_ROOT / args.output

    if output_root.exists() and not args.no_clean:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    sources = iter_source_files(scan_roots)
    if not sources:
        print("No .csv or .parquet files found under scan roots.", file=sys.stderr)
        write_manifest([], output_root, args.rows)
        return 0

    print(f"Scanning {len(sources)} files; sampling {args.rows} rows each.")

    records: list[SampleRecord] = []
    for i, source in enumerate(sources, start=1):
        rec = process_file(source, output_root, args.rows)
        records.append(rec)
        status = "OK" if rec.error is None else f"ERR ({rec.error})"
        print(f"[{i:>4}/{len(sources)}] {rec.source} → {status}")

    manifest_path = write_manifest(records, output_root, args.rows)
    ok = sum(1 for r in records if r.error is None)
    err = len(records) - ok
    print(f"\nDone. {ok} sampled, {err} failed. Manifest: {manifest_path}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
