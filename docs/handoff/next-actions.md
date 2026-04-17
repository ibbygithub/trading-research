# Next Actions
**Last updated:** Session 14 (2026-04-17)

This file tells the next agent (Claude Code or Antigravity) exactly where to start.
Replace the contents at the end of every session.

---

## Immediate Next: Session 15 — Indicator Census

**Plan location:** `docs/session-plans/session-15-indicator-census.md` (to be written)

**What Session 15 covers:**
1. Enumerate all indicator files in `src/trading_research/indicators/`
2. Audit each indicator for look-ahead bias under next-bar-open fill semantics (OI-008)
3. Audit higher-timeframe aggregation for bar-boundary correctness (OI-007)
4. Confirm unadjusted ZN roll parquet is never consumed by indicators or strategy code (OI-009)
5. Write a per-indicator census report to `outputs/validation/session-15-indicator-census.md`

**Before starting Session 15, resolve first:**
- OI-001 (scipy not in pyproject.toml) — run `uv add scipy` from a clean terminal; commit updated `pyproject.toml` + `uv.lock`
- Confirm session 14 PR has been merged to `develop` by Ibby

---

## Backlog (When Session 15 Is Merged)

In priority order:

1. **6A pipeline fix + data pull** (OI-010, OI-011, OI-012) — ~4 hours. Fix RTH window in `validate.py`, fix hardcoded "ZN" strings in `continuous.py`, rename function. Then run 6A historical download.

2. **Session 16 — Feature War Chest** — per the master plan session ordering

3. **Session 17 — Regime Baselines** — event-day blackout filter (FOMC/CPI/NFP)

---

## Low-Priority Cleanup (Do Alongside Any Session)

- OI-002: Update `outputs/planning/planning-state.md` to current state (or retire it)
- OI-003: `git rm --cached .claude/settings.local.json`
- OI-004: Delete the two anomalous empty path-artifact directories
- OI-005: Move `prep_migration_samples.py` to `Legacy/`
