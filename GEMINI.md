# GEMINI.md — Antigravity Agent Addendum

**Defers to `AGENTS.md`.** Read `AGENTS.md` first. Everything in that file applies
to Antigravity sessions. This file covers Antigravity-specific configuration only.

---

## Antigravity-Specific Guidance

### Tools available
Antigravity operates with Google Gemini model access and its own toolset. Where the session plan or `AGENTS.md` references Claude-specific tooling (e.g., `uv run pytest`, the `Bash` tool, `Edit` tool), use the equivalent Antigravity tool or subprocess call.

### Skills
Shared skills are in `.gemini/skills/`. These mirror `.claude/skills/` with tool-specific
differences clearly marked in each skill file. Always use the `.gemini/skills/` version,
not `.claude/skills/`.

### Personas
The quant-mentor and data-scientist personas are defined in `AGENTS.md` by their behavior
contracts. Internalize them — do not look for `.gemini/rules/` files (they don't exist yet).

### Handoff files
Read `docs/handoff/current-state.md`, `docs/handoff/open-issues.md`, and
`docs/handoff/next-actions.md` at the start of every session. Update them at the end.

### PR process
Antigravity opens PRs against `develop` the same as Claude Code. Ibby merges. The agent
does not merge.

---

## What Antigravity Does Not Override

- The Produced vs Accepted distinction (AGENTS.md)
- Session workflow (AGENTS.md)
- Branching convention (AGENTS.md)
- Standing rules — data integrity, backtesting honesty, risk management (CLAUDE.md)
- The human's exclusive authority over real-money decisions

---

## Infrastructure Decision

The VPS "Split-Brain" architecture (Antigravity running live execution remotely) was proposed and rejected. See `docs/adr/0001-claude-antigravity-unification.md`. Antigravity's current scope is research and validation, same as Claude Code. Live execution infrastructure is a penthouse-phase decision.
