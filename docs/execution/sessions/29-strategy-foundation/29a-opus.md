═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           29a-opus
Required model:    Opus 4.7
Required harness:  Claude Code
Phase:             1 (hardening)
Effort:            M (~2 hr Opus time)
Entry blocked by:  Track A complete; plan v2 red-lined by Ibby
Parallel-OK with:  D1 (Sonnet) can run on Day 1 same time
Hand off to:       29b-sonnet, 29c-sonnet, 29d-gemini (all three are unblocked
                   when 29a is DONE)
Branch:            session-29-strategy-foundation
═══════════════════════════════════════════════════════════════

# 29a — Architectural ratification + spec & stub-test authoring

## Self-check

- [ ] I am Opus 4.7. (If not, halt and emit MISROUTE per `policies/dispatcher-routing-rules.md`.)
- [ ] Track A is complete (session 28 work-log shows ACCEPTANCE_GATE_PASSED).
- [ ] Plan v2 is red-lined (the plan-level commitments in master-execution-plan.md are confirmed by Ibby).
- [ ] I am on branch `session-29-strategy-foundation` (or I will create it as my first action).

If any unchecked: halt, escalate.

## What you produce in this sub-sprint

You produce **specs, decisions, and failing test stubs**. You produce NO
production code. Sonnet (29b/c) and Gemini (29d) consume your outputs.

### Output 1 — Ratify the four architectural decisions

Read [`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
sections "Decision 29-D1" through "Decision 29-D4".

For each, write a "Ratification" entry in this file (29a-opus.md) appended
at the bottom that says either:
- "Ratified as recommended" + one-paragraph reasoning, OR
- "Modified to: <new shape>" + reasoning.

### Output 2 — Stub test files (committed, all skipping)

Create these four files. Each contains test functions whose body is
`pytest.skip("Implemented in 29X-Y")` with a docstring describing what the
test asserts. **You do not implement the tests' assertions** — you describe
them. Sonnet/Gemini fill the bodies in 29b/c/d.

- `tests/contracts/test_walkforward_uses_registry.py` — assert that
  `walkforward.run_walkforward()` instantiates strategies via
  `TemplateRegistry` when the YAML config has a `template:` field, and via
  legacy dynamic-import when only `signal_module:` is present.
- `tests/contracts/test_engine_uses_size_position.py` — assert that
  `BacktestEngine` calls `Strategy.size_position(signal, context, instrument)`
  for every entry; assert that returning 0 suppresses the trade; assert
  that an exception in `size_position` propagates rather than silently
  falling back to `BacktestConfig.quantity`.
- `tests/contracts/test_ou_bounds_from_instrument.py` — assert that
  `compute_stationarity` reads `tradeable_ou_bounds_bars` from the passed
  `Instrument` rather than from a module constant; assert that 6E classifies
  as TRADEABLE with ~33-bar OU half-life under 6E's bounds (10–80 bars at
  5m); assert that ZN's existing classifications are unchanged.
- `tests/contracts/test_strategy_naming_convention.py` — assert that
  `vwap-reversion-v1` is registered with kebab-case name; assert that
  strategy instance IDs follow `<template>-<instrument>-<config-hash-short>`
  format.

Each test function: docstring describing the assertion, body
`pytest.skip("Implemented in 29X-Y where X is the next sub-sprint")`.

### Output 3 — Strategy Protocol docstring update (Mulligan freshness invariant)

Edit `src/trading_research/core/strategies.py`. In the `Strategy.exit_rules`
method docstring, add the Mulligan freshness invariant text from
[`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
"Decision 29-D4". This is a docstring change only; no code changes; no behaviour change.

### Output 4 — Handoff artifact

Create `docs/execution/handoffs/29a-handoff.md`:
- Decisions ratified (29-D1, 29-D2, 29-D3, 29-D4) with one-paragraph each.
- Stub test files committed, with absolute paths.
- Strategy Protocol docstring updated.
- Branch state (commit SHA).
- Explicit unblock list: `29b`, `29c`, `29d` are now READY.

## Acceptance checks (must all pass before handoff)

- [ ] Four ratification paragraphs appended to this file.
- [ ] Four stub test files committed under `tests/contracts/`.
- [ ] `uv run pytest tests/contracts/ -v` runs and all four tests SKIP (not fail).
- [ ] Strategy Protocol docstring contains Mulligan freshness invariant text.
- [ ] No production code changed (the only file edits are: this file, 4 new test files, 1 docstring).
- [ ] `docs/execution/handoffs/29a-handoff.md` written.
- [ ] `docs/execution/handoffs/current-state.md` updated: 29a → DONE; 29b, 29c, 29d → READY.

## What you must NOT do

- Implement any production logic (registry coupling, sizing wiring, OU
  migration). Those are 29b, 29c, 29d.
- Write the assertion bodies of the four stub tests. The describing
  docstring is your work; the body is `pytest.skip(...)`.
- Modify any source file other than `core/strategies.py` (docstring only).
- Skip the handoff artifact.

## References

- Original session 29 spec (full context): [`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
- Architect's review of coupling issues: [`outputs/planning/peer-reviews/architect-review.md`](../../../../outputs/planning/peer-reviews/architect-review.md) §1, §2, §3
- Multi-model handoff protocol: [`../../policies/multi-model-handoff-protocol.md`](../../policies/multi-model-handoff-protocol.md)

---

## Ratifications (you fill these in during execution)

### Decision 29-D1 — Walkforward / Registry coupling
Status: <PENDING>

Ratification: …

### Decision 29-D2 — OU bounds location
Status: <PENDING>

Ratification: …

### Decision 29-D3 — Naming convention
Status: <PENDING>

Ratification: …

### Decision 29-D4 — Mulligan freshness invariant
Status: <PENDING>

Ratification: …
