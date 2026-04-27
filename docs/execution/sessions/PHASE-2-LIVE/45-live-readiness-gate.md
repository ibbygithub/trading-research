═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           45
Required model:    Opus 4.7 + all three personas
Effort:            L (~3 hr)
Entry blocked by:  44 (DONE) with verdict PROCEED
Hand off to:       46
Branch:            session-45-live-readiness
═══════════════════════════════════════════════════════════════

# 45 — Live readiness gate

This is the gate that decides whether real money will move. The criteria are
pre-committed in [`../../plan/product-roadmap-to-live.md`](../../plan/product-roadmap-to-live.md).
You apply them; you do not invent them.

## Self-check
- [ ] I am Opus 4.7.
- [ ] 44 verdict is PROCEED.
- [ ] I am applying L1–L9 as written; not modifying.

## The nine criteria (ALL must pass for READY)

| # | Criterion | Persona |
|---|---|---|
| L1 | 30-day paper window completed without restart | Mentor + DS |
| L2 | Realised Calmar's bootstrap CI lower bound > 1.0 (live, not backtest) | DS |
| L3 | Live-vs-backtest divergence within sprint 36 tolerance | DS |
| L4 | Realised max consecutive losses ≤ 8 | Mentor |
| L5 | Ibby has personally watched at least one drawdown to recovery without overriding | Mentor |
| L6 | All circuit breakers fired correctly when triggered (or never triggered) | Architect |
| L7 | Featureset hash zero-drift over 30 days | Architect |
| L8 | Risk-of-ruin (session 46) explicitly computed and acceptable | DS |
| L9 | First-live-trade size determined and committed (session 46) | Mentor + DS |

L8 and L9 are session 46 outputs; they are listed here so you know the
gate's full shape, but they are not evaluated in this session.

## Procedure

For L1–L7 (this session): each persona independently issues READY / NOT READY in writing.

```
## <Persona> verdict — <READY / NOT READY>
L1: <PASS / FAIL — explanation>
L2: ...
...
Items still required before live (not this session):
- ...

Signed: <persona>
Date: <today>
```

If any persona signs NOT READY: cycle returns to 39–44 with documented remediation. A failed criterion is not a "ship anyway."
If all three sign READY: session 46 is unblocked.

## Acceptance
- [ ] Three persona verdicts committed in `45-live-readiness-gate.md`.
- [ ] All-READY OR specific NOT-READY items listed.
- [ ] Handoff: `docs/execution/handoffs/45-handoff.md`.
- [ ] current-state.md: 45 → DONE; 46 → READY (only if all-READY).

## What you must NOT do
- Soften criteria. They are pre-committed.
- Skip a persona.
- Advance to session 46 with any NOT READY criterion.
