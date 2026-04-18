# Repo Census — Session 15
**Date:** 2026-04-17  
**Tree:** `main@de03c04` (canonical Line A, correct tree)  
**Purpose:** Classification of every top-level directory. This replaces the wrong-tree Session 14 census which was run against a tree missing 15 eval modules and 4 GUI modules.

---

## Confidence Legend
- **High** — Classification is definitive from code structure, .gitignore, and git history.
- **Medium** — Classification inferred; could be re-evaluated.
- `needs-human-input` — Cannot classify without a decision from Ibby.

---

## File Count Summary

| Category | Count | Notes |
|---|---|---|
| Python source files (`src/`) | 82 | 12 subpackages |
| Python test files (`tests/`) | 53 | 53 .py files |
| Tests collected by pytest | 337 | See pytest baseline |
| Tests failing | 13 | See Failures section |
| Config files (`configs/`) | 6 | YAML only |
| Documentation files (`docs/`) | 27 | .md files |
| Work-logs tracked (`outputs/work-log/`) | 14 | 3 in main worktree untracked |
| Session plans (`docs/session-plans/`) | 17 | Sessions 02–17 |

---

## Directory Classifications

### Canonical Source — Integral to the project

| Path | Files | Confidence | Notes |
|---|---|---|---|
| `src/trading_research/` | 82 .py | High | Full importable package; 12 subpackages |
| `src/trading_research/backtest/` | 5 .py | High | Engine, fills, signals, walkforward, __init__ |
| `src/trading_research/cli/` | 2 .py | High | Typer entry point |
| `src/trading_research/data/` | 13 .py | High | Pipeline core + TradeStation client (7+6) |
| `src/trading_research/eval/` | 28 .py + 4 .j2 | High | Antigravity portfolio/regime/ML suite + Jinja2 templates |
| `src/trading_research/gui/` | 4 .py | High | Dash GUI builder (Antigravity Session 13) |
| `src/trading_research/indicators/` | 12 .py | High | All indicators + feature builder |
| `src/trading_research/pipeline/` | 5 .py | High | CLI rebuild/verify/inventory/backfill |
| `src/trading_research/replay/` | 6 .py | High | Dash replay app (Visual Cockpit, Floor 1) |
| `src/trading_research/risk/` | 1 .py | High | `__init__.py` only — stub, no implementation |
| `src/trading_research/strategies/` | 3 .py | High | example.py + zn_macd_pullback.py |
| `src/trading_research/utils/` | 2 .py | High | Structlog wrapper |
| `tests/` | 53 .py | High | 337 tests; see Failures section |
| `configs/` | 6 files | High | instruments.yaml, base-v1.yaml, broker_margins, fomc_dates, 2 strategy configs |
| `docs/` | 27 .md | High | Pipeline ref, architecture ADR, session plans, TS API docs |
| `outputs/work-log/` | 14 .md tracked | High | Session memory — functional project artifact |
| `outputs/planning/` | 1 .md | High | planning-state.md — functional project artifact |
| `data/` (skeleton) | gitkeeps + manifests | High | Actual parquet excluded; manifests + quality JSON tracked |
| `scripts/` | 2 .py | High | `build_zn_continuous.py`, `verify_tradestation_auth.py` — utility runners |
| `.claude/rules/` | 2 .md | High | Always-loaded agent personas |
| `.claude/commands/` | 1 .md | High | data-quality-check slash command |
| `.claude/skills/` | 15 .md | High | On-demand skill files |
| `CLAUDE.md` | 1 | High | Project instructions |
| `pyproject.toml` | 1 | High | Project + dependency definition |
| `.env.example` | 1 | High | Documents required env vars |
| `.python-version` | 1 | High | Python 3.12 pin |
| `.gitignore` | 1 | High | Needs update — see .gitignore section |
| `README.md` | 1 | High | Project README |
| `uv.lock` | 1 | High | Locked deps — intentionally committed per .gitignore comment |

### Generated Outputs — Excluded from tracking

| Path | Files | Confidence | Notes |
|---|---|---|---|
| `runs/` | 30+ files | High | Backtest outputs. `runs/**` excluded in .gitignore; only `.gitkeep` tracked |
| `.venv/` | many | High | Virtual environment — excluded |
| `.pytest_cache/` | few | High | Pytest cache — excluded |
| `.ruff_cache/` | few | High | Ruff lint cache — excluded |

**Finding — `runs/.trials.json`:** Exists in the filesystem but NOT tracked (excluded by `runs/**` rule). The Antigravity Session 11 memory claimed "Trials registry (`runs/.trials.json` now tracked)" — this is FALSE on the canonical tree. The rule `runs/**` with only `!runs/.gitkeep` excludes it. This needs a human decision: add `!runs/.trials.json` to `.gitignore` if persistence across sessions is desired. Flagged — `needs-human-input`.

### Archive — Historical, not active code

| Path | Files | Confidence | Notes |
|---|---|---|---|
| `Legacy/` | 3 files | High | Pre-project TS downloader scripts. Preserved for reference. Not imported. |
| `MIGRATION_MANIFEST.md` | 1 | High | April 2026 migration artifact. Historical record. No code deps. |
| `prep_migration_samples.py` | 1 | High | Migration prep script, committed in `f9b8919`, not needed going forward |

### Unknown / Orphan — Migration artifacts, untracked

| Path | Status | Confidence | Notes |
|---|---|---|---|
| `C:Trading-researchconfigsstrategies/` | Untracked dir | High | Windows path mangling from wrong-folder incident. Empty directory. Safe to delete. |
| `C:Trading-researchoutputswork-log/` | Untracked dir | High | Same — Windows path mangling artifact. Empty. Safe to delete. |
| `migration_samples/` | Untracked dir | High | Contains `MANIFEST.json`, `data/`, `runs/`. Covered by `.gitignore`. Can delete. |

### Scratch — Not project artifacts

| Path | Files | Confidence | Notes |
|---|---|---|---|
| `notebooks/` | gitkeep only | High | Empty scratch space per CLAUDE.md. Correct state. |
| `patch_html.py` | 1 | High | One-off report patching script. Covered by `patch_*.py` in .gitignore. Untracked. |
| `patch_report.py` | 1 | High | Same. |
| `pytest_out.txt` | 1 | High | Untracked test output. Covered by `pytest_out.txt` in .gitignore. |

---

## Subpackage Detail: `src/trading_research/eval/` (28 Python files)

This is the largest and most recently modified subpackage (Antigravity Sessions 11–13 in commit `de03c04`). Listed for Session 16 code review scope.

| Module | Function |
|---|---|
| `__init__.py` | Empty init |
| `bootstrap.py` | Bootstrap CI for metrics |
| `capital.py` | Capital efficiency analysis |
| `classifier.py` | Winner/loser trade classifier with purged k-fold |
| `clustering.py` | Trade clustering (UMAP + HDBSCAN) |
| `context.py` | Market-context join (`join_entry_context`) |
| `correlation.py` | Portfolio correlation analysis |
| `data_dictionary.py` | Trade-log column documentation (34 cols) |
| `data_dictionary_portfolio.py` | Portfolio-level data dictionary |
| `distribution.py` | Return distribution analysis |
| `drawdowns.py` | Drawdown forensics |
| `event_study.py` | Event study (around entry/exit) |
| `kelly.py` | Kelly criterion reference (mentor disclaimer required) |
| `meta_label.py` | Meta-labeling readout |
| `monte_carlo.py` | Monte Carlo trade-order shuffle |
| `pipeline_integrity.py` | 5-check audit: bar counts, HTF shift, look-ahead, manifest diff |
| `portfolio.py` | Multi-strategy portfolio loading |
| `portfolio_drawdown.py` | Portfolio-level drawdown attribution |
| `portfolio_report.py` | Portfolio HTML report generator |
| `regime_metrics.py` | Per-regime metric breakdowns |
| `regimes.py` | Regime tagging (volatility, trend, calendar, Fed, econ) |
| `report.py` | Single-strategy HTML report (15 sections, Plotly inline) |
| `shap_analysis.py` | SHAP per trade (numba/shap dependency — see Failures) |
| `sizing.py` | Sizing comparison: equal/vol-target/risk-parity/inverse-DD |
| `stats.py` | DSR, PSR, Omega, Gain-to-Pain, UPI, MAR, Recovery Factor |
| `subperiod.py` | Subperiod stability analysis |
| `summary.py` | Calmar/Sharpe/Sortino/drawdown summary |
| `trials.py` | Trials registry (multi-test Deflated Sharpe) |
| `templates/` | 4 Jinja2 HTML templates (report_v1–v3, portfolio) |

---

## Pytest Baseline

**Run date:** 2026-04-17  
**Command:** `uv run pytest --tb=no -q`  
**Tree:** `main@de03c04`  
**Tests collected:** 337  

**Claimed at Session 11 close (legacy folder):** 384 passing  
**Actual canonical count:** 337 collected — discrepancy of 47 tests. Likely due to structural differences between the legacy tree and canonical tree at the time of measurement, plus the heavy refactoring in `de03c04` (Antigravity merged many test files). Session 16 should verify.

**Known failures (13):**

| Test | Error Type | Module |
|---|---|---|
| `test_vwap.py::TestSessionVWAP::test_resets_on_gap` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestSessionVWAP::test_no_reset_within_session` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestSessionVWAP::test_single_bar_session` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestSessionVWAP::test_no_lookahead` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestSessionVWAP::test_gap_59_does_not_reset` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestWeeklyVWAP::test_resets_at_new_week` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestWeeklyVWAP::test_accumulates_within_week` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestWeeklyVWAP::test_no_lookahead` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestMonthlyVWAP::test_resets_at_new_month` | KeyError | `indicators/vwap.py` |
| `test_vwap.py::TestMonthlyVWAP::test_no_lookahead` | KeyError | `indicators/vwap.py` |
| `test_monte_carlo.py::test_shuffle_trade_order` | AttributeError | `eval/monte_carlo.py` |
| `test_stats.py::test_deflated_sharpe_ratio` | TypeError | `eval/stats.py` |
| `test_subperiod.py::test_subperiod_analysis` | AttributeError | `eval/subperiod.py` |

**Session 17 will audit what these tests exercise.** The VWAP failures (10 of 13) are all KeyError — likely an interface change in `vwap.py` from the `de03c04` Antigravity commit that broke the updated test file. The `deflated_sharpe_ratio` TypeError in `eval/stats.py` is directly relevant to Session 17's DSR formula audit.

---

## .gitignore Assessment

**Current coverage:** Good. The existing `.gitignore` correctly excludes: `.venv/`, `runs/**`, `data/raw/**`, `data/clean/**`, `data/features/**`, `migration_samples/`, `patch_*.py`, `pytest_out.txt`, `.env`, `*.parquet` (with tests/ exception).

**Missing rule — critical:**

`outputs/validation/` — No rule exists to explicitly preserve this directory. The current `outputs/` exclusions only cover `outputs/logs/` and `outputs/reports/*.html`. Since Session 15 creates `outputs/validation/` and its content must be tracked, the negated rule `!outputs/validation/` is required.

**Missing rule — open decision:**

`runs/.trials.json` — Excluded by `runs/**`. If the trials registry should persist across sessions (the Antigravity Session 11 memo implied it should), add `!runs/.trials.json`. If it's intentionally ephemeral, no change needed. `needs-human-input`.

**Orphan directories:** The Windows-mangled directories (`C:Trading-researchconfigsstrategies`, `C:Trading-researchoutputswork-log`) are not tracked and not explicitly ignored. They should be deleted or ignored with a targeted glob pattern. Recommend deletion since they're empty.

**Recommended new rules (minimal — see Deliverable 4 for actual diff):**

```gitignore
# Preserve audit artifacts — these are project memory, not runtime outputs.
!outputs/validation/
!outputs/validation/**
```

---

## Files Flagged for Future `git rm --cached` Cleanup

None. The current `.gitignore` correctly excludes generated files. The worktree-duplicated files under `.claude/worktrees/zen-brown/` and `.claude/worktrees/stoic-engelbart/` are git worktrees, not tracked files. No `git rm --cached` is needed at this time.

The untracked orphan directories should be deleted from the filesystem (not via `git rm --cached` since they're not tracked).

---

## Summary

| Classification | Count | Notes |
|---|---|---|
| Canonical source directories | 7 | src, tests, configs, docs, scripts, .claude, outputs |
| Generated-artifact directories | 4 | runs, .venv, .pytest_cache, .ruff_cache |
| Archive/migration | 3 | Legacy/, MIGRATION_MANIFEST.md, prep_migration_samples.py |
| Orphan/unknown | 3 | Two mangled dirs + migration_samples |
| Scratch | 1 | notebooks/ |
| New .gitignore rules needed | 2 | !outputs/validation/ + !outputs/validation/** |
| Files flagged for git rm --cached | 0 | None |
| Pytest baseline | 337 collected / 13 failing / ~324 passing |
