# Session 40 — Handoff Prompt

**Paste this into Claude Code at the start of session 40.**

---

You are starting session 40 of the Trading Research platform. Read this entire prompt before touching any tools.

## What this project is

A personal quant research lab for CME futures strategies. Single-instrument and pairs work across ZN, 6E, 6A, 6C, 6N. Mean-reversion bias. Honest backtesting with pessimistic fills, full trade forensics, and a validation gate before anything goes to paper.

Working directory: `C:\git\work\Trading-research`
Current branch: `session-39-h4-redesign-h6-exploration`
Main branch: `main`

## How sessions 38–39 changed the project

The last two sessions exposed a problem: agent-driven sessions had drifted into hunting for a profitable strategy (H4 6A monthly VWAP fade, H6 ZN MACD zero-cross) instead of completing the platform. The operator (Ibby) called this scope creep explicitly and redirected.

The new operating model, which is **non-negotiable**:

1. **No agent-driven strategy hunting.** When a strategy fails the validation gate, the correct response is "this strategy doesn't work, here is the honest finding" — *not* "let me design v3 with a new regime filter." Strategy invention is Ibby's job; the platform's job is to give him honest answers.
2. **Documentation before code.** The manual (`docs/manual/`) is being written spec-first. Ibby reviews the manual; once he agrees with how a section describes platform behavior, the code is finished to match. Any code change after a chapter is ratified must either match the manual or be accompanied by a manual revision.
3. **CLI is the API.** Every operation must work as a single `uv run trading-research <subcommand>` invocation. Output must be parseable (tabular for humans, JSON-when-asked for machines). No interactive prompts. The future GUI will be a thin shell over the CLI.

These are saved as durable feedback memories. Do not drift from them.

## Where session 39 left off

### What got built (committed)

- Session 39 explored H4 v2 redesign and H6 ZN MACD zero-cross (commit `2b49890`)
  - H4 v2b (no time gate, `target_mult=0.5`) was the first positive-Calmar variant in H4 history
  - H4 v2b walk-forward: 3/5 folds positive but aggregated Calmar=0.00, regime-dependent; **does not pass validation gate**
  - H6: 16 variants all negative; **DROPPED**
- The Trading Desk Operator's Manual v0.2-draft was created (separate commit on the same branch)
  - `docs/manual/README.md` — manual project overview
  - `docs/manual/00-quick-start.md` — quick-start stub (one page, five commands)
  - `docs/manual/TABLE-OF-CONTENTS.md` — comprehensive TOC, 60+ chapters, 11 parts + extension Part XII, full gap list with priorities
  - `docs/manual/04-data-pipeline.md` — sample chapter at quality bar (~22 print pages), three Mermaid diagrams, full GC cold-start worked example, per-instrument storage forecast

### What Ibby's feedback established for session 40+

- **Manual structure ratified.** 11 parts + extension Part XII, 60+ chapters. Quality bar is Chapter 4.
- **Logging is [PARTIAL], not [EXISTS].** Only 10 of 80+ modules use structlog.
- **Storage management is a v1.0 deliverable**, not optional polish. The platform grew from ~1.5 GB to ~4 GB in 30 days with no cleanup mechanism. Specification is in TOC Chapter 56.5.
- **CLI-as-API is a hard design contract.** Every feature must be a CLI invocation; future GUI wraps the CLI.
- **Two new chapters added to TOC for post-v1.0 work**:
  - Chapter 58 — TradingView Pine Script indicator import (post-v1.0)
  - Chapter 59 — Interactive launcher / GUI wrapper (post-v1.0)
- **Trade-overlay charts in the report** — Ibby flagged that he can't see trades on charts without the replay app; this is post-v1.0 but should be done before live-trading work.

### The v1.0 backlog (from `docs/manual/TABLE-OF-CONTENTS.md` gap list)

| # | Item | Sessions | Notes |
|---|------|----------|-------|
| 1 | Surface existing statistical rigor (DSR/CI/fold variance in headline report) | 1 | Chapter 17.5, 22.7, 23.5, 32.4 |
| 2 | Ship `validate-strategy`, `status`, `migrate-trials` CLIs | 1 | Chapter 49.15, 49.16, 32.5 |
| 3 | Storage management (`clean` subcommands + retention policy) | 1 | Chapter 56.5 |
| 4 | Logging coverage + run_id + rotating file logger + tail-log | 1 | Chapter 52 |
| 5 | Cold-start runbook + quick-start guide finalized end-to-end | 1 | Chapter 54, front matter |
| 6 | Schema migration tooling + daily loss limit in BacktestEngine | 1 | Chapter 6.5, 35.2, 56.3 |
| 7 | Manual writing — remaining chapters at Chapter 4 quality bar | ~7 | One chapter at a time |

**Total: 13–14 sessions to v1.0 with manual; 6–7 sessions code-only if manual is written separately.**

Post-v1.0 (separate phase): trade-overlay charts (1), pairs/spread support (1.5), TradingView Pine import (2–3), TUI launcher (1.5), web GUI (2), then paper-trading and live-execution as their own multi-session project.

## What session 40 is for

The operating decision is between two parallel work streams:

**Stream A — Manual chapter authoring** (continues session 39's work). One or two chapters per session, written at Chapter 4's quality bar, reviewed by Ibby, accepted, then commit. This is the canonical path to v1.0 because it ratifies the spec before any code is touched. Recommended next chapters in priority order:

1. **Chapter 5 — Instrument Registry** (small, foundational, ~5 pages). Every other chapter references the InstrumentSpec contract.
2. **Chapter 56.5 — Storage Management & Cleanup** (~6 pages). Documents the gap explicitly so the code spec is ratified before implementation.
3. **Chapter 49 — CLI Command Reference** (~12 pages). Ibby is most interested in this because it's foundational for the future GUI.
4. **Chapter 50 — Configuration Reference** (~6 pages). Pairs naturally with 49.

**Stream B — Code work against ratified spec.** Pick the highest-priority v1.0 backlog item *whose chapter is already ratified*, and implement to match. This requires Ibby to have accepted the relevant chapter first. Currently only Chapter 4 (Data Pipeline) is ratified, and most of Chapter 4 is [EXISTS] — there's no immediate code work to do from Chapter 4 alone.

**Recommendation for session 40:** Stream A — write Chapter 5 (Instrument Registry) and Chapter 56.5 (Storage Management) in this session. Both are short-to-medium, both unblock subsequent chapters, and Chapter 56.5 ratifies the spec for the highest-priority code gap.

Wait for Ibby to confirm direction before doing anything.

## Read these before writing code or chapters

1. [`CLAUDE.md`](../../CLAUDE.md) — operating contract, standing rules, all conventions
2. [`.claude/rules/quant-mentor.md`](../../.claude/rules/quant-mentor.md) — market structure voice (speak up unprompted)
3. [`.claude/rules/data-scientist.md`](../../.claude/rules/data-scientist.md) — statistical integrity voice (speak up unprompted)
4. [`.claude/rules/platform-architect.md`](../../.claude/rules/platform-architect.md) — system design voice (speak up unprompted)
5. [`docs/manual/README.md`](../../docs/manual/README.md) — manual project overview
6. [`docs/manual/TABLE-OF-CONTENTS.md`](../../docs/manual/TABLE-OF-CONTENTS.md) — every chapter, every section, every gap. Priority work is in the gap list at the bottom.
7. [`docs/manual/04-data-pipeline.md`](../../docs/manual/04-data-pipeline.md) — the quality bar for chapter authoring. New chapters must match this depth and structure.

If session 40 is a code session against a ratified chapter, also read the relevant source files for the gap being closed.

## Conventions for chapter authoring (Stream A)

- One file per chapter: `docs/manual/<NN>-<slug>.md` where `NN` is the chapter number with leading zero.
- Match the structure of Chapter 4: opening status block, `<chapter>.0` overview section, numbered sub-sections, "Why this:" callouts where design choices need defending, cross-references to other chapters, "Related references" closing section.
- Cite source files with full repository-relative paths and where appropriate line numbers (`src/.../engine.py:142`).
- Mark every section with `**[EXISTS]**`, `**[PARTIAL]**`, or `**[GAP]**` in the same way the TOC does. If a section documents a gap, the chapter contains the implementation specification — this is what unlocks code work later.
- Add Mermaid diagrams where flow or dependency relationships matter. Tables for reference material. Code blocks for examples.
- Prefer brevity over coverage. A short tight section beats a long meandering one. Chapter 4 ran ~22 print pages; not every chapter needs that.

## Conventions for code work (Stream B)

- Only implement to match a ratified chapter. If the chapter says `[GAP]` and Ibby has accepted that chapter, the chapter's specification is the source of truth.
- If the implementation diverges from the chapter, update the chapter and re-request review. Never let the code drift from the manual.
- Write tests that verify the chapter's described behavior. The chapter is the test oracle.
- Standard completion protocol: `uv run pytest`, `uv run ruff check src/`, work log, commit on a session branch.

## Operating model — don't break it

The standing rules from sessions 38–39 are preserved as memories and apply to every future session:

- No agent-driven strategy hunting. Strategy invention is Ibby's domain.
- The CLI is the API. Every operation is a CLI command with parseable output.
- Documentation before code. The manual ratifies behavior; code matches.
- The mentor, data scientist, and architect personas exist for *design conversations*, not for steering exploration. They speak up unprompted on their own concerns and let Ibby synthesize.

## Completion protocol

Before ending the session:

1. Run `uv run pytest` — full suite must pass (1 SHAP skip on Windows is pre-existing and OK)
2. Run `uv run ruff check src/` — ruff has pre-existing violations in untouched files; do not fix unless asked. The criterion is "no new violations introduced this session."
3. Write work log to `outputs/work-log/YYYY-MM-DD-HH-MM-session-40.md`
4. Commit on a new branch `session-40-<short-description>`
5. Do not push, do not merge to main — Ibby does that
6. Update memory if any new feedback was given that affects future sessions

End of handoff prompt.
