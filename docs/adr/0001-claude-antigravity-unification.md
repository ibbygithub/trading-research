---
adr: "0001"
title: Claude Code and Antigravity Infrastructure Unification
status: accepted
date: 2026-04-16
deciders: Ibby
source: claude_antigravity_infrastructure_unification_plan.md (provided as chat content 2026-04-17)
relocated_by: session-14
---

# ADR 0001 — Claude Code and Antigravity Infrastructure Unification

## Context

This project uses two AI agent systems:
- **Claude Code** (Anthropic, Sonnet/Opus) — primary development agent, runs in the IDE via the CLI, handles code editing, testing, git operations
- **Antigravity** (Google Gemini-based) — secondary agent used for certain research, planning, and validation sessions

Prior to this decision, the two agents operated with separate configuration conventions, separate skill definitions, and no shared governance. Sessions handed off between agents left gaps: context was duplicated, conventions drifted, and the "Produced vs Accepted" distinction was not consistently enforced.

## Decision

Unify the governance layer so that both agents operate from the same shared constitution (`AGENTS.md`) and the same skill definitions, with tool-specific variants only where unavoidable.

### Produced vs Accepted

A session is **Produced** when the work exists (code written, files created, outputs generated). A session is **Accepted** when it is documented, scoped, and merged into canonical project history (PR opened, Ibby reviewed, merged to `develop`).

The distinction matters because Antigravity sessions were routinely Produced but not Accepted — work existed in branches or outputs but was not formally captured in project history. This ADR establishes that Accepted state requires a PR merge to `develop`.

### Shared Governance Files

| File | Purpose |
|---|---|
| `AGENTS.md` | Shared constitution: mission, rules, definition of done, persona references |
| `GEMINI.md` | Antigravity-specific addendum; defers to `AGENTS.md` in its first paragraph |
| `docs/handoff/current-state.md` | Current project state (updated at end of every session) |
| `docs/handoff/open-issues.md` | Known problems and open decisions |
| `docs/handoff/next-actions.md` | Immediate next task for whichever agent picks up the work |

### Shared Skills

The GitHub Repo Steward skill (v0.1, Session 14) is the first skill to be mirrored across both `.claude/skills/` and `.gemini/skills/`. Future skills follow the same pattern: shared content, clearly marked tool-specific sections.

### Rejected Alternatives

**VPS "Split-Brain" architecture** — proposed by Antigravity review; rejected. No strategy exists yet, no paper trading period completed. VPS adds operational complexity before the house has walls. Decision deferred to penthouse phase. If live execution eventually requires remote execution, the home lab's brainnode-01 is the natural candidate.

**Separate planning tools per agent** — rejected. Maintaining two separate planning document conventions produces drift. A single `docs/session-plans/` tree, readable by both agents, is the correct approach.

## Consequences

- Every session ends with a PR to `develop`. Ibby merges; agents do not.
- `AGENTS.md` is the authoritative source for rules. Both `CLAUDE.md` and `GEMINI.md` defer to it on overlap.
- Skills are maintained in both `.claude/skills/` and `.gemini/skills/`. Near-identical content; tool-specific differences explicitly marked.
- The three Antigravity open risks (HTF validation, look-ahead audit, unadjusted roll consumption) are scheduled for Session 15 regardless of which agent executes it.
