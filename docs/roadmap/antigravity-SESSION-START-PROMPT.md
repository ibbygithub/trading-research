# Session Start Prompt Template

**Purpose:** This is the canonical prompt to kick off any session (Claude Code, Gemini Antigravity, or any other coding agent). Copy the template below, fill in the `{{SESSION_NUMBER}}` placeholder, and paste it as the first message in a new session.

**Why this exists:** Without a standard kickoff, every session burns tokens having the agent discover the project layout, read persona files, find the spec, and re-orient. This template front-loads that context in one structured prompt.

---

## How to use

1. Start a new agent session in the `C:\git\work\Trading-research` directory.
2. Copy everything between the `--- BEGIN PROMPT ---` and `--- END PROMPT ---` markers below.
3. Replace `{{SESSION_NUMBER}}` with the number of the session you're running (e.g. `23-a`, `24`, `D1`).
4. Paste as the first message.
5. The agent will confirm it has read the required docs and present the plan before writing code. Reply with "proceed" or provide course corrections.

---

## --- BEGIN PROMPT ---

You are starting session 25 of the Trading Research platform. This is a personal quant trading research desk. Code goes into `src/trading_research/`, configs into `configs/`, tests into `tests/`.

**Before writing any code, read the following files in this exact order:**

1. `docs/roadmap/session-specs/session-{{SESSION_NUMBER}}.md` — the specification.
2. `/.agent/rules/AGENT.md` — project conventions and "Stop" hook.
3. `/.agent/rules/quant-mentor.md` — persona guidance.
4. `/.agent/rules/data-scientist.md` — persona guidance.
5. `/.agent/rules/platform-architect.md` — persona guidance.
6. `/.agent/skills/` — Read the SKILL.md files for relevant capabilities (e.g., data-pipeline for B1, feature-factory for 26).
7. Any files listed in the "Reference" section of the session spec.

**After reading, do the following in your first response — before any code changes:**

1. State the session goal in one sentence, in your own words.
2. List the in-scope files you will create or modify.
3. List the out-of-scope files you will NOT touch, even if tempted.
4. List the acceptance tests that must pass for the session to be considered done.
5. Identify which persona reviews are required per the spec.
6. Flag any ambiguity in the spec that needs clarification before proceeding.
7. Ask for approval to proceed or await clarification.

**Project conventions you must follow (these are invariants, not preferences):**

- Python 3.12, managed by `uv`. Install deps with `uv sync`, run tests with `uv run pytest`.
- Type hints required on every public function.
- `ruff check` passes with zero errors before you declare done.
- Paths use `pathlib.Path`, never string concatenation.
- Timestamps are timezone-aware, stored in UTC, displayed in `America/New_York`. Naive datetimes are bugs.
- Logging uses `structlog`, not `print()`. No bare `print()` in `src/`.
- Configs in YAML live in `configs/`. Hardcoded values in Python are a smell.
- Commit messages follow the project pattern: `<type>(session-NN): <subject>`. Examples: `feat(session-23a): instrument protocol`, `test(session-23a): registry tests`, `docs(session-23a): work log`.

**Scope discipline (non-negotiable):**

- Do NOT perform opportunistic refactoring ("while I'm here I'll also fix X"). If you see something worth fixing that's out of scope, note it in the session work log under "observed debt" and move on.
- Do NOT add features beyond what the spec requests.
- Do NOT write tests for things the spec doesn't mention. Tests for in-scope code only.
- Do NOT touch the trial registry format, manifest format, or any schema unless the spec explicitly says so.
- Do NOT merge to `main` under any circumstances. You may push to `origin/develop` or a feature branch. Human merges to main.

**Completion protocol:**

When all acceptance tests pass and the definition-of-done checklist is satisfied:

1. Run the full test suite: `uv run pytest`. Report the full pass/fail count.
2. Run linters: `ruff check src/ tests/` and `mypy src/` if configured. Report results.
3. Write a work log to `outputs/work-log/YYYY-MM-DD-HH-MM-session-{{SESSION_NUMBER}}.md` following the format in CLAUDE.md section "Session work logs".
4. Stage and commit changes on a feature branch named `session-{{SESSION_NUMBER}}-<short-slug>`. Use `git add <specific-files>`, never `git add -A`.
5. Summarize: what shipped, what tests pass, what reviews are needed.

**If you hit a blocker:**

- If the spec is ambiguous, stop and ask. Do not guess.
- If a required test is failing for reasons unrelated to the session, stop and ask. Do not paper over.
- If you realize the spec's scope is wrong (too large, too small, missing a dependency), stop and ask. Specs can be revised; silent overruns cannot.
- Token budget: if you are approaching token limits before completing the session, stop at the next clean stopping point, commit what works, write a partial work log, and surface the handoff state.

**Personas:**

The three personas loaded via `.claude/rules/*.md` are active for the whole session. If market logic is at stake, the mentor speaks up. If statistical integrity is at stake, the data scientist speaks up. If architectural integrity is at stake, the architect speaks up. You don't have to wait to be asked.

---

## --- END PROMPT ---

## Variations

### For Gemini Antigravity

Gemini does not auto-load the `.claude/rules/` persona files. Add to the top of the prompt:

```
Note: If persona files under .claude/rules/ cannot be loaded directly, read their content
and adopt the three voices (quant mentor, data scientist, platform architect) throughout
the session. The persona files are the authoritative voice guide.
```

### For a partial/resume session

If a previous agent stopped mid-session and you're resuming:

```
This session was started by a prior agent and is being resumed. Before reading the
session spec, first read the most recent work log at outputs/work-log/ to understand
what has already been completed. Then read the spec and determine what remains.
```

### For a spec-less exploratory session

If there is no session spec (e.g. a bug-fix or spike session):

```
This is an exploratory session, not a spec-driven one. No session spec exists in
docs/roadmap/session-specs/. The goal is: {{STATE GOAL HERE}}.

Skip step 1 in the reading list. Still read all other files. In your first response,
propose a scope, an acceptance criterion, and whether this work should produce a
durable spec for future reference.
```

---

## Maintenance

Update this template when:

- Project conventions change (edit the "Project conventions you must follow" section).
- A new persona file is added.
- The commit message pattern changes.
- A new tool (linter, type checker, test runner) is added to the required-pass list.

Do not let this template rot. A stale template wastes more tokens than no template.
