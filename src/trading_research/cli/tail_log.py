"""``trading-research tail-log`` — filter and pretty-print the JSONL log stream.

Reads JSONL files under ``logs/{YYYY-MM-DD}/`` (the layout produced by
:func:`trading_research.utils.logging.configure_file_logging`) and prints
matching events. Default output is a human-readable single line per event;
``--json`` passes the original JSONL through untouched.

Example::

    # All events from a specific run:
    trading-research tail-log --run-id 20260513T180000Z-abc123

    # Errors only in the last hour:
    trading-research tail-log --since 1h --errors-only

    # All events matching a field filter (repeatable, AND logic):
    trading-research tail-log --field symbol=ZN --field stage=backtest
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

_PROJECT_ROOT = Path(__file__).parents[3]
_DEFAULT_LOG_ROOT = _PROJECT_ROOT / "logs"

_ERROR_LEVELS: frozenset[str] = frozenset({"error", "critical", "exception"})


def _parse_since(spec: str) -> timedelta:
    """Parse ``--since`` values like ``1h``, ``30m``, ``7d``."""
    m = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", spec)
    if not m:
        raise ValueError(
            f"Invalid --since value '{spec}'. "
            "Use a number followed by s, m, h, or d (e.g. 30m, 2h, 7d)."
        )
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "s":
        return timedelta(seconds=n)
    if unit == "m":
        return timedelta(minutes=n)
    if unit == "h":
        return timedelta(hours=n)
    return timedelta(days=n)


def _parse_field(spec: str) -> tuple[str, str]:
    """Parse ``--field key=value`` into a (key, value) tuple."""
    if "=" not in spec:
        raise ValueError(f"--field expects key=value; got '{spec}'.")
    key, _, value = spec.partition("=")
    return key.strip(), value.strip()


def _iter_log_files(
    log_root: Path,
    *,
    since: datetime | None = None,
) -> Iterator[Path]:
    """Yield JSONL log files under ``log_root``, oldest first.

    When ``since`` is given, date directories strictly before its date
    are skipped (the directory name is the UTC calendar day).
    """
    if not log_root.is_dir():
        return
    since_day = since.astimezone(UTC).date() if since else None
    for day_dir in sorted(log_root.iterdir()):
        if not day_dir.is_dir():
            continue
        try:
            day = datetime.strptime(day_dir.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if since_day is not None and day < since_day:
            continue
        yield from sorted(day_dir.glob("*.jsonl"))


def _iter_events(files: Iterable[Path]) -> Iterator[tuple[Path, int, dict]]:
    """Yield ``(file, lineno, event_dict)`` for every JSONL line."""
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        yield path, lineno, event
        except OSError:
            continue


def _matches(
    event: dict,
    *,
    run_id: str | None,
    fields: list[tuple[str, str]],
    since: datetime | None,
    errors_only: bool,
) -> bool:
    if run_id is not None and str(event.get("run_id", "")) != run_id:
        return False
    for key, value in fields:
        if str(event.get(key, "")) != value:
            return False
    if errors_only:
        level = str(event.get("level", "")).lower()
        if level not in _ERROR_LEVELS:
            return False
    if since is not None:
        ts_raw = event.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                return True  # unparseable timestamp → don't drop
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if ts < since:
                return False
    return True


def _format_event(event: dict) -> str:
    """Render one event as a single human-readable line."""
    ts = str(event.get("timestamp", ""))
    level = str(event.get("level", "")).upper().rjust(7)
    name = str(event.get("event", ""))
    well_known = {"timestamp", "level", "event"}
    extras = {k: v for k, v in event.items() if k not in well_known}
    extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
    return f"{ts} [{level}] {name}  {extra_str}".rstrip()


def tail_log_command(
    run_id: Annotated[
        str | None, typer.Option("--run-id", help="Filter to a single run_id.")
    ] = None,
    field: Annotated[
        list[str] | None,
        typer.Option(
            "--field",
            help="key=value filter (repeatable; AND logic).",
        ),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Window like 1h, 30m, 7d. Events older than this are dropped.",
        ),
    ] = None,
    errors_only: Annotated[
        bool, typer.Option("--errors-only", help="Show only error/critical events.")
    ] = False,
    json_out: Annotated[
        bool, typer.Option("--json", help="Pass JSONL through unchanged.")
    ] = False,
    log_root: Annotated[
        Path | None,
        typer.Option("--log-root", help="Override the logs/ directory."),
    ] = None,
) -> None:
    """Filter and print the platform's JSONL log stream.

    Exit code 0 if events were printed, 1 on bad usage, 0 if no events
    matched (silent is fine — the operator can rerun with looser filters).
    """
    root = log_root or _DEFAULT_LOG_ROOT

    field_pairs: list[tuple[str, str]] = []
    for spec in field or []:
        try:
            field_pairs.append(_parse_field(spec))
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    since_dt: datetime | None = None
    if since is not None:
        try:
            delta = _parse_since(since)
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        since_dt = datetime.now(tz=UTC) - delta

    if not root.is_dir():
        typer.echo(f"No logs directory at {root}", err=True)
        raise typer.Exit(code=0)

    files = list(_iter_log_files(root, since=since_dt))
    matched = 0
    for _, _, event in _iter_events(files):
        if not _matches(
            event,
            run_id=run_id,
            fields=field_pairs,
            since=since_dt,
            errors_only=errors_only,
        ):
            continue
        if json_out:
            typer.echo(json.dumps(event, sort_keys=True))
        else:
            typer.echo(_format_event(event))
        matched += 1

    if matched == 0:
        typer.echo("No events matched the given filters.", err=True)
