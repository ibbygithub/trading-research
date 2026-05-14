"""Verify pipeline: walk all parquet files in RAW/CLEAN/FEATURES and report manifest health."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from trading_research.data.manifest import is_stale, manifest_path_for
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

_DATA_ROOT = Path(__file__).parents[3] / "data"


@dataclass
class FileStatus:
    path: Path
    has_manifest: bool
    stale: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.has_manifest and not self.stale


@dataclass
class LayerResult:
    layer: str
    files: list[FileStatus] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.files)

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.files if f.ok)

    @property
    def stale_count(self) -> int:
        return sum(1 for f in self.files if f.has_manifest and f.stale)

    @property
    def missing_manifest_count(self) -> int:
        return sum(1 for f in self.files if not f.has_manifest)


@dataclass
class VerifyResult:
    layers: list[LayerResult] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return sum(lr.total for lr in self.layers)

    @property
    def total_ok(self) -> int:
        return sum(lr.ok_count for lr in self.layers)

    @property
    def total_stale(self) -> int:
        return sum(lr.stale_count for lr in self.layers)

    @property
    def total_missing(self) -> int:
        return sum(lr.missing_manifest_count for lr in self.layers)

    @property
    def clean(self) -> bool:
        return self.total_stale == 0 and self.total_missing == 0


def _check_file(path: Path) -> FileStatus:
    mp = manifest_path_for(path)
    if not mp.exists():
        return FileStatus(path=path, has_manifest=False, stale=True, reasons=["NO_MANIFEST"])
    stale, reasons = is_stale(path)
    return FileStatus(path=path, has_manifest=True, stale=stale, reasons=reasons)


def _scan_layer(layer_dir: Path, layer_name: str) -> LayerResult:
    result = LayerResult(layer=layer_name)
    if not layer_dir.exists():
        return result

    # Walk all subdirectories (e.g. raw/contracts/)
    for parquet in sorted(layer_dir.rglob("*.parquet")):
        result.files.append(_check_file(parquet))

    logger.info("layer_scanned", layer=layer_name, files=result.total)
    return result


def verify_all(data_root: Path = _DATA_ROOT) -> VerifyResult:
    """Walk all three data layers and return a VerifyResult.

    The caller is responsible for printing results and determining exit code.
    """
    logger.info("verify_start", stage="verify", action="start", outcome="ok")
    result = VerifyResult()
    for layer_name, subdir in [("RAW", "raw"), ("CLEAN", "clean"), ("FEATURES", "features")]:
        result.layers.append(_scan_layer(data_root / subdir, layer_name))
    logger.info(
        "verify_complete",
        stage="verify",
        action="finish",
        outcome="ok" if result.clean else "warning",
        clean=result.clean,
        layers=len(result.layers),
    )
    return result


def print_verify_result(result: VerifyResult) -> None:
    """Print a human-readable verify report to stdout."""
    for lr in result.layers:
        stale_msg = f"  {lr.stale_count} STALE" if lr.stale_count else ""
        missing_msg = f"  {lr.missing_manifest_count} NO MANIFEST" if lr.missing_manifest_count else ""
        print(f"{lr.layer:<10} {lr.total:>4} files   {lr.ok_count:>4} OK{stale_msg}{missing_msg}")

        for fs in lr.files:
            if not fs.ok:
                print(f"  {fs.path}")
                for reason in fs.reasons:
                    print(f"    {reason}")

    print()
    summary_parts = [f"{result.total_files} files total", f"{result.total_ok} OK"]
    if result.total_stale:
        summary_parts.append(f"{result.total_stale} stale")
    if result.total_missing:
        summary_parts.append(f"{result.total_missing} missing manifests")
    print("Summary: " + ", ".join(summary_parts) + ".")
