# AGENTS.md — Shared Agent Constitution
**Version:** 1.0  
**Adopted:** Session 14 (2026-04-17)  
**Applies to:** Claude Code (Anthropic) and Antigravity (Google Gemini)

This file is the shared constitution for all AI agents working in this repository.
Every agent reads this file first. `CLAUDE.md` and `GEMINI.md` extend it — they do
not override it on any point where they conflict.

---

## Mission

Design, validate, and eventually run CME futures trading strategies for a $25k personal account.
Capital preservation with consistent income. No heroics.

Primary instrument: ZN (10-Year Treasury Note futures).  
Second instrument: 6A (Aussie Dollar futures) once ZN is validated.

Full roadmap: `docs/strategy/master-plan-2026-04.md`.

---

## Always-Loaded Personas

Two persona files in `.claude/rules/` are always active for Claude Code:

- **`.claude/rules/quant-mentor.md`** — 20-year quant veteran. Reasons about markets, strategy,
  and risk. Blunt, experienced. Pushes back on curve-fitting and ML-before-rules.

- **`.claude/rules/data-scientist.md`** — Quantitative integrity officer. Defends every claim
  the framework makes. Flags leakage, overfitting, sample-size problems, and distributional
  assumptions. Allergic to sloppy claims.

Both personas speak up unprompted when they see something in their domain. Disagreement between
them is healthy and should be visible to Ibby.

Antigravity: use `GEMINI.md` for equivalent persona guidance.

---

## Operating Contract

**Agents do the work. The human provides judgment, credentials, and consent.**

The human (Ibby) does:
- Provides secrets and credentials
- Confirms destructive operations
- Authorizes any action touching real money
- Reviews PRs and decides whether to merge
- Gives final approval on strategy decisions

Everything else — installs, file edits, git operations, test runs, backtest runs, data pulls — is the agent's job.

---

## Produced vs Accepted

A session is **Produced** when the work exists (code written, files created, outputs generated).

A session is **Accepted** when it is documented, scoped, and merged into canonical project history.

**Definition of Accepted:**
1. All deliverables exist at their specified paths
2. Tests pass (`uv run pytest`)
3. PR opened from the session branch against `develop`
4. Ibby reviews the PR
5. Ibby merges (not the agent)

Work that is Produced but not Accepted does not count as done. Agents do not merge to `develop`.

---

## Session Workflow

Every session follows this structure:

**Start:**
1. Read `AGENTS.md` (this file)
2. Read `docs/handoff/current-state.md` — what the project state is
3. Read `docs/handoff/open-issues.md` — what's broken or undecided
4. Read `docs/handoff/next-actions.md` — what to work on
5. Read the session plan at `docs/session-plans/session-NN-<name>.md`
6. Create branch: `session/NN-<name>` off `develop`

**End:**
1. All deliverables committed to the session branch
2. `docs/handoff/current-state.md`, `open-issues.md`, `next-actions.md` updated
3. Work log written to `outputs/work-log/YYYY-MM-DD-HH-MM-summary.md`
4. PR opened against `develop` with the completion block filled in
5. Ibby notified — his review, his merge

**No session ends without a PR.** If the session is planning-only and produced no code, the PR contains only updated handoff files and the work log.

---

## Branching Convention

| Branch | Purpose |
|---|---|
| `main` | Production-grade merged code only. Ibby merges here from `develop`. |
| `develop` | Integration branch. All session branches merge here via PR. |
| `session/NN-<name>` | One branch per session. Example: `session/14-repo-census`. |

Agents work on `session/NN-<name>`. Agents do not merge to `develop` or `main`.

---

## Commit Message Convention

```
<type>(session-NN): <short imperative description>

<body: what changed and why, one paragraph>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

One commit per logical deliverable. Do not batch unrelated changes into one commit.

---

## Standing Rules (Non-Negotiable)

Full rules in `CLAUDE.md`. These are the most commonly relevant:

**Data integrity**
- 1-minute bars are the canonical base resolution. Higher timeframes are resampled, never re-downloaded.
- Every dataset passes calendar-aware quality check before strategy code can consume it.
- `buy_volume` and `sell_volume` are nullable. Strategies must handle nulls explicitly.
- Instrument specs come from `configs/instruments.yaml`. Hard-coding tick sizes, session hours, or contract values in strategy code is a bug.

**Backtesting honesty**
- Default fill: next-bar-open. Same-bar fills require written justification.
- TP/SL ambiguous bars: pessimistic by default (stop hit first).
- Slippage and commission: pessimistic relative to TradeStation rates.
- Threshold parameters fit on test set = leakage.
- Trade logs capture both trigger bar and entry bar separately.

**Risk management**
- Default sizing: volatility targeting. Kelly requires explicit override.
- Averaging down without a fresh signal is forbidden.
- Daily and weekly loss limits required for paper and live. Backtest-only may omit with warning.

**Evaluation**
- Headline metric: Calmar (not Sharpe). Sharpe reported but not centered.
- Deflated Sharpe computed whenever multiple strategy variants tested.
- Trades per week and max consecutive losses always reported.

---

## Project Layout

```
configs/               Instrument registry, strategy configs, feature sets
data/                  RAW → CLEAN → FEATURES (parquet payloads excluded from git)
docs/                  Architecture docs, session plans, ADRs, strategy docs, handoff
outputs/               Work logs, planning state, validation audit reports
runs/                  Backtest outputs (excluded from git except .trials.json)
src/trading_research/  Canonical Python package
tests/                 pytest suite
.claude/               Claude Code rules, skills, commands
.gemini/               Antigravity rules, skills
```

Full layout: `CLAUDE.md` → "Project layout" section.  
Data architecture: `docs/pipeline.md`, `docs/architecture/data-layering.md`.

---

## PR Template

Every PR opened by an agent includes this completion block:

```
## Session NN — Completion

**Branch:** session/NN-<name>
**Deliverables:**
- [ ] All deliverables at specified paths
- [ ] Tests pass (uv run pytest)
- [ ] Handoff files updated
- [ ] Work log written

**Changed files:**
- (list)

**Pipeline robustness change:** none / [describe if any]

**Open issues created:** none / [list]

**Known limitations:** none / [list]

🤖 Generated with Claude Code (claude-sonnet-4-6)
```
