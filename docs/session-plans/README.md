# Session Plans

This directory holds one Markdown file per planned, in-progress, or completed session. A session is a bounded unit of work with explicit scope, deliverables, and acceptance criteria. No work happens without a plan here first.

## Naming

```
session-NN-{descriptive-slug}.md
```

Examples: `session-14-repo-census.md`, `session-15-indicator-census.md`, `session-16-feature-war-chest.md`.

Generic names like `session-14-plan.md` are not allowed. The slug is how a human reader knows what the session is about without opening the file.

Superseded plans move to `archive/` with a front-matter `superseded_by:` pointer. They are not deleted.

## Required Frontmatter

```yaml
---
session: <int>
title: <short title>
status: Draft | Approved | In Progress | Complete | Accepted
created: YYYY-MM-DD
planner: <who wrote the plan>
executor: <who will execute — Claude Code Sonnet, Claude Code Opus, Antigravity, human>
reviewer: <who approves — typically Ibby>
branch: session/NN-slug
depends_on: <list of session numbers or 'none'>
blocks: <list of downstream sessions or work>
repo: https://github.com/ibbygithub/trading-research
---
```

## Required Sections

Every plan has these sections in this order:

1. **Why this session, why first** — a short paragraph that explains *ordering*, not just scope. For a research project, when matters as much as what.
2. **Objective** — one paragraph.
3. **In Scope** — bullet list. Explicit.
4. **Out of Scope** — bullet list. Also explicit. Naming what you are *not* doing prevents scope drift mid-session.
5. **Preconditions** — what must be true before execution starts.
6. **Deliverables** — every deliverable has a concrete output path. If you cannot name the file, it is not a deliverable.
7. **Acceptance Criteria** — a checkbox list. This is the definition of done.
8. **Files / Areas Expected to Change** — a table, one row per path.
9. **Risks / Open Questions** — what could go wrong, what is uncertain.
10. **Executor Notes** — specific, actionable guidance for whoever executes the plan. This is where the planner speaks to the executor; it replaces chat memory as the handoff mechanism.
11. **Completion Block** — a template the executor fills in. Not a separate document. One artifact per session.

Deliberately omitted:
- No "Assumptions" section — put assumptions in Preconditions or Risks.
- No separate "Validation" section — validation is a Deliverable and an Acceptance Criterion.
- No formal sign-off — the PR merge is the sign-off.

## Produced vs Accepted

A session is **Produced** when the work exists. A session is **Accepted** when it is documented, scoped, tested, and merged into the canonical project history on `develop`. Acceptance Criteria drive the transition. Most of the time, a session should not be closed as Produced — it should either be Accepted or still In Progress.

## Validation artifacts

Validation output for a session lives at `outputs/validation/session-NN-*.md`. Unlike most outputs, these files are *tracked in git* — they are the record of how we know the work is real. Supporting evidence (command logs, grep results, intermediate data) lives at `outputs/validation/session-NN-evidence/` and is also tracked.

## Reference example

The canonical example of this format is [`session-14-repo-census.md`](session-14-repo-census.md).
