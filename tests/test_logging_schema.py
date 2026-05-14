"""Tests for the shared structlog schema and run_id propagation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import structlog

from trading_research.utils.logging import (
    SCHEMA_FIELDS,
    bind_run_id,
    configure,
    configure_file_logging,
    detach_file_logging,
    get_logger,
    get_run_id,
    new_run_id,
    reap_old_log_dirs,
)


@pytest.fixture(autouse=True)
def _isolated_logging():
    """Reconfigure stdlib + structlog cleanly around each test."""
    configure(level=logging.INFO)
    structlog.contextvars.clear_contextvars()
    yield
    detach_file_logging()
    structlog.contextvars.clear_contextvars()


def test_schema_fields_constant():
    """The documented schema fields are the seven well-known keys."""
    assert frozenset({
        "run_id",
        "symbol",
        "timeframe",
        "stage",
        "action",
        "outcome",
        "event",
    }) == SCHEMA_FIELDS


def test_new_run_id_unique_and_sortable():
    """Run IDs are unique and lexicographically sortable."""
    ids = [new_run_id() for _ in range(100)]
    assert len(set(ids)) == 100
    # Format prefix is sortable.
    sorted_ids = sorted(ids)
    assert all(rid.startswith("20") for rid in sorted_ids)


def test_bind_run_id_propagates_to_log_record(tmp_path: Path):
    """An event logged within bind_run_id includes the run_id field in JSONL."""
    rid = "test-run-001"
    log_path = configure_file_logging(rid, log_root=tmp_path)

    logger = get_logger("test")
    with bind_run_id(rid, stage="backtest", symbol="ZN"):
        assert get_run_id() == rid
        logger.info("event_under_test", action="start", outcome="ok")

    # File handler buffers; force flush.
    logging.getLogger().handlers[-1].flush()

    contents = log_path.read_text(encoding="utf-8").strip()
    assert contents, "no events written"
    event = json.loads(contents.splitlines()[-1])
    assert event["run_id"] == rid
    assert event["stage"] == "backtest"
    assert event["symbol"] == "ZN"
    assert event["event"] == "event_under_test"
    assert event["action"] == "start"
    assert event["outcome"] == "ok"
    assert event["level"] == "info"


def test_bind_run_id_unbinds_on_exit():
    """Schema fields are removed from context after the block exits."""
    with bind_run_id("rid-1", stage="features"):
        assert get_run_id() == "rid-1"
    assert get_run_id() is None
    assert "stage" not in structlog.contextvars.get_contextvars()


def test_bind_run_id_generates_fresh_when_none():
    """Passing None to bind_run_id mints a fresh ID."""
    with bind_run_id(None) as rid:
        assert rid is not None
        assert get_run_id() == rid


def test_file_logging_writes_jsonl(tmp_path: Path):
    """configure_file_logging writes one JSONL line per logged event."""
    rid = new_run_id()
    log_path = configure_file_logging(rid, log_root=tmp_path)

    logger = get_logger("test")
    with bind_run_id(rid, stage="bootstrap"):
        logger.info("a")
        logger.warning("b")
        logger.error("c")

    logging.getLogger().handlers[-1].flush()

    lines = [
        line for line in log_path.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(lines) == 3
    events = [json.loads(line) for line in lines]
    assert [e["event"] for e in events] == ["a", "b", "c"]
    assert [e["level"] for e in events] == ["info", "warning", "error"]
    assert all(e["run_id"] == rid for e in events)


def test_file_logging_path_includes_date_directory(tmp_path: Path):
    """The on-disk path is logs/{YYYY-MM-DD}/{run_id}.jsonl."""
    rid = "abc-123"
    log_path = configure_file_logging(rid, log_root=tmp_path)
    # parent name is YYYY-MM-DD
    assert log_path.parent.parent == tmp_path
    assert log_path.name == f"{rid}.jsonl"
    parts = log_path.parent.name.split("-")
    assert len(parts) == 3 and len(parts[0]) == 4


def test_reap_old_log_dirs_dry_run(tmp_path: Path):
    """reap_old_log_dirs respects retention_days and dry_run."""
    # Create three day directories with widely-separated dates.
    (tmp_path / "2000-01-01").mkdir()
    (tmp_path / "2100-01-01").mkdir()
    (tmp_path / "not-a-date").mkdir()  # ignored
    (tmp_path / "2000-01-01" / "x.jsonl").write_text("{}", encoding="utf-8")

    candidates = reap_old_log_dirs(tmp_path, retention_days=30, dry_run=True)
    names = {p.name for p in candidates}
    assert "2000-01-01" in names
    assert "2100-01-01" not in names
    assert "not-a-date" not in names
    # Dry run leaves directories on disk.
    assert (tmp_path / "2000-01-01").exists()


def test_reap_old_log_dirs_apply_deletes(tmp_path: Path):
    """Apply mode actually removes the directory tree."""
    (tmp_path / "2000-01-01").mkdir()
    (tmp_path / "2000-01-01" / "x.jsonl").write_text("{}", encoding="utf-8")

    reap_old_log_dirs(tmp_path, retention_days=30, dry_run=False)
    assert not (tmp_path / "2000-01-01").exists()


def test_pipeline_module_log_includes_bound_fields(tmp_path: Path):
    """A hot-path module's own logger inherits the bound run_id."""
    rid = "rid-from-cli"
    log_path = configure_file_logging(rid, log_root=tmp_path)

    # Pretend the CLI bound run_id and stage…
    structlog.contextvars.bind_contextvars(run_id=rid, stage="features")
    try:
        # …and a hot-path module logs an event:
        from trading_research.utils.logging import get_logger
        get_logger("trading_research.indicators.features").info(
            "build_features_start",
            action="start",
            outcome="ok",
        )
    finally:
        structlog.contextvars.clear_contextvars()

    logging.getLogger().handlers[-1].flush()

    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert event["run_id"] == rid
    assert event["stage"] == "features"
    assert event["event"] == "build_features_start"
