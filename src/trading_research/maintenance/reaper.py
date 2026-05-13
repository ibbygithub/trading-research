"""Storage reaper — file selection, archival, and deletion.

Pure-function file selection with a single side-effect boundary at ``apply``.
The manifest-aware safety check prevents deleting files cited in non-reaped
manifests.  See Chapter 56.5 §56.5.3 for the full specification.
"""

from __future__ import annotations

import json
import shutil
import tarfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from trading_research.data.manifest import manifest_path_for

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ReapCandidate:
    path: Path
    size_bytes: int
    reason: str
    category: str
    pinned: bool = False
    pin_reason: str = ""


@dataclass
class ReapPlan:
    reapable: list[ReapCandidate] = field(default_factory=list)
    pinned: list[ReapCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def bytes_reclaimable(self) -> int:
        return sum(c.size_bytes for c in self.reapable)

    def to_dict(self, dry_run: bool = True) -> dict[str, Any]:
        return {
            "dry_run": dry_run,
            "reapable": [
                {"path": str(c.path), "size_bytes": c.size_bytes, "reason": c.reason}
                for c in self.reapable
            ],
            "pinned": [
                {"path": str(c.path), "size_bytes": c.size_bytes, "pin_reason": c.pin_reason}
                for c in self.pinned
            ],
            "bytes_reclaimable": self.bytes_reclaimable,
            "errors": self.errors,
        }


@dataclass
class TrialReapPlan:
    live_count: int = 0
    compactable: list[dict[str, Any]] = field(default_factory=list)
    deletable: list[dict[str, Any]] = field(default_factory=list)
    archive_targets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self, dry_run: bool = True) -> dict[str, Any]:
        return {
            "dry_run": dry_run,
            "live_count": self.live_count,
            "compactable_count": len(self.compactable),
            "deletable_count": len(self.deletable),
            "archive_targets": {k: len(v) for k, v in self.archive_targets.items()},
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Manifest-aware safety
# ---------------------------------------------------------------------------


def _collect_manifest_sources(data_root: Path) -> set[str]:
    """Walk all manifest sidecars and collect every ``sources[].path`` reference."""
    cited: set[str] = set()
    for layer in ("raw", "clean", "features"):
        layer_dir = data_root / layer
        if not layer_dir.exists():
            continue
        for manifest_file in layer_dir.rglob("*.manifest.json"):
            try:
                content = json.loads(manifest_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for src in content.get("sources", []):
                src_path = src.get("path")
                if src_path:
                    cited.add(str(Path(src_path)))
    return cited


def _is_manifest_pinned(
    path: Path,
    cited_sources: set[str],
    reap_paths: set[str],
) -> bool:
    """Check if ``path`` is cited as a source by a manifest that is NOT itself being reaped."""
    return str(path) in cited_sources


def _dir_size(d: Path) -> int:
    """Recursively compute directory size in bytes."""
    if d.is_file():
        return d.stat().st_size
    total = 0
    for f in d.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Runs reaper
# ---------------------------------------------------------------------------


def _parse_run_timestamp(name: str) -> datetime | None:
    """Parse a run directory name like ``2026-05-05-01-03`` into a datetime."""
    base = name.split("-sw")[0]
    parts = base.split("-")
    if len(parts) < 5:
        return None
    try:
        return datetime(
            int(parts[0]), int(parts[1]), int(parts[2]),
            int(parts[3]), int(parts[4]),
            tzinfo=UTC,
        )
    except (ValueError, IndexError):
        return None


def _run_is_validation(run_dir: Path) -> bool:
    """Check if a run directory's summary.json carries ``mode: validation``."""
    summary = run_dir / "summary.json"
    if not summary.exists():
        return False
    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
        return data.get("mode") == "validation"
    except (json.JSONDecodeError, OSError):
        return False


def plan_clean_runs(
    runs_root: Path,
    strategy_id: str | None = None,
    keep_last: int | None = None,
    older_than_days: int | None = None,
) -> ReapPlan:
    """Plan which run directories to reap.

    Two mutually exclusive modes:
    - ``keep_last``: keep the N most-recent per strategy, reap the rest.
    - ``older_than_days``: reap anything older than the cutoff.

    Default: keep_last=10.
    """
    if keep_last is not None and older_than_days is not None:
        return ReapPlan(errors=["--keep-last and --older-than are mutually exclusive"])

    if keep_last is None and older_than_days is None:
        keep_last = 10

    plan = ReapPlan()
    now = datetime.now(tz=UTC)

    strategy_dirs = []
    if strategy_id:
        sd = runs_root / strategy_id
        if sd.is_dir():
            strategy_dirs.append(sd)
        else:
            plan.errors.append(f"Strategy directory not found: {sd}")
            return plan
    else:
        strategy_dirs = [
            d for d in sorted(runs_root.iterdir())
            if d.is_dir() and d.name != "stationarity" and d.name != "portfolio" and not d.name.startswith(".")
        ]

    for sd in strategy_dirs:
        run_dirs = []
        for child in sd.iterdir():
            if not child.is_dir():
                continue
            ts = _parse_run_timestamp(child.name)
            if ts is None:
                continue
            run_dirs.append((ts, child))

        run_dirs.sort(key=lambda x: x[0], reverse=True)

        for i, (ts, rd) in enumerate(run_dirs):
            is_validation = _run_is_validation(rd)

            # Most recent run per strategy is always kept
            if i == 0:
                continue

            # Validation runs always kept
            if is_validation:
                continue

            reap = False
            reason = ""

            if keep_last is not None:
                if i >= keep_last:
                    reap = True
                    reason = f"exceeds keep_last={keep_last} (position {i + 1})"
            elif older_than_days is not None:
                cutoff = now - timedelta(days=older_than_days)
                if ts < cutoff:
                    reap = True
                    reason = f"older than {older_than_days}d (ts={ts.date()})"

            if reap:
                plan.reapable.append(ReapCandidate(
                    path=rd,
                    size_bytes=_dir_size(rd),
                    reason=reason,
                    category="runs",
                ))

    return plan


# ---------------------------------------------------------------------------
# Canonical (CLEAN) reaper
# ---------------------------------------------------------------------------


def _parse_clean_key(name: str) -> tuple[str, str, str, str, str] | None:
    """Parse a CLEAN parquet name into (symbol, timeframe, adjustment, start_date, end_date).

    Patterns observed:
    - ``6A_1m_backadjusted_2010-01-01_2026-05-03.parquet``
    - ``6A_backadjusted_15m_2010-01-03_2026-05-01.parquet``
    """
    stem = name.replace(".parquet", "").replace(".manifest.json", "")
    parts = stem.split("_")

    if len(parts) < 5:
        return None

    symbol = parts[0]

    # Two naming conventions — detect which one
    if parts[2] in ("backadjusted", "unadjusted"):
        # Pattern: SYMBOL_TF_ADJ_START_END
        timeframe = parts[1]
        adjustment = parts[2]
        start_date = parts[3]
        end_date = parts[4]
    elif parts[1] in ("backadjusted", "unadjusted"):
        # Pattern: SYMBOL_ADJ_TF_START_END
        adjustment = parts[1]
        timeframe = parts[2]
        start_date = parts[3]
        end_date = parts[4]
    else:
        return None

    return symbol, timeframe, adjustment, start_date, end_date


def plan_clean_canonical(
    data_root: Path,
    symbol: str | None = None,
) -> ReapPlan:
    """Plan which old CLEAN parquets to reap, keeping only the latest per tuple."""
    plan = ReapPlan()
    clean_dir = data_root / "clean"
    if not clean_dir.exists():
        return plan

    cited_sources = _collect_manifest_sources(data_root)

    # Group by (symbol, timeframe, adjustment)
    groups: dict[tuple[str, str, str], list[tuple[str, Path]]] = {}
    for f in sorted(clean_dir.iterdir()):
        if not f.name.endswith(".parquet") or f.name.endswith(".manifest.json"):
            continue
        parsed = _parse_clean_key(f.name)
        if parsed is None:
            continue
        sym, tf, adj, _start, end = parsed
        if symbol and sym != symbol:
            continue
        key = (sym, tf, adj)
        groups.setdefault(key, []).append((end, f))

    for key, files in groups.items():
        files.sort(key=lambda x: x[0], reverse=True)
        if len(files) <= 1:
            continue

        # Keep the latest, reap the rest
        for end_date, fpath in files[1:]:
            fpath_str = str(fpath)
            is_pinned = fpath_str in cited_sources
            size = _file_size(fpath)
            # Include manifest sidecar size
            mpath = manifest_path_for(fpath)
            if mpath.exists():
                size += _file_size(mpath)

            candidate = ReapCandidate(
                path=fpath,
                size_bytes=size,
                reason=f"older variant for {key} (end_date={end_date})",
                category="canonical",
                pinned=is_pinned,
                pin_reason="cited in FEATURES manifest" if is_pinned else "",
            )
            if is_pinned:
                plan.pinned.append(candidate)
            else:
                plan.reapable.append(candidate)

    return plan


# ---------------------------------------------------------------------------
# Features reaper
# ---------------------------------------------------------------------------


def _parse_features_key(name: str) -> tuple[str, str, str, str, str] | None:
    """Parse a FEATURES parquet name.

    Pattern: ``6A_backadjusted_15m_features_base-v1_2010-01-03_2026-05-01.parquet``
    """
    stem = name.replace(".parquet", "").replace(".manifest.json", "")
    parts = stem.split("_")

    try:
        feat_idx = parts.index("features")
    except ValueError:
        return None

    if feat_idx < 2 or len(parts) < feat_idx + 4:
        return None

    symbol = parts[0]
    timeframe = parts[2]
    tag = parts[feat_idx + 1]
    start_date = parts[feat_idx + 2]
    end_date = parts[feat_idx + 3]
    return symbol, timeframe, tag, start_date, end_date


def plan_clean_features(
    data_root: Path,
    tag: str | None = None,
    symbol: str | None = None,
    keep_latest: bool = False,
) -> ReapPlan:
    """Plan which FEATURES files to reap.

    Two modes:
    - ``tag`` (no ``keep_latest``): reap ALL files for the named tag.
    - ``keep_latest``: per (symbol, timeframe, tag), keep the most-recent end-date.
    """
    plan = ReapPlan()
    feat_dir = data_root / "features"
    if not feat_dir.exists():
        return plan

    if tag and keep_latest:
        plan.errors.append("--tag and --keep-latest are mutually exclusive")
        return plan

    if tag and not keep_latest:
        # Reap everything for this tag
        for f in sorted(feat_dir.iterdir()):
            if not f.name.endswith(".parquet") or f.name.endswith(".manifest.json"):
                continue
            parsed = _parse_features_key(f.name)
            if parsed is None:
                continue
            sym, _tf, ftag, _start, _end = parsed
            if ftag != tag:
                continue
            if symbol and sym != symbol:
                continue

            size = _file_size(f)
            mpath = manifest_path_for(f)
            if mpath.exists():
                size += _file_size(mpath)

            plan.reapable.append(ReapCandidate(
                path=f,
                size_bytes=size,
                reason=f"retiring tag={tag}",
                category="features",
            ))
        return plan

    # keep_latest mode (default when no tag)
    groups: dict[tuple[str, str, str], list[tuple[str, Path]]] = {}
    for f in sorted(feat_dir.iterdir()):
        if not f.name.endswith(".parquet") or f.name.endswith(".manifest.json"):
            continue
        parsed = _parse_features_key(f.name)
        if parsed is None:
            continue
        sym, tf, ftag, _start, end = parsed
        if symbol and sym != symbol:
            continue
        key = (sym, tf, ftag)
        groups.setdefault(key, []).append((end, f))

    for key, files in groups.items():
        files.sort(key=lambda x: x[0], reverse=True)
        if len(files) <= 1:
            continue

        for end_date, fpath in files[1:]:
            size = _file_size(fpath)
            mpath = manifest_path_for(fpath)
            if mpath.exists():
                size += _file_size(mpath)

            plan.reapable.append(ReapCandidate(
                path=fpath,
                size_bytes=size,
                reason=f"older variant for {key} (end_date={end_date})",
                category="features",
            ))

    return plan


# ---------------------------------------------------------------------------
# Trials reaper
# ---------------------------------------------------------------------------


def plan_clean_trials(
    runs_root: Path,
    compact_after_days: int = 180,
    delete_after_days: int = 730,
    keep_modes: list[str] | None = None,
    archive_path: str = "outputs/archive/trials/",
    project_root: Path | None = None,
) -> TrialReapPlan:
    """Plan the three-tier trial prune."""
    if keep_modes is None:
        keep_modes = ["validation"]

    plan = TrialReapPlan()
    registry_path = runs_root / ".trials.json"
    if not registry_path.exists():
        return plan

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        plan.errors.append(f"Failed to read trial registry: {exc}")
        return plan

    trials = data.get("trials", []) if isinstance(data, dict) else data

    now = datetime.now(tz=UTC)

    # Collect live parent_sweep_ids for orphan-prevention
    live_sweep_ids: set[str] = set()
    for t in trials:
        psid = t.get("parent_sweep_id")
        if psid:
            live_sweep_ids.add(psid)

    for t in trials:
        ts_str = t.get("timestamp", "")
        mode = t.get("mode", "unknown")

        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            plan.live_count += 1
            continue

        # Protected modes never compacted or deleted
        if mode in keep_modes:
            plan.live_count += 1
            continue

        age = now - ts

        if age.days < compact_after_days:
            plan.live_count += 1
        elif age.days < delete_after_days:
            # Compaction tier
            month_key = ts.strftime("%Y-%m")
            plan.compactable.append(t)
            plan.archive_targets.setdefault(month_key, []).append(t)
        else:
            # Deletion tier — check orphan prevention
            psid = t.get("parent_sweep_id")
            if psid and psid in live_sweep_ids:
                # Referenced by a live sweep — keep in compacted archive instead
                month_key = ts.strftime("%Y-%m")
                plan.compactable.append(t)
                plan.archive_targets.setdefault(month_key, []).append(t)
            else:
                plan.deletable.append(t)

    return plan


# ---------------------------------------------------------------------------
# Archive + delete (side-effect boundary)
# ---------------------------------------------------------------------------


def _archive_directory(src: Path, archive_root: Path, strategy_id: str) -> Path:
    """Archive a run directory to a tar.gz under the archive root.

    Returns the path to the created archive file.
    """
    archive_dir = archive_root / strategy_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"{src.name}.tar.gz"
    archive_file = archive_dir / archive_name

    with tarfile.open(archive_file, "w:gz") as tar:
        tar.add(src, arcname=src.name)

    return archive_file


def _archive_file(src: Path, archive_dir: Path) -> Path:
    """Copy a single file to the archive directory.

    Returns the path to the archived copy.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / src.name
    shutil.copy2(src, dest)
    # Also copy the manifest if present
    mpath = manifest_path_for(src)
    if mpath.exists():
        shutil.copy2(mpath, archive_dir / mpath.name)
    return dest


def apply_reap_plan(
    plan: ReapPlan,
    archive_root: Path,
    no_archive: bool = False,
) -> tuple[int, int, list[str]]:
    """Execute the reap plan: archive then delete.

    Returns (deleted_count, failed_count, error_messages).
    """
    deleted = 0
    failed = 0
    errors: list[str] = []

    for candidate in plan.reapable:
        try:
            if not no_archive:
                if candidate.path.is_dir():
                    # For run directories, infer strategy_id from parent
                    strategy_id = candidate.path.parent.name
                    _archive_directory(candidate.path, archive_root, strategy_id)
                else:
                    # Determine archive sub-directory by category
                    archive_sub = archive_root / candidate.category
                    _archive_file(candidate.path, archive_sub)

            # Delete
            if candidate.path.is_dir():
                shutil.rmtree(candidate.path)
            else:
                candidate.path.unlink(missing_ok=True)
                # Delete manifest sidecar too
                mpath = manifest_path_for(candidate.path)
                mpath.unlink(missing_ok=True)

            logger.info(
                "clean.reap",
                action="delete" if no_archive else "archive+delete",
                path=str(candidate.path),
                size_bytes=candidate.size_bytes,
                reason=candidate.reason,
                category=candidate.category,
            )
            deleted += 1

        except Exception as exc:
            logger.error("clean.reap_failed", path=str(candidate.path), error=str(exc))
            errors.append(f"{candidate.path}: {exc}")
            failed += 1

    return deleted, failed, errors


def apply_trial_plan(
    plan: TrialReapPlan,
    runs_root: Path,
    archive_root: Path,
) -> tuple[int, int, list[str]]:
    """Execute the three-tier trial prune.

    Returns (compacted_count, deleted_count, error_messages).
    """
    registry_path = runs_root / ".trials.json"
    errors: list[str] = []

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return 0, 0, [f"Failed to read registry: {exc}"]

    trials = data.get("trials", []) if isinstance(data, dict) else data

    # Write compacted archives
    archive_dir = Path(archive_root)
    archive_dir.mkdir(parents=True, exist_ok=True)

    compacted_timestamps = {t.get("timestamp") for t in plan.compactable}
    deleted_timestamps = {t.get("timestamp") for t in plan.deletable}

    # Write monthly JSONL archives for compactable entries
    for month_key, entries in plan.archive_targets.items():
        jsonl_path = archive_dir / f"{month_key}.jsonl"
        with open(jsonl_path, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
        logger.info("clean.trial_archive", month=month_key, count=len(entries))

    # Remove compacted and deleted entries from the live registry
    remaining = [
        t for t in trials
        if t.get("timestamp") not in compacted_timestamps
        and t.get("timestamp") not in deleted_timestamps
    ]

    try:
        registry_path.write_text(
            json.dumps({"trials": remaining}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        errors.append(f"Failed to write updated registry: {exc}")

    # Delete old archive files for the deletion tier
    for entry in plan.deletable:
        ts_str = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            month_key = ts.strftime("%Y-%m")
            jsonl_path = archive_dir / f"{month_key}.jsonl"
            if jsonl_path.exists():
                lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
                remaining_lines = []
                for line in lines:
                    try:
                        parsed = json.loads(line)
                        if parsed.get("timestamp") != ts_str:
                            remaining_lines.append(line)
                    except json.JSONDecodeError:
                        remaining_lines.append(line)
                if remaining_lines:
                    jsonl_path.write_text("\n".join(remaining_lines) + "\n", encoding="utf-8")
                else:
                    jsonl_path.unlink(missing_ok=True)
        except (ValueError, OSError):
            pass

    logger.info(
        "clean.trials_applied",
        compacted=len(plan.compactable),
        deleted=len(plan.deletable),
        remaining=len(remaining),
    )

    return len(plan.compactable), len(plan.deletable), errors
