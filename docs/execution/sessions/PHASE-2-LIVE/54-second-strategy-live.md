═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           54
Required model:    Sonnet 4.6 + Opus 4.7 + Ibby
Effort:            L (~3-4 hr across multiple touches)
Entry blocked by:  53 (DONE PASS) + second-strategy 30-day paper window completed
Hand off to:       55
Branch:            session-54-second-live
═══════════════════════════════════════════════════════════════

# 54 — Second-strategy live promotion

Mirrors session-49-flow for the second strategy. The 6E strategy continues at its current scaled size; second strategy enters at 1 micro of its instrument.

## Self-check
- [ ] Second-strategy 30-day paper window COMPLETED.
- [ ] Live 6E continues without changes.

## What you do

### Sub-flow (mirrors sessions 45-49 for the second strategy)
- Live readiness gate (45-equivalent): 9-criterion gate against second-strategy's paper data.
- Risk-of-ruin (46-equivalent): combined risk across 6E live + second strategy live.
- Live plumbing (47-equivalent): if second strategy needs new broker code, plumb it. Otherwise reuse.
- Drill (48-equivalent): drills include multi-strategy interference.
- First trade (49-equivalent): pre-flight checklist; one micro contract.
- Post-trade (50-equivalent): scaling rule + halt rule for second strategy specifically.

### Multi-strategy considerations (architect)
- Engine state for two strategies must NOT conflict.
- Combined account margin headroom: 2× safety factor against combined required margin.
- Combined daily loss limit: applies to BOTH strategies summed.
- Kill-switch hierarchy: single strategy halt does not affect other.

## Acceptance
- [ ] Live readiness gate equivalent passed for second strategy.
- [ ] Risk-of-ruin computed for combined exposure.
- [ ] First live trade on second strategy executed.
- [ ] Live 6E unaffected (confirmed by logs).
- [ ] Scaling and halt rules committed for second strategy.
- [ ] Handoff: `docs/execution/handoffs/54-handoff.md`.
- [ ] current-state.md: 54 → DONE; 55 → READY.

## What you must NOT do
- Promote second strategy without 30-day paper window completing.
- Modify live 6E parameters.
- Skip the readiness gate equivalent.
- Place second-strategy first trade larger than 1 micro contract of its instrument.
