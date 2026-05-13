# Chapter 49 — CLI Command Reference

> **Chapter status:** [EXISTS]. Every subcommand the platform exposes
> through `trading-research <subcommand>` is documented here at a
> consistent depth: synopsis, options, examples, exit codes, output
> format, common errors, and see-also. Section numbering matches the
> Table of Contents: §49.1–§49.14 cover the original fourteen
> subcommands; §49.15–§49.16 cover the three new commands shipped this
> session (`validate-strategy`, `status`); §49.17–§49.21 cover the five
> `clean` subcommands shipped in session 43; §49.22 covers
> `migrate-trials`.

---

## 49.0 What this chapter covers

The CLI is the platform's API (Chapter 3 §3.6). Every operation — data
acquisition, validation, backtesting, walk-forward, sweeps,
leaderboards, reports, replay, cleanup, status — is reachable as a
single `trading-research <subcommand>` invocation with parseable
output and a well-defined exit code. There is no other entry point that
does anything the CLI cannot do; a future GUI is a thin shell over
these commands, never a re-implementation. This chapter is the
exhaustive reference.

After reading this chapter you will be able to:

- Find the exact option name for any operation without grepping the
  source
- Predict the exit-code behaviour of any command so you can wire
  commands into shell pipelines and CI
- Know which commands are read-only, which write to the filesystem,
  and which have a `--dry-run`/`--apply` safety pattern
- Recognise the JSON output shapes for scripting use

Reading order: skim §49.1 to confirm the universal conventions, then
jump to the subcommand you need. Cross-references at the end of each
section link to the chapter that explains the underlying capability in
depth.

### Universal conventions

These hold for every subcommand in this chapter; individual sections
note exceptions only when they exist.

- **Help.** `--help` on any command prints option list and short
  description; exit code 0.
- **Exit codes (default mapping).** `0` = success; `1` = unexpected
  error (I/O failure, internal exception); `2` = bad usage (unknown
  symbol, malformed flag, missing file); `3` = refused due to a
  safety precondition (used by `clean --apply` when `verify` reports
  staleness — see §49.17). Sections that deviate from this mapping
  call it out.
- **Stdout vs stderr.** Tabular and human-readable output goes to
  stdout. Errors, warnings, and progress lines go to stderr. JSON
  output (when supported via `--json`) is a single object on stdout,
  with diagnostic text suppressed.
- **Logging.** Structured `structlog` events are emitted at module
  boundaries; the field schema is documented in
  [Chapter 52](52-logging-observability.md). The CLI does not configure
  log levels — that's a process-environment concern.
- **No interactive prompts.** Per the CLI-as-API contract
  ([Chapter 3 §3.6](03-operating-principles.md)), no command waits on
  stdin. Confirmation is expressed through opt-in flags (`--apply`,
  `--prune-validation`).
- **Path resolution.** Override flags (`--data-root`, `--runs-root`,
  `--out`, `--project-root`) are absolute or relative-to-CWD. When
  omitted, paths resolve against the repository layout (Chapter 51).

*Why this:* the universal conventions are what make the CLI scriptable.
Anywhere they were violated in early development, a script broke six
weeks later; codifying them here is the contract every command must
keep.

---

## 49.1 `verify`

**Synopsis**

```
uv run trading-research verify [--data-root PATH]
```

**Purpose.** Walk every parquet under `data/` and report whether each
file's manifest sidecar is present and current relative to its sources.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--data-root PATH` | `data/` | Override the data root (useful for tests) |

**Exit codes**

| Code | Meaning |
|------|---------|
| 0 | All manifests present and not stale |
| 1 | One or more files have missing or stale manifests |

**Output format.** A line per file: status (`OK`, `STALE`,
`NO MANIFEST`), path, and a reason for non-`OK` entries. Trailing
summary: `<N> OK, <M> stale, <K> missing`.

**Common errors.** None — the command does not modify state.

**See also.** Chapter 4 §4.4 (manifest schema and staleness rules),
§49.17 (`clean runs` honours `verify` as a precondition),
[`pipeline/verify.py`](../../src/trading_research/pipeline/verify.py).

---

## 49.2 `backfill-manifests`

**Synopsis**

```
uv run trading-research backfill-manifests [--dry-run] [--data-root PATH]
```

**Purpose.** Write manifest sidecars for parquet files that predate the
manifest convention. Sessions 02–04 produced parquets without
manifests; this command computes them retroactively from file mtime
and source content. Each backfilled manifest carries `backfilled:
true` so a downstream consumer can distinguish them.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--dry-run` | off | Print what would be written, write nothing |
| `--data-root PATH` | `data/` | Override the data root |

**Exit codes.** `0` always (informational), `2` on data-root not found.

**Output format.** `Backfill complete: <N> manifests written.` or
`Dry run: <N> manifests would be written.`

**See also.** Chapter 4 §4.4, [`pipeline/backfill.py`](../../src/trading_research/pipeline/backfill.py).

---

## 49.3 `rebuild clean`

**Synopsis**

```
uv run trading-research rebuild clean --symbol SYM [--data-root PATH]
```

**Purpose.** Rebuild every CLEAN file (1m back-adjusted, 1m unadjusted,
plus 5m / 15m / 60m / 240m / 1D resamples) for `SYM` from already-cached
RAW contracts. Does **not** call the TradeStation API. If RAW contracts
are missing, the command fails fast with a `FileNotFoundError`-style
message; run `pipeline` to download.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--symbol SYM` | required | Instrument symbol (e.g. `ZN`, `6E`) |
| `--data-root PATH` | `data/` | Override the data root |

**Exit codes.** `0` success; `1` rebuild error; `2` unknown symbol or
missing RAW contracts.

**Output format.** A progress line per timeframe written, with the
output path. The final line is the count of CLEAN files produced.

**See also.** Chapter 4 §4.7 (cold-start checklist), §49.5
(`pipeline` is the supertype that includes this stage).

---

## 49.4 `rebuild features`

**Synopsis**

```
uv run trading-research rebuild features --symbol SYM [--set TAG] [--data-root PATH]
```

**Purpose.** Apply a named feature-set (default `base-v1`) to the CLEAN
parquets for `SYM`, producing FEATURES parquets keyed by
`(symbol, timeframe, feature-set-tag)`.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--symbol SYM` | required | Instrument symbol |
| `--set TAG` | `base-v1` | Feature-set tag from `configs/featuresets/<tag>.yaml` |
| `--data-root PATH` | `data/` | Override the data root |

**Exit codes.** `0` success; `1` build error; `2` unknown symbol or
feature-set tag.

**See also.** Chapter 8 (Feature Sets), Chapter 7 (Indicator Library).

---

## 49.5 `pipeline`

**Synopsis**

```
uv run trading-research pipeline --symbol SYM [--set TAG]
                                  [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                                  [--skip-validate] [--data-root PATH]
```

**Purpose.** Run the three-stage data pipeline end-to-end: download &
rebuild CLEAN → validate against the trading calendar → rebuild
FEATURES. This is the **Track A acceptance gate**: it must succeed for
any registered instrument without code changes beyond
`configs/instruments_core.yaml`.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--symbol SYM` | required | Instrument symbol |
| `--set TAG` | `base-v1` | Feature-set tag |
| `--start YYYY-MM-DD` | full history | Restrict download/build to a start date |
| `--end YYYY-MM-DD` | today | Restrict to an end date |
| `--skip-validate` | off | Skip stage 2 (the data quality gate) |
| `--data-root PATH` | `data/` | Override the data root |

**Exit codes.** `0` success; `1` rebuild or validation error; `2` bad
input (unknown symbol, missing dependencies).

**Output format.** Three stage banners (`Stage 1/3 — CLEAN`,
`Stage 2/3 — VALIDATE`, `Stage 3/3 — FEATURES`). The validate stage
prints row count, duplicate timestamps, negative volumes, inverted
OHLC, large-gap count split into RTH vs overnight, and buy/sell
volume coverage percentage. Closes with `Pipeline complete`.

**Common errors.** Missing RAW contracts on first run (the command
downloads them); structural validation failure on dirty data
(duplicates, negative volumes, inverted OHLC, null required fields).
Gap warnings on back-adjusted continuous contracts are informational
and do not abort the pipeline.

*Why this:* one command end-to-end is the contract that lets a new
instrument come online by editing config and nothing else. Any change
that splits the pipeline into manual steps belongs in `rebuild` or
elsewhere, never in `pipeline`.

**See also.** Chapter 4 (Data Pipeline), Chapter 6 (Bar Schema &
Calendar Validation), [`pipeline/rebuild.py`](../../src/trading_research/pipeline/rebuild.py).

---

## 49.6 `inventory`

**Synopsis**

```
uv run trading-research inventory [--data-root PATH]
```

**Purpose.** Print a table of every data file under `data/` with its
size, row count, date range, and manifest status. The operator's
ground-truth view of what has been built.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--data-root PATH` | `data/` | Override the data root |

**Exit codes.** `0` always.

**Output format.** Columns: path, size (human-readable), row count,
date range, manifest status. Grouped by layer (RAW / CLEAN / FEATURES).

**See also.** §49.16 `status` (one-screen dashboard that complements
inventory), Chapter 51 (file layout reference).

---

## 49.7 `replay`

**Synopsis**

```
uv run trading-research replay --symbol SYM [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                [--trades PATH] [--port PORT]
```

**Purpose.** Launch the Dash trade-replay app for visual forensic work.
Renders bars, indicator overlays, and (if `--trades` is supplied) trade
markers with trigger / fill / exit annotations.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--symbol SYM` | required | Instrument symbol |
| `--from YYYY-MM-DD` | last 90 days | Window start |
| `--to YYYY-MM-DD` | today | Window end |
| `--trades PATH` | none | Trade log to overlay (any parquet/JSON the loader accepts) |
| `--port PORT` | `8050` | Dash server port |

**Exit codes.** Runs until interrupted (Ctrl-C); `2` if the symbol's
features parquet is not found.

**Output format.** Stdout prints the URL to open in the browser. All
other output is rendered in the Dash UI.

**See also.** Chapter 18 (The Replay App), [`replay/`](../../src/trading_research/replay/).

---

## 49.8 `backtest`

**Synopsis**

```
uv run trading-research backtest --strategy PATH
                                  [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                  [--out PATH]
```

**Purpose.** Run a single backtest from a YAML strategy config. Supports
all three dispatch paths automatically: YAML template (`entry:` block),
registered StrategyTemplate (`template:` key), and legacy Python
module (`signal_module:` key).

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--strategy PATH` | required | Path to a strategy YAML in `configs/strategies/` |
| `--from YYYY-MM-DD` | full history | Restrict the bar window |
| `--to YYYY-MM-DD` | full history | Restrict the bar window |
| `--out PATH` | `runs/` | Override the output root |

**Exit codes.** `0` success; `1` engine error; `2` bad config, missing
features parquet, or empty bar window.

**Output format.** Three written artefacts (`trades.parquet`,
`equity_curve.parquet`, `summary.json`) plus a stdout summary table
showing point estimates with 90% bootstrap CIs and deflated Sharpe
(Chapter 23). The backtest also records a trial entry in
`runs/.trials.json` ([Chapter 32](32-trial-registry-leaderboard.md)).

**Common errors.** Unknown symbol, features parquet not built yet,
expression error in the strategy YAML, conflicting dispatch keys.
Use `validate-strategy` (§49.15) to surface expression errors before
running the backtest.

**See also.** Chapter 14 (Backtest Engine), Chapter 16 (Running a
Backtest), Chapter 17 (Trader's Desk Report).

---

## 49.9 `report`

**Synopsis**

```
uv run trading-research report RUN_ID [--ts TIMESTAMP] [--out PATH]
```

**Purpose.** Generate the Trader's Desk HTML report for a completed
backtest run. Writes a self-contained `report.html`, plus
`pipeline_integrity.md` and `data_dictionary.md` companions.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `RUN_ID` | required | Strategy directory name under `runs/` |
| `--ts TIMESTAMP` | latest | Specific timestamped run directory; else picks newest |
| `--out PATH` | `runs/` | Override the runs root |

**Exit codes.** `0` success; `2` run directory not found.

**Output format.** Three written files; stdout prints each path. The
pipeline-integrity report runs as a non-fatal extra; failure emits a
WARNING but does not change the exit code.

**See also.** Chapter 17 (Trader's Desk Report), Chapter 53
(Appendix D — full Help output).

---

## 49.10 `walkforward`

**Synopsis**

```
uv run trading-research walkforward --strategy PATH
                                     [--n-folds N] [--gap BARS] [--embargo BARS]
                                     [--trial-group LABEL] [--out PATH]
```

**Purpose.** Run a purged walk-forward robustness test on a strategy.
Produces per-fold OOS metrics, an OOS equity curve, and an aggregated
fold-variance table. The headline gate criterion is
"OOS Calmar > 0 across the majority of folds"
([Chapter 22 §22.6](22-walk-forward-validation.md)).

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--strategy PATH` | required | Strategy YAML |
| `--n-folds N` | `10` | Number of contiguous folds |
| `--gap BARS` | `100` | Purge between train and test |
| `--embargo BARS` | `50` | Embargo after test |
| `--trial-group LABEL` | strategy_id | Cohort for deflated-Sharpe counting |
| `--out PATH` | `runs/` | Override the runs root |

**Exit codes.** `0` success; `1` walk-forward error.

**Output format.** `walkforward.parquet`, `walkforward_equity.parquet`,
plus a stdout per-fold table and aggregated OOS line.

**See also.** Chapter 22 (Walk-Forward Validation), Chapter 23
(Deflated Sharpe).

---

## 49.11 `stationarity`

**Synopsis**

```
uv run trading-research stationarity --symbol SYM
                                      [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                                      [--timeframes 1m,5m,15m] [--out PATH]
```

**Purpose.** Run the ADF / Hurst / Ornstein-Uhlenbeck half-life suite on
CLEAN 1m bars for the symbol, across the requested timeframes. Outputs
a parquet, a JSON summary, and a Markdown report under
`runs/stationarity/<SYM>/<ts>/`.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--symbol SYM` | required | Instrument symbol |
| `--start` / `--end` | full history | Restrict the bar window |
| `--timeframes` | `1m,5m,15m` | Comma-separated TF list |
| `--out PATH` | `runs/` | Override the runs root |

**Exit codes.** `0` success; `2` unknown symbol or missing CLEAN data.

**See also.** Chapter 24 (Stationarity Suite),
[`stats/stationarity.py`](../../src/trading_research/stats/stationarity.py).

---

## 49.12 `portfolio`

**Synopsis**

```
uv run trading-research portfolio RUN_ID [RUN_ID...] [--output-dir PATH]
```

**Purpose.** Aggregate a list of backtest runs into a multi-strategy
portfolio report: combined equity, per-strategy contribution,
correlation, aggregated drawdown.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `RUN_IDS` | required | Two or more run-id arguments |
| `--output-dir PATH` | `runs/portfolio/<ts>/` | Output location |

**Exit codes.** `0` success; `1` aggregation error.

**See also.** Chapter 40 (Portfolio Reports), Chapters 41–43
(correlation, drawdown, clustering).

---

## 49.13 `sweep`

**Synopsis**

```
uv run trading-research sweep --strategy PATH --param 'key=v1,v2,v3' [--param ...] [--out PATH]
```

**Purpose.** Cartesian-product expansion of one or more knob ranges over
a base strategy YAML. Every variant runs as an `exploration`-mode
backtest sharing a `parent_sweep_id`; the trial registry records all
of them.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--strategy PATH` | required | Base strategy YAML |
| `--param 'k=v1,v2,v3'` | repeatable | Comma-separated values per knob |
| `--out PATH` | `runs/` | Override the runs root |

**Exit codes.** `0` even when individual variants fail (the sweep is
the unit, not each variant). Variant failures are listed in stderr.

**Output format.** A per-variant row in a table: variant number, knob
values, Sharpe, Calmar, trade count. Final line: `Sweep ID: <hex>` for
later leaderboard filtering.

**Common errors.** No `--param` supplied (warns and runs a single
"identity sweep"); knob name typo (the YAML loads but the override is
ignored — `validate-strategy` will not catch this; the sweep just
produces unaffected variants).

**See also.** Chapter 31 (The Sweep Tool), Chapter 32 (Trial Registry).

---

## 49.14 `leaderboard`

**Synopsis**

```
uv run trading-research leaderboard [--filter 'key=value' ...] [--sort METRIC]
                                     [--ascending] [--html-out PATH] [--out PATH]
```

**Purpose.** Ranked listing of recorded trials. Filter and sort by any
trial field; optionally render an HTML view.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--filter 'k=v'` | repeatable | AND-combined filters on trial fields |
| `--sort METRIC` | `calmar` | Metric to sort by |
| `--ascending` | off | Reverse sort direction |
| `--html-out PATH` | none | If set, also write an HTML leaderboard |
| `--out PATH` | `runs/` | Override the runs root |

**Exit codes.** `0` always (zero results is not an error).

**Output format.** A table with columns: rank, strategy_id, mode,
timestamp, Sharpe, Sharpe CI, Calmar, Calmar CI, trades, win_rate.
Trials recorded with bootstrap CI bounds display them; older trials
without bounds show `—`.

**See also.** Chapter 32 (Trial Registry & Leaderboard), Chapter 23
(DSR — the deflation count comes from this registry).

---

## 49.15 `validate-strategy`

**Synopsis**

```
uv run trading-research validate-strategy CONFIG_PATH [--verbose] [--data-root PATH]
```

**Purpose.** Lint a strategy YAML before running a backtest. Loads the
YAML, enforces Chapter 13.2 cross-key constraints, resolves the features
parquet for the configured `symbol`/`timeframe`/`feature_set`, reads the
parquet's column schema, builds a 100-bar synthetic DataFrame on those
columns, evaluates every `entry:` and `exits:` expression against it,
and reports name-resolution failures, type errors, and trivial-rate
warnings.

The command is the implementation of Chapter 13.4 and Chapter 11.7 —
the lint-time error surface for the expression evaluator. Before this
shipped, expression errors surfaced only at backtest time and required
the operator to wait through bar loading and signal generation before
seeing a name typo.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `CONFIG_PATH` | required | Strategy YAML path |
| `--verbose` | off | Print the resolved column list and knob values |
| `--data-root PATH` | `data/` | Override the data root |

**Exit codes**

| Code | Meaning |
|------|---------|
| 0 | Strategy is syntactically valid; expressions resolved cleanly |
| 1 | One or more validation errors found |
| 2 | YAML not parseable, features parquet not found, or unknown symbol |

**Output format (clean strategy)**

```
Validating: configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml
  Dispatch:    yaml-template
  Symbol:      6A / 60m / base-v1
  Feature set: 6A_backadjusted_60m_features_base-v1_2010-01-04_2026-04-30.parquet [OK]
  Synthetic signal rate: long=12%, short=9% on 100-bar test

  No errors.
```

**Output format (with errors)**

```
Validating: configs/strategies/bad-strategy.yaml
  Dispatch:    yaml-template
  Symbol:      6A / 60m / base-v1
  Feature set: 6A_backadjusted_60m_features_base-v1_*.parquet [OK]

  ERROR: signal generation: Name 'atr_15' is not a column (first 8: [open, high, low,
         close, volume, atr_14, rsi_14, vwap_monthly]) or a knob ([band, stop_mult])

  1 error(s) found. Fix before running backtest.
```

**Dispatch handling.** The command lints the YAML-template path
(`entry:` block) in full. For the registered-template and
`signal-module` dispatch paths, the command reports the dispatch type
but does not import or evaluate the Python module; running the
backtest on a short window remains the way to surface module-specific
errors. This is intentional — `validate-strategy` is a *static* check
for the declarative path, not a sandbox for arbitrary Python.

**Common errors and what to look for.**

| Symptom in output | Likely cause |
|-------------------|--------------|
| `features parquet not found` | Symbol/timeframe/feature-set combination has not been built; run `rebuild features` |
| `Name 'x' is not a column ... or a knob` | Typo in a column name (check `--verbose` for the column list) or a knob name (check `knobs:` block in the YAML) |
| `Invalid expression syntax 'expr'` | Python syntax error in the expression string — usually a missing operator, unbalanced parentheses, or stray quote |
| `Only numeric constants allowed; got str` | A string literal was used in an expression; expressions take bare column names and numeric literals only |
| `synthetic signal rate is 0%/0%` (warning) | Conditions never fire on synthetic data — may be correct (tight regime filter) or may indicate over-restrictive conditions |
| `synthetic signal rate exceeds 80%` (warning) | A condition may be trivially always-true |

**Limitations.** The synthetic dataset is uniform random-walk-like
numeric data, not realistic price action. A condition that depends on
exact ATR or VWAP relationships will fire at a rate that has no
predictive value for the real backtest. Use signal-rate warnings as a
sanity check that conditions are not *trivially* wrong, not as an
expected-trade-count estimator.

*Why this:* the expression evaluator is the YAML strategy path's
contract surface, and most authoring mistakes (column typos, knob
mis-references, missing operators) are caught the moment the
expression evaluates against a real schema. Catching them before a
backtest run is the difference between a fifteen-second iteration loop
and a fifteen-minute one.

**See also.** Chapter 11 (Expression Evaluator), Chapter 13.4 (the
spec this command implements),
[`cli/validate_strategy.py`](../../src/trading_research/cli/validate_strategy.py).

---

## 49.16 `status`

**Synopsis**

```
uv run trading-research status [--json] [--project-root PATH]
```

**Purpose.** One-screen dashboard of platform state — data freshness
per registered instrument, the last five backtest runs, registered
strategy count, trial registry counts (live and compacted archive),
disk footprint by layer, and the retention-pressure flag from
Chapter 56.5 §56.5.6.3.

This is the command the operator runs after a long absence to figure
out where things are. It is read-only, fast (sub-second on a healthy
project), and produces both human-readable and JSON output.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--json` | off | Emit a single JSON object on stdout; suppress diagnostic text |
| `--project-root PATH` | repo root | Override the project root |

**Exit codes**

| Code | Meaning |
|------|---------|
| 0 | Report generated |
| 1 | Unexpected I/O error reading a manifest or the registry |

**Sections of the human-readable output**

1. **Data freshness** — one row per registered instrument with symbol,
   name, end-date of the latest CLEAN 1m back-adjusted parquet, and
   "days behind today" computed from that end-date. Instruments with
   no CLEAN parquet show `(none)`.
2. **Recent backtest runs** — the five most recent timestamped
   run directories across all strategies. Columns: strategy_id,
   timestamp, mode (exploration / validation / unknown), trade count,
   Sharpe, Calmar. Sourced from each run's `summary.json`.
3. **Registered strategies & trials** — strategy YAML count under
   `configs/strategies/`, live trial registry count with a per-mode
   breakdown, and the count of trials in the compacted archive at
   `outputs/archive/trials/`.
4. **Disk footprint** — bytes under `data/`, `runs/`, `outputs/` and
   the total. `.venv/` is intentionally excluded — it rebuilds
   idempotently and is not part of the storage management problem
   (Chapter 56.5 §56.5.1).
5. **Retention pressure** — the level flag (green / amber / red /
   critical) and the corresponding recommended action, mirroring the
   table in Chapter 56.5 §56.5.6.3.

**JSON output shape**

```json
{
  "project_root": "...",
  "instruments": [{"symbol": "6A", "name": "...", "clean_1m_end_date": "2026-04-30", "days_behind_today": 13, "registered": true}, ...],
  "recent_runs": [{"strategy_id": "...", "timestamp": "...", "mode": "...", "total_trades": ..., "sharpe": "...", "calmar": "..."}, ...],
  "strategies_count": 19,
  "trials": {"live": 169, "archived": 0, "by_mode": {"exploration": 96, "validation": 73}},
  "disk_bytes": {"data": ..., "runs": ..., "outputs": ..., "total": ...},
  "retention_pressure": {"level": "green", "message": "no action needed."}
}
```

**See also.** Chapter 56.5 (Storage Management & Cleanup),
[`cli/status.py`](../../src/trading_research/cli/status.py).

---

## 49.17 `clean runs`

**Synopsis**

```
uv run trading-research clean runs [--strategy ID] [--keep-last N | --older-than DURATION]
                                    [--apply] [--no-archive] [--json]
                                    [--ignore-staleness]
```

**Purpose.** Reap old timestamped run directories under
`runs/<strategy_id>/`. Two selection modes (mutually exclusive):
`--keep-last N` retains the N most-recent timestamps per strategy;
`--older-than DURATION` (e.g. `90d`, `6m`) reaps anything older than
the cutoff regardless of count. The single most recent run per
strategy is always preserved, as is every run whose `summary.json`
records `mode: "validation"`.

**Shared safety pattern.** Dry-run is the default; `--apply` is
required to delete. Reaped files are archived to
`outputs/archive/runs/<strategy_id>/<YYYY-MM>.tar.gz` unless
`--no-archive` is passed. `--apply` refuses to run with exit code `3`
if `verify` reports staleness; pass `--ignore-staleness` to override
(logged loudly).

**Exit codes.** `0` success; `1` apply error; `2` bad usage; `3`
refused due to verify staleness.

**See also.** Chapter 56.5 §56.5.3.2,
[`cli/clean.py`](../../src/trading_research/cli/clean.py).

---

## 49.18 `clean canonical`

**Synopsis**

```
uv run trading-research clean canonical [--symbol SYM] [--keep-latest]
                                         [--apply] [--no-archive] [--json]
                                         [--ignore-staleness]
```

**Purpose.** For each `(symbol, timeframe, adjustment)` tuple in
`data/clean/`, keep the parquet with the latest end-date suffix and
reap the older variants. **Manifest-aware:** a CLEAN file cited as a
`sources[]` entry in any non-reaped FEATURES manifest is held back and
listed under "Pinned." `--keep-latest` is the default and only
operating mode in v1.0.

**Exit codes.** As in §49.17.

**See also.** Chapter 56.5 §56.5.3.3, Chapter 4 §4.4 (manifest
schema).

---

## 49.19 `clean features`

**Synopsis**

```
uv run trading-research clean features [--tag TAG] [--symbol SYM] [--keep-latest]
                                        [--apply] [--no-archive] [--json]
                                        [--ignore-staleness]
```

**Purpose.** Two mutually-exclusive operating modes:

- `--tag TAG` (without `--keep-latest`) reaps **all** FEATURES files
  for the named feature-set tag — for retiring an experiment tag.
- `--keep-latest` (without `--tag`) keeps the most-recent end-date
  variant per `(symbol, timeframe, tag)` and reaps the older ones.

The YAML in `configs/featuresets/` is never touched — git history is
the audit trail for the config.

**Exit codes.** As in §49.17, plus `2` for "neither flag given."

**See also.** Chapter 56.5 §56.5.3.4.

---

## 49.20 `clean trials`

**Synopsis**

```
uv run trading-research clean trials [--apply] [--json]
                                      [--compact-after DURATION]
                                      [--delete-after DURATION]
                                      [--keep-mode validation]
```

**Purpose.** Three-tier prune of the trial registry:

| Tier | Default age | What happens |
|------|-------------|--------------|
| **Live** | < 180 days, or `mode == "validation"` at any age | Nothing |
| **Compacted archive** | ≥ 180 days, exploration-mode | Moved into `outputs/archive/trials/<YYYY-MM>.jsonl`; removed from live registry |
| **Deletion** | ≥ 730 days, exploration, not referenced by any live `parent_sweep_id` | Deleted from the archive |

Validation-mode trials are never compacted or deleted at any age. The
DSR and multiple-testing modules read both the live registry and the
compacted archive when counting historical trials, so a compaction
does not change the deflation count.

**Exit codes.** `0` success; `1` apply error; `2` malformed registry.

**See also.** Chapter 56.5 §56.5.3.5, Chapter 23 (DSR), Chapter 33
(Multiple-Testing Correction).

---

## 49.21 `clean dryrun`

**Synopsis**

```
uv run trading-research clean dryrun [--json]
```

**Purpose.** Combined preview across `clean runs`, `clean canonical`,
`clean features --keep-latest`, and `clean trials`. Produces a single
table with category, reapable count, pinned count, and bytes
reclaimable, plus a total. `--apply` is intentionally not supported on
`dryrun`; to reap, run the per-category command.

**Exit codes.** `0` always.

**See also.** Chapter 56.5 §56.5.3.6.

---

## 49.22 `migrate-trials`

**Synopsis**

```
uv run trading-research migrate-trials [--registry PATH] [--apply] [--no-backup] [--json]
```

**Purpose.** Bring the trial registry to the current schema. The
migration changes the legacy flat-list JSON format to the versioned
`{"trials": [...]}` dict format and fills missing fields with
conservative defaults. Pre-session-35 entries that carry
`mode="unknown"` are promoted to `mode="validation"` — the historical
record-of-truth before the exploration/validation distinction existed.

The command binds an existing helper (`migrate_trials` in
[`eval/trials.py:267`](../../src/trading_research/eval/trials.py))
to a CLI surface with the standard dry-run-by-default pattern.

**Options**

| Flag | Default | Meaning |
|------|---------|---------|
| `--registry PATH` | `runs/.trials.json` | Path to the registry JSON |
| `--apply` | off | Apply changes (without it, the command is dry-run) |
| `--no-backup` | off | Skip the `.json.backup` sidecar on apply |
| `--json` | off | Machine-readable JSON output |

**Exit codes**

| Code | Meaning |
|------|---------|
| 0 | Registry already current, dry-run succeeded, or apply succeeded |
| 1 | Unexpected I/O error |
| 2 | Registry not found at the given path |

**Output format (dry-run with pending changes)**

```
Registry: runs/.trials.json
  Total trials:                              169
  Changes:
    mode (unknown → validation): 18

Dry run — pass --apply to write the migrated registry.
```

**Output format (already current)**

```
Registry: runs/.trials.json
  Total trials:                              169
  Status: already current — no changes needed.
```

**Idempotency.** Running `migrate-trials --apply` twice on the same
registry produces the same result. The second run is a no-op.

**Safety.** On `--apply`, a sidecar at `<registry>.json.backup` is
written before the migrated file. `--no-backup` skips this.

**See also.** Chapter 32.5 (the spec for this binding), Chapter 23
(why mode-tagging matters for DSR),
[`cli/migrate_trials.py`](../../src/trading_research/cli/migrate_trials.py).

---

## 49.23 Related references

### Code modules

- [`src/trading_research/cli/main.py`](../../src/trading_research/cli/main.py) —
  Typer app and all top-level command registrations.
- [`src/trading_research/cli/clean.py`](../../src/trading_research/cli/clean.py) —
  the `clean` sub-app (five subcommands).
- [`src/trading_research/cli/sweep.py`](../../src/trading_research/cli/sweep.py) —
  parameter-grid expansion helper used by §49.13.
- [`src/trading_research/cli/validate_strategy.py`](../../src/trading_research/cli/validate_strategy.py) —
  §49.15 implementation.
- [`src/trading_research/cli/status.py`](../../src/trading_research/cli/status.py) —
  §49.16 implementation.
- [`src/trading_research/cli/migrate_trials.py`](../../src/trading_research/cli/migrate_trials.py) —
  §49.22 implementation.

### Tests

- [`tests/test_cli.py`](../../tests/test_cli.py) — original command
  smoke tests (verify, backfill, rebuild).
- [`tests/test_clean_safety.py`](../../tests/test_clean_safety.py) —
  the safety-invariant suite for `clean`.
- [`tests/cli/test_validate_strategy.py`](../../tests/cli/test_validate_strategy.py),
  [`tests/cli/test_status.py`](../../tests/cli/test_status.py),
  [`tests/cli/test_migrate_trials.py`](../../tests/cli/test_migrate_trials.py)
  — coverage for the three commands shipped this session.

### Other manual chapters

- **Chapter 3 §3.6** — the CLI-as-API design contract that constrains
  every command in this chapter.
- **Chapter 4** — the pipeline that `verify`, `backfill-manifests`,
  `rebuild`, `pipeline`, and `inventory` operate on.
- **Chapter 13** — strategy YAML reference, the contract
  `validate-strategy` enforces.
- **Chapter 14, 17, 18, 22** — the operations behind `backtest`,
  `report`, `replay`, and `walkforward`.
- **Chapter 23, 32** — DSR and the trial registry, behind
  `leaderboard` and `migrate-trials`.
- **Chapter 31** — the sweep tool, behind `sweep`.
- **Chapter 56.5** — the storage cleanup spec implemented by §49.17–§49.21.
- **Chapter 52** — the structlog field schema that every command emits.

---

*End of Chapter 49. The next reference chapter is Chapter 50 —
Configuration Reference.*
