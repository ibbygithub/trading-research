# Changelog

All notable changes to this project are documented here.
Format: `[SESSION-NN] YYYY-MM-DD — Session Name`

---

## [SESSION-14] 2026-04-17 — Governance Bootstrap

> **⚠️ Reconciliation note (Session 15, 2026-04-17):** The Session 14 repo census
> and pipeline robustness audit were run against an incomplete tree (missing 15 eval
> modules and 4 GUI modules from Antigravity Sessions 11–13). Those findings have been
> superseded by the Session 15 redo. Census and pipeline verdict entries below are
> **STRUCK** — do not rely on them. Governance artifacts (AGENTS.md, handoff docs,
> ADR, master plan, skills) were rescued from the archive tag and remain valid.
> See `outputs/validation/session-15-repo-census.md` and
> `outputs/validation/session-15-pipeline-robustness.md` for correct findings.

### ~~Census summary~~ *(wrong-tree — superseded by Session 15)*

~~See `outputs/validation/session-14-repo-census.md`.~~ File does not exist on
canonical tree. Correct census is in `outputs/validation/session-15-repo-census.md`.

### ~~Pipeline robustness verdict~~ *(wrong-tree — superseded by Session 15)*

~~See `outputs/validation/session-14-pipeline-robustness.md`.~~ File does not exist
on canonical tree. Correct audit is in `outputs/validation/session-15-pipeline-robustness.md`.
Key correction: Roll handling is **State C** (not B) — `continuous.py` has hardcoded ZN
roll convention and ZN output paths; Calendar validation is **State A** (not B) — it uses
instrument registry lookup. 6A direct download works today on the State A path.

### Governance files created

- `AGENTS.md` — shared constitution for all AI agents
- `GEMINI.md` — Antigravity-specific addendum
- `docs/handoff/current-state.md`, `open-issues.md`, `next-actions.md`
- `docs/handoff/archive/2026-04-16-sessions-10-13.md` — Antigravity Sessions 10-13 handoff
- `docs/adr/0001-claude-antigravity-unification.md` — governance unification decision record
- `docs/strategy/master-plan-2026-04.md` — active master plan with 2026-04-17 amendments
- `.claude/skills/github-repo-steward/SKILL.md` — Repo Steward v0.1
- `.gemini/skills/github-repo-steward/SKILL.md` — mirrored skill for Antigravity

### Infrastructure

- `.gitattributes` added for LF line-ending normalization
- GitHub remote: `https://github.com/ibbygithub/trading-research`
- ~~`develop` and `session/14-repo-census` branches created~~ — orphan branches on wrong
  remote line (Line B); do not merge to main. See `folder_recovery_emergency.md`.
- ~~`.gitignore` updated: `runs/.trials.json` now tracked~~ — NOT true on canonical tree;
  `.trials.json` is excluded by `runs/**`. Open decision — see Session 15 census finding.

### Open issues created

OI-001 through OI-012 — see `docs/handoff/open-issues.md`

---

## [SESSIONS 02–13] 2026-04-13 to 2026-04-15 — Foundation through Reporting Suite

All work from Sessions 02–13 was captured in the initial git commit on 2026-04-17.
See `outputs/work-log/` for session-by-session summaries.

Key milestones:
- **Sessions 02–05:** Data pipeline — RAW→CLEAN→FEATURES for ZN (14 years, 154+ tests)
- **Session 06:** CLI automation (verify, rebuild, features, inventory)
- **Session 07:** Visual cockpit — Dash 4-pane MTF replay app (5m/15m/60m/1D)
- **Sessions 08–09:** Backtest engine + portfolio risk; ZN MACD pullback strategy
- **Sessions 10–13:** Reporting suite — 24-section HTML reports, walk-forward runner, deflated Sharpe, Monte Carlo, drawdown catalog, trials registry, portfolio report
