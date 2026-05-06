# Session 43 — Storage Cleanup CLI Implementation

**Status:** Spec
**Effort:** 1 session, code + tests + manual cross-reference
**Model:** Opus 4.7
**Depends on:** Session 40 (Chapter 56.5 ratified as the spec)
**Workload:** v1.0 manual completion

## Goal

Implement the `clean` CLI subcommand group exactly as specified in
ratified Chapter 56.5. The chapter is the contract; the code lands
to match. After this session, the storage-management gap on the v1.0
backlog is closed and the platform has working cleanup, archival,
and dry-run discipline.

## In scope

### Implementation

- `src/trading_research/cli/clean.py` — Typer subcommand group with
  five subcommands: `runs`, `canonical`, `features`, `trials`,
  `dryrun`. Wired into `src/trading_research/cli/main.py` via
  `app.add_typer(clean_app, name="clean")`.
- `src/trading_research/maintenance/reaper.py` — pure-function file
  selection + archive helpers; `--apply` is the only side-effect
  boundary.
- `src/trading_research/maintenance/retention.py` — typed
  `RetentionPolicy` model with documented defaults; loads
  `configs/retention.yaml` if present, falls back to defaults
  otherwise.
- `configs/retention.yaml` — committed with the documented defaults
  from Chapter 56.5 §56.5.4.

### Safety invariants (Chapter 56.5 §56.5.3.1)

1. Dry-run is the default; `--apply` required to delete.
2. Archive before delete; archive failure aborts the delete.
3. Manifest-aware: refuse to reap a file cited in any non-reaped
   manifest's `sources[]`.
4. Verify-clean precondition: `clean --apply` refuses if `verify`
   reports staleness; override via `--ignore-staleness`.
5. Output: tabular by default; `--json` for machine consumption.
6. Exit codes: 0 / 1 / 2 / 3 per spec.
7. Structlog `event=clean.reap` for every reap.

### Three-tier trial registry logic (§56.5.3.5)

- Live: < 180 days OR `mode=validation`.
- Compacted archive: 180–730 days, exploration-mode → monthly JSONL
  in `outputs/archive/trials/{YYYY-MM}.jsonl`.
- Deletion: > 730 days, exploration-mode, AND not referenced by any
  live `parent_sweep_id`. Validation-mode never deleted.
- DSR / multiple-testing modules read both live and archive.

### Tests

- `tests/test_clean_safety.py` — exercises every invariant above
  against a synthetic data tree.
- `tests/test_clean_trials_tiers.py` — covers all three tiers,
  including the parent_sweep_id orphan-prevention case.

### Manual touch-up

If implementation surfaces any spec deviation from Chapter 56.5,
revise the chapter to match and request re-ratification. Do not let
the code drift from the chapter.

## Out of scope

- Implementing `validate-strategy`, `status`, `migrate-trials` CLIs
  (those are session 49).
- Logging consolidation across the platform (session 50).
- Schema migration tooling (session 52).

## Hand-off after this session

- `clean runs|canonical|features|trials|dryrun` works end-to-end.
- All tests pass; no new ruff violations in the new code.
- Branch `session-43-storage-cleanup-cli` committed locally.
- Storage cleanup gap closed on the v1.0 backlog.
- Next session: 44 (Part III strategy authoring chapters).
