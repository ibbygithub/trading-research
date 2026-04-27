═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           48
Required model:    Sonnet 4.6 + Opus 4.7 mid-session
Effort:            L (~3 hr)
Entry blocked by:  47 (DONE)
Hand off to:       49
Branch:            session-48-killswitch-drill
═══════════════════════════════════════════════════════════════

# 48 — Kill-switch DRILL against real broker

## Self-check
- [ ] I am Sonnet 4.6 (or Opus 4.7 for mid-session review).
- [ ] 47 DONE; TS LIVE plumbing exists.
- [ ] Real (paper-mode-flagged) TS LIVE account session is available.

## Sub-split

| Sub | Model | Workload |
|---|---|---|
| 48a | Sonnet 4.6 | Run drills against real broker; observe behaviour |
| 48b | Opus 4.7 | Mid-session review: real-broker behaviour vs SIM fixtures, surprises |
| 48c | Sonnet 4.6 | Address any gaps from 48b |

## Drills (real broker, paper-mode)

For each, fire the trigger condition and verify the response. **Verify the
flatten order WOULD be the right shape; do NOT actually submit.**

1. **Heartbeat:** simulate API silence; auto-flatten attempts; flatten order shape correct.
2. **Loss limit:** simulate trade fills that breach daily limit; halt fires.
3. **Idempotency:** submit same order ID twice; second rejected.
4. **Account-level kill switch:** disarms entire system on command.
5. **Featureset hash mismatch:** triggers account-level kill.
6. **NTP drift:** clock drift > 1 sec halts on session start.
7. **Lockfile:** YAML edit during live session triggers halt.

## Output
`kill-switch-drill-report.md` per drill: pass/fail, observed real-broker
behaviour, any divergence from SIM fixtures.

## Acceptance
- [ ] All 7 drills pass.
- [ ] Mid-session review (48b) committed.
- [ ] Any gaps from 48b addressed (48c).
- [ ] No real orders submitted.
- [ ] Handoff: `docs/execution/handoffs/48-handoff.md`.
- [ ] current-state.md: 48 → DONE; 49 → READY.

## What you must NOT do
- Submit real orders.
- Skip a drill.
- Mark a drill PASS that did not actually trigger.
