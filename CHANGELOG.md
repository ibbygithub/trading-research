# Changelog

All notable changes to this project are documented here.
Format: `[SESSION-NN] YYYY-MM-DD — Session Name`

---

## [SESSION-14] 2026-04-17 — Repo Census, Pipeline Audit, Governance Bootstrap

### Census summary

| Category | Count |
|---|---|
| Canonical source directories | 10 |
| Generated/excluded (data, .venv, runs) | 3 |
| Archive (Legacy) | 1 |
| Experimental (notebooks) | 1 |
| Hybrid (data/, outputs/) | 2 |
| Anomalous path-artifact dirs (empty) | 2 |
| git rm --cached scope | 0 files |

### Pipeline robustness verdict: **State B**

| Step | State |
|---|---|
| Download | A |
| Timezone normalization | A |
| Schema enforcement | A |
| Calendar validation | B — RTH window hardcoded for ZN |
| Gap detection | B — inherits RTH window issue |
| Session alignment | B — inherits RTH window issue |
| Roll handling | B — 3 hardcoded "ZN" strings in output paths |
| Quality report generation | B — inherits RTH window issue |

Adding 6A is a ~4-hour targeted fix session. See `outputs/validation/session-14-pipeline-robustness.md`.

### Validation artifacts

- `outputs/validation/session-14-repo-census.md`
- `outputs/validation/session-14-pipeline-robustness.md`
- `outputs/validation/session-14-evidence/` (3 files)

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

- Git initialized; initial commit includes all Sessions 02–13 work (217 files)
- `develop` and `session/14-repo-census` branches created
- `.gitattributes` added for LF line-ending normalization
- `.gitignore` updated: `runs/.trials.json` now tracked for DSR auditability; `outputs/validation/` rules added; `outputs/reports/` broadened; `.claude/settings.local.json` excluded
- GitHub remote: `https://github.com/ibbygithub/trading-research`

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
