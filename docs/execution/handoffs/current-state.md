# Current Execution State

**Last updated:** 2026-05-13
**Status:** ⚠ **This file documents a planning model that was not adopted.**
The dispatcher-driven sub-sprint system described below
(`docs/execution/sessions/PHASE-2-LIVE/`, sub-sprint IDs like `29a`,
`29b`, `33a` etc.) was scaffolded but never used as the live execution
ledger. **Actual session execution runs off `docs/roadmap/session-specs/`
and is tracked in `outputs/work-log/`.**

If a session-start prompt or any other automation points you to this
file as the authoritative state, that prompt is stale. Follow the
**Where actual state lives** section instead.

---

## Where actual state lives

### The authoritative session-spec directory

```
docs/roadmap/session-specs/
├── README.md
├── session-23a.md ... session-47-validation-rigor.md
├── session-48-exploration-risk-portfolio.md
├── session-49-cli-reference-and-clis.md
├── ... through session-52
├── session-B1, F1, F2, F3, track-D-*
```

The next session to run is the lowest-numbered file in this directory
whose work-log does not exist in `outputs/work-log/`. Always check
this directory first; ignore any reference to PHASE-2-LIVE paths.

### Where completed sessions are recorded

Three sources, in order of authority:

1. **`outputs/work-log/YYYY-MM-DD-HH-MM-session-NN.md`** — the per-session
   work log. Densest source of truth for what changed and what's next.
2. **`git log main`** — every session lands on `main` via the
   `session-NN-<slug>` → `develop` → `main` merge chain. Look for
   `feat(session-NN):` / `docs(manual):` / `feat(eval):` commits.
3. **`docs/manual/`** — the operator's manual itself is the artifact of
   sessions 39–47.

### Status as of 2026-05-13

- **Sessions 02–47 are DONE.** All work merged into `main` and pushed
  to `origin/main`.
- **Phase 1 (sessions 29–38)** done: strategy foundation, 6E backtest,
  regime filter, Mulligan controller, Track C gate, research-lab reset,
  parameter sweep + leaderboard, YAML strategy authoring,
  ExprEvaluator, multi-timeframe join, composable regime filters,
  first structured exploration.
- **v1.0 manual completion workload (sessions 39–47)** done: manual
  scaffold and v0.2-draft TOC, Chapters 1–18 plus Chapter 56.5 (Parts
  I–IV plus storage-cleanup CLI), Chapters 19–30 (Part V — Validation
  and Statistical Rigor), DSR / CI flags / fold variance surfaced in
  the Trader's Desk Report.
- **Next eligible session:** **49** (CLI reference + remaining
  deferred CLIs — `validate-strategy`, `status`, `migrate-trials`).
  Spec at
  [`docs/roadmap/session-specs/session-49-cli-reference-and-clis.md`](../../roadmap/session-specs/session-49-cli-reference-and-clis.md).

### Why this file exists at all

The dispatcher / sub-sprint model described in the deprecated section
below was an experiment in fine-grained sprint planning that did not
match the project's actual rhythm. The session-spec model (one spec
file per session, one work log per completed session, one branch per
session merged through `develop` → `main`) is the operational reality
and is documented in
[`../../roadmap/session-specs/README.md`](../../roadmap/session-specs/README.md).

This file is preserved as a record of the abandoned experiment and as
a redirect for any tooling that still references it.

---

## DEPRECATED — original dispatcher ledger (not in use)

The section below is the original 2026-04-26 ledger. It is preserved
for historical reference only. None of its sub-sprint IDs (`29a`, `29b`,
`33a`, etc.) correspond to executed work. Do not update it; do not
treat its BLOCKED markers as live state.

> The file was the live state ledger. Every sub-sprint updates it on
> completion. The dispatcher reads this to find the next eligible
> sub-sprint.

### Status legend (original)

- `NOT_STARTED` — never executed.
- `READY` — entry-blocking sub-sprints are all DONE; can be picked up.
- `IN_PROGRESS` — picked up by a model; not yet handed off.
- `DONE` — handoff artifacts present and verified.
- `FAILED` — execution stopped without completion; needs human review.
- `MISROUTED` — last attempt was misrouted; awaiting re-route.
- `BLOCKED` — entry-blocking sub-sprints not yet DONE.

### Phase 1 (original) — sprints 29–38

| Spec ID | Original status | Notes |
|---|---|---|
| 29a, 29b, 29c, 29d | NEVER EXECUTED | session-29 ran as a single session, not four sub-sprints |
| 30a, 30b | NEVER EXECUTED | session-30 ran as a single session |
| 31a, 31b | NEVER EXECUTED | session-31 ran as a single session |
| 32a, 32b | NEVER EXECUTED | sessions 31 and 32 actually shipped on one branch |
| 33a, 33b | NEVER EXECUTED | session-33 ran as a single session |
| 34a, 34b | NEVER EXECUTED | session-34 ran as a single session |
| 35a, 35b, 35c | NEVER EXECUTED | session-35 ran as a single session |
| 36a, 36b | NEVER EXECUTED | sessions 36 and 37 actually shipped on one branch |
| 37a, 37b, 37c | NEVER EXECUTED | shipped with 36 |
| 38a, 38b, 38c, 38d | NEVER EXECUTED | session-38 ran as a single session |
| B1, D1, D2, D3, D4 | NEVER EXECUTED | tracked separately in track-D specs |
| F1, F2, F3 | NEVER EXECUTED | tracked separately as feature work |

### Phase 2 (original) — sprints 39–55

Originally specced as a live-trading workload (TS LIVE API, kill-switch
drills, first live trade). **None of this was executed.** Sessions
39–47 actually ran as the v1.0 manual completion workload. See the
session-spec directory for the active spec set.

### Notes for the dispatcher (original)

The dispatcher concept (a separate router agent that picks the next
sub-sprint) was not implemented. Future sessions should follow the
session-spec model directly:

1. Read `docs/roadmap/session-specs/session-<NN>-<slug>.md`.
2. Do the work.
3. Write the work log to `outputs/work-log/`.
4. Commit on `session-<NN>-<slug>` branch.
5. Operator merges through `develop` → `main`.

---

## How future sessions should avoid this file's confusion

If a session-start prompt template asks you to read this file or
`docs/execution/handoffs/current-state.md`:

1. Treat that prompt as stale.
2. Read this file only for the redirect to `docs/roadmap/session-specs/`
   and `outputs/work-log/`.
3. The next session is the lowest-numbered session-spec file whose
   matching work-log does not exist.
4. If a session-spec file references a model (Opus 4.7 vs Sonnet 4.6)
   that doesn't match the model in use, mention it to the operator —
   they choose whether to proceed or switch.

The session-start template at the top of session prompts also
references `docs/manual/` and the v1.0 manual completion workload —
that's the right reference set.
