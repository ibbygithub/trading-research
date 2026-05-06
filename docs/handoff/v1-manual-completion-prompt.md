# V1.0 Manual Completion — Session Start Prompt

> **How to use this:** copy everything below the dashed line into a
> fresh Claude Code terminal at the start of any session in the v1.0
> manual completion workload (sessions 41–52). Replace `<NN>` with the
> current session number before pasting. The agent reads the linked
> session spec and proceeds from there.

> **Workload:** v1.0 platform completion through the operator's
> manual + paired code gaps. Twelve sessions total (41–52). Session
> specs live in `docs/roadmap/session-specs/`. This file is the
> reusable entry point.

---

You are starting session **<NN>** of the trading-research project's
v1.0 manual completion workload. Read this entire prompt before
touching any tools.

## Project orientation

- **Working directory:** `C:\git\work\Trading-research`
- **Main branch:** `main`
- **Project rules:** `CLAUDE.md` at the project root; global rules in
  `C:\Users\toddi\.claude\CLAUDE.md`
- **Personas (always loaded):** `.claude/rules/quant-mentor.md`,
  `.claude/rules/data-scientist.md`,
  `.claude/rules/platform-architect.md`
- **Manual chapters:** `docs/manual/`
- **Session specs:** `docs/roadmap/session-specs/` — this is the
  canonical location, formalised in
  [`docs/roadmap/session-specs/README.md`](../../docs/roadmap/session-specs/README.md)

## What you do first, in order

1. Read `CLAUDE.md` and the three persona files. The personas speak
   up unprompted on their own concerns (markets, statistical
   integrity, system design); let them.
2. Read **today's session spec** at
   `docs/roadmap/session-specs/session-<NN>-<slug>.md`. The slug
   varies by session — list the directory if you need to identify
   today's file. The spec names: the session goal, model
   recommendation (Opus or Sonnet, sometimes mixed), in-scope
   deliverables, out-of-scope items, and what state to leave the
   project in.
3. Read the relevant manual chapters being touched this session.
   For doc-only sessions, that's the chapters being authored. For
   bundled chapter+code sessions (43, 46, 49, 50, 52), it's the
   ratified chapter that the code lands against.
4. Read [`docs/manual/04-data-pipeline.md`](../manual/04-data-pipeline.md)
   if you have not seen the quality bar before. Every new chapter
   matches its structure, depth, and citation discipline.
5. Read [`docs/manual/TABLE-OF-CONTENTS.md`](../manual/TABLE-OF-CONTENTS.md)
   for the gap-list status — it is updated each session as items
   close.

## Standing rules (non-negotiable)

These rules are saved as durable feedback memories and apply to
every session in this workload.

1. **No agent-driven strategy hunting.** When something fails the
   validation gate, the correct response is "this doesn't work,
   here is the honest finding" — not "let me design v3 with a new
   regime filter." Strategy invention is the operator's domain.
2. **Documentation before code.** Manual chapters ratify the
   platform's behavior; code lands to match. Any code change after
   a chapter is ratified must either match the chapter or come
   with a chapter revision.
3. **Manual prose describes v1.0 state, not transitional state.**
   No session-N references in chapter prose, no "until
   consolidated" hedging, no `[PARTIAL]` warts in the prose where
   single-truth is possible. Transitional code-cleanup tasks go in
   the gap list, not in chapter content. (Codified after session
   40 Chapter 5 review.)
4. **The CLI is the API.** Every operation reachable as a single
   `uv run trading-research <subcommand>` invocation. Output
   parseable: tabular for humans, `--json` for machines. No
   interactive prompts. The future GUI is a thin shell over this
   CLI.

## The model recommendation in your session spec

Each session spec names the recommended model. The split:

- **Opus 4.7** — chapters that teach a concept (Ch 11, 14, 22, 23);
  code work where architectural judgment matters; bundled
  chapter+code sessions where the chapter has design decisions to
  ratify in-session.
- **Sonnet 4.6** — chapters that primarily *describe what exists in
  code*; reference-depth chapters in Parts V–VIII; appendices and
  layout references.

If you are running on Opus and the spec says Sonnet, it is fine to
proceed but the operator will prefer the cheaper model. If running
on Sonnet and the spec says Opus, raise it before doing the work
that needs the deeper reasoning.

## Conventions for chapter authoring

- One file per chapter at `docs/manual/<NN>-<slug>.md`.
- Match Chapter 4's structure: opening status block, `<chapter>.0`
  overview, numbered subsections, `*Why this:*` callouts on design
  defenses, cross-references to other chapters, closing
  "Related references" section.
- Cite source with full repo-relative paths and line numbers when
  appropriate (`src/trading_research/backtest/engine.py:142`).
- Mark sections `[EXISTS]`, `[PARTIAL]`, `[GAP]` only when the
  state is genuinely partial or absent. Do not use these markers
  to document transitional code that should be cleaned up — that
  rule from Session 40.
- Mermaid diagrams where dependency or flow matters; tables for
  reference data; code blocks for examples.
- Brevity over coverage. A short tight section beats a long
  meandering one.

## Conventions for code work

- Implement only against ratified chapters. The chapter is the
  contract.
- If implementation diverges from the chapter, update the chapter
  and request re-ratification. Never let code drift from the
  manual.
- Tests verify the chapter's described behavior. The chapter is
  the test oracle.

## Completion protocol

Before ending the session:

1. **Run the full test suite:** `uv run pytest -q`. All tests must
   pass; the SHAP skip on Windows is pre-existing and OK.
2. **Run ruff:** `uv run ruff check src/`. The criterion is "no
   *new* violations introduced this session." Pre-existing errors
   in untouched files are not your problem.
3. **Write the work log** to
   `outputs/work-log/YYYY-MM-DD-HH-MM-session-<NN>.md`. Format:
   Completed / Files changed / Decisions made / Next session
   starts from. One page; dense, not wordy.
4. **Update the TOC gap list** if any [GAP] or [PARTIAL] item
   closed this session. The gap list at the bottom of
   `docs/manual/TABLE-OF-CONTENTS.md` should reflect the post-
   session state.
5. **Update memory** if any new feedback was given that affects
   future sessions. Memory directory:
   `C:\Users\toddi\.claude\projects\C--git-work-Trading-research\memory\`.
6. **Commit on a session branch:** `session-<NN>-<short-slug>`.
   Branch from current main; do not push, do not merge to main —
   the operator does that on acceptance.

End of prompt. Proceed by reading the files listed in the
"What you do first" section.
