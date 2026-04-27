# Session 37 — Hardening pass + monitoring polish

**Status:** Spec — explicit cleanup sprint per architect's "every session spawns 2–3 cleanup tasks"
**Effort:** 1 day, three sub-sprints (S+M+S)
**Depends on:** Sprint 36 (paper window open)
**Unblocks:** Sprint 38 (trader's-desk polish)
**Personas required:** Architect (punch-list owner)
**Hard rule:** strategy keeps running on paper; no behaviour change.

## Goal

Close the cleanup debt accumulated through sprints 29–36 against the
real evidence of paper-trading day 1. This is the only sprint reserved for
non-feature work. Skipping it is technically possible; the cost of skipping is
that sprint 38 absorbs cleanup AND polish, which means polish is shallow.

## In scope

### 37a — Punch-list authoring (Opus 4.7, ~1 hr)

**Inputs:**
- All work logs from sprints 29–36.
- Sprint 36b paper-day-1 review.
- `outputs/planning/peer-reviews/architect-review.md`.

**Outputs:**
- `outputs/work-log/2026-XX-XX-37a-punch-list.md`:
  - Each item ranked by **blast radius** (how many modules affected by leaving
    it broken):
    - **Critical:** breaks paper trading or hides risk → must fix this sprint.
    - **High:** breaks future sprints (29–38 scope) → fix this sprint.
    - **Medium:** breaks future sprints (>38) or accumulates debt → backlog
      with explicit rationale.
    - **Low:** cosmetic / nice-to-have → may be deferred or absorbed by 37c.

**Common items expected on the list:**
- Inconsistent timestamp tz handling at any seam (logs vs. trade-log vs. broker).
- Missing structured-log fields (run_id, strategy_id, signal_id correlation).
- Manifest fields added without migration of older artifacts.
- Cost-model drift if 36b found realised slippage outside backtest tolerance.
- Heartbeat false-positive frequency too high (D2 needs tuning).
- ZN strategies still using legacy `signal_module` path (sprint 29's
  decommissioning queue).
- Test coverage gaps on touched modules.

### 37b — Critical and high punch-list items (Sonnet 4.6, ~3 hr)

Knock out top of the list. Each item gets a small commit referencing the
punch-list line. Hard rule: **no strategy behaviour changes**. The strategy
is in its 30-day discipline window. Cleanup touches infrastructure only.

If a punch-list item turns out to require a strategy change, escalate — it
becomes a structural bug, not a cleanup item, and either the window restarts
or the item moves to backlog.

### 37c — Mechanical fan-out (Gemini 3.1, ~2 hr)

This sub-sprint follows `outputs/planning/gemini-validation-playbook.md`.

**Inputs:** punch-list "Low" items + any docstring/test-coverage fan-out
spec'd by 37b.

**Outputs:**
- Docstring fills on touched modules.
- Test coverage on functions newly touched in 37b (Sonnet pre-writes the
  test fixtures; Gemini fills implementations and assertions).
- README updates if any.
- Copy edits in error messages.

**What Gemini must NOT do here:**
- Modify production strategy/risk/execution logic.
- Author its own tests against canonical references without spec-author
  pre-writing the parity fixture.

## Acceptance

- [ ] Punch-list committed (37a).
- [ ] All Critical and High items closed or moved with explicit rationale (37b).
- [ ] Full test suite green.
- [ ] One-page health-check CLI command (`uv run trading-research health`)
      runs and prints status of every active component:
      - Paper-trading loop running (yes/no, last heartbeat).
      - Open positions count + total exposure.
      - Day's P&L vs daily limit.
      - Featureset hash matches expected.
      - Engine fingerprint stamp from session start.
- [ ] No strategy behaviour change confirmed in commit log.

## Out of scope

- Strategy tuning (would restart the 30-day window).
- New features.
- Adding strategies.
- ML.

## References

- `outputs/planning/peer-reviews/architect-review.md`
- `runs/paper-trading/<strategy-id>/day-1/` (sprint 36 outputs)
