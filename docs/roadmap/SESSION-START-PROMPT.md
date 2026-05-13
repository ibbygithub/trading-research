# Session Start Prompt Template

**Purpose:** This is the canonical prompt to kick off any session. Copy the
template below, replace `{{SESSION_NUMBER}}` with the session number, and paste
it as the first message in a new session.

**Why this exists:** Without a standard kickoff, every session burns tokens
having the agent discover the project layout, read persona files, find the
spec, and re-orient. This template front-loads that context.

**Revision history:**
- v1 (session 40): initial template.
- v2 (session 47): added pre-flight checks to catch the wrong-checkout failure
  mode, moved the model handshake earlier, marked Chapter 4 / TOC as
  first-session-only reads, made "agents do not push or merge to main" an
  explicit standing rule, removed broken auto-link markdown, removed stale
  bundled-sessions list.

---

## How to use

1. Start a new agent session targeted at `C:\git\work\Trading-research`.
2. Copy everything between the `--- BEGIN PROMPT ---` and `--- END PROMPT ---`
   markers below.
3. Replace `{{SESSION_NUMBER}}` with the session number (e.g. `48`, `49`, `B1`).
4. Paste as the first message.
5. The agent runs the pre-flight checks, reads the session spec, presents the
   plan, and waits for "proceed" before doing the work.

---

## --- BEGIN PROMPT ---

You are starting **Session {{SESSION_NUMBER}}** of the trading-research project.

Read this entire prompt before touching any tools.

## Pre-flight (run before anything else)

Run these commands. If any check fails, STOP and report — do not start work
on a broken foundation. This catches the session-47 failure mode (prompt
fired against a stale worktree).

```
cd C:\git\work\Trading-research
git rev-parse --show-toplevel       # -> C:/git/work/Trading-research
git status                           # -> On branch main, clean
git log --oneline -1                 # -> tip is last session's commit
ls docs/roadmap/session-specs/       # -> session-{{SESSION_NUMBER}}-*.md present
ls outputs/work-log/                  # -> previous session's log present
```

Red flags that mean STOP and report before doing any work:

- `show-toplevel` returns a path under `.claude/worktrees/` — you are in a
  stale worktree, not the main repo.
- `docs/manual/` does not exist or is sparse — you're on a stale branch
  checkout. Reconcile before proceeding.
- No spec file exists for this session number. Confirm the number is correct.

## Project orientation

- Working dir: `C:\git\work\Trading-research` (main repo, not a worktree)
- Active branch at start: `main`. You will create `session-{{SESSION_NUMBER}}-<slug>`.
- Project rules: `CLAUDE.md` at project root + `C:\Users\toddi\.claude\CLAUDE.md` (global)
- Personas (always loaded): `.claude/rules/quant-mentor.md`,
  `.claude/rules/data-scientist.md`, `.claude/rules/platform-architect.md`
- Manual: `docs/manual/`
- Session specs: `docs/roadmap/session-specs/`
- Work logs: `outputs/work-log/`

## Standing rules

1. **No agent-driven strategy hunting.** Failed validation → "this doesn't
   work, here is the honest finding," never "let me design v3." Strategy
   invention is the operator's domain.

2. **Documentation before code.** Manual chapters ratify behavior; code lands
   to match. Code that diverges requires a chapter revision first.

3. **Manual prose describes v1.0 state.** No `session-N` references in chapter
   prose. No "until consolidated" hedging. No `[PARTIAL]` markers for
   transitional cleanup — those go in the TOC gap list.

4. **The CLI is the API.** Every operation reachable as
   `uv run trading-research <subcommand>`. Parseable output. No interactive
   prompts. The future GUI is a thin shell over this CLI.

5. **Agents do not push or merge to main.** Commit on the session branch; the
   operator handles `develop → main` on acceptance.

## Read these, in order

1. **Today's session spec.** `docs/roadmap/session-specs/session-{{SESSION_NUMBER}}-*.md`.
   Names goal, model, in-scope deliverables, out-of-scope items, success
   criteria.

2. **Model handshake.** The spec recommends Opus 4.7 (teaching chapters,
   architectural code work) or Sonnet 4.6 (chapters that describe existing
   code, appendices, reference depth).
   - Running Opus when spec says Sonnet → proceed; mention to operator
     (cheaper model preferred unless reasoning depth is needed).
   - Running Sonnet when spec says Opus → raise it BEFORE the work that needs
     deeper reasoning.

3. **Previous session's work log.** `outputs/work-log/*-session-<prev>.md`
   where `<prev>` is `{{SESSION_NUMBER}} - 1`. Tells you the state the
   project is in and what was deferred.

4. **The chapters or modules this session touches.** For docs: the chapters
   being authored. For code or chapter+code: the ratified chapter the code
   lands against, plus relevant source modules.

5. **First-session-only quality references** (skip on subsequent sessions
   unless a structural question arises):
   - `docs/manual/04-data-pipeline.md` — the structural template every chapter
     matches: status block → `<chapter>.0` overview → numbered subsections →
     `*Why this:*` callouts on design defenses → cross-references →
     "Related references" closer.
   - `docs/manual/TABLE-OF-CONTENTS.md` — section status markers and the gap
     list at the bottom.

## In your first response

Before doing any work:

1. Confirm pre-flight passed (one line per check, "OK" or what's wrong).
2. State the session goal in one sentence, in your own words.
3. List in-scope deliverables.
4. List out-of-scope items you will NOT touch even if tempted.
5. Flag any ambiguity in the spec that needs clarification.
6. Confirm or question the model recommendation.
7. Ask for approval to proceed.

## Chapter authoring conventions

- One file per chapter: `docs/manual/<NN>-<slug>.md`
- Match Chapter 4's structure (see above).
- Cite source with repo-relative paths and line numbers
  (`src/trading_research/backtest/engine.py:142`).
- `[EXISTS] [PARTIAL] [GAP]` only when genuinely partial or absent — never
  for transitional cleanup.
- Mermaid diagrams for flow/dependency; tables for reference data; code
  blocks for examples.
- Brevity beats coverage.

## Code conventions

- Implement against ratified chapters; the chapter is the contract.
- If code diverges from the chapter, update the chapter first, then the code.
- Tests verify the chapter's described behavior — the chapter is the test
  oracle.
- Python 3.12 via `uv`. Type hints on public functions. `pathlib.Path`, never
  string concatenation. Timezone-aware UTC timestamps. `structlog`, not
  `print()`. Config in YAML, not hardcoded.
- Commit messages: `<type>(session-{{SESSION_NUMBER}}): <subject>`.

## Scope discipline

- No opportunistic refactoring. Note observed debt in the work log; move on.
- No features beyond what the spec requests.
- No tests for things the spec doesn't cover.
- No schema or registry changes unless the spec says so.

## Completion protocol

Before ending the session:

1. **Tests:** `uv run pytest -q`. All pass; the SHAP skip on Windows
   (OI-013) is pre-existing and OK.
2. **Ruff:** `uv run ruff check src/`. Criterion: no NEW violations
   introduced this session. Pre-existing errors in untouched files are not
   your problem.
3. **Work log:** `outputs/work-log/YYYY-MM-DD-HH-MM-session-{{SESSION_NUMBER}}.md`.
   Sections: Completed / Files changed / Decisions made / Next session
   starts from. One page. Dense, not wordy.
4. **TOC gap list:** Update `docs/manual/TABLE-OF-CONTENTS.md` if any
   `[GAP]` or `[PARTIAL]` closed. If nothing closed, note "no gap-list
   changes this session" in the work log.
5. **Memory:** Update
   `C:\Users\toddi\.claude\projects\C--git-work-Trading-research\memory\`
   only if a durable rule, constraint, or correction was established.
   Memory is for future sessions, not "what we did" (that's the work log).
6. **Commit:** `session-{{SESSION_NUMBER}}-<short-slug>` branch off current
   main. Use specific file names with `git add`, never `git add -A`.
   Do NOT push. Do NOT merge to main. The operator handles all merges
   and pushes on acceptance.

## If you hit a blocker

- Spec is ambiguous → stop and ask. Do not guess.
- A required test fails for reasons unrelated to the session → stop and
  ask. Do not paper over.
- Spec's scope is wrong (too large, too small, missing a dependency) →
  stop and ask. Specs can be revised; silent overruns cannot.
- Token budget approaching → stop at the next clean stopping point,
  commit what works, write a partial work log, surface the handoff state.

## Personas

The three persona files in `.claude/rules/` are active for the whole
session. Mentor speaks up on market logic; data scientist on statistical
integrity; architect on system design. They speak up unprompted — let them.

## --- END PROMPT ---

## Variations

### For Gemini Antigravity or other agents without auto-loaded personas

Add to the top of the prompt:

```
Note: If persona files under .claude/rules/ cannot be loaded directly,
read their content and adopt the three voices (quant mentor, data
scientist, platform architect) throughout the session. The persona files
are the authoritative voice guide.
```

### For a partial/resume session

If a previous agent stopped mid-session and you're resuming:

```
This session was started by a prior agent and is being resumed. Before
reading the session spec, first read the most recent work log at
outputs/work-log/ to understand what has already been completed. Then read
the spec and determine what remains.
```

### For a spec-less exploratory session

If there is no session spec (e.g. a bug-fix or spike session):

```
This is an exploratory session, not a spec-driven one. No session spec
exists in docs/roadmap/session-specs/. The goal is: {{STATE GOAL HERE}}.

Skip the spec read in the order. Still run pre-flight. In your first
response, propose a scope, an acceptance criterion, and whether this
work should produce a durable spec for future reference.
```

---

## Maintenance

Update this template when:

- Project conventions change.
- A new persona file is added.
- A new tool (linter, type checker, test runner) joins the required-pass list.
- A session uncovers a failure mode the pre-flight should catch.

Do not let this template rot. A stale template wastes more tokens than no
template at all — and worse, can route a session into a bad state (see the
session-47 worktree misroute that motivated the v2 revision).
