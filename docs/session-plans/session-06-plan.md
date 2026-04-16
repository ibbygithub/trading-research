# Session 06 — Pipeline Automation and Foundations

## Objective

Turn the conventions adopted manually in session 05 into a small, enforced CLI. By end of session: `uv run trading-research` is a working entry point with `verify`, `rebuild clean`, `rebuild features`, and `backfill-manifests` subcommands. Every file under `data/raw/`, `data/clean/`, and `data/features/` has a valid manifest sidecar. A stale CLEAN or FEATURES file can be detected and rebuilt with a single command.

**This session is foundations only. No new experimental indicators, no strategy work, no backtest engine. That's session 07+.** Ibby's explicit request: foundation before novelty.

## Required reading before starting

1. `docs/architecture/data-layering.md`
2. `docs/pipeline.md` — especially the manifest schema and cold-start checklist
3. `outputs/work-log/` — most recent session 05 summary
4. `configs/featuresets/base-v1.yaml`

---

## Context after session 05

By the start of session 06, the project state is:

| What | State |
|---|---|
| `src/trading_research/indicators/` | Full indicator suite with tests |
| `src/trading_research/indicators/features.py` | `build_features()` working, emits manifests |
| `src/trading_research/data/manifest.py` | `write_manifest()` helper exists |
| `data/clean/` | 1m, 5m, 15m, 60m, 240m, 1D parquets for ZN (backadjusted + unadjusted 1m) |
| `data/features/` | 5m and 15m `base-v1` feature parquets for ZN |
| Manifests | Present on every file **written during or after session 05**; missing on anything older |
| CLI | Does not exist |
| `pyproject.toml` | No console script entry point |

---

## Step 1 — CLI scaffolding

### 1a — Add the entry point

Edit `pyproject.toml`:

```toml
[project.scripts]
trading-research = "trading_research.cli:main"
```

Create `src/trading_research/cli/__init__.py` and `src/trading_research/cli/main.py`. Use `typer` (already a reasonable default) or stdlib `argparse` — pick one and commit. Typer gives cleaner subcommand help; argparse has zero new dependencies. **Default choice: Typer** unless a dep audit says otherwise.

### 1b — Command skeleton

```
uv run trading-research --help

Commands:
  verify              Walk all manifests and report staleness
  rebuild clean       Regenerate CLEAN from RAW
  rebuild features    Regenerate a feature set from CLEAN
  backfill-manifests  Write manifest sidecars for files that predate the convention
  inventory           Print a table of all data files, their sizes, row counts, and manifest status
```

Each command is a thin typer callback that delegates to a module in `src/trading_research/pipeline/`.

### 1c — `uv sync && uv run trading-research --help` green

Test: a dedicated `tests/test_cli.py` invokes the CLI entry point via typer's `CliRunner` and asserts that `--help` exits 0 and the subcommand list is correct.

---

## Step 2 — Manifest module hardening

Session 05 wrote a small `write_manifest()` helper. Session 06 promotes it to a proper module.

### 2a — `src/trading_research/pipeline/manifest.py`

Functions:

```python
def write_manifest(parquet_path: Path, manifest: dict) -> Path: ...
def read_manifest(parquet_path: Path) -> dict | None: ...
def manifest_path_for(parquet_path: Path) -> Path: ...
def build_raw_manifest(...) -> dict: ...
def build_clean_manifest(...) -> dict: ...
def build_features_manifest(...) -> dict: ...
def is_stale(parquet_path: Path) -> tuple[bool, list[str]]: ...
```

`is_stale` returns `(True, ["reason 1", "reason 2"])` or `(False, [])`. Reasons:
- `"source missing: <path>"`
- `"source newer: <path> built_at > self built_at"`
- `"code commit unknown"` (treated as warning, not failure)
- `"parameters drift: <key>"` (for FEATURES vs current feature-set YAML)
- `"schema version mismatch"`

### 2b — Tests

`tests/test_manifest.py`:
- Roundtrip: write + read = identity
- Stale detection: construct two temp parquets, make source newer, assert stale
- Missing source: remove source, assert stale
- Fresh: all timestamps in order → `is_stale` returns False

---

## Step 3 — `verify` command

Walks `data/raw/`, `data/clean/`, `data/features/` in order. For each parquet:

1. Check for manifest sidecar. If missing → report `NO_MANIFEST`.
2. If present, run `is_stale`. If stale → report reasons.
3. If fresh → OK.

Output format:

```
RAW     66 files    66 OK
CLEAN   10 files     8 OK    2 STALE
  data/clean/ZN_backadjusted_5m_....parquet
    source newer: data/clean/ZN_1m_backadjusted_....parquet
FEATURES 2 files    2 OK

Summary: 78 files total, 76 OK, 2 stale, 0 missing manifests.
Exit code: 1 (stale files present)
```

Exit code: 0 if all OK, 1 if any stale or missing manifest. Useful for CI and pre-commit.

Tests: synthetic `tmp_path` with a few parquets, some stale, some fresh.

---

## Step 4 — `backfill-manifests` command

Writes manifests for files that predate the convention: everything in `data/raw/contracts/`, the original full ZN pull, and any CLEAN file written before session 05 (1m backadjusted, 1m unadjusted, 5m, 15m that were built in session 04).

### 4a — Strategy

For each existing file, reconstruct the manifest from:
- File-level facts (row count, date range, file mtime as built_at)
- Known source chain (TYH10..TYM26 → ZN back-adjusted → resamples), inferred from filename and project history
- Current code commit as the `code_commit` field (with a note in the manifest: `"backfilled": true`)

### 4b — Implementation

`src/trading_research/pipeline/backfill.py` contains per-layer backfill functions:

```python
def backfill_raw_contract(path: Path) -> dict: ...
def backfill_raw_bulk(path: Path) -> dict: ...
def backfill_clean(path: Path) -> dict: ...
```

The CLI command is `uv run trading-research backfill-manifests [--dry-run]`. Dry-run prints what would be written; without it, writes the sidecars.

### 4c — Tests

Use the existing on-disk data (read-only) with a `tmp_path` copy:
- Copy a few contract parquets and a CLEAN parquet to `tmp_path`
- Run `backfill-manifests` against `tmp_path`
- Assert manifest sidecars exist, `"backfilled": true` is set, row counts match

### 4d — Run it for real

End of step 4: run `uv run trading-research backfill-manifests` against the actual `data/` directory. Then `uv run trading-research verify` should report all OK.

---

## Step 5 — `rebuild clean` command

Regenerate CLEAN files from RAW deterministically.

### 5a — What it does

```
uv run trading-research rebuild clean --symbol ZN
```

Steps:
1. Locate the RAW sources for the symbol (currently: `data/raw/contracts/TY*.parquet`).
2. Rebuild the back-adjusted continuous series via existing `build_back_adjusted_continuous()`.
3. Write `ZN_1m_backadjusted_...parquet` and `ZN_1m_unadjusted_...parquet` + manifests.
4. Resample to 5m, 15m, 60m, 240m, 1D + manifests.
5. Print a summary: which files changed, how long each step took.

### 5b — Idempotency

Running `rebuild clean` twice in a row when nothing has changed should produce identical manifests (byte-for-byte of the manifest content minus timestamps — add a `--check` mode that exits nonzero if output differs from what was already on disk). This is the test that determinism works.

### 5c — Tests

- Happy path: `tmp_path` with synthetic RAW contracts → rebuild → CLEAN files exist with valid manifests
- Determinism: two rebuilds in a row, manifests compare equal on parameters + source hashes (not on `built_at`)

---

## Step 6 — `rebuild features` command

Regenerate a named feature set from CLEAN.

### 6a — What it does

```
uv run trading-research rebuild features --set base-v1 --symbol ZN
```

Steps:
1. Load `configs/featuresets/base-v1.yaml`.
2. For each target timeframe in the config, call `build_features()` (from session 05).
3. Write the feature parquets + manifests.
4. Print summary.

### 6b — `--set experiment-13min` path

The worked example in `docs/pipeline.md` shows a 13-minute experiment. This command is what enables it: one flag to build a whole feature set under a new tag, no copying, no hand-editing.

### 6c — Tests

- Build `base-v1` for a synthetic short CLEAN series → assert feature file exists with expected columns
- `--set` with a missing YAML → clean error message, exit code 2
- `--symbol` not in the registry → clean error, exit code 2

---

## Step 7 — `inventory` command

A human-readable summary of everything in `data/`. Columns:

```
Layer    Symbol  TF   Adjust     Rows        Range                 Manifest  Stale?
RAW      TY(*)   1m   raw       ~5.2M       2010-01 .. 2026-04     OK         no
CLEAN    ZN      1m   backadj    4,673,993   2010-01-03 .. 2026-04 OK         no
CLEAN    ZN      5m   backadj    1,064,432   2010-01-03 .. 2026-04 OK         no
...
FEATURES ZN      5m   backadj    1,064,432   2010-01-03 .. 2026-04 OK         no  (base-v1)
```

Pure read-only. Useful for the cold-start checklist in `docs/pipeline.md`.

---

## Step 8 — Documentation updates

### 8a — `docs/pipeline.md`

Update the cold-start checklist to reference the real commands:
- Step 5: `uv run trading-research verify`
- Step 7: `uv run trading-research rebuild clean` / `rebuild features --set base-v1`
- Add a new "CLI reference" section with the subcommand summary

### 8b — `CLAUDE.md`

Update the session-06 entry in the pipeline build order (if still relevant) and confirm the `docs/pipeline.md` pointer is in place.

### 8c — Work log

End-of-session work log as always, plus: if any session 05 deferred items were fixed incidentally, note them.

---

## Out of scope for session 06

- New indicators
- Strategy code
- Backtest engine
- Replay app
- FX instrument feature files
- ML scaffolding
- Performance optimization beyond what `rebuild` needs
- Parallelization of rebuild
- Watch mode / filesystem triggers

These all live in session 07+.

---

## Success criteria

| Item | Done when |
|---|---|
| CLI entry point | `uv run trading-research --help` works and lists all subcommands |
| Manifest module | Read/write/stale-check functions exist with tests |
| `verify` | Walks `data/` tree, reports status, correct exit codes |
| `backfill-manifests` | Dry-run works, real run writes manifests for all pre-existing files |
| All existing data has manifests | `verify` reports 0 missing-manifest files |
| `rebuild clean` | Idempotent rebuild of ZN CLEAN from RAW, deterministic |
| `rebuild features --set base-v1` | Produces identical feature files to what session 05 wrote |
| `inventory` | Prints a clean table of all data files |
| `docs/pipeline.md` CLI reference | Section added, cold-start checklist updated to use real commands |
| Test suite | All tests pass. Target: session 05 total + CLI tests + manifest tests ≈ 130+ |
| First real rebuild | `uv run trading-research rebuild clean && uv run trading-research rebuild features --set base-v1 && uv run trading-research verify` all green in sequence |
