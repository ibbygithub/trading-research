# Session 50 — Chapter 52 Logging + ship logging coverage (bundled)

**Status:** Spec
**Effort:** 1 session, chapter + cross-module code touch + tail-log CLI
**Model:** Opus 4.7
**Depends on:** Sessions 41–49
**Workload:** v1.0 manual completion

## Goal

Bundled session: Chapter 52 (Logging & Observability) and the cross-
module work to bring all hot-path code under structlog with a
consistent field schema. The chapter currently has four [PARTIAL]/
[GAP] markers — ~10 of 80+ modules log; no shared `run_id`; no file
logger; no `tail-log` CLI. By the end of this session, the platform
has working observability and the chapter describes it as
[EXISTS].

## In scope

### Chapter 52 (~4 pages)

- §52.1 Structured logging with structlog — the field schema:
  `run_id`, `symbol`, `timeframe`, `stage`, `action`, `outcome`,
  `event`. Conventions for nested context.
- §52.2 Run IDs and correlation — every pipeline-driving CLI
  generates a `run_id` at entry; the ID propagates through every
  stage (data download → CLEAN → FEATURES → backtest → report).
- §52.3 Log file locations — `logs/{YYYY-MM-DD}/{run_id}.jsonl`
  with rotation; default retention 30 days; configurable via
  `configs/retention.yaml` (extending the file from session 43).
- §52.4 The observability ladder — stage-level event log;
  per-run summary log; errors-only log; the `tail-log` CLI.

### Code work

- `src/trading_research/utils/logging.py` — extend the existing
  module: shared field schema; `run_id` context manager; file
  handler with rotation.
- Hot-path modules that need structlog imports + minimal logging:
  `data/contracts.py`, `data/continuous.py`, `data/resample.py`,
  `data/validate.py`, `data/manifest.py`, `indicators/features.py`,
  `pipeline/verify.py`, `pipeline/inventory.py`, `pipeline/rebuild.py`,
  `eval/report.py`, `eval/bootstrap.py`. The discipline: log at
  stage boundaries (start/finish/error), not in tight loops.
- `src/trading_research/cli/tail_log.py` — `trading-research
  tail-log [--run-id <id>] [--field key=value] [--since 1h]
  [--errors-only]`. Reads JSONL files in `logs/` and pretty-prints
  matching events. Plain text default; `--json` passes through.
- `configs/retention.yaml` — add `logs:` block extending from
  session 43.
- Tests: `tests/test_logging_schema.py` covers the run_id
  propagation; `tests/test_tail_log.py` covers filtering.

### Manual touch-up

- Strip [PARTIAL]/[GAP] markers from Ch 52.1–52.4. Update TOC gap
  list.
- Update Ch 56.5 §56.5.3.1 invariant 7 to point at the now-extant
  shared field schema.

## Out of scope

- Distributed tracing or external log aggregation — out of scope
  for v1.0.
- Replacing every `print()` in non-hot-path code — only the hot
  paths listed above.

## Hand-off after this session

- Chapter 52 ratified.
- Logging coverage lives across hot paths; `run_id` propagates;
  rotating file logger writes JSONL; `tail-log` works.
- v1.0 backlog: logging item closed.
- Next session: 51 (Part IX + Part X reference chapters + appendices).
