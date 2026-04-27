═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           38d-opus
Required model:    Opus 4.7
Effort:            S (~1 hr)
Entry blocked by:  38b, 38c (DONE)
Hand off to:       Phase 2 — session 39 (week-1 paper review)
Branch:            session-38-traders-desk
═══════════════════════════════════════════════════════════════

# 38d — Three-persona readiness review (NOT a live-readiness gate)

## Self-check
- [ ] I am Opus 4.7.
- [ ] 38b, 38c DONE.
- [ ] I understand: this review confirms platform readiness for the rest of the 30-day window. It does NOT advance to live capital.

## What you produce

`runs/.../38d-readiness-review.md` with three persona verdicts.

### Mentor — READY / NOT READY for "platform carries strategy through rest of window"
- Strategy genuinely behaving as 6E recommendation predicted?
- Cost realism in live trades?
- Behavioural metrics tolerable?
- ML deferral defended: "is there ANY case for starting Track G now?" Expected answer: no, not until 30 days completes.

### Data Scientist
- Live trade metrics consistent with sprint 33 CIs?
- Featureset hash drift?
- DSR cohort bookkeeping intact across 35–38?
- Per-trade divergence within 36b's tolerance?

### Architect
- Coupling integrity holds (registry, sizing, OU bounds)?
- New hardcodings in 35–38 sprint code?
- Test coverage on touched modules adequate?
- Health-check command surfaces every active component?

### Synthesis verdict
- All three READY: Phase 1 DONE; Phase 2 (sessions 39–55) opens.
- Any NOT READY: items become Phase 2 entry-blockers; specific session listed.

## Acceptance
- [ ] Three persona verdict blocks committed.
- [ ] Final synthesis decision committed.
- [ ] ML deferral defended explicitly in work log.
- [ ] Handoff: `docs/execution/handoffs/38d-handoff.md` — Phase 1 complete.
- [ ] current-state.md: 38d → DONE; **session 39 (Phase 2) → READY pending calendar +5 days**.

## What you must NOT do
- Advance the strategy to live trading.
- Override the 30-day window requirement.
- Approve ML or pairs work to start now.

## References
- Round-2 peer reviews: [`../../peer-reviews/`](../../peer-reviews/)
- Phase 2 plan: [`../../plan/product-roadmap-to-live.md`](../../plan/product-roadmap-to-live.md)
