"""Tests for the three-tier trial registry cleanup.

Covers all three tiers from Chapter 56.5 section 56.5.3.5:
  - Live: < compact_after days OR mode=validation (any age)
  - Compacted archive: >= compact_after days, exploration-mode
  - Deletion: >= delete_after days, exploration-mode, AND not referenced
              by any live parent_sweep_id

Includes the parent_sweep_id orphan-prevention case.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from trading_research.maintenance.reaper import (
    apply_trial_plan,
    plan_clean_trials,
)


def _make_trial(
    timestamp: datetime,
    strategy_id: str = "test-strat",
    mode: str = "exploration",
    parent_sweep_id: str | None = None,
    sharpe: float = 1.0,
) -> dict:
    return {
        "timestamp": timestamp.isoformat(),
        "strategy_id": strategy_id,
        "config_hash": "abc123",
        "sharpe": sharpe,
        "trial_group": strategy_id,
        "code_version": "test",
        "featureset_hash": None,
        "cohort_label": "test",
        "mode": mode,
        "parent_sweep_id": parent_sweep_id,
    }


def _write_registry(runs_root: Path, trials: list[dict]) -> None:
    registry = runs_root / ".trials.json"
    runs_root.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps({"trials": trials}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_registry(runs_root: Path) -> list[dict]:
    registry = runs_root / ".trials.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    return data.get("trials", [])


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


class TestTierClassification:
    def test_recent_exploration_stays_live(self, tmp_path: Path) -> None:
        """Exploration trials younger than compact_after stay live."""
        now = datetime.now(tz=UTC)
        trials = [_make_trial(now - timedelta(days=30))]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180)
        assert plan.live_count == 1
        assert len(plan.compactable) == 0
        assert len(plan.deletable) == 0

    def test_validation_stays_live_regardless_of_age(self, tmp_path: Path) -> None:
        """Validation-mode trials are never compacted or deleted, regardless of age."""
        now = datetime.now(tz=UTC)
        trials = [
            _make_trial(now - timedelta(days=1000), mode="validation"),
            _make_trial(now - timedelta(days=500), mode="validation"),
        ]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert plan.live_count == 2
        assert len(plan.compactable) == 0
        assert len(plan.deletable) == 0

    def test_old_exploration_is_compactable(self, tmp_path: Path) -> None:
        """Exploration trials older than compact_after but younger than delete_after are compactable."""
        now = datetime.now(tz=UTC)
        trials = [_make_trial(now - timedelta(days=200))]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert plan.live_count == 0
        assert len(plan.compactable) == 1
        assert len(plan.deletable) == 0

    def test_very_old_exploration_is_deletable(self, tmp_path: Path) -> None:
        """Exploration trials older than delete_after are deletable."""
        now = datetime.now(tz=UTC)
        trials = [_make_trial(now - timedelta(days=800))]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert plan.live_count == 0
        assert len(plan.compactable) == 0
        assert len(plan.deletable) == 1


# ---------------------------------------------------------------------------
# Orphan prevention
# ---------------------------------------------------------------------------


class TestOrphanPrevention:
    def test_referenced_old_trial_kept_in_compact(self, tmp_path: Path) -> None:
        """A deletion-age trial referenced by a live parent_sweep_id stays in compacted archive."""
        now = datetime.now(tz=UTC)
        sweep_id = "sweep-abc123"
        trials = [
            # Very old exploration trial with a parent_sweep_id
            _make_trial(now - timedelta(days=800), parent_sweep_id=sweep_id),
            # Recent trial also referencing the same sweep (makes it live)
            _make_trial(now - timedelta(days=10), parent_sweep_id=sweep_id),
        ]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert plan.live_count == 1  # the recent one
        assert len(plan.compactable) == 1  # the old one (protected by sweep ref)
        assert len(plan.deletable) == 0

    def test_unreferenced_old_trial_deleted(self, tmp_path: Path) -> None:
        """A deletion-age trial with no live sweep reference is deletable."""
        now = datetime.now(tz=UTC)
        trials = [_make_trial(now - timedelta(days=800), parent_sweep_id=None)]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert len(plan.deletable) == 1


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------


class TestMixedScenarios:
    def test_mixed_trial_population(self, tmp_path: Path) -> None:
        """A registry with trials in all three tiers plus validation."""
        now = datetime.now(tz=UTC)
        sweep_id = "sweep-mixed"
        trials = [
            # Live: recent exploration
            _make_trial(now - timedelta(days=10), strategy_id="s1"),
            _make_trial(now - timedelta(days=50), strategy_id="s2"),
            # Live: old validation
            _make_trial(now - timedelta(days=500), strategy_id="s3", mode="validation"),
            # Compactable: old exploration
            _make_trial(now - timedelta(days=200), strategy_id="s4"),
            _make_trial(now - timedelta(days=300), strategy_id="s5"),
            # Deletable: very old, unreferenced exploration
            _make_trial(now - timedelta(days=800), strategy_id="s6"),
            # Protected: very old but referenced by sweep
            _make_trial(
                now - timedelta(days=900), strategy_id="s7", parent_sweep_id=sweep_id,
            ),
            # Recent trial in same sweep (makes sweep_id live)
            _make_trial(now - timedelta(days=5), strategy_id="s8", parent_sweep_id=sweep_id),
        ]
        _write_registry(tmp_path, trials)

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert plan.live_count == 4  # s1, s2, s3(validation), s8
        assert len(plan.compactable) == 3  # s4, s5, s7(protected by sweep)
        assert len(plan.deletable) == 1  # s6


# ---------------------------------------------------------------------------
# Apply: compaction and deletion
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_compacts_to_archive(self, tmp_path: Path) -> None:
        """Compactable trials are written to monthly JSONL archives."""
        now = datetime.now(tz=UTC)
        old_ts = now - timedelta(days=200)
        trials = [
            _make_trial(now - timedelta(days=10)),  # live
            _make_trial(old_ts),  # compactable
        ]
        _write_registry(tmp_path, trials)
        archive_root = tmp_path / "archive" / "trials"

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        assert len(plan.compactable) == 1

        compacted, deleted, errors = apply_trial_plan(plan, tmp_path, archive_root)
        assert compacted == 1
        assert deleted == 0
        assert not errors

        # Registry should only have the live trial
        remaining = _read_registry(tmp_path)
        assert len(remaining) == 1

        # Archive file should exist
        month_key = old_ts.strftime("%Y-%m")
        jsonl = archive_root / f"{month_key}.jsonl"
        assert jsonl.exists()
        lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_apply_deletes_from_registry(self, tmp_path: Path) -> None:
        """Deletable trials are removed from the live registry."""
        now = datetime.now(tz=UTC)
        trials = [
            _make_trial(now - timedelta(days=10)),  # live
            _make_trial(now - timedelta(days=800)),  # deletable
        ]
        _write_registry(tmp_path, trials)
        archive_root = tmp_path / "archive" / "trials"

        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180, delete_after_days=730)
        compacted, deleted, errors = apply_trial_plan(plan, tmp_path, archive_root)

        remaining = _read_registry(tmp_path)
        assert len(remaining) == 1  # only the live trial

    def test_apply_is_idempotent(self, tmp_path: Path) -> None:
        """Running apply twice produces the same result."""
        now = datetime.now(tz=UTC)
        trials = [
            _make_trial(now - timedelta(days=10)),
            _make_trial(now - timedelta(days=200)),
        ]
        _write_registry(tmp_path, trials)
        archive_root = tmp_path / "archive" / "trials"

        # First apply
        plan = plan_clean_trials(runs_root=tmp_path, compact_after_days=180)
        apply_trial_plan(plan, tmp_path, archive_root)
        count_after_first = len(_read_registry(tmp_path))

        # Second apply (nothing should change)
        plan2 = plan_clean_trials(runs_root=tmp_path, compact_after_days=180)
        apply_trial_plan(plan2, tmp_path, archive_root)
        count_after_second = len(_read_registry(tmp_path))

        assert count_after_first == count_after_second


# ---------------------------------------------------------------------------
# Retention policy loading
# ---------------------------------------------------------------------------


class TestRetentionPolicy:
    def test_defaults_load_without_yaml(self, tmp_path: Path) -> None:
        from trading_research.maintenance.retention import load_retention_policy

        policy = load_retention_policy(project_root=tmp_path)
        assert policy.runs.keep_last_per_strategy == 10
        assert policy.runs.archive_older_than_days == 90
        assert policy.trials.compact_after_days == 180
        assert policy.trials.delete_after_days == 730
        assert policy.trials.keep_modes == ["validation"]

    def test_yaml_overrides_defaults(self, tmp_path: Path) -> None:
        from trading_research.maintenance.retention import load_retention_policy

        configs = tmp_path / "configs"
        configs.mkdir()
        (configs / "retention.yaml").write_text(
            "runs:\n  keep_last_per_strategy: 5\n"
            "trials:\n  compact_after: 90d\n  delete_after: 365d\n",
            encoding="utf-8",
        )

        policy = load_retention_policy(project_root=tmp_path)
        assert policy.runs.keep_last_per_strategy == 5
        assert policy.trials.compact_after_days == 90
        assert policy.trials.delete_after_days == 365

    def test_duration_parsing(self) -> None:
        from trading_research.maintenance.retention import _parse_duration

        assert _parse_duration("90d") == 90
        assert _parse_duration("6m") == 180
        assert _parse_duration("2y") == 730

        with pytest.raises(ValueError):
            _parse_duration("invalid")
