# Session 49 — Chapter 49 CLI Reference + ship three CLIs (bundled)

**Status:** Spec
**Effort:** 1 session, large chapter + three CLI implementations
**Model:** Opus 4.7
**Depends on:** Sessions 41–48 (Parts I–VIII done; Ch 13.4 spec
ratified for the validate-strategy linter)
**Workload:** v1.0 manual completion

## Goal

The single largest chapter in the manual (Ch 49 at ~12 pages) bundled
with the three CLI implementations whose specs land in this chapter.
Every CLI subcommand the platform exposes is documented to a
consistent format; the three [GAP] commands (`validate-strategy`,
`status`, `migrate-trials`) are implemented to match.

The bundle is necessary because Ch 49.15 and 49.16 *are* the spec for
the new commands — they have to land together, and Ch 32.5 binds
`migrate-trials` to a CLI (the helper exists; the CLI surface
doesn't).

## In scope

### Chapter 49 (~12 pages)

For each existing subcommand: synopsis, options, examples, exit
codes, output format, common errors, see-also. Sections:

- §49.1 `verify`, §49.2 `backfill-manifests`, §49.3 `rebuild clean`,
  §49.4 `rebuild features`, §49.5 `pipeline`, §49.6 `inventory`,
  §49.7 `replay`, §49.8 `backtest`, §49.9 `report`, §49.10
  `walkforward`, §49.11 `stationarity`, §49.12 `portfolio`,
  §49.13 `sweep`, §49.14 `leaderboard`, §49.17–§49.21 `clean
  runs`/`canonical`/`features`/`trials`/`dryrun` (closed in session
  43).
- §49.15 `validate-strategy` — the spec for the linter that's
  shipped this session.
- §49.16 `status` — the spec for the status dashboard CLI.
- §49.22 `migrate-trials` — the spec for the trial-migration
  subcommand.

### Code work

- `src/trading_research/cli/validate_strategy.py` — load a strategy
  YAML; resolve the feature set; evaluate each `entry`/`exits`
  expression on a 100-bar synthetic dataset; report any name-
  resolution failures, expected trade-count estimate, key problems.
  Exit 0 = clean lint, exit 1 = errors, exit 2 = warnings only.
- `src/trading_research/cli/status.py` — print: data freshness
  per registered instrument, last 5 backtest runs, registered
  strategies count, trial registry summary (live + archived
  counts), total disk footprint, retention pressure flag.
- `src/trading_research/cli/migrate_trials.py` — wrap the existing
  helper from `eval/trials.py` as a subcommand. Migrates the 18
  pre-session-35 `mode="unknown"` trials; idempotent; dry-run by
  default.
- All three commands wired into `cli/main.py` and exposed in the
  `--help` listing.
- Tests under `tests/cli/`.

### Manual touch-up

- Strip [GAP]/[PARTIAL] markers from Ch 11.7, 13.4, 32.5, 49.15,
  49.16. Update TOC gap list.

## Out of scope

- The interactive launcher (post-v1.0).
- Logging consolidation (session 50).
- Schema migration tooling (session 52).

## Hand-off after this session

- Chapter 49 ratified at quality bar.
- Three CLIs working end-to-end.
- v1.0 backlog: deferred CLIs item closed.
- Next session: 50 (Chapter 52 logging + ship logging coverage).
