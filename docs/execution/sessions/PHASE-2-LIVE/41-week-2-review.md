═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           41
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  39 (DONE) and (40 DONE OR 40 skipped)
Hand off to:       42 (conditional) OR 43
Branch:            session-41-week2-review
═══════════════════════════════════════════════════════════════

# 41 — Week-2 paper review (calendar +12)

## Self-check
- [ ] I am Opus 4.7.
- [ ] Two weeks of paper data exist.

## Three-persona pass (two-week dataset)

Same shape as session 39, plus:

**Data Scientist new emphasis:**
- DSR computed on observed paper trades (new cohort of N trades vs backtest cohort). Is the live cohort's DSR within sprint 33's bootstrap CI?

**Mentor explicit question:**
- Has Ibby personally watched a drawdown without overriding? **This is L5 of the live-readiness gate.** If observed and survived: note it. If overridden: that's a finding.

## Output
`runs/.../week-2-review.md`. Verdict drives session 42:
- "Continue clean" → skip 42, next is 43 at +19 days.
- "Cost-model recalibration needed" → 42 fires.
- "Structural problem" → escalate.

## Acceptance
- [ ] Three persona observations.
- [ ] Drawdown-survival observation explicit (yes / no / not yet observed).
- [ ] Verdict explicit.
- [ ] Strategy still RUNNING.
- [ ] Handoff: `docs/execution/handoffs/41-handoff.md`.
