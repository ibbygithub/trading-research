═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           47
Required model:    Sonnet 4.6
Effort:            L (~4 hr)
Entry blocked by:  46 (DONE)
Hand off to:       48
Branch:            session-47-ts-live-api
═══════════════════════════════════════════════════════════════

# 47 — TS LIVE API integration (distinct from SIM)

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 46 DONE; first-trade size committed.
- [ ] **CRITICAL:** TS LIVE ≠ TS SIM. Different auth, different endpoints, different settlement mechanics. I will treat this as a fresh integration, not a SIM rename.

## What you implement

### Files
- `src/trading_research/execution/tradestation_live.py` — concrete Broker Protocol against TS LIVE endpoints. Auth via real credentials (Ibby provides at session start).
- `src/trading_research/execution/preflight.py` — checks before ANY live order:
  - Account state matches expected.
  - Available margin > order's required × 2× safety factor.
  - Featureset hash matches strategy's expected.
  - All circuit breakers ARMED (not tripped).
  - Time-of-day within allowed live-trading window.
  - Manual confirmation flag PRESENT in config.
  - NTP time-sync verified within 1 second.
- `tests/execution/test_tradestation_live_paper_mode.py` — runs LIVE client in paper-mode against TS to verify auth + endpoints. **No real orders.**

### Plus operational components
- Daily reconciliation against broker statements (T+1 reality handling).
- Lockfile mechanism for configuration immutability during live session.
- Failover behaviour: on restart, query broker for open positions and pending orders, reconcile against strategy state, default HALT and prompt.
- Stuck-state distinct from silent-state (broker reachable but rejecting).

### Operational runbook
- `docs/operations/runbook.md` — what to do when X breaks.
- Featureset hash mismatch → procedure.
- Account-state mismatch → halt and reconcile.
- Order rejected → catalog of common reasons.
- Laptop crash mid-position → broker state is truth; reconcile on restart.

## Acceptance
- [ ] All preflight checks implemented.
- [ ] TS LIVE auth verified in paper-mode (no orders).
- [ ] Lockfile mechanism tested.
- [ ] Failover restart test passes (HALT and prompt).
- [ ] NTP check fires when time drifts >1 sec.
- [ ] Operational runbook drafted with at least 5 scenarios.
- [ ] Handoff: `docs/execution/handoffs/47-handoff.md`.
- [ ] current-state.md: 47 → DONE; 48 → READY.

## What you must NOT do
- Place ANY real orders. Paper-mode only.
- Skip the preflight or lockfile.
- Reuse SIM code as LIVE code without explicit review.
- Mark DONE without runbook draft.

## References
- Round-2 architect §4.1, 4.5, 4.6, 4.7, 4.8, 4.9.
- Round-2 mentor §4.7 (TS account setup, 1256 treatment).
