"""Tests for `trading-research migrate-trials`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from trading_research.cli.main import app
from trading_research.eval.trials import diff_trials_migration, migrate_trials

runner = CliRunner()


def _write_registry(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_help():
    result = runner.invoke(app, ["migrate-trials", "--help"])
    assert result.exit_code == 0


def test_missing_registry_exits_2(tmp_path: Path):
    result = runner.invoke(
        app, ["migrate-trials", "--registry", str(tmp_path / "no.json")]
    )
    assert result.exit_code == 2
    assert "not found" in result.output.lower()


def test_dry_run_does_not_write(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        [
            {"strategy_id": "s1", "sharpe": 1.0, "mode": "unknown"},
            {"strategy_id": "s2", "sharpe": 1.2},  # missing mode entirely
        ],
    )
    original = path.read_text(encoding="utf-8")

    result = runner.invoke(app, ["migrate-trials", "--registry", str(path)])
    assert result.exit_code == 0
    assert "Dry run" in result.output
    assert path.read_text(encoding="utf-8") == original


def test_apply_writes_and_backs_up(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        [
            {"strategy_id": "s1", "sharpe": 1.0, "mode": "unknown"},
        ],
    )
    result = runner.invoke(
        app, ["migrate-trials", "--registry", str(path), "--apply"]
    )
    assert result.exit_code == 0
    after = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(after, dict)
    trial = after["trials"][0]
    assert trial["mode"] == "validation"
    assert trial["code_version"] == "pre-hardening"
    backup = path.with_suffix(".json.backup")
    assert backup.is_file()


def test_apply_idempotent(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        {
            "trials": [
                {
                    "strategy_id": "s1",
                    "sharpe": 1.0,
                    "mode": "validation",
                    "code_version": "abc1234",
                    "cohort_label": "abc1234",
                    "featureset_hash": None,
                    "parent_sweep_id": None,
                }
            ]
        },
    )
    # First apply — should be a no-op.
    result1 = runner.invoke(
        app, ["migrate-trials", "--registry", str(path), "--apply"]
    )
    assert result1.exit_code == 0
    # Second apply — also a no-op, same output content.
    result2 = runner.invoke(
        app, ["migrate-trials", "--registry", str(path), "--apply"]
    )
    assert result2.exit_code == 0
    assert "no changes needed" in result2.output.lower() or "already current" in result2.output.lower()


def test_json_output(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        [{"strategy_id": "s1", "mode": "unknown"}],
    )
    result = runner.invoke(
        app, ["migrate-trials", "--registry", str(path), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["would_promote_unknown_to_validation"] == 1


def test_diff_helper_no_op_on_already_migrated(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        {
            "trials": [
                {
                    "strategy_id": "s1",
                    "mode": "validation",
                    "code_version": "abc",
                    "cohort_label": "abc",
                    "featureset_hash": None,
                    "parent_sweep_id": None,
                }
            ]
        },
    )
    diff = diff_trials_migration(path)
    assert diff["no_op"] is True
    assert diff["total"] == 1


def test_diff_helper_detects_unknown_mode(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        {
            "trials": [
                {"strategy_id": "s1", "mode": "unknown"},
                {"strategy_id": "s2", "mode": "unknown"},
            ]
        },
    )
    diff = diff_trials_migration(path)
    assert diff["no_op"] is False
    assert diff["would_promote_unknown_to_validation"] == 2


def test_no_backup_flag(tmp_path: Path):
    path = _write_registry(
        tmp_path / ".trials.json",
        [{"strategy_id": "s1", "mode": "unknown"}],
    )
    result = runner.invoke(
        app,
        ["migrate-trials", "--registry", str(path), "--apply", "--no-backup"],
    )
    assert result.exit_code == 0
    assert not path.with_suffix(".json.backup").exists()
