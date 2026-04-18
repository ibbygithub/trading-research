# Open Issues
**Last updated:** Session 14 (2026-04-17)

Issues are listed by severity. Remove when resolved; add session number when fixed.

---

## Medium — Address Before Session 15

### OI-001: scipy not in pyproject.toml / uv.lock
**Opened:** Session 11  
**Symptom:** `scipy` was installed via `pip install scipy` directly into `.venv` because the `trading-research.exe` process held a lock during `uv add`. If someone does a fresh `uv sync`, scipy may not be installed.  
**Fix:** From a clean terminal (CLI process not running): `uv add scipy`. Then commit updated `pyproject.toml` and `uv.lock`.

### OI-002: planning-state.md is stale
**Opened:** Session 14 (census finding)  
**Symptom:** `outputs/planning/planning-state.md` was last updated 2026-04-14 and shows Sessions 06–07 as the next work. Sessions 07–13 have since completed.  
**Fix:** Rewrite `outputs/planning/planning-state.md` to reflect current canonical state. Or retire it in favour of `docs/handoff/current-state.md` (this file's preferred replacement). Decision for Session 15.

### OI-003: .claude/settings.local.json tracked in git
**Opened:** Session 14 (census finding)  
**Symptom:** `settings.local.json` was committed in the initial commit before `.gitignore` was updated to exclude it. The file contains local Claude Code settings that are machine-specific.  
**Fix:** `git rm --cached .claude/settings.local.json` then commit. This is a `git rm --cached` cleanup — review the file contents first to confirm nothing sensitive is in it.

---

## Low — Backlog

### OI-004: anomalous path-artifact directories at root
**Opened:** Session 14 (census finding)  
**Symptom:** Two empty directories exist with Windows path-separator artifacts in their names: `C:Trading-researchconfigsstrategies/` and `C:Trading-researchoutputswork-log/`. They are empty and not tracked by git.  
**Fix:** `rm -rf` both directories. No git operation needed (they're not tracked).

### OI-005: prep_migration_samples.py at repo root
**Opened:** Session 14 (census finding)  
**Symptom:** One-time migration utility that no longer has a clear operational role. Lives at root alongside canonical pyproject.toml.  
**Fix:** Move to `Legacy/` or delete if the migration is confirmed complete.

### OI-006: runs/.trials.json excluded from initial commits
**Opened:** Session 14  
**Status:** Resolved for future — `.gitignore` now has `!runs/.trials.json` negation. The file does not yet exist on disk (created by backtest runs). Once it is created, it will be tracked.  
**No action needed** unless a backtest has been run and the file exists but wasn't committed.

---

## Scheduled for Session 15 (Indicator Census)

These are not bugs — they are open audit items from the Antigravity handoff:

### OI-007: HTF aggregation validation
**Description:** Higher-timeframe resample correctness not fully audited. Bar-boundary edge cases (e.g., 15m bars spanning a session boundary) and OHLC ordering under thin overnight periods are untested.

### OI-008: Indicator look-ahead strictness under next-bar-open fill
**Description:** Indicators compute at bar T close; fills execute at bar T+1 open. Any indicator using bar T+1 open in its own computation introduces forward leakage. Surface read found no violations; systematic audit pending.

### OI-009: Unadjusted ZN roll consumption audit
**Description:** All load paths in strategy and indicator code should consume back-adjusted parquets, not unadjusted. `rebuild_features()` explicitly globs for `backadjusted` files. Full audit of all load paths pending.

---

## Pipeline Generalization Issues (Scheduled for 6A Fix Session)

From Session 14 pipeline robustness audit (State B findings):

### OI-010: RTH window hardcoded for ZN in validate.py
**File:** `src/trading_research/data/validate.py`, lines near `_RTH_OPEN_ET`  
**Issue:** `_RTH_OPEN_ET = 08:20 ET`, `_RTH_CLOSE_ET = 15:00 ET` — ZN RTH hours. FX instruments have 08:00–17:00 RTH. Gaps in 15:00–17:00 window for 6A would be silently misclassified as overnight.  
**Fix:** Read RTH window from `InstrumentRegistry` using the `symbol` argument already passed to `validate_bar_dataset()`.

### OI-011: Hardcoded "ZN" in continuous.py output paths
**File:** `src/trading_research/data/continuous.py`  
**Issue:** Three output paths contain literal `"ZN"` string. A call with `symbol="6A"` would write `ZN_1m_backadjusted_...`.  
**Fix:** Replace `"ZN"` with `symbol` variable in the three path assignments.

### OI-012: last_trading_day_zn() misleading function name
**File:** `src/trading_research/data/continuous.py`  
**Issue:** Function name implies ZN-specificity; logic is generic CME quarterly futures rule.  
**Fix:** Rename to `last_trading_day_quarterly_cme()` and update callers.
