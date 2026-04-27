═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           D3-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  D2 (DONE)
Parallel-OK with:  31a, 31b
Hand off to:       D4-sonnet
Branch:            session-D3-idempotency
═══════════════════════════════════════════════════════════════

# D3 — Order idempotency + reconciliation scaffold

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] D2 DONE.

## What you implement

Per track-D-circuit-breakers.md §D3 + plan-v2 alignment:
- Idempotency token generator.
- Dedupe debounce.
- Broker-fill reconciler against fixtures.
- **Plan-v2 alignment:** reconciler verifies `featureset_hash` consistency on every fill cycle. Mismatch raises and D4 account-level kill switch fires.

## Acceptance
- [ ] Dedupe test: duplicate signals within debounce window → exactly one order recorded.
- [ ] Reconciler matches 100% of fixture fills.
- [ ] Featureset hash mismatch path triggers escalation.
- [ ] Handoff: `docs/execution/handoffs/D3-handoff.md`.
- [ ] current-state.md: D3 → DONE; D4 → READY.

## What you must NOT do
- Implement kill switches (D4).
- Live broker integration.
