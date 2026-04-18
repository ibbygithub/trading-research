# Changelog

All notable changes to this project are documented here.
Format: `[SESSION-NN] YYYY-MM-DD — Session Name`

---

## [SESSION-17] 2026-04-18 — Statistical Rigor Audit & Implementation

Math verification against primary sources (Bailey & Lopez de Prado 2014 for DSR,
Lopez de Prado AFML Ch.7 for purged k-fold). Two Severity-1 bugs fixed. Math
utility consolidation completed.

### Severity-1 fixes

- **`backtest/walkforward.py`** — `gap_bars` and `embargo_bars` were silently
  ignored; fold boundaries abutted. Now wired: gap separates consecutive test
  windows, embargo excludes bars at each fold's leading edge.
- **`eval/classifier.py`** — purge was a `pass` stub. Training used symmetric
  KFold, including post-test observations. Replaced with strict walk-forward:
  train on `[0, val_start − purge_bars)` only.

### Severity-2 fixes

- **`eval/meta_label.py`** — Calmar in threshold sweep used hardcoded `/16.0`
  denominator. Replaced with `utils/stats.calmar()` using actual span_days
  derived from trade timestamps.

### New: `utils/stats.py`

Single source of truth for `annualised_sharpe`, `annualised_sortino`, `calmar`,
`win_rate`, `profit_factor`. All duplicate implementations in `eval/summary.py`,
`eval/bootstrap.py`, and `eval/meta_label.py` now delegate here.

### Data: `configs/calendars/fomc_dates.yaml`

Added complete FOMC statement dates for 2011–2022 (was missing entirely;
replaced stub 2018 entries). Full coverage 2010-01-27 → 2025-01-29, including
March 2020 emergency inter-meeting cuts.

### Audit verdicts (open items)

- PSR/DSR formulas correct for Pearson kurtosis (normal=3). Caveat: callers
  using scipy `kurtosis()` default (excess/Fisher, normal=0) will get the wrong
  variance. Severity-2 follow-up: grep callers and fix.
- Trials registry not idempotent; `.trials.json` may be gitignored. Severity-3
  follow-up.
- Look-ahead audit for Antigravity indicators and HTF DST boundary deferred to
  Session 18 (Indicator Census).

### Artifacts

- `outputs/validation/session-17-statistical-rigor.md` — full audit report
- `outputs/validation/session-17-evidence/psr_dsr_verification.py` — worked examples
- `outputs/work-log/2026-04-18-10-47-session-17-summary.md`

---

## [SESSION-16] 2026-04-18 — Precautionary Code Review: main@de03c04

Structural review of commit `de03c04` (Antigravity Sessions 11–13 bootstrap push,
~80 files). Read-only session — no source changes.

### Review scope

- 27 eval modules (portfolio analytics, DSR/PSR/stats, bootstrap CIs, regime tagging,
  classifier, clustering, SHAP, meta-labeling, Monte Carlo, event study, sizing, Kelly)
- `backtest/walkforward.py` — purged walk-forward runner
- `gui/` — Dash parameter-sandbox GUI (4 modules)
- Jinja2 HTML templates (4 files)
- YAML configs: `broker_margins.yaml`, `fomc_dates.yaml`
- 17 test files touched in de03c04

### Verdict: Adjacent but salvageable

The skeleton of the eval suite is correct — DSR, PSR, regime tagging, walk-forward,
meta-labeling are the right capabilities. The structural problems are load-bearing:

- **Blocking:** `classifier.py` — purge gap is `pass` (stub). Function claims
  "purged k-fold" in docstring but does not implement it. Any classifier AUC from this
  module is potentially contaminated with overlapping-label leakage.
- **Blocking:** `fomc_dates.yaml` — 2011–2017 FOMC dates entirely absent (marked
  "Mocked middle years"). Regime tagger mis-classifies 7 years of a 16-year ZN dataset.
- **Systematic:** `gap_bars`/`embargo_bars` in `walkforward.py` are accepted as
  parameters but silently ignored. The 3 walk-forward tests that would catch this are
  all `pass` stubs.
- **Systematic:** 3 failing tests (`test_monte_carlo`, `test_stats::test_deflated_sharpe_ratio`,
  `test_subperiod`) share same root cause — API refactor without test update.

### Artifacts

- `outputs/validation/session-16-inventory.md` — commit inventory (LOC, deps, test ratios)
- `outputs/validation/session-16-antigravity-review.md` — file-by-file review (34 files,
  14 clean / 18 has-questions / 2 blocking)
- `outputs/validation/session-16-evidence/` — raw commit stat, import smoke test

### Session 17 target list

15 files flagged for statistical-rigor audit — see Section "Files Flagged for Session 17"
in `outputs/validation/session-16-antigravity-review.md`. Priority order:
`classifier.py` → `walkforward.py` → `fomc_dates.yaml` → `stats.py` → `bootstrap.py`

---

## [SESSION-15] 2026-04-17 — Repo Census Redo (Correct Tree)

Re-ran the Session 14 census and pipeline robustness audit against the correct canonical
tree (`main@de03c04`). Session 14 findings are superseded.

### Census: main@de03c04

- 82 Python source files across 12 subpackages
- 53 test files, 337 tests collected, **13 failures** (10× VWAP KeyError, 3× eval API mismatch)
- 6 config files, 27 docs files
- `eval/` subpackage: 28 Python files + 4 Jinja2 templates (Antigravity Sessions 11–13)
- `gui/` subpackage: 4 Python files (Antigravity Session 13)
- Artifact: `outputs/validation/session-15-repo-census.md`

### Pipeline robustness verdict: State B (one State C blocker)

- Steps A–C (download, calendar, gap detect, session align, TZ, schema, quality report):
  **State A** for 6A — work today on direct download path
- Roll handling (`continuous.py`): **State C** — ZN-specific roll convention and hardcoded
  output paths. Blocks 6A per-contract stitching (direct download path is unaffected)
- Artifact: `outputs/validation/session-15-pipeline-robustness.md`

### .gitignore fix

Added `!outputs/validation/` and `!outputs/validation/**` to preserve audit artifacts.

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