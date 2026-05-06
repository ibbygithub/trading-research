"""``trading-research clean`` subcommand group.

Five subcommands: ``runs``, ``canonical``, ``features``, ``trials``, ``dryrun``.
Implements the shared safety pattern from Chapter 56.5 §56.5.3.1:
  1. Dry-run is the default; ``--apply`` required to delete.
  2. Archive before delete; archive failure aborts the delete.
  3. Manifest-aware: refuse to reap a file cited in any non-reaped manifest.
  4. Verify-clean precondition: ``--apply`` refuses if ``verify`` reports staleness.
  5. Output: tabular default; ``--json`` for machine consumption.
  6. Exit codes: 0 / 1 / 2 / 3 per spec.
  7. Structlog ``event=clean.reap`` for every reap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

clean_app = typer.Typer(
    help="Storage cleanup: reap old files with archive-then-delete discipline.",
    no_args_is_help=True,
)

_PROJECT_ROOT = Path(__file__).parents[3]
_DATA_ROOT = _PROJECT_ROOT / "data"
_RUNS_ROOT = _PROJECT_ROOT / "runs"


def _check_staleness(data_root: Path) -> bool:
    """Run verify and return True if the pipeline is clean (not stale)."""
    from trading_research.pipeline.verify import verify_all

    result = verify_all(data_root)
    return result.clean


def _format_bytes(n: int) -> str:
    """Human-readable byte size."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


def _staleness_gate(
    apply: bool,
    ignore_staleness: bool,
    data_root: Path,
) -> None:
    """Enforce the verify-clean precondition for --apply."""
    if not apply:
        return
    if ignore_staleness:
        typer.echo("WARNING: --ignore-staleness: skipping verify-clean check.", err=True)
        return
    if not _check_staleness(data_root):
        typer.echo(
            "ERROR: verify reports stale manifests. Refusing --apply.\n"
            "Fix staleness with `rebuild` commands, or pass --ignore-staleness to override.",
            err=True,
        )
        raise typer.Exit(code=3)


# ---------------------------------------------------------------------------
# clean runs
# ---------------------------------------------------------------------------


@clean_app.command(name="runs")
def clean_runs(
    strategy: Annotated[str | None, typer.Option(help="Strategy ID to scope to.")] = None,
    keep_last: Annotated[int | None, typer.Option("--keep-last", help="Keep the N most-recent runs per strategy.")] = None,
    older_than: Annotated[str | None, typer.Option("--older-than", help="Reap runs older than DURATION (e.g. 90d, 6m).")] = None,
    apply: Annotated[bool, typer.Option("--apply", help="Actually delete (default: dry-run).")] = False,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Delete without archiving.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")] = False,
    ignore_staleness: Annotated[bool, typer.Option("--ignore-staleness", help="Skip the verify-clean check.")] = False,
    runs_root: Annotated[Path | None, typer.Option(help="Override runs/ root.")] = None,
    data_root: Annotated[Path | None, typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Reap old run directories under runs/{strategy_id}/."""
    from trading_research.maintenance.reaper import apply_reap_plan, plan_clean_runs
    from trading_research.maintenance.retention import _parse_duration, load_retention_policy

    rr = runs_root or _RUNS_ROOT
    dr = data_root or _DATA_ROOT

    _staleness_gate(apply, ignore_staleness, dr)

    older_than_days = None
    if older_than:
        older_than_days = _parse_duration(older_than)

    plan = plan_clean_runs(
        runs_root=rr,
        strategy_id=strategy,
        keep_last=keep_last,
        older_than_days=older_than_days,
    )

    if plan.errors:
        for e in plan.errors:
            typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)

    if json_out:
        typer.echo(json.dumps(plan.to_dict(dry_run=not apply), indent=2))
    else:
        if not plan.reapable:
            typer.echo("No run directories to reap.")
        else:
            typer.echo(f"{'Path':<70} {'Size':>10}  Reason")
            for c in plan.reapable:
                typer.echo(f"{str(c.path):<70} {_format_bytes(c.size_bytes):>10}  {c.reason}")
            typer.echo(f"\nReapable: {len(plan.reapable)} dirs, {_format_bytes(plan.bytes_reclaimable)}", err=True)

    if apply and plan.reapable:
        policy = load_retention_policy(_PROJECT_ROOT)
        archive_root = _PROJECT_ROOT / policy.runs.archive_dir
        deleted, failed, errors = apply_reap_plan(plan, archive_root, no_archive=no_archive)
        typer.echo(f"Applied: {deleted} deleted, {failed} failed.", err=True)
        if errors:
            for e in errors:
                typer.echo(f"  ERROR: {e}", err=True)
            raise typer.Exit(code=1)
    elif not apply and plan.reapable:
        typer.echo("\nDry run — pass --apply to delete.", err=True)


# ---------------------------------------------------------------------------
# clean canonical
# ---------------------------------------------------------------------------


@clean_app.command(name="canonical")
def clean_canonical(
    symbol: Annotated[str | None, typer.Option(help="Filter to one symbol.")] = None,
    keep_latest: Annotated[bool, typer.Option("--keep-latest", help="Keep latest per tuple (default).")] = True,
    apply: Annotated[bool, typer.Option("--apply", help="Actually delete (default: dry-run).")] = False,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Delete without archiving.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")] = False,
    ignore_staleness: Annotated[bool, typer.Option("--ignore-staleness", help="Skip the verify-clean check.")] = False,
    data_root: Annotated[Path | None, typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Reap old date-stamped CLEAN parquets, keeping the latest per (symbol, timeframe, adjustment)."""
    from trading_research.maintenance.reaper import apply_reap_plan, plan_clean_canonical
    from trading_research.maintenance.retention import load_retention_policy

    dr = data_root or _DATA_ROOT

    _staleness_gate(apply, ignore_staleness, dr)

    plan = plan_clean_canonical(data_root=dr, symbol=symbol)

    if plan.errors:
        for e in plan.errors:
            typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)

    if json_out:
        typer.echo(json.dumps(plan.to_dict(dry_run=not apply), indent=2))
    else:
        if not plan.reapable and not plan.pinned:
            typer.echo("No CLEAN files to reap.")
        else:
            if plan.reapable:
                typer.echo(f"{'Path':<70} {'Size':>10}  Reason")
                for c in plan.reapable:
                    typer.echo(f"{str(c.path.name):<70} {_format_bytes(c.size_bytes):>10}  {c.reason}")
            if plan.pinned:
                typer.echo("\nManifest-pinned (not reapable):")
                for c in plan.pinned:
                    typer.echo(f"  {c.path.name}  — {c.pin_reason}")
            typer.echo(
                f"\nReapable: {len(plan.reapable)} files, {_format_bytes(plan.bytes_reclaimable)}  |  "
                f"Pinned: {len(plan.pinned)} files",
                err=True,
            )

    if apply and plan.reapable:
        policy = load_retention_policy(_PROJECT_ROOT)
        archive_root = _PROJECT_ROOT / policy.canonical.archive_dir
        deleted, failed, errors = apply_reap_plan(plan, archive_root, no_archive=no_archive)
        typer.echo(f"Applied: {deleted} deleted, {failed} failed.", err=True)
        if errors:
            for e in errors:
                typer.echo(f"  ERROR: {e}", err=True)
            raise typer.Exit(code=1)
    elif not apply and plan.reapable:
        typer.echo("\nDry run — pass --apply to delete.", err=True)


# ---------------------------------------------------------------------------
# clean features
# ---------------------------------------------------------------------------


@clean_app.command(name="features")
def clean_features(
    tag: Annotated[str | None, typer.Option(help="Feature-set tag to retire entirely.")] = None,
    symbol: Annotated[str | None, typer.Option(help="Filter to one symbol.")] = None,
    keep_latest: Annotated[bool, typer.Option("--keep-latest", help="Keep latest per (symbol, timeframe, tag).")] = False,
    apply: Annotated[bool, typer.Option("--apply", help="Actually delete (default: dry-run).")] = False,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Delete without archiving.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")] = False,
    ignore_staleness: Annotated[bool, typer.Option("--ignore-staleness", help="Skip the verify-clean check.")] = False,
    data_root: Annotated[Path | None, typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Reap FEATURES files: either retire a tag entirely or keep-latest per tuple."""
    from trading_research.maintenance.reaper import apply_reap_plan, plan_clean_features

    dr = data_root or _DATA_ROOT

    if not tag and not keep_latest:
        typer.echo("ERROR: specify --tag <tag> or --keep-latest.", err=True)
        raise typer.Exit(code=2)

    _staleness_gate(apply, ignore_staleness, dr)

    plan = plan_clean_features(data_root=dr, tag=tag, symbol=symbol, keep_latest=keep_latest)

    if plan.errors:
        for e in plan.errors:
            typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)

    if json_out:
        typer.echo(json.dumps(plan.to_dict(dry_run=not apply), indent=2))
    else:
        if not plan.reapable:
            typer.echo("No FEATURES files to reap.")
        else:
            typer.echo(f"{'Path':<80} {'Size':>10}  Reason")
            for c in plan.reapable:
                typer.echo(f"{str(c.path.name):<80} {_format_bytes(c.size_bytes):>10}  {c.reason}")
            typer.echo(f"\nReapable: {len(plan.reapable)} files, {_format_bytes(plan.bytes_reclaimable)}", err=True)

    if apply and plan.reapable:
        archive_root = _PROJECT_ROOT / "outputs" / "archive" / "features"
        deleted, failed, errors = apply_reap_plan(plan, archive_root, no_archive=no_archive)
        typer.echo(f"Applied: {deleted} deleted, {failed} failed.", err=True)
        if errors:
            for e in errors:
                typer.echo(f"  ERROR: {e}", err=True)
            raise typer.Exit(code=1)
    elif not apply and plan.reapable:
        typer.echo("\nDry run — pass --apply to delete.", err=True)


# ---------------------------------------------------------------------------
# clean trials
# ---------------------------------------------------------------------------


@clean_app.command(name="trials")
def clean_trials(
    apply: Annotated[bool, typer.Option("--apply", help="Actually apply (default: dry-run).")] = False,
    compact_after: Annotated[str | None, typer.Option("--compact-after", help="Age threshold for compaction (default: 180d).")] = None,
    delete_after: Annotated[str | None, typer.Option("--delete-after", help="Age threshold for deletion (default: 730d).")] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")] = False,
    runs_root: Annotated[Path | None, typer.Option(help="Override runs/ root.")] = None,
) -> None:
    """Three-tier prune of the trial registry: live, compacted archive, deletion."""
    from trading_research.maintenance.reaper import apply_trial_plan, plan_clean_trials
    from trading_research.maintenance.retention import _parse_duration, load_retention_policy

    rr = runs_root or _RUNS_ROOT
    policy = load_retention_policy(_PROJECT_ROOT)

    compact_days = _parse_duration(compact_after) if compact_after else policy.trials.compact_after_days
    delete_days = _parse_duration(delete_after) if delete_after else policy.trials.delete_after_days

    plan = plan_clean_trials(
        runs_root=rr,
        compact_after_days=compact_days,
        delete_after_days=delete_days,
        keep_modes=policy.trials.keep_modes,
        archive_path=policy.trials.archive_path,
    )

    if plan.errors:
        for e in plan.errors:
            typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(plan.to_dict(dry_run=not apply), indent=2))
    else:
        total = plan.live_count + len(plan.compactable) + len(plan.deletable)
        typer.echo(f"Trial registry:        {total} entries")
        typer.echo(f"  -- live (kept):           {plan.live_count}")
        typer.echo(f"  -- compactable:          {len(plan.compactable):>3}")
        if plan.archive_targets:
            targets = ", ".join(sorted(plan.archive_targets.keys()))
            typer.echo(f"     ->  {targets}")
        typer.echo(f"  -- deletable:            {len(plan.deletable):>3}")
        typer.echo(f"\nAfter apply:           {plan.live_count} live, "
                   f"{len(plan.compactable)} archived, {len(plan.deletable)} deleted.")

    if apply and (plan.compactable or plan.deletable):
        archive_root = _PROJECT_ROOT / policy.trials.archive_path
        compacted, deleted, errors = apply_trial_plan(plan, rr, archive_root)
        typer.echo(f"Applied: {compacted} compacted, {deleted} deleted.", err=True)
        if errors:
            for e in errors:
                typer.echo(f"  ERROR: {e}", err=True)
            raise typer.Exit(code=1)
    elif not apply and (plan.compactable or plan.deletable):
        typer.echo("\nDry run — pass --apply to apply.", err=True)


# ---------------------------------------------------------------------------
# clean dryrun
# ---------------------------------------------------------------------------


@clean_app.command(name="dryrun")
def clean_dryrun(
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")] = False,
    runs_root: Annotated[Path | None, typer.Option(help="Override runs/ root.")] = None,
    data_root: Annotated[Path | None, typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Preview what all clean subcommands would do, without applying."""
    from trading_research.maintenance.reaper import (
        plan_clean_canonical,
        plan_clean_features,
        plan_clean_runs,
        plan_clean_trials,
    )
    from trading_research.maintenance.retention import load_retention_policy

    rr = runs_root or _RUNS_ROOT
    dr = data_root or _DATA_ROOT
    policy = load_retention_policy(_PROJECT_ROOT)

    runs_plan = plan_clean_runs(runs_root=rr)
    canonical_plan = plan_clean_canonical(data_root=dr)
    features_plan = plan_clean_features(data_root=dr, keep_latest=True)
    trials_plan = plan_clean_trials(
        runs_root=rr,
        compact_after_days=policy.trials.compact_after_days,
        delete_after_days=policy.trials.delete_after_days,
        keep_modes=policy.trials.keep_modes,
    )

    if json_out:
        combined = {
            "dry_run": True,
            "runs": runs_plan.to_dict(),
            "canonical": canonical_plan.to_dict(),
            "features": features_plan.to_dict(),
            "trials": trials_plan.to_dict(),
            "total_bytes_reclaimable": (
                runs_plan.bytes_reclaimable
                + canonical_plan.bytes_reclaimable
                + features_plan.bytes_reclaimable
            ),
        }
        typer.echo(json.dumps(combined, indent=2))
    else:
        typer.echo(f"{'Category':<20} {'Reapable':>10} {'Pinned':>10} {'Bytes reclaimable':>20}")
        typer.echo(
            f"{'runs':<20} {str(len(runs_plan.reapable)) + ' dirs':>10} "
            f"{'-':>10} {_format_bytes(runs_plan.bytes_reclaimable):>20}"
        )
        typer.echo(
            f"{'canonical':<20} {str(len(canonical_plan.reapable)) + ' files':>10} "
            f"{str(len(canonical_plan.pinned)) + ' files':>10} "
            f"{_format_bytes(canonical_plan.bytes_reclaimable):>20}"
        )
        typer.echo(
            f"{'features':<20} {str(len(features_plan.reapable)) + ' files':>10} "
            f"{'-':>10} {_format_bytes(features_plan.bytes_reclaimable):>20}"
        )
        typer.echo(
            f"{'trials (compact)':<20} {str(len(trials_plan.compactable)) + ' entries':>10} "
            f"{'-':>10} {'-':>20}"
        )
        typer.echo(
            f"{'trials (delete)':<20} {str(len(trials_plan.deletable)) + ' entries':>10} "
            f"{'-':>10} {'-':>20}"
        )
        total = (
            runs_plan.bytes_reclaimable
            + canonical_plan.bytes_reclaimable
            + features_plan.bytes_reclaimable
        )
        typer.echo("-" * 65)
        typer.echo(f"{'Total':<20} {'':>10} {'':>10} {_format_bytes(total):>20}")
