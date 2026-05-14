"""``trading-research migrate-trials`` — bring the trial registry to current schema.

Wraps ``trading_research.eval.trials.migrate_trials`` with a CLI surface and
the standard dry-run-by-default safety pattern.

What it changes (per ``eval/trials.py``):
  - Converts legacy flat-list format to ``{"trials": [...]}``.
  - Sets ``code_version`` to ``"pre-hardening"`` for entries that lack it.
  - Sets ``cohort_label`` to ``"pre-hardening"`` for entries that lack it.
  - Sets ``featureset_hash`` to None for entries that lack it.
  - Sets ``mode`` to ``"validation"`` for entries that lack it.
  - Sets ``parent_sweep_id`` to None for entries that lack it.
  - Promotes pre-session-35 entries with ``mode="unknown"`` to
    ``mode="validation"`` — the historical record-of-truth.

Idempotent: a second run on a fully migrated file is a no-op.

Specification: Chapter 32.5 + Chapter 49.22.

Exit codes:
    0 — registry already current, dry-run succeeded, or apply succeeded.
    1 — unexpected I/O error.
    2 — registry not found at the given path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

_PROJECT_ROOT = Path(__file__).parents[3]
_DEFAULT_REGISTRY = _PROJECT_ROOT / "runs" / ".trials.json"


def _print_diff_text(diff: dict, path: Path) -> None:
    typer.echo(f"Registry: {path}")
    if diff.get("error"):
        typer.echo(f"  ERROR: {diff['error']}", err=True)
        return
    typer.echo(f"  Total trials:                              {diff['total']}")
    if diff.get("no_op"):
        typer.echo("  Status: already current — no changes needed.")
        return
    if diff.get("format_change"):
        typer.echo("  Format: legacy flat-list → versioned dict")
    counters = [
        ("code_version (→ pre-hardening)", "would_set_code_version"),
        ("cohort_label (→ pre-hardening)", "would_set_cohort_label"),
        ("featureset_hash (→ null)", "would_set_featureset_hash"),
        ("mode (missing → validation)", "would_set_mode_validation"),
        ("parent_sweep_id (→ null)", "would_set_parent_sweep_id"),
        ("mode (unknown → validation)", "would_promote_unknown_to_validation"),
    ]
    typer.echo("  Changes:")
    for label, key in counters:
        n = diff.get(key, 0)
        if n:
            typer.echo(f"    {label}: {n}")


def migrate_trials_command(
    registry: Annotated[
        Path | None,
        typer.Option(help="Path to the trial registry JSON (default: runs/.trials.json)."),
    ] = None,
    apply: Annotated[
        bool, typer.Option("--apply", help="Apply changes (default: dry-run).")
    ] = False,
    no_backup: Annotated[
        bool,
        typer.Option(
            "--no-backup",
            help="Skip writing the .json.backup sidecar when applying.",
        ),
    ] = False,
    json_out: Annotated[
        bool, typer.Option("--json", help="Machine-readable JSON output.")
    ] = False,
) -> None:
    """Migrate the trial registry to the current schema; dry-run by default.

    Default behaviour prints a summary of changes and exits without writing.
    Pass ``--apply`` to write. Writes a ``.json.backup`` sidecar by default
    so the previous registry is recoverable.
    """
    from trading_research.eval.trials import diff_trials_migration, migrate_trials

    path = registry or _DEFAULT_REGISTRY

    if not path.is_file():
        typer.echo(f"ERROR: registry not found at {path}", err=True)
        raise typer.Exit(code=2)

    try:
        diff = diff_trials_migration(path)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_out:
        out = {
            "registry": str(path),
            "dry_run": not apply,
            **diff,
        }
        typer.echo(json.dumps(out, indent=2))
    else:
        _print_diff_text(diff, path)

    if not apply:
        if not json_out and not diff.get("no_op"):
            typer.echo("")
            typer.echo("Dry run — pass --apply to write the migrated registry.")
        return

    if diff.get("no_op"):
        return

    try:
        migrate_trials(path, backup=not no_backup)
    except Exception as exc:
        typer.echo(f"ERROR: migration failed — {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not json_out:
        typer.echo("")
        typer.echo(f"Applied. Migrated registry written to {path}.")
        if not no_backup:
            typer.echo(f"Backup at {path.with_suffix('.json.backup')}.")
