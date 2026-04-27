═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           D2-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  D1 (DONE)
Parallel-OK with:  30a, 30b
Hand off to:       D3-sonnet
Branch:            session-D2-heartbeat
═══════════════════════════════════════════════════════════════

# D2 — Inactivity heartbeat + auto-flatten

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] D1 DONE.

## What you implement

Per track-D-circuit-breakers.md §D2:
- Heartbeat monitor against TradeStation API stub.
- On silence > N seconds, flip account-level switch.
- Tests with fake API stub.

## Acceptance
- [ ] Unit test simulates 30-second API silence; flatten path fires.
- [ ] Tests pass.
- [ ] Handoff: `docs/execution/handoffs/D2-handoff.md`.
- [ ] current-state.md: D2 → DONE; D3 → READY.

## What you must NOT do
- Implement idempotency (D3) or kill switches (D4).
