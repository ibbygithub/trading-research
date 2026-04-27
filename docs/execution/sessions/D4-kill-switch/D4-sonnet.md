═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           D4-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  D3 (DONE)
Parallel-OK with:  32a, 32b, F2
Hand off to:       35a-sonnet (Track D complete)
Branch:            session-D4-kill-switch
═══════════════════════════════════════════════════════════════

# D4 — Strategy / instrument / account kill switches

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] D1, D2, D3 DONE.

## What you implement

Per track-D-circuit-breakers.md §D4 + plan-v2 alignment:
- Three-level kill-switch hierarchy: strategy → instrument → account.
- Integrate with D1 (LossLimitMonitor) and D2 (heartbeat).
- **Plan-v2 alignment:** drill test in acceptance must include featureset-hash mismatch scenario AND existing API-outage and loss-limit-breach scenarios.

## Acceptance
- [ ] Drill test (simulated API outage) flattens at account level.
- [ ] Single-strategy loss-limit breach halts only that strategy.
- [ ] Featureset hash mismatch triggers account-level kill.
- [ ] All Track D acceptance tests green.
- [ ] Handoff: `docs/execution/handoffs/D4-handoff.md` — Track D COMPLETE.
- [ ] current-state.md: D4 → DONE; sprint 35 entry-blockers all met.

## What you must NOT do
- Drill against real broker (that's session 48).
- Live order plumbing.
