# Session 52 — Part XI Operations + final v1.0 code gaps

**Status:** Spec
**Effort:** 1 session (slightly oversized — Opus), chapter authoring +
final code gaps + status-CLI surfacings + cold-start verification
**Model:** Opus 4.7
**Depends on:** Sessions 41–51
**Workload:** v1.0 manual completion (final session)

## Goal

The closing session. Four tasks:

1. Author Part XI (operations chapters, including the cold-start
   runbook).
2. Close the remaining v1.0 code gaps: schema migration tooling +
   daily loss limit in BacktestEngine + instrument-loader
   consolidation.
3. Close the two small `status`-CLI surfacings that were deferred
   from sessions 43 and 49: per-instrument growth-rate forecast
   (Ch 56.5.6) and per-tag feature inventory (Ch 8.6).
4. Author the one-page quick reference card for the front matter,
   and verify the cold-start runbook works end-to-end on a clean
   clone.

After this session, every v1.0 backlog item is closed and the
manual is complete. The next action is operator review and v1.0
tag.

## In scope

### Part XI — Operations and Troubleshooting (~12 pages)

- **Chapter 54 — Cold-Start Procedure (~4 pages).** Pre-flight
  checks; the seven-step cold start (extending §4.8); the 30-minute
  first run. This chapter is also the verification artefact —
  it must work on a clean clone or it gets revised until it does.
- **Chapter 55 — Common Errors & Resolutions (~4 pages).** Data,
  strategy, backtest, statistical, environment errors. Cross-
  references to specific chapters.
- **Chapter 56 — Maintenance (~4 pages, ex-§56.5 which was done in
  session 40).** Adding a new instrument, rebuilding features,
  schema-change migration procedure (now that the tooling lands
  this session).
- **Chapter 57 — Versioning and Compatibility (~2 pages).** Code,
  feature-set, schema, manual versioning policies.

### Code work — three final gaps

- **Schema migration tooling.** `src/trading_research/data/migrate.py`:
  takes a parquet at SCHEMA_VERSION N, applies a migration spec,
  writes at SCHEMA_VERSION N+1; round-trip tested. CLI surface:
  `trading-research migrate-schema --layer clean|features --target-version V`.
- **Daily loss limit in BacktestEngine.** Hook into the engine: when
  cumulative day P&L drops below `daily_loss_limit_usd`, reject
  further entries for that day; emit `LossLimitTripped` exit-reason
  for any open positions. Configurable via strategy YAML's
  `risk.daily_loss_limit_usd` key.
- **Instrument-loader consolidation.** Migrate `data/instruments.py`
  to read from `configs/instruments_core.yaml`; delete
  `configs/instruments.yaml` and the legacy nested-schema loader;
  update tests. Removes the dual-store gap from session 40.

### `status`-CLI surfacings — two small additions

- **Per-instrument growth-rate forecast (Ch 56.5.6).** Extend
  `cli/status.py` to show, for each registered instrument, an
  estimated days-to-next-pressure-tier based on observed per-month
  growth in `data/{clean,features}/{symbol}_*.parquet` byte size.
  Document the heuristic in Ch 56.5.6 (~0.25 page) so the operator
  knows it is a rolling estimate, not a guarantee.
- **Per-tag feature inventory (Ch 8.6).** Extend `cli/status.py` to
  list every feature-set tag found on disk with its latest-build
  date, row count, and freshness flag against the corresponding
  CLEAN file. Closes the §8.6 [PARTIAL] marker carried over from
  session 48's work log.

Both items are pure surfacings — no new state, no new artifacts.
Each carries a unit test in `tests/cli/test_status.py`.

### Cold-start verification

On a fresh clone (or a fresh `worktree` to simulate one), follow
Ch 54 step-by-step. Record any deviation between the chapter and
the actual experience. If anything fails, the chapter is wrong;
fix it, not the operator's procedure.

### Manual touch-up

- Strip [GAP] markers from Ch 6.5, 35.2, 54, 56.3, 56.5.6.
- Strip [PARTIAL] marker from Ch 8.6.
- Update TOC gap list to reflect zero outstanding v1.0 items. The
  "Front matter | Quick-start guide" row is stale — `00-quick-start.md`
  ships [EXISTS] as of session 47; strike the row through.
- Author the **quick reference card** in the front matter
  (`docs/manual/00a-quick-reference.md`) — one page listing every CLI
  command and its one-line purpose. Lift the synopses from Chapter 49
  §49.0. This is the only Front-Matter component still missing per
  TOC line 31.
- Add the v1.0 release section to the front matter.

## Out of scope

- Post-v1.0 work (Part XII, pairs, paper, live, trade-overlay
  charts, TUI, web GUI).
- Any new manual chapter.

## Hand-off after this session

- Manual complete at v1.0.
- All v1.0 code gaps closed.
- Cold-start runbook verified end-to-end.
- Operator reviews; on acceptance, v1.0 tag is cut.
- Next session: post-v1.0 phase planning (separate roadmap).
