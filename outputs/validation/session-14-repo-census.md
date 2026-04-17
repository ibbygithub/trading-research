# Session 14 — Repo Census Report
**Date:** 2026-04-17  
**Branch:** session/14-repo-census  
**Auditor:** Claude Code (Sonnet)

---

## Summary

| Category | Directories | Tracked Files |
|---|---|---|
| Canonical (source of truth) | 10 | ~180 |
| Generated / downloaded artifact | 3 | 0 (excluded by .gitignore) |
| Archive / legacy | 1 | 3 |
| Experimental / scratch | 1 | 1 (.gitkeep) |
| Hybrid (partial tracking) | 2 | ~35 (manifests + work-logs) |
| Anomalous (path artifacts) | 2 | 0 (empty, not tracked) |
| Root-level files | — | 11 |

**Structural smells (>500 files not data/generated):** None found. `data/` is large but correctly excluded.

---

## Directory-by-Directory Classification

### `.claude/`
**Classification: canonical** | **Confidence: confident**

- 17 files: persona rules, skills, commands, local settings
- Contains: `rules/quant-mentor.md`, `rules/data-scientist.md`, `commands/data-quality-check.md`, 16 skills under `skills/`
- `.claude/settings.local.json` — local override file; should probably be in `.gitignore` (open item: low priority)
- No directories exceeding 500 files

### `Legacy/`
**Classification: archive** | **Confidence: confident**

- 3 files: two pre-migration TradeStation downloader scripts + README
- Superseded by `src/trading_research/data/tradestation/`
- Kept for reference; `MIGRATION_MANIFEST.md` at root documents the migration
- No further work expected here; safe to leave as-is

### `configs/`
**Classification: canonical** | **Confidence: confident**

- 4 files: `instruments.yaml`, `featuresets/base-v1.yaml`, `strategies/example.yaml`, `strategies/zn-macd-pullback-v1.yaml`
- Instrument registry is the single source of truth for tick sizes, session hours, calendar names
- Any new instrument must be added here before any pipeline code touches it

### `data/`
**Classification: hybrid** | **Confidence: confident**

- 180 files on disk; ~20 tracked (manifests + `.gitkeep` files)
- Three layers: `raw/` (downloaded 1m parquets), `clean/` (back-adjusted/resampled), `features/` (indicator-enriched)
- `.gitignore` correctly excludes `*.parquet` payloads; manifest sidecars and quality reports are tracked
- `data/raw/.in_progress/` — resumable download temp dir; never tracked ✓
- `data/raw/contracts/` — per-contract parquet cache (66+ files for ZN); excluded by `*.parquet` rule ✓
- **Finding:** `data/raw/known_outages.yaml` is tracked (correct — it's a canonical calendar override, not generated data)
- **Finding:** FX sample manifests present (`6A`, `6C`, `6N` for 2024-01); suggests FX download test was run but pipeline not validated

### `docs/`
**Classification: canonical** | **Confidence: confident**

- 28 files across 5 subdirectories
- `pipeline.md` — living reference for RAW/CLEAN/FEATURES architecture
- `architecture/data-layering.md` — decision record
- `session-plans/` — 13 session plans (02–14) + README
- `tradestation-api/` — 9 API reference documents
- `Tradestation-trading-symbol-list.md` — broker symbol mapping reference
- **Missing (finding):** Three source documents referenced in `session-14-repo-census.md` under "File moves" (`antigravity-handoff-2026-04-16.md`, `claude_antigravity_infrastructure_unification_plan.md`, `trading_desk_master_plan_for_claude_code.md`) were shared in planning sessions as chat content and never written to disk. Content is reconstructed from work-log `2026-04-17-14-30-summary.md` for governance scaffolding.
- **Missing (finding):** `docs/handoff/`, `docs/adr/`, `docs/strategy/` directories do not yet exist — they are deliverables of this session

### `notebooks/`
**Classification: experimental** | **Confidence: confident**

- 1 file (`.gitkeep` only)
- Per CLAUDE.md: scratch space only; promoted work goes to `src/`
- No tracked notebooks — consistent with the project rule

### `outputs/`
**Classification: hybrid** | **Confidence: confident**

- 15 files tracked: 14 work-log summaries + `planning/planning-state.md`
- `outputs/work-log/` — project memory; explicitly kept in `.gitignore` via `!outputs/work-log/`
- `outputs/planning/` — tracked (planning-state.md is canonical project state)
- `outputs/reports/` — does not exist on disk yet; `.gitignore` rule covers it when it does
- `outputs/validation/` — this session's audit artifacts; should be tracked (see `.gitignore` update in Deliverable 3)
- **Finding:** `planning-state.md` is stale (last updated 2026-04-14, shows Sessions 06–07 as next; Sessions 07–13 have since completed). Should be updated.

### `runs/`
**Classification: generated** | **Confidence: confident**

- 25 files on disk: backtest trade logs, equity curves, summary JSONs, HTML reports
- Only `.gitkeep` tracked; everything else excluded by `runs/**` in `.gitignore` ✓
- Three strategies with timestamped runs: `example-v1` (4 runs) and `zn-macd-pullback-v1` (3 runs)
- `runs/.trials.json` — trials registry for deflated Sharpe; currently excluded by `runs/**`. **This is a finding** — the trials registry needs to either be tracked or live outside `runs/`. If not tracked, deflated Sharpe computations can't be audited across sessions. See open issues.

### `scripts/`
**Classification: canonical** | **Confidence: confident**

- 2 files: `build_zn_continuous.py` (one-time ZN continuous builder runner), `verify_tradestation_auth.py` (auth test utility)
- Both are operational utilities, not test fixtures or generated output

### `src/`
**Classification: canonical** | **Confidence: confident**

- 64 Python source files, 13 subdirectories
- Package structure: `trading_research/{backtest,cli,data,eval,indicators,pipeline,replay,risk,strategies,utils}`
- `__pycache__/` directories present on disk (excluded by `.gitignore` ✓) — not tracked
- `src/trading_research/risk/` exists as a directory with only `__init__.py` — empty module stub, not yet built

### `tests/`
**Classification: canonical** | **Confidence: confident**

- 43 test files, 88 total files (includes `__init__.py`, fixtures, `__pycache__`)
- Coverage: indicators (9 test files), data pipeline (6), backtest engine (4), eval suite (11), replay (3), CLI (1)
- `tests/fixtures/tradestation_zn_sample.json` — tracked ✓ (fixture, not generated)
- `tests/fixtures/*.parquet` — allowed by `!tests/**/*.parquet` negated rule ✓ (none currently present)

---

## Root-Level Files

| File | Classification | Notes |
|---|---|---|
| `.env` | Secret (not tracked ✓) | TradeStation credentials; excluded by .gitignore |
| `.env.example` | Canonical | Template for required env vars |
| `.gitattributes` | Canonical | Added Session 14; normalizes LF line endings |
| `.gitignore` | Canonical | Comprehensive; see update in Deliverable 3 |
| `.python-version` | Canonical | Python 3.12 pin for uv |
| `CLAUDE.md` | Canonical | Project instructions and operating contract |
| `MIGRATION_MANIFEST.md` | Canonical | Documents what was migrated from Legacy/ |
| `README.md` | Canonical | Project overview |
| `prep_migration_samples.py` | Experimental | One-time migration utility; could be archived to Legacy/ |
| `pyproject.toml` | Canonical | uv-managed dependencies and project metadata |
| `uv.lock` | Canonical | Locked dependency versions |

---

## Anomalous Directories

Two empty directories with malformed names exist at the repo root:
- `C:Trading-researchconfigsstrategies/` (empty)
- `C:Trading-researchoutputswork-log/` (empty)

These are Windows path-separator artifacts — a command was run with an unquoted path like `C:\Trading-research\configs\strategies` that git or a shell tool interpreted as a single directory name. They are empty and git does not track them (git doesn't track empty directories). Safe to delete:

```bash
rm -rf "C:/Trading-research/C:Trading-researchconfigsstrategies"
rm -rf "C:/Trading-research/C:Trading-researchoutputswork-log"
```

**Classification: anomalous** | **Confidence: confident**

---

## Recommended `.gitignore` Additions

The following rules are missing or insufficient. Details in Deliverable 3.

| Rule | Reason |
|---|---|
| `outputs/reports/` | The glob `outputs/reports/*.html` only catches top-level; report subdirs not covered |
| `outputs/validation/**` + `!outputs/validation/*.md` | Validation audit `.md` files should be tracked; any generated artifacts (e.g., HTML snapshots) should not |
| `runs/.trials.json` exclusion override | Currently excluded by `runs/**`; needs `!runs/.trials.json` if we decide to track it |
| `.claude/settings.local.json` | Local override; should not be tracked in a shared repo |

---

## Directories Flagged for `git rm --cached` Follow-Up

None required at this time. The initial commit was made after `.gitignore` was in place, so no generated artifacts were committed to history. The `.pytest_cache/`, `.ruff_cache/`, and `__pycache__/` directories exist on disk but were never committed.

**Estimated `git rm --cached` scope: 0 files.** (This is better than typical — the repo was initialized after .gitignore was established.)

---

## Files Flagged for Archival or Cleanup

| File/Dir | Recommendation | Priority |
|---|---|---|
| `prep_migration_samples.py` | Move to `Legacy/` — one-time utility, not operational | Low |
| `C:Trading-researchconfigsstrategies/` | Delete (empty artifact) | Low |
| `C:Trading-researchoutputswork-log/` | Delete (empty artifact) | Low |
| `outputs/planning/planning-state.md` | Update — stale since 2026-04-14 | Medium |
| `runs/.trials.json` | Decision needed: track or relocate | Medium |

---

## Evidence Files

Raw command outputs saved to `outputs/validation/session-14-evidence/`:
- `directory-sizes.txt` — `du -sh` per top-level dir
- `tracked-file-list.txt` — `git ls-files` output from initial commit
- `top-level-structure.txt` — `find . -maxdepth 2 -type d` output
