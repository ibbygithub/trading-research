# Dispatcher Routing Rules
Version: 1.0
Date: 2026-04-26

This document is the contract between the dispatching agent (or human acting
as dispatcher) and the model receiving work. It is intentionally mechanical.
A dispatcher implementing this should be able to do so without market or
strategy knowledge.

## The routing header — what every per-model spec starts with

Every per-model spec file begins with this block (literal, not a placeholder):

```
═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           <e.g., 29a-opus>
Required model:    <Opus 4.7 | Sonnet 4.6 | Gemini 3.1>
Required harness:  <Claude Code | Antigravity | either>
Phase:             <1: hardening | 2: paper window | 3: live readiness | 4: live ops>
Effort:            <S | M | L>
Entry blocked by:  <list of spec IDs that must be DONE>
Parallel-OK with:  <list of spec IDs that may run concurrently>
Hand off to:       <next spec ID(s)>
Branch:            <git branch name>
═══════════════════════════════════════════════════════════════
```

If you receive a file and the first non-comment block is not a routing
header in this exact shape, the file is not a valid execution spec.
Do not act on it. Report back to the dispatcher.

## Model self-check protocol

When a model begins a spec, before any tool calls, it executes:

```
1. Read the routing header.
2. Compare "Required model" to your own model identity:
   - You are Opus 4.7 if your system identity reports Opus 4.7
   - You are Sonnet 4.6 if your system identity reports Sonnet 4.6
   - You are Gemini 3.1 if you are running in Antigravity
3. If they match: proceed.
4. If they do NOT match: halt and emit MISROUTE report (template below).
```

## The MISROUTE report

When a model receives a misrouted spec, it emits this and stops:

```
╔═════════════════════════════════════════════════════════════╗
║  MISROUTE DETECTED                                          ║
╠═════════════════════════════════════════════════════════════╣
║  Spec ID:         <from header>                             ║
║  Spec path:       <file path>                               ║
║  Required model:  <from header>                             ║
║  Receiving model: <my identity>                             ║
║                                                             ║
║  Action: dispatcher must re-route to <required>.            ║
║  I have made no tool calls and no edits.                    ║
╚═════════════════════════════════════════════════════════════╝
```

No tool calls. No "let me just check the file structure first." Halt is halt.

## Eligibility check — when can a sub-sprint start

A sub-sprint is eligible to run when:

1. Every Spec ID listed under "Entry blocked by" has status DONE in
   [`../handoffs/current-state.md`](../handoffs/current-state.md).
2. No Spec ID in "Entry blocked by" has status FAILED. (FAILED requires
   human review before downstream work proceeds.)
3. The current branch is the one named in the routing header (or the
   dispatcher creates it).

Status values in `current-state.md`:
- `NOT_STARTED` — never executed.
- `IN_PROGRESS` — picked up by a model; not yet handed off.
- `DONE` — handoff artifacts present and verified.
- `FAILED` — execution stopped without completion; needs human review.
- `MISROUTED` — last attempt was misrouted; awaiting re-route.

## Parallel scheduling

Two sub-sprints may run in parallel iff:
- Each lists the other under "Parallel-OK with" (the relation is symmetric
  in the plan; the dispatcher verifies both halves).
- They share no source files in their "Files I will modify" sections.
- Their branches are distinct.

The plan's [`../plan/dependency-dag.md`](../plan/dependency-dag.md) lists the
full parallel-eligibility matrix.

## Handoff verification

When a model finishes, its checklist requires three things in order:

1. **Acceptance tests pass.** The model runs the listed test commands and
   confirms green.
2. **Handoff artifact written.** A short markdown file at
   `docs/execution/handoffs/<spec-id>-handoff.md` describing what was done
   and what state the next agent inherits.
3. **`current-state.md` updated.** Status set to DONE; timestamp; any
   downstream sub-sprints whose entry-block list is now satisfied are
   marked READY.

The dispatcher verifies #2 and #3 before marking the sub-sprint complete.
If #1 fails, the model marks IN_PROGRESS and reports the failure — it does
NOT mark FAILED unilaterally; that's a human call.

## Cross-model context handoff

Because models cannot share working memory, every cross-model handoff lives
in files. A receiving model reads:

1. Its own per-model spec.
2. The previous spec's handoff artifact (`docs/execution/handoffs/<prev>-handoff.md`).
3. Any explicitly-referenced files (the spec lists them).

It does NOT read the parent session README unless the spec tells it to.
Reading the README exposes other models' work and risks scope creep.

## What a dispatcher does not need to understand

- Trading strategy logic.
- Statistical methodology.
- The codebase structure.

The dispatcher's job is purely: read DAG, check eligibility, read routing
header, route to matching model, verify handoff. If a sub-sprint has no
eligible model available (all are mis-claimed), the dispatcher reports the
queue state to the human and stops.

## What a model must not do

- Execute work for a different model "because I'm capable of it."
- Skip the routing-header self-check.
- Skip the `current-state.md` update at handoff.
- Edit a different sub-sprint's spec mid-execution.
- Author its own validation tests for a Gemini sub-sprint (those come
  pre-written in the spec; see [`gemini-validation-playbook.md`](gemini-validation-playbook.md)).

## Anti-pattern catalog

These are the failure modes this protocol exists to prevent:

| Anti-pattern | Why it happens | What this protocol does |
|---|---|---|
| Sonnet does Opus design work because the spec mentions both | Sonnet sees both sections in one file | Per-model files; routing header halts on mismatch |
| Gemini ships subtly wrong stats code that passes its own tests | Gemini authors implementation + test together | Spec author pre-writes the tests; Gemini fills implementation only |
| A "parallel" sub-sprint waits because the file system blocks | Dispatcher didn't verify the parallel-OK relation is symmetric | Symmetric verification in eligibility check |
| Downstream work proceeds on a FAILED sub-sprint | Status defaults too permissive | FAILED blocks downstream; only human can clear |
| Handoff loss between sessions | No durable state file | `current-state.md` updated at every handoff |

## Failure escalation

If a model encounters a situation the spec did not anticipate:
- Stop work.
- Write `docs/execution/handoffs/<spec-id>-escalation.md` describing what
  was unexpected and what would be needed to proceed.
- Mark the sub-sprint IN_PROGRESS in `current-state.md` (not FAILED — failure
  is a human call).
- Notify the dispatcher / human.

Do not extemporise. The cost of a stopped sub-sprint is one re-routing; the
cost of a wrong-extemporised sub-sprint can be a corrupted backtest result
six sessions downstream.
