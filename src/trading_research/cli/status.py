"""``trading-research status`` — one-screen dashboard of platform state.

Reports:
  - Data freshness per registered instrument (latest CLEAN 1m end date)
  - Last five backtest run directories (mtime-sorted)
  - Registered strategies count
  - Trial registry summary (live + archived; mode breakdown)
  - Total disk footprint (data + runs + outputs)
  - Retention pressure flag (Chapter 56.5 §56.5.6.3 thresholds)

Specification: Chapter 49.16 of the operator's manual.

Exit codes:
    0 — report generated.
    1 — unexpected I/O error reading registry or manifests.
"""

from __future__ import annotations

import glob as _glob
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

_PROJECT_ROOT = Path(__file__).parents[3]
_DATA_ROOT = _PROJECT_ROOT / "data"
_RUNS_ROOT = _PROJECT_ROOT / "runs"
_OUTPUTS_ROOT = _PROJECT_ROOT / "outputs"
_CONFIGS_ROOT = _PROJECT_ROOT / "configs"


# Retention pressure thresholds (Chapter 56.5 §56.5.6.3).
_PRESSURE_GREEN_GB = 5.0
_PRESSURE_AMBER_GB = 10.0
_PRESSURE_RED_GB = 25.0


@dataclass
class StatusReport:
    """Structured platform-state snapshot."""

    project_root: Path
    instruments: list[dict] = field(default_factory=list)
    recent_runs: list[dict] = field(default_factory=list)
    strategies_count: int = 0
    trials_live: int = 0
    trials_archived: int = 0
    trials_by_mode: dict[str, int] = field(default_factory=dict)
    data_bytes: int = 0
    runs_bytes: int = 0
    outputs_bytes: int = 0
    pressure_level: str = "green"
    pressure_message: str = ""


def _directory_size(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def _pressure(data_bytes: int) -> tuple[str, str]:
    gb = data_bytes / (1024**3)
    if gb < _PRESSURE_GREEN_GB:
        return "green", "no action needed."
    if gb < _PRESSURE_AMBER_GB:
        return "amber", "run `clean dryrun` weekly; apply when reapable >1 GB."
    if gb < _PRESSURE_RED_GB:
        return "red", "run `clean runs --older-than 90d --apply` and `clean canonical --apply` monthly."
    return "critical", "audit per-instrument footprint via `inventory`; reap cold instruments."


def _gather_instruments(data_root: Path) -> list[dict]:
    """For each registered instrument, find the latest CLEAN 1m back-adjusted parquet."""
    from trading_research.core.instruments import InstrumentRegistry

    rows: list[dict] = []
    try:
        registry = InstrumentRegistry()
        instruments = registry.list()
    except (FileNotFoundError, KeyError):
        return rows

    clean_dir = data_root / "clean"
    for inst in instruments:
        pattern = str(clean_dir / f"{inst.symbol}_1m_backadjusted_*.parquet")
        matches = sorted(_glob.glob(pattern))
        end_date = None
        manifest_age_days = None
        if matches:
            latest = Path(matches[-1])
            # Manifest sidecar holds date_range; fall back to mtime if absent.
            manifest_path = latest.with_suffix(".parquet.manifest.json")
            try:
                if manifest_path.is_file():
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                    dr = m.get("date_range") or {}
                    end_date = dr.get("end")
                if end_date is None:
                    end_date = datetime.fromtimestamp(
                        latest.stat().st_mtime, tz=UTC
                    ).date().isoformat()
                # Convert end-date to "days behind today" for the freshness column.
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00")) \
                    if "T" in end_date else datetime.fromisoformat(end_date)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=UTC)
                manifest_age_days = (datetime.now(tz=UTC) - end_dt).days
            except (OSError, json.JSONDecodeError, ValueError):
                manifest_age_days = None
        rows.append({
            "symbol": inst.symbol,
            "name": inst.name,
            "clean_1m_end_date": end_date,
            "days_behind_today": manifest_age_days,
            "registered": True,
        })
    return rows


def _gather_recent_runs(runs_root: Path, n: int = 5) -> list[dict]:
    """Return the n most-recent timestamped run directories across all strategies."""
    if not runs_root.is_dir():
        return []
    candidates: list[tuple[float, Path]] = []
    for strategy_dir in runs_root.iterdir():
        if not strategy_dir.is_dir() or strategy_dir.name.startswith("."):
            continue
        for ts_dir in strategy_dir.iterdir():
            if ts_dir.is_dir():
                try:
                    candidates.append((ts_dir.stat().st_mtime, ts_dir))
                except OSError:
                    continue
    candidates.sort(reverse=True)

    rows = []
    for mtime, ts_dir in candidates[:n]:
        summary_path = ts_dir / "summary.json"
        mode = "?"
        total_trades = "?"
        sharpe = "?"
        calmar = "?"
        if summary_path.is_file():
            try:
                s = json.loads(summary_path.read_text(encoding="utf-8"))
                mode = s.get("mode", "?")
                total_trades = s.get("total_trades", "?")
                sharpe_val = s.get("sharpe")
                calmar_val = s.get("calmar")
                if isinstance(sharpe_val, (int, float)) and sharpe_val == sharpe_val:
                    sharpe = f"{sharpe_val:.2f}"
                if isinstance(calmar_val, (int, float)) and calmar_val == calmar_val:
                    calmar = f"{calmar_val:.2f}"
            except (OSError, json.JSONDecodeError):
                pass

        rows.append({
            "strategy_id": ts_dir.parent.name,
            "timestamp": ts_dir.name,
            "mtime_iso": datetime.fromtimestamp(mtime, tz=UTC).isoformat(timespec="seconds"),
            "mode": mode,
            "total_trades": total_trades,
            "sharpe": sharpe,
            "calmar": calmar,
        })
    return rows


def _count_strategies(configs_root: Path) -> int:
    strat_dir = configs_root / "strategies"
    if not strat_dir.is_dir():
        return 0
    return sum(1 for p in strat_dir.glob("*.yaml") if p.is_file())


def _summarize_trial_registry(runs_root: Path) -> tuple[int, dict[str, int]]:
    """Return (count, mode_breakdown) for the live trial registry."""
    path = runs_root / ".trials.json"
    if not path.is_file():
        return 0, {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, {}
    if isinstance(raw, dict):
        trials = raw.get("trials", [])
    elif isinstance(raw, list):
        trials = raw
    else:
        return 0, {}
    by_mode: dict[str, int] = {}
    for t in trials:
        mode = t.get("mode", "unknown")
        by_mode[mode] = by_mode.get(mode, 0) + 1
    return len(trials), by_mode


def _count_archived_trials(outputs_root: Path) -> int:
    archive_dir = outputs_root / "archive" / "trials"
    if not archive_dir.is_dir():
        return 0
    n = 0
    for jsonl in archive_dir.glob("*.jsonl"):
        try:
            with jsonl.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        n += 1
        except OSError:
            continue
    return n


def build_status_report(
    project_root: Path | None = None,
) -> StatusReport:
    """Build a StatusReport snapshot of the current platform state."""
    root = project_root or _PROJECT_ROOT
    data_root = root / "data"
    runs_root = root / "runs"
    outputs_root = root / "outputs"
    configs_root = root / "configs"

    report = StatusReport(project_root=root)
    report.instruments = _gather_instruments(data_root)
    report.recent_runs = _gather_recent_runs(runs_root, n=5)
    report.strategies_count = _count_strategies(configs_root)
    report.trials_live, report.trials_by_mode = _summarize_trial_registry(runs_root)
    report.trials_archived = _count_archived_trials(outputs_root)

    report.data_bytes = _directory_size(data_root)
    report.runs_bytes = _directory_size(runs_root)
    report.outputs_bytes = _directory_size(outputs_root)

    report.pressure_level, report.pressure_message = _pressure(report.data_bytes)

    return report


def _print_text(report: StatusReport) -> None:
    typer.echo("Trading Research Platform — status")
    typer.echo(f"Project: {report.project_root}")
    typer.echo("")

    typer.echo("Data freshness (CLEAN 1m back-adjusted):")
    if not report.instruments:
        typer.echo("  (no registered instruments)")
    else:
        typer.echo(f"  {'Symbol':<8} {'Name':<26} {'End date':<12}  {'Days behind':>12}")
        for r in report.instruments:
            end = r["clean_1m_end_date"] or "(none)"
            days = r["days_behind_today"]
            days_s = f"{days}d" if isinstance(days, int) else "—"
            typer.echo(f"  {r['symbol']:<8} {r['name'][:26]:<26} {end:<12}  {days_s:>12}")

    typer.echo("")
    typer.echo("Recent backtest runs (most-recent first):")
    if not report.recent_runs:
        typer.echo("  (no runs found)")
    else:
        typer.echo(
            f"  {'Strategy':<40} {'Timestamp':<19} {'Mode':<11} "
            f"{'Trades':>7}  {'Sharpe':>7}  {'Calmar':>7}"
        )
        for r in report.recent_runs:
            typer.echo(
                f"  {r['strategy_id'][:40]:<40} {r['timestamp']:<19} "
                f"{str(r['mode']):<11} {str(r['total_trades']):>7}  "
                f"{r['sharpe']:>7}  {r['calmar']:>7}"
            )

    typer.echo("")
    typer.echo("Registered strategies & trials:")
    typer.echo(f"  Strategies (YAML files):   {report.strategies_count}")
    typer.echo(f"  Trials, live registry:     {report.trials_live}")
    if report.trials_by_mode:
        mode_parts = ", ".join(
            f"{k}={v}" for k, v in sorted(report.trials_by_mode.items())
        )
        typer.echo(f"    by mode:                 {mode_parts}")
    typer.echo(f"  Trials, compacted archive: {report.trials_archived}")

    total = report.data_bytes + report.runs_bytes + report.outputs_bytes
    typer.echo("")
    typer.echo("Disk footprint:")
    typer.echo(f"  data/    {_format_bytes(report.data_bytes):>10}")
    typer.echo(f"  runs/    {_format_bytes(report.runs_bytes):>10}")
    typer.echo(f"  outputs/ {_format_bytes(report.outputs_bytes):>10}")
    typer.echo(f"  Total    {_format_bytes(total):>10}  (excludes .venv/)")

    typer.echo("")
    typer.echo(f"Retention pressure: {report.pressure_level.upper()} — {report.pressure_message}")


def _print_json(report: StatusReport) -> None:
    out = {
        "project_root": str(report.project_root),
        "instruments": report.instruments,
        "recent_runs": report.recent_runs,
        "strategies_count": report.strategies_count,
        "trials": {
            "live": report.trials_live,
            "archived": report.trials_archived,
            "by_mode": report.trials_by_mode,
        },
        "disk_bytes": {
            "data": report.data_bytes,
            "runs": report.runs_bytes,
            "outputs": report.outputs_bytes,
            "total": report.data_bytes + report.runs_bytes + report.outputs_bytes,
        },
        "retention_pressure": {
            "level": report.pressure_level,
            "message": report.pressure_message,
        },
    }
    typer.echo(json.dumps(out, indent=2))


def status_command(
    json_out: Annotated[
        bool, typer.Option("--json", help="Machine-readable JSON output.")
    ] = False,
    project_root: Annotated[
        Path | None,
        typer.Option(help="Override project root (for testing/alt installs)."),
    ] = None,
) -> None:
    """Print a one-screen dashboard of platform state.

    Default output: human-readable tables. With --json, emit a single JSON
    object on stdout suitable for scripting.
    """
    try:
        report = build_status_report(project_root=project_root)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_out:
        _print_json(report)
    else:
        _print_text(report)
