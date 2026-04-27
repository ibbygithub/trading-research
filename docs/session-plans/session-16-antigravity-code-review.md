---
session: 16
title: Precautionary Code Review — main@de03c04 (Antigravity Sessions 11–13)
status: Draft
created: 2026-04-17
planner: Claude Code (Opus 4), with quant-mentor + data-scientist review
executor: Claude Code (Sonnet or Opus — see note in Executor Notes)
reviewer: Ibby (human)
branch: session/16-antigravity-review
depends_on:
  - session-15-repo-census (needs census + pipeline audit to scope the review)
blocks:
  - session-17-statistical-rigor-audit (Session 17 drills into code that Session 16 has already structurally surveyed)
repo: https://github.com/ibbygithub/trading-research
---

# Session 16 — Precautionary Code Review: main@de03c04

## Why this session exists

Commit `de03c04` ("feat(eval): implement portfolio analytics suite and GUI builder") landed **~80 files** in a single push from Antigravity Sessions 11–13. It went to `origin/main` as a bootstrap push and was not fully reviewed before sticking. This is the largest un-reviewed surface in the project, and it includes:

- `src/trading_research/eval/` — 27 Python modules covering bootstrap CIs, deflated Sharpe, PSR, Omega, regime tagging, meta-labeling, SHAP, portfolio-level analytics, Kelly, sizing, event studies, clustering, classifier, and associated report/template infrastructure.
- `src/trading_research/backtest/walkforward.py` — purged walk-forward runner.
- `src/trading_research/gui/` — 4 modules for the parameter-sandbox GUI (the thing the archived Session 14 plan was going to build; Antigravity shipped it early).
- Tests, configs, HTML templates, trade-log forensics infrastructure.

Session 16 is the **structural review**: what exists, what claims it makes, does it fit the project's standards, where are the surface-level red flags. It does **not** drill into the math — that is Session 17's job. The two-session split lets the structural review happen with broad context, then Session 17 goes deep on a scoped list of files that Session 16 has already marked for rigor.

The **quant-mentor** persona is the load-bearing voice here. The question is "does this look like trading software written by someone who's seen markets, or does it look like a textbook implementation dropped on top of a real codebase?"

## Objective

Produce a file-by-file inventory of `main@de03c04` with a status flag per file (clean / has-questions / blocking-issue), a cross-reference to which Session 17 rigor check (if any) it feeds, and an architectural-fit verdict ("this code belongs in this project / this code is adjacent but salvageable / this code is a graft that doesn't fit"). At the end of the session, Session 17 has a precise target list and Ibby has an honest read on whether the Antigravity work is production-track or needs a rewrite pass.

## In Scope

- **Commit inventory.** Full enumeration of files changed in `de03c04`: module list, line counts, test-to-code ratio, any new dependencies pinned in `pyproject.toml`.
- **File-by-file structural review** of every `.py` file in the commit.
  - Does it have type hints on public functions (per project convention)?
  - Does it have a module docstring stating purpose?
  - Are imports clean (no wildcard, no sys.path hacks)?
  - Does it use `pathlib.Path` rather than string paths?
  - Does it use `structlog` rather than `print`?
  - Does it read instrument specs from `configs/instruments.yaml` rather than hardcoding?
  - Are timestamps tz-aware in UTC?
  - Are there silent `try/except Exception:` blocks?
  - Does it have tests?
- **Test surface review.** For each test file in the commit: what does it cover, what does it leave uncovered, are there obviously smoke-only tests that look like coverage but aren't.
- **`pyproject.toml` diff review.** Any new dependencies get a note: why needed, how wide the attack surface, any known deprecation or maintenance concerns.
- **Template + HTML review.** The `eval/templates/` tree ships Jinja2 and HTML. Sanity-check: no inline JS eval of user input, no remote asset loads (the report is supposed to be self-contained/offline).
- **Config review.** Any new YAML configs: are they consistent with `configs/instruments.yaml` conventions, do they have explicit units, no hardcoded contract values.
- **Architectural-fit verdict.** Does the Antigravity work extend the existing project's idioms, or does it introduce parallel idioms? Specifically look for:
  - Two different ways to load trades.
  - Two different logger setups.
  - Two different config schemas.
  - Duplicate metric computations (e.g., Sharpe in both `summary.py` and `stats.py`).
- **Look-ahead flag pass** (surface-level only — deep look-ahead audit is Session 17). If any `eval/` or `indicators/` module visibly uses `bar[t].close` to compute `indicator[t]` without a `shift(1)`, flag it.
- **Findings report** → `outputs/validation/session-16-antigravity-review.md`.
- **Session 17 target list** → appended to `outputs/validation/session-16-antigravity-review.md` as a named section: "Files flagged for Session 17 statistical-rigor audit", with per-file rationale.

## Out of Scope

- **Verifying DSR / PSR / Sharpe math against references** (→ Session 17).
- **Verifying walk-forward purge/embargo correctness** (→ Session 17).
- **Verifying trials registry schema semantics** (→ Session 17).
- **Verifying meta-labeling labels / purge / leakage prevention** (→ Session 17).
- **Deep look-ahead audit of Antigravity indicators under next-bar-open fill** (→ Session 17).
- **Fixing anything.** Findings get documented. Fixes are separate sessions scoped against the findings.
- **Running the reports.** Session 16 reads code; Session 17 runs the code. (Possible exception: import smoke test — see Executor Notes.)
- **Reviewing code that predates `de03c04`.** Pre-existing modules are only reviewed insofar as they interact with Antigravity's additions.
- **Any strategy work, data work, or config changes to `configs/instruments.yaml`.**

## Preconditions

- Session 15 complete and merged (or at minimum, Session 15's census report available).
- `outputs/validation/session-15-pipeline-robustness.md` exists — it may surface findings that change Session 16's targeting.
- `outputs/validation/session-15-repo-census.md` exists — it establishes what "the tree" actually is.
- `main@de03c04` unchanged since the recovery started.
- `uv sync` clean; imports of `trading_research` package succeed.

## Deliverables

1. **Commit Inventory** → `outputs/validation/session-16-inventory.md`
   - `git show --stat de03c04` output, annotated by module.
   - Module-to-LOC table.
   - Test-to-code ratio per subpackage (`eval/`, `backtest/`, `gui/`).
   - New dependencies from `pyproject.toml` delta.

2. **File-by-file Review Report** → `outputs/validation/session-16-antigravity-review.md`
   - One row per `.py` file: path | LOC | has-tests | status (clean / has-questions / blocking) | notes.
   - Per-file notes cite line numbers for anything flagged.
   - Summary section: architectural-fit verdict, count of files in each status bucket, list of duplicate-idiom findings.
   - Named section: "Files flagged for Session 17 statistical-rigor audit" — this is the input to Session 17.

3. **Template + HTML Review** → appended to the review report as a section.
   - Each template file checked against the "self-contained / offline / no remote assets" requirement.

4. **Config Review** → appended to the review report.
   - Any new YAML audited for unit consistency, no hardcoded values, alignment with `instruments.yaml` conventions.

5. **Evidence directory** → `outputs/validation/session-16-evidence/`
   - Raw `git show`, `grep`, `rg` outputs that informed the review.
   - Any scripts written to produce the inventory (one-off, not committed as tools).

6. **Session 16 work log** → `outputs/work-log/YYYY-MM-DD-HH-MM-session-16-summary.md`.

7. **CHANGELOG.md entry** for `[SESSION-16]`.

## Acceptance Criteria

- [ ] Every `.py` file added or modified by `de03c04` appears in the file-by-file review table.
- [ ] Every file flagged `has-questions` or `blocking` has a cited line number and a one-sentence rationale.
- [ ] The architectural-fit verdict is explicit. "Cohesive extension" / "Adjacent but salvageable" / "Graft that needs rework" — pick one and defend it.
- [ ] The Session 17 target list is present and ordered by priority.
- [ ] No code under `src/trading_research/` is modified (read-only session).
- [ ] If the import smoke test (`python -c "import trading_research.eval.stats"` etc.) fails for any module, that is a blocking finding and the affected module's status is `blocking`, not `has-questions`.
- [ ] The review identifies at least the known Antigravity risks from the handoff: HTF aggregation in `resample_daily()`, unadjusted ZN roll consumption, look-ahead under next-bar-open fill. If any of these are *not* present in the code (possibly already fixed), that is a finding too — "handoff claimed X, code does not contain X".
- [ ] Mentor-voice commentary appears in the summary section. This is not a dry inventory; it is a trader reading code and saying what smells right and what smells like a textbook.

## Files / Areas Expected to Change

| Path | Change | Why |
|---|---|---|
| `outputs/validation/session-16-inventory.md` | Created | Deliverable 1 |
| `outputs/validation/session-16-antigravity-review.md` | Created | Deliverables 2–4 |
| `outputs/validation/session-16-evidence/` | Created | Deliverable 5 |
| `outputs/work-log/<new>-session-16-summary.md` | Created | Deliverable 6 |
| `CHANGELOG.md` | Entry added | Deliverable 7 |

Nothing under `src/`, `configs/`, `tests/`, `notebooks/`.

## Risks / Open Questions

- **Scope creep into Session 17.** A reviewer reading `eval/stats.py` and seeing the DSR implementation will be tempted to verify the math. Do not. Flag the file for Session 17 and move on. Discipline matters because Session 16's value is breadth, not depth.
- **"Clean" file count may be misleading.** A file that passes every surface check (types, docstring, tests present) can still be mathematically wrong. "Clean" in this session means "no structural red flags", not "correct".
- **Test-to-code ratio can flatter.** If Antigravity tests are mostly import-smoke or fixture construction, the ratio lies. Sample-check at least 3 test files per subpackage to verify the tests exercise behavior, not just existence.
- **Parallel idioms may be intentional.** If `eval/summary.py` and `eval/stats.py` both compute Sharpe, the question is why. Maybe it's duplication to remove; maybe it's a deliberate "fast path for CLI, full path for report". Ask before assuming.
- **Jinja2 templates are HTML injection territory.** Any use of `{% autoescape false %}` or `| safe` filter needs line-by-line review. This is the one area where a "surface review" can still catch a real issue.
- **GUI review is the thinnest.** The GUI is Dash-based and behavior lives in callbacks; a structural read may not catch runtime issues. Flag the GUI for a separate "run-the-app" session if the structural review cannot reach a verdict.

## Executor Notes

**Model choice:** This session benefits from Opus 4 on the summary + verdict portions, and Sonnet on the file-by-file mechanical pass. If only one model is available, Opus is the right choice — the architectural-fit verdict is the load-bearing deliverable and Sonnet tends to be more willing to score everything "clean" under time pressure. Ibby decides at session start.

Order of work:

1. **Phase A — Inventory.** `git show --stat de03c04 > outputs/validation/session-16-evidence/commit-stat.txt`. Produce the inventory table. Read the commit message. Cross-reference against Session 15's census.
2. **Phase A — Import smoke test.** `uv run python -c "import trading_research.eval; import trading_research.backtest; import trading_research.gui"` — just confirm the packages import. Record result in evidence dir.
3. **Phase B — File-by-file pass on `eval/`.** 27 files. This is the bulk of the session. Work through them in import-dependency order: `stats.py`, `bootstrap.py`, `drawdowns.py`, ... up to the reports. Flag aggressively; unflag selectively on second pass.
4. **Phase B — `backtest/walkforward.py` and any other backtest touches.** Small surface.
5. **Phase B — `gui/` pass.** Schemas registry, callbacks, app. Look for dynamic rule-construction code that bypasses the schemas (the archived Session 14 plan flagged this as a risk).
6. **Phase B — Templates and configs.** Short.
7. **Phase C — Test surface.** Walk the tests dir; map each test file to the module it covers. Sample-check 3 test files per subpackage to verify behavior coverage.
8. **Phase C — Architectural-fit verdict.** This is where the mentor voice speaks. Write it plain. If the verdict is unflattering, say so.
9. **Phase D — Session 17 target list.** From the aggregate flags, produce the ordered file list for Session 17. Each entry: file, rationale, specific check needed.
10. **Phase D — Work log + CHANGELOG.**

No per-file commits. Commit the review documents when they are complete, one commit per deliverable.

If any `blocking` finding is surfaced (broken import, obvious look-ahead, unsafe Jinja2 autoescape off), stop and raise it to Ibby immediately. Do not continue the pass pretending the finding didn't happen.

## Completion Block

```
Session 16 — Completion

Branch: session/16-antigravity-review at <SHA>

Commits:
- (sha : message) x5–7

Validation artifacts:
- outputs/validation/session-16-inventory.md
- outputs/validation/session-16-antigravity-review.md
- outputs/validation/session-16-evidence/ (N files)

Files reviewed: N total (E in eval/, B in backtest/, G in gui/, T in templates, C in configs)
Status buckets:
- clean: N
- has-questions: N
- blocking: N

Architectural-fit verdict: Cohesive extension / Adjacent but salvageable / Graft that needs rework
(one-paragraph rationale)

Session 17 target list:
1. <file> — <check>
2. <file> — <check>
...

Known Antigravity handoff risks status:
- HTF aggregation validation: present / absent / already fixed
- Look-ahead strictness under next-bar-open fill: (finding)
- Unadjusted ZN roll consumption: (finding)

Duplicate-idiom findings:
- (list or "none")

Import smoke test: pass / fail (if fail, which modules)

Decisions made during execution:
- (any)

Known limitations:
- GUI runtime not exercised this session
- (others)

Next session: Session 17 — Statistical Rigor Audit.
```
