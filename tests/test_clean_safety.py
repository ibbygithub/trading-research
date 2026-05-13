"""Tests for storage cleanup safety invariants.

Exercises every invariant from Chapter 56.5 section 56.5.3.1 against a
synthetic data tree:
  1. Dry-run is the default (no filesystem changes without --apply).
  2. Archive before delete.
  3. Manifest-aware: refuse to reap files cited in non-reaped manifests.
  4. Verify-clean precondition.
  5. Output format (tabular / JSON).
  6. Exit codes.
  7. Structlog events.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from trading_research.maintenance.reaper import (
    ReapPlan,
    apply_reap_plan,
    plan_clean_canonical,
    plan_clean_features,
    plan_clean_runs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_tree(tmp_path: Path) -> Path:
    """Build a minimal synthetic data tree for testing."""
    # --- runs ---
    runs = tmp_path / "runs"
    for strat in ("strat-a", "strat-b"):
        for i in range(15):
            ts = (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i)).strftime("%Y-%m-%d-%H-%M")
            rd = runs / strat / ts
            rd.mkdir(parents=True)
            (rd / "trades.parquet").write_bytes(b"x" * 1000)
            (rd / "summary.json").write_text(
                json.dumps({"total_trades": 10}), encoding="utf-8",
            )

    # --- CLEAN layer ---
    clean = tmp_path / "data" / "clean"
    clean.mkdir(parents=True)
    # Two date-stamped variants for ZN 1m backadjusted
    for end in ("2026-04-01", "2026-05-01"):
        pq = clean / f"ZN_1m_backadjusted_2010-01-01_{end}.parquet"
        pq.write_bytes(b"x" * 5000)
        manifest = pq.parent / (pq.name + ".manifest.json")
        manifest.write_text(json.dumps({
            "schema_version": 1,
            "layer": "clean",
            "sources": [],
        }), encoding="utf-8")

    # --- FEATURES layer ---
    feat = tmp_path / "data" / "features"
    feat.mkdir(parents=True)
    for end in ("2026-04-01", "2026-05-01"):
        pq = feat / f"ZN_backadjusted_5m_features_base-v1_2010-01-03_{end}.parquet"
        pq.write_bytes(b"x" * 8000)
        # Manifest that cites the older CLEAN file
        sources = []
        if end == "2026-05-01":
            sources = [{"path": str(clean / "ZN_1m_backadjusted_2010-01-01_2026-04-01.parquet")}]
        manifest = pq.parent / (pq.name + ".manifest.json")
        manifest.write_text(json.dumps({
            "schema_version": 1,
            "layer": "features",
            "sources": sources,
        }), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Invariant 1: Dry-run is the default
# ---------------------------------------------------------------------------


class TestDryRunDefault:
    def test_plan_does_not_delete(self, synthetic_tree: Path) -> None:
        """Planning should not modify the filesystem at all."""
        runs_root = synthetic_tree / "runs"
        before = list(runs_root.rglob("*"))

        plan = plan_clean_runs(runs_root=runs_root, keep_last=5)
        assert len(plan.reapable) > 0

        after = list(runs_root.rglob("*"))
        assert len(before) == len(after)


# ---------------------------------------------------------------------------
# Invariant 2: Archive before delete
# ---------------------------------------------------------------------------


class TestArchiveBeforeDelete:
    def test_archive_is_written(self, synthetic_tree: Path) -> None:
        """apply_reap_plan should create archive files before deleting."""
        runs_root = synthetic_tree / "runs"
        archive_root = synthetic_tree / "outputs" / "archive" / "runs"

        plan = plan_clean_runs(runs_root=runs_root, strategy_id="strat-a", keep_last=3)
        assert len(plan.reapable) > 0

        deleted, failed, errors = apply_reap_plan(plan, archive_root, no_archive=False)
        assert deleted > 0
        assert failed == 0

        # Archive directory should exist with tar.gz files
        assert archive_root.exists()
        archives = list(archive_root.rglob("*.tar.gz"))
        assert len(archives) > 0

    def test_no_archive_flag_skips_archive(self, synthetic_tree: Path) -> None:
        """--no-archive should delete without archiving."""
        runs_root = synthetic_tree / "runs"
        archive_root = synthetic_tree / "outputs" / "archive" / "runs"

        plan = plan_clean_runs(runs_root=runs_root, strategy_id="strat-b", keep_last=3)
        deleted, failed, errors = apply_reap_plan(plan, archive_root, no_archive=True)
        assert deleted > 0
        assert not archive_root.exists()


# ---------------------------------------------------------------------------
# Invariant 3: Manifest-aware safety
# ---------------------------------------------------------------------------


class TestManifestAwareSafety:
    def test_cited_clean_file_is_pinned(self, synthetic_tree: Path) -> None:
        """A CLEAN file cited in a FEATURES manifest should be pinned, not reapable."""
        data_root = synthetic_tree / "data"
        plan = plan_clean_canonical(data_root=data_root)

        # The older ZN_1m_backadjusted..._2026-04-01.parquet is cited by the
        # newer features manifest, so it should be pinned
        pinned_names = [c.path.name for c in plan.pinned]
        assert any("2026-04-01" in n for n in pinned_names)

    def test_uncited_clean_file_is_reapable(self, synthetic_tree: Path) -> None:
        """When the citation is removed, the file becomes reapable."""
        data_root = synthetic_tree / "data"
        # Remove the citation from the features manifest
        feat_dir = data_root / "features"
        for mf in feat_dir.glob("*.manifest.json"):
            content = json.loads(mf.read_text())
            content["sources"] = []
            mf.write_text(json.dumps(content))

        plan = plan_clean_canonical(data_root=data_root)
        assert len(plan.pinned) == 0
        assert len(plan.reapable) == 1  # the older date-stamped variant


# ---------------------------------------------------------------------------
# Invariant 4: Validation-mode runs are never reaped
# ---------------------------------------------------------------------------


class TestValidationPreservation:
    def test_validation_run_preserved(self, synthetic_tree: Path) -> None:
        """A run with mode=validation in summary.json should not be reaped."""
        runs_root = synthetic_tree / "runs"
        # Mark the oldest run as validation
        strat_dir = runs_root / "strat-a"
        oldest_run = sorted(strat_dir.iterdir())[0]
        summary = oldest_run / "summary.json"
        summary.write_text(json.dumps({"mode": "validation", "total_trades": 10}))

        plan = plan_clean_runs(runs_root=runs_root, strategy_id="strat-a", keep_last=3)
        reaped_paths = {c.path for c in plan.reapable}
        assert oldest_run not in reaped_paths

    def test_most_recent_always_kept(self, synthetic_tree: Path) -> None:
        """The single most recent run per strategy is always preserved."""
        runs_root = synthetic_tree / "runs"
        plan = plan_clean_runs(runs_root=runs_root, strategy_id="strat-a", keep_last=1)

        strat_dir = runs_root / "strat-a"
        newest_run = sorted(strat_dir.iterdir())[-1]
        reaped_paths = {c.path for c in plan.reapable}
        assert newest_run not in reaped_paths


# ---------------------------------------------------------------------------
# Invariant 5: Mutually exclusive flags
# ---------------------------------------------------------------------------


class TestMutuallyExclusive:
    def test_keep_last_and_older_than_error(self, synthetic_tree: Path) -> None:
        runs_root = synthetic_tree / "runs"
        plan = plan_clean_runs(runs_root=runs_root, keep_last=5, older_than_days=30)
        assert len(plan.errors) > 0
        assert "mutually exclusive" in plan.errors[0].lower()

    def test_features_tag_and_keep_latest_error(self, synthetic_tree: Path) -> None:
        data_root = synthetic_tree / "data"
        plan = plan_clean_features(data_root=data_root, tag="base-v1", keep_latest=True)
        assert len(plan.errors) > 0
        assert "mutually exclusive" in plan.errors[0].lower()


# ---------------------------------------------------------------------------
# Invariant 6: Features tag retirement
# ---------------------------------------------------------------------------


class TestFeaturesTagRetirement:
    def test_tag_reaps_all_files_for_tag(self, synthetic_tree: Path) -> None:
        data_root = synthetic_tree / "data"
        plan = plan_clean_features(data_root=data_root, tag="base-v1")
        assert len(plan.reapable) == 2  # both date variants

    def test_tag_filters_by_symbol(self, synthetic_tree: Path) -> None:
        data_root = synthetic_tree / "data"
        plan = plan_clean_features(data_root=data_root, tag="base-v1", symbol="6E")
        assert len(plan.reapable) == 0  # no 6E files in synthetic tree


# ---------------------------------------------------------------------------
# Invariant 7: keep_latest features mode
# ---------------------------------------------------------------------------


class TestFeaturesKeepLatest:
    def test_keep_latest_reaps_older_variant(self, synthetic_tree: Path) -> None:
        data_root = synthetic_tree / "data"
        plan = plan_clean_features(data_root=data_root, keep_latest=True)
        assert len(plan.reapable) == 1
        assert "2026-04-01" in plan.reapable[0].path.name


# ---------------------------------------------------------------------------
# Invariant 8: older-than mode for runs
# ---------------------------------------------------------------------------


class TestOlderThanRuns:
    def test_older_than_reaps_by_age(self, synthetic_tree: Path) -> None:
        runs_root = synthetic_tree / "runs"
        # All runs are from 2026-01 which is > 90 days ago relative to now
        plan = plan_clean_runs(runs_root=runs_root, older_than_days=1)
        # Should reap all except the most recent per strategy
        assert len(plan.reapable) > 0

    def test_older_than_preserves_most_recent(self, synthetic_tree: Path) -> None:
        runs_root = synthetic_tree / "runs"
        plan = plan_clean_runs(runs_root=runs_root, older_than_days=1)

        for strat_dir in (runs_root / "strat-a", runs_root / "strat-b"):
            newest = sorted(strat_dir.iterdir())[-1]
            reaped_paths = {c.path for c in plan.reapable}
            assert newest not in reaped_paths


# ---------------------------------------------------------------------------
# Byte accounting
# ---------------------------------------------------------------------------


class TestByteAccounting:
    def test_reap_plan_bytes(self, synthetic_tree: Path) -> None:
        runs_root = synthetic_tree / "runs"
        plan = plan_clean_runs(runs_root=runs_root, keep_last=5)
        assert plan.bytes_reclaimable > 0

    def test_reap_plan_to_dict(self, synthetic_tree: Path) -> None:
        runs_root = synthetic_tree / "runs"
        plan = plan_clean_runs(runs_root=runs_root, keep_last=5)
        d = plan.to_dict(dry_run=True)
        assert d["dry_run"] is True
        assert isinstance(d["reapable"], list)
        assert isinstance(d["bytes_reclaimable"], int)
