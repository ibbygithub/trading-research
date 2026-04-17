---
session: 14
title: Repo Census, Pipeline Audit, and Governance Bootstrap
status: Draft
created: 2026-04-17
planner: Claude Code (quant-mentor + data-scientist review)
executor: Claude Code (Sonnet) — this session
reviewer: Ibby (human)
branch: session/14-repo-census
depends_on: none
blocks:
  - session-15-indicator-census
  - session-16-feature-war-chest
  - session-17-regime-baselines
  - 6a-data-pull (blocked on pipeline-robustness audit outcome)
repo: https://github.com/ibbygithub/trading-research
---

# Session 14 — Repo Census, Pipeline Audit, and Governance Bootstrap

## Why this session, why first

The repository currently contains ~16,000 files across ~2,400 folders. This is not a code-quality failure — it is a governance failure. It is impossible to do an honest Indicator Census (Session 15) when indicator files cannot be reliably located, distinguished from duplicates, or separated from generated artifacts. It is equally impossible to add a second instrument (6A) when we do not yet know whether the RAW→CLEAN pipeline is generalized or ZN-specific.

This session does three things, in order:

1. **Classifies** every top-level area of the repo as canonical / generated / experimental / duplicate / archive / unknown, and sets `.gitignore` rules so generated artifacts stop polluting tracked state.
2. **Audits** the data pipeline for generalization — for each step of RAW→CLEAN, classifies the code as State A (fully generalized), State B (half-generalized with instrument-specific edge cases), or State C (ZN-specific with cosmetic abstraction). The audit output is what lets the next session price the cost of adding 6A.
3. **Bootstraps** the governance infrastructure the master plan and unification plan both require: `AGENTS.md`, `GEMINI.md`, the three handoff files, the `docs/session-plans/` and `docs/adr/` trees, and the first version of the GitHub Repo Steward skill in both `.claude/skills/` and `.gemini/skills/`.

No coding in the research sense. No indicator work. No data downloads. No strategy changes. This is governance, classification, and skeleton-laying.

## Objective

Produce a repository that a new contributor (human or agent) can navigate in under fifteen minutes, with an honest audit of the data pipeline's readiness for a second instrument, and the governance scaffolding required to accept future sessions cleanly.

## In Scope

- Full repo census: directory-by-directory file counts and classification.
- `.gitignore` updates to stop tracking generated outputs going forward. (Does not retroactively untrack already-committed files — that is a named follow-up.)
- Pipeline robustness audit for the RAW→CLEAN path, per-step A/B/C classification.
- Archival of superseded planning documents. Specifically: any existing `docs/session-plans/session-14-plan.md` referencing the Strategy Builder GUI (from the Antigravity Session 13 handoff) is moved to `docs/session-plans/archive/` with a deprecation note pointing at the master plan reset.
- Relocation of the three source documents that triggered this reset:
  - `antigravity-handoff-2026-04-16.md` → `docs/handoff/archive/2026-04-16-sessions-10-13.md`
  - `claude_antigravity_infrastructure_unification_plan.md` → `docs/adr/0001-claude-antigravity-unification.md`
  - `trading_desk_master_plan_for_claude_code.md` → `docs/strategy/master-plan-2026-04.md`
- Creation of `AGENTS.md` at repo root (shared constitution: mission, rules, definition of done, persona references).
- Creation of `GEMINI.md` at repo root (Antigravity-specific addendum that defers to `AGENTS.md`).
- Creation of three handoff files under `docs/handoff/`: `current-state.md`, `open-issues.md`, `next-actions.md`.
- First-pass GitHub Repo Steward skill in both `.claude/skills/github-repo-steward/SKILL.md` and `.gemini/skills/github-repo-steward/SKILL.md`. Minimum viable: branch naming convention, commit message convention, PR template, acceptance checklist. Hardening can follow.
- `CHANGELOG.md` created or updated at repo root with a "Session 14 — Repo Census" entry.

## Out of Scope

- Indicator code changes (Session 15).
- Feature engineering work (Session 16).
- Deleting or rewriting tracked files that `.gitignore` now covers. The `git rm --cached` cleanup pass is a named follow-up ticket, not part of this session.
- Implementing the other seven skills proposed in the unification plan. Only GitHub Repo Steward is scaffolded in this session.
- Downloading 6A data. Blocked on this session's pipeline-audit output.
- Any fix to the three open risks from the Antigravity handoff (HTF validation, look-ahead strictness, unadjusted ZN roll). Those slot into Session 15.
- Rewriting indicators, strategies, or tests.
- Any refactor that changes behavior.

## Preconditions

- The current `develop` branch is in a committed, pushable state. If it is not, that is a named blocker and this session does not start until `develop` is clean.
- Python environment resolvable via `uv sync` so the pipeline-audit reader scripts can import the `trading_research` package. If `uv sync` fails on a fresh clone, that is itself a finding and gets documented in the pipeline audit.
- GitHub remote `origin` points at `github.com/ibbygithub/trading-research` and push access is confirmed.
- Ibby has reviewed and approved this plan. Acceptance Criteria below are binding once approved.

## Deliverables

Every deliverable below has a concrete output path. If a deliverable has no output artifact, it is not a deliverable.

1. **Repo Census Report** → `outputs/validation/session-14-repo-census.md`
   - File counts per top-level directory.
   - Classification: canonical / generated / experimental / duplicate / archive / unknown, each with a confidence flag (confident / tentative / needs-human-input).
   - Recommended `.gitignore` additions.
   - List of directories flagged for `git rm --cached` follow-up with estimated file counts.
   - Identification of any directories exceeding 500 files that are not data or generated outputs — those are structural smells.

2. **Pipeline Robustness Audit** → `outputs/validation/session-14-pipeline-robustness.md`
   - For each step of RAW→CLEAN (download, calendar validation, gap detection, roll handling, session alignment, timezone normalization, schema enforcement, quality-report generation): State A / B / C classification with one-sentence evidence citation (file path + function name + why).
   - Named edge cases found in ZN-specific code that would break on 6A (e.g., hard-coded session hours, hard-coded roll month, symbol-specific branches).
   - Estimate: "adding 6A is an N-hour session" vs "adding 6A requires T-level rework" based on the aggregate state.

3. **Updated `.gitignore`** → `.gitignore`
   - New rules for `outputs/`, `runs/`, generated report subdirectories, `.ipynb_checkpoints/`, `__pycache__/`, any report HTML cache, any Dash asset cache.
   - Each new rule annotated with a comment explaining what it covers.

4. **Governance Scaffolding**
   - `AGENTS.md` at repo root.
   - `GEMINI.md` at repo root.
   - `docs/handoff/current-state.md`, `docs/handoff/open-issues.md`, `docs/handoff/next-actions.md`.
   - `docs/session-plans/` directory exists with this plan committed in it.
   - `docs/adr/` directory exists with `0001-claude-antigravity-unification.md` in it.
   - `docs/strategy/` directory exists with `master-plan-2026-04.md` in it.
   - `docs/handoff/archive/` directory exists with `2026-04-16-sessions-10-13.md` in it.

5. **GitHub Repo Steward Skill v0.1**
   - `.claude/skills/github-repo-steward/SKILL.md`
   - `.gemini/skills/github-repo-steward/SKILL.md`
   - Both files near-identical; tool-specific differences clearly marked.
   - Content: branch naming convention, commit message format, PR template, acceptance checklist, the "Produced vs Accepted" distinction from the unification plan.

6. **Deprecation of superseded plans**
   - If `docs/session-plans/session-14-plan.md` (the old Strategy Builder plan) exists, it is moved to `docs/session-plans/archive/session-14-strategy-builder-DEPRECATED.md` with a front-matter note: `superseded_by: docs/strategy/master-plan-2026-04.md`.

7. **`CHANGELOG.md`** → repo root, `[SESSION-14]` entry with the classification summary, pipeline audit verdict (A/B/C aggregate), and links to the two validation artifacts.

## Acceptance Criteria

A session is **Produced** when the work exists. A session is **Accepted** when it is documented, scoped, and merged into canonical project history. Definition of done:

- [ ] All seven deliverables above exist at their specified paths.
- [ ] `git status` on branch `session/14-repo-census` after `.gitignore` changes shows a meaningful, reviewable diff — not a wall of 10,000 newly-ignored files. If the diff is too noisy, the `.gitignore` ruleset is over-broad and must be revised.
- [ ] Both validation artifacts under `outputs/validation/` are committed to the branch (this is one of the few cases where we want validation output tracked in git — it is *the record of the audit*, not generated strategy output).
- [ ] `AGENTS.md` references `.claude/rules/quant-mentor.md` and `.claude/rules/data-scientist.md` by path and states they are always-loaded.
- [ ] `GEMINI.md` defers to `AGENTS.md` in its first paragraph.
- [ ] `docs/handoff/current-state.md` states the current canonical session (14, complete), the next approved session (15 Indicator Census), and lists the three Antigravity open risks as scheduled.
- [ ] The GitHub Repo Steward skill mirrors across `.claude/` and `.gemini/` and both versions are identical except for explicitly-marked tool-specific sections.
- [ ] PR opened from `session/14-repo-census` against `develop` on `github.com/ibbygithub/trading-research` with the completion block filled in.
- [ ] Ibby has reviewed the PR and either requested changes or merged. Merge is his act, not the executor's.
- [ ] Commit history on the branch uses the convention defined in the GitHub Repo Steward skill (i.e., this session uses the skill it ships — dogfooding is the acceptance test for the skill).

## Files / Areas Expected to Change

| Path | Change | Why |
|---|---|---|
| `.gitignore` | Modified | Add rules for generated outputs |
| `AGENTS.md` | Created | Shared constitution |
| `GEMINI.md` | Created | Antigravity addendum |
| `CHANGELOG.md` | Created or updated | Session record |
| `docs/handoff/current-state.md` | Created | Project state doc |
| `docs/handoff/open-issues.md` | Created | Known problems list |
| `docs/handoff/next-actions.md` | Created | Immediate next task list |
| `docs/handoff/archive/2026-04-16-sessions-10-13.md` | Moved | From `antigravity-handoff-2026-04-16.md` at repo root (or wherever it currently lives) |
| `docs/adr/0001-claude-antigravity-unification.md` | Moved | From `claude_antigravity_infrastructure_unification_plan.md` |
| `docs/strategy/master-plan-2026-04.md` | Moved | From `trading_desk_master_plan_for_claude_code.md` |
| `docs/session-plans/session-14-repo-census.md` | This file — already committed | Session plan |
| `docs/session-plans/archive/session-14-strategy-builder-DEPRECATED.md` | Moved (if old plan exists) | Supersession |
| `.claude/skills/github-repo-steward/SKILL.md` | Created | Skill v0.1 |
| `.gemini/skills/github-repo-steward/SKILL.md` | Created | Mirrored skill |
| `outputs/validation/session-14-repo-census.md` | Created | Audit artifact |
| `outputs/validation/session-14-pipeline-robustness.md` | Created | Audit artifact |

No files under `src/trading_research/` are modified. If execution finds it needs to modify source code to complete the audit, that is scope drift and must be flagged as a finding, not silently done.

## Risks / Open Questions

- **Classification ambiguity.** Some directories may not cleanly fit canonical / generated / experimental / duplicate. The deliverable explicitly allows a "needs-human-input" classification. Escalate to Ibby rather than guessing.
- **Pipeline audit may return State C.** If the audit finds the RAW→CLEAN pipeline is ZN-specific with cosmetic abstraction, the cost of adding 6A goes up materially. This is a *finding*, not a failure. Report it honestly; the next session pricing depends on it.
- **`.gitignore` over-broadness.** Aggressive ignore rules can silently hide a tracked file that should have been canonical. Every new ignore rule requires a one-line comment stating what it covers and what it should *not* cover.
- **Old `session-14-plan.md` content.** The old Strategy Builder plan referenced by the Antigravity handoff may not exist, may be partial, or may not be at the expected path. If not found, document the non-existence rather than assuming.
- **Noisy diff.** This session will produce a large PR by file count. That is inherent — governance bootstrap touches many paths. Keep the diff *logically small* by grouping changes into clear commits: one commit per deliverable category.
- **`outputs/` tracking inversion.** This session tracks validation artifacts under `outputs/validation/` while simultaneously `.gitignore`-ing other subdirectories of `outputs/`. This is intentional but must be explicit in the `.gitignore` with a negated rule (`!outputs/validation/`).

## Executor Notes (for Claude Code, Sonnet)

Read `AGENTS.md` and `docs/strategy/master-plan-2026-04.md` before starting. At session start they do not yet exist — they are deliverables of *this* session. The source material for both lives at `docs/handoff/archive/2026-04-16-sessions-10-13.md`, `docs/adr/0001-claude-antigravity-unification.md`, and `docs/strategy/master-plan-2026-04.md` after the file moves in step 4. Read the source documents before you write the governance scaffolding.

Work in this order:

1. Create branch `session/14-repo-census` off `develop`.
2. **Deliverable 1 — Repo Census Report.** Produce classification before any file moves. You need the classification to decide what to `.gitignore`.
3. **Deliverable 2 — Pipeline Robustness Audit.** Read-only. No code changes. Per-step A/B/C with evidence citations.
4. **Mid-session checkpoint (mandatory).** After deliverables 1 and 2 are committed to the branch, stop and surface the findings to Ibby. Expected format: a short summary of the census classification counts, the pipeline A/B/C aggregate verdict, and any findings that would change downstream sequencing. Do not proceed to deliverables 3–7 until Ibby gives the go-ahead. If the pipeline audit returns an aggregate State C, this checkpoint is especially important — we may want to re-sequence before bootstrapping governance.
5. File moves (Deliverable 4 partial, Deliverable 6). Use `git mv` so history is preserved.
6. Update `.gitignore` (Deliverable 3).
7. Create governance files (Deliverables 4, 5).
8. Update `CHANGELOG.md` (Deliverable 7).
9. Open PR.

Per-commit granularity: one commit per numbered deliverable. PR body includes the completion block below.

If during execution you find that any deliverable is infeasible as specified, **do not silently substitute**. Open a finding in `outputs/validation/session-14-findings.md` and stop. Ambiguity gets escalated, not papered over.

Save every command output that informs a classification decision — file listings, grep results, `git log` output — under `outputs/validation/session-14-evidence/`. Ibby wants to see the work, not just the conclusion.

**Auto-merge posture.** The GitHub Repo Steward skill (v0.1) does not require mandatory PR review when all validation checks are green. If every acceptance-criterion checkbox ticks and CI (when we have it) is green, the PR may be merged without a blocking human review. Ibby retains the right to review any PR at his discretion; the skill just does not *force* it.

## Completion Block

To be filled by the executor after work is done and before PR is opened.

```
Session 14 — Completion

Changed files:
- (enumerated list)

Commits:
- (sha : message)

Validation artifacts:
- outputs/validation/session-14-repo-census.md
- outputs/validation/session-14-pipeline-robustness.md
- outputs/validation/session-14-evidence/ (N files)

Pipeline robustness verdict: State A / B / C (aggregate)
Per-step classifications:
- download: A/B/C
- calendar validation: A/B/C
- gap detection: A/B/C
- roll handling: A/B/C
- session alignment: A/B/C
- timezone normalization: A/B/C
- schema enforcement: A/B/C
- quality-report generation: A/B/C

Repo census summary:
- Canonical source directories: N
- Generated-artifact directories: N
- Experimental directories: N
- Duplicate/archive candidates: N
- Unknown: N
- New .gitignore rules: N
- Files flagged for future `git rm --cached`: N

Decisions made during execution:
- (any classification call-outs, edge-case handling, deviations from plan)

Known limitations:
- (anything not done, anything done partially, anything deferred)

Follow-up tickets:
- `git rm --cached` cleanup session (estimated file count: N)
- (any other surfaced work)

Commit message convention used:
- (the exact format per the GitHub Repo Steward skill)

PR: https://github.com/ibbygithub/trading-research/pull/<N>

Acceptance state: accepted / provisional
```

