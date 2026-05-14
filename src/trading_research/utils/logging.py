"""Structlog configuration for the trading-research platform.

This module is the single source of truth for the platform's logging
surface. Import :func:`get_logger` everywhere structured logging is
needed and call :func:`configure` (idempotent) once at process entry.

Field schema
------------

Every log event uses a stable set of well-known keys so that
``trading-research tail-log`` can filter consistently:

* ``run_id``    — opaque identifier for the pipeline-driving CLI
  invocation. Generated once at process entry by
  :func:`new_run_id` and bound into the structlog contextvars by
  :func:`bind_run_id` so it appears on every subsequent event.
* ``symbol``    — instrument symbol (e.g. ``ZN``, ``6A``). Bound when
  a stage scopes to a single instrument.
* ``timeframe`` — bar timeframe (``1m``, ``5m``, …).
* ``stage``     — pipeline stage (``clean``, ``features``, ``backtest``,
  ``report``, ``verify``, …).
* ``action``    — verb describing what happened (``start``, ``finish``,
  ``error``, ``write``, ``read``, ``skip``).
* ``outcome``   — coarse result tag (``ok``, ``warning``, ``failure``).
* ``event``     — short snake_case message name (the structlog "event"
  positional). Identifies the event type for grep / filter.

Modules are free to add domain-specific keys (``trades_count``,
``elapsed_seconds``, …) — the schema above defines the *guaranteed*
filter surface, not the entire log payload.
"""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
import os
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import structlog

# Public list of guaranteed schema keys. Kept frozen so tests can assert
# against it without dragging in a runtime dependency on this list.
SCHEMA_FIELDS: frozenset[str] = frozenset({
    "run_id",
    "symbol",
    "timeframe",
    "stage",
    "action",
    "outcome",
    "event",
})


_FILE_HANDLER: logging.Handler | None = None
_CONFIGURED: bool = False


class _DynamicStderr:
    """File-like proxy that resolves ``sys.stderr`` at write time.

    A ``logging.StreamHandler(stream=sys.stderr)`` captures the
    ``sys.stderr`` reference at construction time. Tests using pytest
    ``capsys`` replace ``sys.stderr`` at Python level *after* this
    handler was created, so writes through the captured reference
    bypass ``capsys``. Resolving the stream on every write fixes that
    without weakening production behaviour.
    """

    def write(self, msg: str) -> int:  # pragma: no cover - thin proxy
        return sys.stderr.write(msg)

    def flush(self) -> None:  # pragma: no cover - thin proxy
        with contextlib.suppress(Exception):
            sys.stderr.flush()


def _stderr_formatter() -> logging.Formatter:
    return structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=False),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ],
    )


def _jsonl_formatter() -> logging.Formatter:
    return structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(sort_keys=True),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ],
    )


def configure(level: int = logging.INFO) -> None:
    """Configure structlog and the stdlib root logger.

    Idempotent — calling more than once replaces handlers in place
    rather than stacking duplicates. Adds a stderr handler with the
    human-readable ConsoleRenderer; the JSONL file handler is opt-in
    via :func:`configure_file_logging`.
    """
    global _CONFIGURED

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stderr_handler = logging.StreamHandler(stream=_DynamicStderr())
    stderr_handler.setFormatter(_stderr_formatter())
    stderr_handler.setLevel(level)
    root.addHandler(stderr_handler)
    root.setLevel(level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def configure_file_logging(
    run_id: str,
    log_root: Path | None = None,
    level: int = logging.INFO,
) -> Path:
    """Attach a JSONL file handler at ``{log_root}/{YYYY-MM-DD}/{run_id}.jsonl``.

    Returns the resolved path. Idempotent for a given ``run_id`` — calling
    twice replaces the handler. Date directory rotation: each calendar day
    (UTC) gets its own subdirectory, which is the natural retention unit
    (see ``configs/retention.yaml`` ``logs:`` block).
    """
    global _FILE_HANDLER

    if not _CONFIGURED:
        configure(level=level)

    if log_root is None:
        log_root = Path.cwd() / "logs"
    log_root = Path(log_root)

    day_dir = log_root / datetime.now(tz=UTC).strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    log_path = day_dir / f"{run_id}.jsonl"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(_jsonl_formatter())
    handler.setLevel(level)

    root = logging.getLogger()
    if _FILE_HANDLER is not None:
        root.removeHandler(_FILE_HANDLER)
    root.addHandler(handler)
    _FILE_HANDLER = handler
    return log_path


def detach_file_logging() -> None:
    """Remove the file handler if one is attached. Safe to call repeatedly."""
    global _FILE_HANDLER
    if _FILE_HANDLER is None:
        return
    logging.getLogger().removeHandler(_FILE_HANDLER)
    with contextlib.suppress(Exception):
        _FILE_HANDLER.close()
    _FILE_HANDLER = None


def new_run_id() -> str:
    """Generate a fresh run identifier.

    Format: ``{YYYYMMDDTHHMMSSZ}-{hex6}`` — sortable, UTC, unique enough
    for the platform's single-host workload.
    """
    now = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:6]
    return f"{now}-{suffix}"


@contextmanager
def bind_run_id(
    run_id: str | None = None,
    *,
    stage: str | None = None,
    **fields: object,
) -> Iterator[str]:
    """Bind ``run_id`` (and optional schema fields) into structlog context.

    If ``run_id`` is None a fresh one is generated. On exit the bound
    keys are unbound. Yields the active ``run_id`` so callers can pass
    it to downstream artifacts (``runs/<run_id>/``, summary JSON, etc.).
    """
    rid = run_id or new_run_id()
    bound: dict[str, object] = {"run_id": rid}
    if stage is not None:
        bound["stage"] = stage
    bound.update({k: v for k, v in fields.items() if v is not None})
    structlog.contextvars.bind_contextvars(**bound)
    try:
        yield rid
    finally:
        structlog.contextvars.unbind_contextvars(*bound.keys())


@contextmanager
def cli_run(
    stage: str,
    *,
    log_root: Path | None = None,
    level: int = logging.INFO,
    **fields: object,
) -> Iterator[tuple[str, Path | None]]:
    """Bootstrap a pipeline-driving CLI invocation.

    Generates a fresh ``run_id``, configures the stderr console logger,
    attaches a JSONL file handler at ``logs/{YYYY-MM-DD}/{run_id}.jsonl``
    (skipped under pytest to keep test runs clean), and binds the
    schema fields ``run_id``, ``stage``, and any supplied keyword fields
    into the structlog contextvars.

    Yields ``(run_id, log_path)`` — ``log_path`` is ``None`` when file
    logging was skipped.
    """
    configure(level=level)
    rid = new_run_id()

    log_path: Path | None = None
    if "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            log_path = configure_file_logging(rid, log_root=log_root, level=level)
        except OSError:
            log_path = None

    with bind_run_id(rid, stage=stage, **fields):
        try:
            yield rid, log_path
        finally:
            if log_path is not None:
                detach_file_logging()


def get_run_id() -> str | None:
    """Return the currently bound ``run_id`` or None."""
    ctx = structlog.contextvars.get_contextvars()
    rid = ctx.get("run_id")
    return rid if isinstance(rid, str) else None


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog bound logger."""
    if not _CONFIGURED:
        # Lazy: the first caller in a test or library context gets a
        # working logger without having to remember to call configure().
        configure(level=logging.INFO)
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def reap_old_log_dirs(
    log_root: Path,
    retention_days: int,
    *,
    archive_dir: Path | None = None,
    dry_run: bool = True,
) -> list[Path]:
    """Reap (or archive) log directories older than ``retention_days``.

    Returns the list of date-directory paths that would be (or were)
    removed. Directory ``YYYY-MM-DD`` is the unit of retention — once
    a day's logs are written they are immutable and either kept,
    archived, or deleted as a single unit.
    """
    if not log_root.is_dir():
        return []
    cutoff = datetime.now(tz=UTC).date()
    cutoff_ordinal = cutoff.toordinal() - retention_days

    candidates: list[Path] = []
    for child in sorted(log_root.iterdir()):
        if not child.is_dir():
            continue
        try:
            day = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day.toordinal() < cutoff_ordinal:
            candidates.append(child)

    if dry_run:
        return candidates

    for path in candidates:
        if archive_dir is not None:
            archive_dir.mkdir(parents=True, exist_ok=True)
            target = archive_dir / path.name
            if not target.exists():
                with contextlib.suppress(OSError):
                    os.rename(path, target)
                    continue
        # Fall through to delete on archive failure or no archive_dir.
        for sub in path.iterdir():
            with contextlib.suppress(OSError):
                sub.unlink()
        with contextlib.suppress(OSError):
            path.rmdir()
    return candidates
