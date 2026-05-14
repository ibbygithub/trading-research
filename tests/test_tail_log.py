"""Tests for ``trading-research tail-log``."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from trading_research.cli.main import app
from trading_research.cli.tail_log import _matches, _parse_field, _parse_since

runner = CliRunner()


def _write_events(log_root: Path, day: str, run_id: str, events: list[dict]) -> Path:
    day_dir = log_root / day
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{run_id}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    return path


def _today_utc() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d")


def test_help():
    result = runner.invoke(app, ["tail-log", "--help"])
    assert result.exit_code == 0
    assert "--run-id" in result.output
    assert "--field" in result.output
    assert "--since" in result.output
    assert "--errors-only" in result.output


def test_parse_since_units():
    assert _parse_since("30s") == timedelta(seconds=30)
    assert _parse_since("15m") == timedelta(minutes=15)
    assert _parse_since("2h") == timedelta(hours=2)
    assert _parse_since("7d") == timedelta(days=7)


def test_parse_since_invalid():
    with pytest.raises(ValueError):
        _parse_since("bad")


def test_parse_field_roundtrip():
    assert _parse_field("symbol=ZN") == ("symbol", "ZN")
    assert _parse_field("stage=backtest") == ("stage", "backtest")
    with pytest.raises(ValueError):
        _parse_field("no_equals_sign")


def test_matches_run_id():
    event = {"run_id": "alpha", "event": "x"}
    assert _matches(event, run_id="alpha", fields=[], since=None, errors_only=False)
    assert not _matches(event, run_id="beta", fields=[], since=None, errors_only=False)


def test_matches_field_filter():
    event = {"symbol": "ZN", "stage": "backtest", "event": "x"}
    assert _matches(
        event,
        run_id=None,
        fields=[("symbol", "ZN")],
        since=None,
        errors_only=False,
    )
    assert not _matches(
        event,
        run_id=None,
        fields=[("symbol", "6A")],
        since=None,
        errors_only=False,
    )


def test_matches_errors_only():
    info = {"level": "info", "event": "x"}
    err = {"level": "error", "event": "y"}
    assert not _matches(info, run_id=None, fields=[], since=None, errors_only=True)
    assert _matches(err, run_id=None, fields=[], since=None, errors_only=True)


def test_filter_by_run_id_end_to_end(tmp_path: Path):
    today = _today_utc()
    _write_events(
        tmp_path,
        today,
        "rid-A",
        [{"event": "a", "level": "info", "run_id": "rid-A"}],
    )
    _write_events(
        tmp_path,
        today,
        "rid-B",
        [{"event": "b", "level": "info", "run_id": "rid-B"}],
    )

    result = runner.invoke(
        app,
        ["tail-log", "--run-id", "rid-A", "--log-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert " a  " in result.output
    assert " b  " not in result.output


def test_field_filter_end_to_end(tmp_path: Path):
    today = _today_utc()
    _write_events(
        tmp_path,
        today,
        "rid-1",
        [
            {"event": "zn", "level": "info", "symbol": "ZN", "stage": "backtest"},
            {"event": "ad", "level": "info", "symbol": "6A", "stage": "backtest"},
            {"event": "zn-clean", "level": "info", "symbol": "ZN", "stage": "clean"},
        ],
    )

    result = runner.invoke(
        app,
        [
            "tail-log",
            "--field",
            "symbol=ZN",
            "--field",
            "stage=backtest",
            "--log-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert " zn  " in result.output
    assert " ad  " not in result.output
    assert " zn-clean  " not in result.output


def test_errors_only_end_to_end(tmp_path: Path):
    today = _today_utc()
    _write_events(
        tmp_path,
        today,
        "rid-x",
        [
            {"event": "ok", "level": "info"},
            {"event": "boom", "level": "error"},
        ],
    )

    result = runner.invoke(
        app, ["tail-log", "--errors-only", "--log-root", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "boom" in result.output
    assert " ok  " not in result.output


def test_json_passthrough(tmp_path: Path):
    today = _today_utc()
    payload = {"event": "j", "level": "info", "run_id": "rid-j", "symbol": "ZN"}
    _write_events(tmp_path, today, "rid-j", [payload])

    result = runner.invoke(
        app,
        ["tail-log", "--run-id", "rid-j", "--json", "--log-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    line = next(line for line in result.output.splitlines() if line.startswith("{"))
    parsed = json.loads(line)
    assert parsed["event"] == "j"
    assert parsed["symbol"] == "ZN"


def test_no_logs_directory(tmp_path: Path):
    """A missing logs/ dir is non-fatal and exits 0."""
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["tail-log", "--log-root", str(missing)])
    assert result.exit_code == 0


def test_since_window_drops_old_events(tmp_path: Path):
    today = _today_utc()
    old_ts = (datetime.now(tz=UTC) - timedelta(hours=5)).isoformat()
    new_ts = datetime.now(tz=UTC).isoformat()
    _write_events(
        tmp_path,
        today,
        "rid-t",
        [
            {"event": "old", "level": "info", "timestamp": old_ts},
            {"event": "new", "level": "info", "timestamp": new_ts},
        ],
    )

    result = runner.invoke(
        app, ["tail-log", "--since", "1h", "--log-root", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "new" in result.output
    assert " old  " not in result.output
