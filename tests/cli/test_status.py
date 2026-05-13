"""Tests for `trading-research status`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from trading_research.cli.main import app
from trading_research.cli.status import _pressure, build_status_report

runner = CliRunner()


def _scaffold_project(tmp_path: Path) -> Path:
    """Build a minimal project tree for status to read."""
    (tmp_path / "data" / "clean").mkdir(parents=True)
    (tmp_path / "data" / "features").mkdir(parents=True)
    (tmp_path / "runs").mkdir(parents=True)
    (tmp_path / "outputs" / "archive" / "trials").mkdir(parents=True)
    (tmp_path / "configs" / "strategies").mkdir(parents=True)
    return tmp_path


def test_help():
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0


def test_status_empty_project(tmp_path: Path):
    """status on an empty project runs without error and reports zero state."""
    _scaffold_project(tmp_path)
    result = runner.invoke(app, ["status", "--project-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Trading Research Platform" in result.output
    assert "Strategies (YAML files):   0" in result.output
    assert "Retention pressure: GREEN" in result.output


def test_status_json_emits_valid_json(tmp_path: Path):
    _scaffold_project(tmp_path)
    result = runner.invoke(
        app, ["status", "--json", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "project_root" in payload
    assert "instruments" in payload
    assert "trials" in payload
    assert "disk_bytes" in payload
    assert "retention_pressure" in payload
    assert payload["retention_pressure"]["level"] == "green"


def test_status_counts_strategies(tmp_path: Path):
    _scaffold_project(tmp_path)
    (tmp_path / "configs" / "strategies" / "a.yaml").write_text("strategy_id: a\n")
    (tmp_path / "configs" / "strategies" / "b.yaml").write_text("strategy_id: b\n")
    (tmp_path / "configs" / "strategies" / "skip.txt").write_text("not yaml")

    result = runner.invoke(
        app, ["status", "--json", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["strategies_count"] == 2


def test_status_reads_live_trial_registry(tmp_path: Path):
    _scaffold_project(tmp_path)
    registry = tmp_path / "runs" / ".trials.json"
    registry.write_text(
        json.dumps(
            {
                "trials": [
                    {"strategy_id": "x", "mode": "validation"},
                    {"strategy_id": "y", "mode": "exploration"},
                    {"strategy_id": "z", "mode": "exploration"},
                ]
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["status", "--json", "--project-root", str(tmp_path)]
    )
    payload = json.loads(result.output)
    assert payload["trials"]["live"] == 3
    assert payload["trials"]["by_mode"]["exploration"] == 2
    assert payload["trials"]["by_mode"]["validation"] == 1


def test_status_counts_archived_trials(tmp_path: Path):
    _scaffold_project(tmp_path)
    archive = tmp_path / "outputs" / "archive" / "trials" / "2025-09.jsonl"
    archive.write_text('{"a":1}\n{"a":2}\n{"a":3}\n', encoding="utf-8")
    result = runner.invoke(
        app, ["status", "--json", "--project-root", str(tmp_path)]
    )
    payload = json.loads(result.output)
    assert payload["trials"]["archived"] == 3


def test_pressure_thresholds():
    """Retention pressure levels match Chapter 56.5 §56.5.6.3."""
    assert _pressure(1 * (1024**3))[0] == "green"
    assert _pressure(7 * (1024**3))[0] == "amber"
    assert _pressure(15 * (1024**3))[0] == "red"
    assert _pressure(30 * (1024**3))[0] == "critical"


def test_status_recent_runs_picks_up_summary(tmp_path: Path):
    _scaffold_project(tmp_path)
    run_dir = tmp_path / "runs" / "test-strat" / "2026-01-01-12-00"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "mode": "exploration",
                "total_trades": 42,
                "sharpe": 1.234,
                "calmar": 0.567,
            }
        ),
        encoding="utf-8",
    )
    report = build_status_report(project_root=tmp_path)
    assert len(report.recent_runs) == 1
    r = report.recent_runs[0]
    assert r["strategy_id"] == "test-strat"
    assert r["mode"] == "exploration"
    assert r["total_trades"] == 42
