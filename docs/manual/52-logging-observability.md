# Chapter 52 — Logging & Observability

> **Chapter status:** [EXISTS] — every section in this chapter describes
> a capability present in the platform. The structlog field schema, the
> `run_id` propagation contract, the rotating JSONL file logger, and the
> `tail-log` CLI all ship.

---

## 52.0 What this chapter covers

This chapter is the operator's reference for how the platform logs.
Logging in a research codebase is not decoration — it is the only
honest record of what a pipeline did, in what order, and under which
conditions. A backtest that produces a beautiful HTML report tells you
*what the numbers were*. The log tells you *which feature set was
loaded, which bars were dropped during validation, which trial
parameters were tried, and which warnings the data scientist persona
was about to flag*. After this chapter you will know:

- The seven well-known fields every log event carries
- How a single `run_id` ties together a data pull, a backtest, a
  walk-forward run, and the published report
- Where log files live on disk, how they rotate, and how long they are
  kept
- How to filter the log stream with the `tail-log` CLI

This chapter is roughly 4 pages. It is referenced by Chapter 3
(Operating Principles §3.6), Chapter 49 (CLI Reference §49.0,
§49.23), and Chapter 56.5 (Storage Management §56.5.3.1) — the last
one because every reap event emits a log line that follows this
chapter's schema.

---

## 52.1 Structured logging with structlog

The platform standardises on [structlog](https://www.structlog.org/)
configured through
[`src/trading_research/utils/logging.py`](../../src/trading_research/utils/logging.py).
Every module that emits log events imports the same `get_logger`
helper:

```python
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)
```

`get_logger(__name__)` returns a structlog `BoundLogger` that resolves
its configuration on first use. The configuration is set up once at
process entry by `_init_cli_logging()` in
[`src/trading_research/cli/main.py`](../../src/trading_research/cli/main.py).
Outside the CLI (tests, library use) the default structlog
configuration is used.

### 52.1.1 The shared field schema

Every event uses seven well-known keys. These are the *filter surface*
— the keys you can pass to `tail-log --field`. Domain-specific keys
are encouraged on top of these but the seven are guaranteed:

| Key | Purpose | Example |
|-----|---------|---------|
| `run_id`    | Opaque ID for one pipeline-driving CLI invocation. | `20260513T184217Z-a1b2c3` |
| `symbol`    | Instrument symbol when an event is scoped to one. | `ZN`, `6A` |
| `timeframe` | Bar timeframe when relevant. | `1m`, `5m`, `60m` |
| `stage`     | Pipeline stage. | `clean`, `features`, `backtest`, `report`, `verify`, `bootstrap` |
| `action`    | Verb describing what happened. | `start`, `finish`, `error`, `write`, `read`, `skip` |
| `outcome`   | Coarse result tag. | `ok`, `warning`, `failure` |
| `event`     | Short snake_case message name (structlog's positional). | `build_features_start`, `manifest_written` |

The set is declared at
[`src/trading_research/utils/logging.py:48-56`](../../src/trading_research/utils/logging.py#L48)
as `SCHEMA_FIELDS` and a test in
[`tests/test_logging_schema.py:36-46`](../../tests/test_logging_schema.py#L36)
locks it. If you find yourself wanting a new well-known key, change
that constant *and* this chapter.

### 52.1.2 The discipline: stage boundaries, not loops

The structlog standard reaches all hot-path modules:

| Module | Stage events |
|--------|--------------|
| [`data/continuous.py`](../../src/trading_research/data/continuous.py) | `contract_*`, `build_back_adjusted_continuous` start/finish |
| [`data/resample.py`](../../src/trading_research/data/resample.py) | per-timeframe resample completion |
| [`data/validate.py`](../../src/trading_research/data/validate.py) | `validate_bar_dataset` start/finish, gap reports |
| [`data/manifest.py`](../../src/trading_research/data/manifest.py) | `manifest_written`, stale reasons |
| [`indicators/features.py`](../../src/trading_research/indicators/features.py) | `build_features_start`, `features_built` |
| [`pipeline/verify.py`](../../src/trading_research/pipeline/verify.py) | `verify_start`, `layer_scanned`, `verify_complete` |
| [`pipeline/inventory.py`](../../src/trading_research/pipeline/inventory.py) | `inventory_start`, `inventory_complete` |
| [`pipeline/rebuild.py`](../../src/trading_research/pipeline/rebuild.py) | `rebuild_clean_*`, `rebuild_features_*` per stage |
| [`backtest/engine.py`](../../src/trading_research/backtest/engine.py) | engine-internal warnings, mulligan events |
| [`eval/report.py`](../../src/trading_research/eval/report.py) | `report_start`, `report_complete` |
| [`eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py) | `bootstrap_start`, `bootstrap_complete`, `bootstrap_skipped` |

The convention is **log at stage boundaries (start, finish, error),
not inside tight loops**. A backtest that runs 100,000 bars does not
write 100,000 log lines — it writes one start, one finish, and one
error per failure mode. Loops that need progress visibility use a
progress bar (typer's `progressbar`) or summary counters in the
finish event.

> *Why this:* The log file is intended to be human-readable in
> aggregate via `tail-log`. A million debug events per run drowns the
> signal. The boundary discipline keeps the file informative enough
> to scan but small enough to grep.

---

## 52.2 Run IDs and correlation

Every pipeline-driving CLI generates a fresh `run_id` at entry and
binds it into structlog's `contextvars`. Every log event for the
remainder of the process automatically inherits the field. Helpers in
[`src/trading_research/utils/logging.py:175-220`](../../src/trading_research/utils/logging.py#L175):

- `new_run_id()` — returns a sortable, unique identifier of the form
  `{YYYYMMDDTHHMMSSZ}-{hex6}`.
- `bind_run_id(run_id, *, stage=..., **fields)` — context manager that
  binds `run_id` (and optional schema fields) for the lifetime of a
  block.
- `get_run_id()` — returns the currently bound `run_id`, or `None`.

The CLI helper `_init_cli_logging(stage, **fields)` in
[`src/trading_research/cli/main.py:32-50`](../../src/trading_research/cli/main.py#L32)
does all four things at once: configures stderr + file handlers,
mints a fresh `run_id`, and binds it (with `stage` and any
caller-supplied fields) for the rest of the command's body.

### 52.2.1 Which CLIs generate run IDs

Pipeline-driving commands — those that produce artifacts and traverse
multiple stages — generate run IDs:

| CLI subcommand | Bound `stage` | Bound fields |
|----------------|---------------|--------------|
| `pipeline`              | `pipeline`         | `symbol`, `feature_set` |
| `rebuild clean`         | `rebuild_clean`    | `symbol` |
| `rebuild features`      | `rebuild_features` | `symbol`, `feature_set` |
| `backtest`              | `backtest`         | `strategy` |
| `walkforward`           | `walkforward`      | `strategy`, `n_folds` |
| `sweep`                 | `sweep`            | `strategy` |
| `report`                | `report`           | `run_id_arg` (the report target's run dir) |

Read-only or one-shot commands (`verify`, `inventory`, `status`,
`validate-strategy`, `migrate-trials`, `tail-log`) do not allocate a
run ID. Their events flow to stderr only — the file logger is opt-in
via `configure_file_logging(run_id)` and the pipeline-drivers are the
only callers.

### 52.2.2 Correlation across stages

Because `run_id` is bound via structlog's `contextvars`, every
downstream module's log events inherit it for free — there is no
manual plumbing through function signatures. A `backtest` invocation
calls `bootstrap_summary` deep inside; the bootstrap module's
`bootstrap_start`/`bootstrap_complete` events arrive in the JSONL
file with the parent backtest's `run_id`. Filter on that `run_id`
with `tail-log` to see everything that happened during the run, in
order.

---

## 52.3 Log file locations and retention

Two sinks are active when a pipeline-driving CLI is running:

1. **Stderr** — human-readable single-line events via structlog's
   `ConsoleRenderer`. This is the operator-facing channel; it is what
   you see while a backtest is running.
2. **JSONL file** — at
   `logs/{YYYY-MM-DD}/{run_id}.jsonl`, one event per line. UTC date
   directory. The directory is the unit of retention (see below).

The path layout is fixed by
[`src/trading_research/utils/logging.py:configure_file_logging`](../../src/trading_research/utils/logging.py#L121).

### 52.3.1 Path layout

```
logs/
├── 2026-05-13/
│   ├── 20260513T184217Z-a1b2c3.jsonl      # one backtest run
│   ├── 20260513T192201Z-d4e5f6.jsonl      # one rebuild features run
│   └── 20260513T215803Z-7a8b9c.jsonl
├── 2026-05-14/
│   └── 20260514T103015Z-1f2e3d.jsonl
└── 2026-05-15/
    └── ...
```

The `logs/` root is `.gitignore`d; nothing in it is ever committed.

### 52.3.2 Retention

Retention is governed by the `logs:` block in
[`configs/retention.yaml`](../../configs/retention.yaml):

```yaml
logs:
  retention_days: 30
  archive_dir: outputs/archive/logs/
```

The reaping function is
[`reap_old_log_dirs`](../../src/trading_research/utils/logging.py#L237)
in `utils/logging.py`. The unit of retention is the **date directory**,
not the file — once a day is past, that whole directory either gets
archived to `outputs/archive/logs/{YYYY-MM-DD}/` or removed entirely.
The function supports dry-run by default; an explicit `dry_run=False`
performs the move/delete.

> *Why directory-as-unit:* Files within a day's directory are
> co-temporal and share a query pattern ("what happened on Tuesday").
> Reaping at directory granularity makes `find` faster and tarballs
> larger but fewer.

A future `trading-research clean logs` subcommand will wrap this
function as part of the Chapter 56.5 cleanup group.

---

## 52.4 The observability ladder

The platform's observability is structured in three layers, listed
from highest to lowest signal-to-noise:

1. **Per-run summary log (`runs/<strategy_id>/<ts>/summary.json`).**
   Not a structlog file — a JSON dictionary written by the backtest
   engine at the end of a run, capturing the headline metrics, CI
   bounds, DSR, and provenance. This is what the Trader's Desk report
   consumes (Chapter 17). The summary log is what an operator looks
   at when answering "did this run produce a tradeable result?"
2. **Per-run event log (`logs/{date}/{run_id}.jsonl`).** The structlog
   JSONL file. Every event during the run, in order. This is what
   `tail-log` filters. The event log answers "what happened during
   this run, including the warnings that did not break it?"
3. **Errors-only filter (`tail-log --errors-only`).** A view onto the
   event log scoped to `level >= warning`. This is the first thing
   to check after a run that did not produce a `summary.json`.

### 52.4.1 The `tail-log` CLI

Shipped at [`src/trading_research/cli/tail_log.py`](../../src/trading_research/cli/tail_log.py),
wired in [`cli/main.py`](../../src/trading_research/cli/main.py) as
`trading-research tail-log`:

```
trading-research tail-log [--run-id ID] [--field KEY=VALUE]
                          [--since DURATION] [--errors-only]
                          [--json] [--log-root PATH]
```

Filter semantics (all filters AND together):

| Flag | Effect |
|------|--------|
| `--run-id ID`     | Only events whose `run_id` exactly equals `ID`. |
| `--field k=v`     | Only events whose field `k` equals `v`. Repeatable. |
| `--since 1h`      | Only events newer than the given window (units: `s`, `m`, `h`, `d`). |
| `--errors-only`   | Only events with `level` in `error`, `critical`, `exception`. |
| `--json`          | Emit the original JSONL line verbatim (no pretty-print). |
| `--log-root PATH` | Override `logs/`; useful for archived investigations. |

Default output is one line per event: timestamp, level, event name,
remaining fields as `key=value` pairs. The flag set is the contract;
tests at
[`tests/test_tail_log.py`](../../tests/test_tail_log.py) lock each
filter independently.

### 52.4.2 Worked example

The "what went wrong in last Tuesday's backtest" workflow:

```bash
# 1. Confirm the run exists on disk.
ls logs/2026-05-13/

# 2. Get a feel for the run — last 50 events.
trading-research tail-log --run-id 20260513T184217Z-a1b2c3 | head -50

# 3. Errors only — usually one or two lines tells the story.
trading-research tail-log --run-id 20260513T184217Z-a1b2c3 --errors-only

# 4. If the failure was during the bootstrap stage:
trading-research tail-log --run-id 20260513T184217Z-a1b2c3 \
                          --field stage=bootstrap

# 5. Want the raw JSONL to pipe to jq?
trading-research tail-log --run-id 20260513T184217Z-a1b2c3 --json | jq .
```

The pattern: find the `run_id` (from the `runs/<strategy_id>/<ts>/`
directory name or from the operator-visible stderr), then peel back
the event log until the failure is located.

---

## Related references

- Chapter 3 §3.6 — CLI-as-API conventions; structured output and
  exit codes.
- Chapter 17 — Trader's Desk report; consumes `summary.json`.
- Chapter 49 §49.0 — universal CLI conventions; references this
  chapter for the field schema.
- Chapter 49 §49.23 — `tail-log` operator reference.
- Chapter 56.5 §56.5.3.1 — `clean` subcommand reaps emit events that
  obey this chapter's schema.
- `src/trading_research/utils/logging.py` — the single source of
  truth for `configure`, `configure_file_logging`, `bind_run_id`,
  `new_run_id`, `reap_old_log_dirs`, and `SCHEMA_FIELDS`.
- `configs/retention.yaml` `logs:` block — retention policy
  defaults.
