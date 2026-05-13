# Session Specs — Canonical Location and Conventions

This directory is **the** location for session-by-session execution
plans. Going forward, every numbered session of the trading-research
project has exactly one spec file in this directory.

## Why one location

Earlier in the project's life, session plans accumulated in two places
(`docs/session-plans/` for sessions 02–17 and `docs/roadmap/session-specs/`
for sessions 23–38). The split was historical accident, not design.
Operating across two directories produced confusion every time a new
session was planned: which folder, which naming convention, which
template. This file ends that.

**From session 41 onward, all session specs live in
`docs/roadmap/session-specs/`.** The older `docs/session-plans/`
directory is preserved as historical record for sessions 02–17 but
receives no new files.

## Naming convention

`session-<NN>-<short-slug>.md` where:

- `<NN>` is the session number with leading zero (`session-41-...`,
  not `session-1-...`)
- `<short-slug>` is a 2–4-word kebab-case description of the session's
  primary deliverable (`storage-cleanup-cli`, `part-i-concepts`)

Example file names:

```
session-41-part-i-concepts.md
session-43-storage-cleanup-cli.md
session-49-cli-reference-and-clis.md
```

The slug is for readability when scanning the directory listing; the
session number is the canonical identifier.

## Spec file format

Each spec contains, at minimum:

```markdown
# Session <NN> — <descriptive title>

**Status:** Spec | In Progress | Done | Deferred
**Effort:** estimated hours / sub-sprints
**Model:** Opus 4.7 | Sonnet 4.6 | Mixed (specify which sub-sections)
**Depends on:** previous session(s) or none
**Workload:** which multi-session program this belongs to (e.g. "v1.0 manual completion")

## Goal
One paragraph: what this session produces and why it matters.

## In scope
- Bullet list of deliverables
- Each deliverable names its model and rough effort if mixed

## Out of scope
- What this session deliberately does not do

## Hand-off after this session
- What state the platform / manual / backlog is in
- What the next session's spec is
```

The `session-38-traders-desk.md` file is the reference example for a
complex multi-sub-sprint spec; simpler sessions can be much shorter.

## Where the start prompt lives

The reusable start-of-session prompt (the thing copy-pasted into a
fresh Claude session) lives in `docs/handoff/`, not here. As of
session 41 the active prompt for the v1.0 manual completion workload
is `docs/handoff/v1-manual-completion-prompt.md`.

## Cross-references

- Session work logs: `outputs/work-log/YYYY-MM-DD-HH-MM-session-NN.md`
- Manual chapters being authored: `docs/manual/`
- Project rules and persona files: `CLAUDE.md`, `.claude/rules/`
