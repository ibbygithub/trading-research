# Changelog

All notable changes to this project are documented here.
Format: `[SESSION-NN] YYYY-MM-DD — Session Name`

> **Merge note:** This branch (`session/15-repo-census-redo`) creates CHANGELOG.md
> from scratch. The `session/14-governance` branch contains the SESSION-14 and
> SESSIONS 02-13 entries (reconciled in Session 15 Deliverable 6). When both branches
> merge to `develop`, combine this file with the governance branch version — SESSION-15
> entry goes above SESSION-14.

---

## [SESSION-15] 2026-04-17 — Repo Census, Pipeline Audit, Governance Reconciliation

### Census summary (correct tree: `main@de03c04`)

| Category | Count |
|---|---|
| Canonical source directories | 7 (src, tests, configs, docs, scripts, .claude, outputs) |
| Generated / excluded | 4 (runs, .venv, .pytest_cache, .ruff_cache) |
| Archive / migration | 3 (Legacy/, MIGRATION_MANIFEST.md, prep_migration_samples.py) |
| Orphan / unknown | 3 (2 mangled dirs + migration_samples) |
| Scratch | 1 (notebooks/) |
| New .gitignore rules | 2 (!outputs/validation/, !outputs/validation/**) |
| Files flagged for git rm --cached | 0 |
| Pytest baseline | 337 collected / 13 failing / ~324 passing |

### Pipeline robustness verdict: **State B** (one isolated C)

| Step | State | Notes |
|---|---|---|
| Download | **A** | Symbol → instrument registry → TS symbol; works for 6A |
| Calendar validation | **A** | Calendar from instrument registry; CMEGlobex_FX configured |
| Gap detection | **B** | RTH constants correct for 6A but not parametric |
| Roll handling | **C** | ZN-specific convention + hardcoded output paths in `continuous.py` |
| Session alignment | **B** | +6h offset correct for all CME Globex instruments |
| Timezone normalization | **A** | BAR_SCHEMA instrument-agnostic |
| Schema enforcement | **A** | BAR_SCHEMA instrument-agnostic |
| Quality report generation | **A** | `{parquet.stem}.quality.json` — instrument-agnostic |

**6A verdict:** Direct download path (Session 03 method) works today. Per-contract
stitching is blocked by `continuous.py:build_back_adjusted_continuous` (State C).

See `outputs/validation/session-15-pipeline-robustness.md` for full per-step evidence.

### Key findings

- **13 test failures** on canonical tree: 10 VWAP KeyErrors, 1 monte_carlo AttributeError,
  1 `deflated_sharpe_ratio` TypeError, 1 subperiod AttributeError. Not debugged — recorded
  for Session 17 statistical rigor audit.
- **Pytest count discrepancy:** 337 collected vs Antigravity's claimed 384. Wrong-tree count.
- **`runs/.trials.json` not tracked:** Excluded by `runs/**` despite Session 11 memo claiming
  it was tracked. Open decision — see census finding.
- **Stop hook path corrected:** `.claude/settings.local.json` Stop hook was pointing to
  `C:/Trading-research` (wrong legacy folder). Fixed to canonical zen-brown worktree path.

### Validation artifacts

- `outputs/validation/session-15-repo-census.md`
- `outputs/validation/session-15-pipeline-robustness.md`
- `outputs/validation/session-15-evidence/` (5 files)

### Files changed this session

- `.gitignore` — add `!outputs/validation/` preservation rules
- `docs/session-plans/archive/session-14-strategy-builder-DEPRECATED.md` — archived via `git mv`
- `outputs/work-log/2026-04-17-15-53-folder-recovery-stage-1.md` — committed to tracked set
- `outputs/work-log/2026-04-17-16-45-recovery-stages-2-3.md` — committed to tracked set
- `CHANGELOG.md` on `session/14-governance` — reconciled wrong-tree Session 14 entries
- `.claude/settings.local.json` — Stop hook path corrected

### Governance reconciliation (`session/14-governance` branch)

- `CHANGELOG.md` Session 14 entry: struck wrong-tree census and pipeline verdict; corrected
  pipeline state (Roll=C not B, Calendar=A not B); struck orphan branch and `.trials.json`
  claims. Reconciliation commit: `ae1d717`.
