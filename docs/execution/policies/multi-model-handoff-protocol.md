# Multi-Model Handoff Protocol
Version: 1.0
Date: 2026-04-26
Owner: Architect persona
Applies to: All sprints 29+ that split work across Opus / Sonnet / Gemini.

## Purpose

Plans that split work across model tiers fail at the handoff, not at the
implementation. A great Opus design degrades into a mediocre Sonnet implementation
when the spec is ambiguous. A clean Sonnet spec degrades into broken Gemini code
when the validation tests are owned by the implementer. This document codifies
the handoff rules so the model-tier downgrade is *only* a cost downgrade, not a
quality downgrade.

## Three rules

### Rule 1 — The spec is the contract.

When sub-sprint A hands off to sub-sprint B, the artifact crossing the boundary
is a **spec document**, not a conversation summary, not a "here is the work log,
go from there." The spec lives at a known path, has a fixed structure, and is
committed to the repo before B begins.

**Spec structure (mandatory):**
```
# Sub-sprint <id> — <title>
## Inputs (paths, schemas, prior trial IDs)
## Outputs (paths, schemas, expected files)
## Public API surface (function signatures, types, docstring contracts)
## Acceptance tests (file path, function names, what they assert)
## Out of scope (explicit list)
## References (related modules, papers, prior sub-sprints)
```

If the agent picking up B asks "what should X do?" and the answer is not in the
spec, the spec is broken. Fix the spec; do not let B make a judgment call.

### Rule 2 — The implementer does not author its own validation.

When Gemini ships a statistical method, the **parity test against the canonical
reference is written by the spec author** (Opus or Sonnet). Gemini writes only
the implementation that the test exercises.

This is the single most important rule for keeping less-capable models honest.
A Gemini-authored test against a Gemini-authored implementation tests internal
consistency, not correctness. By the time you notice, you have shipped wrong
numbers and built a strategy on top of them.

The same rule applies to Sonnet when the spec author is Opus and the work is
on a high-stakes statistical or risk path.

**Worked patterns are in `gemini-validation-playbook.md`.**

### Rule 3 — Cohort fingerprinting on every shipped trial.

Anything that produces a backtest trial, a stationarity report, or a metric
artifact records the engine fingerprint:

```python
record_trial(
    ...,
    code_version=git_short_sha(),
    engine_fingerprint=hash_module(backtest.engine),
    featureset_hash=current_featureset_hash(),
)
```

This is what allows multi-day, multi-model sprint sequences to remain
comparable. Skip it once and the comparison report two sprints later is
silently wrong.

## Per-model fit

### Opus 4.7 — design, synthesis, gate decisions

Use for:
- Architectural decisions with multiple defensible options.
- Persona-synthesis sessions (mentor + data-scientist + architect together).
- Walk-forward gate evaluations where the result requires interpretation.
- Debugging where the cause is not isolated to a single module.

Do not use for:
- Mechanical refactors with a defined target state.
- Acceptance test authoring once the design is fixed.
- Routine implementation against a written spec.

Output style for Opus sub-sprints: **always produce a written spec for the
next sub-sprint**, even when the next sub-sprint is the same physical session.
The spec is the deliverable, not the conversation.

### Sonnet 4.6 — workhorse implementation

Use for:
- Implementation against a written spec.
- Walk-forward backtest runs and trade-log analysis.
- Test authoring when the test design is in the spec.
- Debugging within a known module.

Do not use for:
- Decisions that require persona synthesis.
- Architectural choices not yet made in the spec.
- Authoring acceptance tests for code Sonnet itself wrote (use a separate
  Sonnet sub-sprint or escalate to Opus).

Output style: PR-shaped change. Branch, commit, work log, ready for review.

### Gemini 3.1 (Antigravity) — spec-shape mechanical work

Use for:
- Implementing a method whose canonical reference exists and whose parity
  test was written by another agent.
- Resampling, manifest field additions, CLI subcommand wiring, HTML/CSS,
  docstring fan-out, copy edits.
- Routine code migrations where the target shape is fully specified.

Do not use for:
- Anything where Gemini also writes the validation test.
- Strategy logic, risk logic, or live-trading code paths.
- Decisions about where state lives, how modules couple, or what an interface
  should expose.

Output style: PR against the spec. If Gemini cannot satisfy the spec without
a judgment call, Gemini stops and asks; it does not extrapolate.

## The spec→test→impl ordering

The order is non-negotiable for any handoff that crosses a model boundary:

1. **Spec author writes the spec** (Opus or Sonnet, as appropriate).
2. **Spec author writes the acceptance tests** including any canonical-method
   parity tests, in the same commit as the spec.
3. **Implementer (Sonnet or Gemini) implements against the failing tests.**
4. **Spec author reviews the diff before merge.**

Step 2 is the load-bearing one. It is where less-experienced plans cut corners.
Do not cut this corner. The 30 minutes it takes to write the test fixture is
the only thing that distinguishes "validated" from "we hope so."

## Concretely: how a sprint 29 day looks

**Step 1 (Opus 4.7, ~30 min Opus time, your morning).**
Opus produces:
- `docs/roadmap/session-specs/session-29-strategy-foundation.md` (this doc).
- Stub test files under `tests/contracts/` with `pytest.skip` or NotImplemented
  body and clear docstrings explaining what each test asserts.
- Decision log entries in the work log for: registry coupling option, OU bounds
  location, naming convention.

**Step 2 (Sonnet 4.6, ~3 hr Sonnet time).**
Sonnet implements 29b and 29c against the spec and stub tests. The stubs
become real implementations. Sonnet does not modify the spec.

**Step 3 (Gemini 3.1, ~2 hr in Antigravity).**
Gemini implements 29d (OU bounds migration) and the canonical-method parity
tests *that Sonnet already wrote stubs for*. Gemini does not author tests
beyond filling in fixtures the stubs declared.

**Step 4 (Sonnet 4.6 or you, ~30 min).**
Review and merge. Trial registry contract test runs; engine fingerprint check
runs; CI green. Work log captures actual durations vs. estimates.

The protocol is the contract. If it slips on day 1, every later sprint pays for
the slip. Hold the line.

## When the protocol breaks

If during a sprint a sub-sprint's spec turns out to be wrong (an interface
doesn't exist, a contract is impossible to satisfy, a canonical reference
returns different output shape), the sub-sprint **stops and the spec author
returns to fix the spec**. The implementer does not extemporise.

This will happen. The expected rate is ~1 in 10 sub-sprints. Budget for it;
do not pretend it does not happen.

## When NOT to use multi-model

There are sub-sprints where the model split costs more than it saves:

- **Investigative debugging.** When the problem is "why did the equity curve
  go to zero on fold 7," splitting across Opus design / Sonnet implementation
  is wasteful. Run the whole investigation in one model — usually Opus.
- **Dense architectural exploration.** Sprint 29a is design-only. Sonnet does
  not get half the work; Opus owns the whole thing and produces the spec.
- **Tiny one-shot tasks.** A 15-minute fix is not worth a spec document.
  Just do it; commit; move on.

The protocol exists for sub-sprints with implementation work that another
model can do. It does not exist for every piece of work.

## Telemetry to keep

After every multi-model sprint, the work log records:
- Which models were used, in which sub-sprints.
- Estimated vs. actual duration per sub-sprint.
- Whether any sub-sprint had to be re-run because of spec defects.
- Subjective quality assessment (did the Sonnet output need rework? did
  Gemini produce something that matched the spec?).

After 5 sprints we will have data on whether the protocol is producing the
efficiency gains we are betting on. If it is not, revise; do not double down.
