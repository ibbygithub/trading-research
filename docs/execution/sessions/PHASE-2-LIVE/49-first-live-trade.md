═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           49
Required model:    Opus 4.7 + Ibby (joint, real-time)
Effort:            M (~2-3 hr observation)
Entry blocked by:  48 (DONE) with all 7 drills PASS
Hand off to:       50
Branch:            session-49-first-live-trade
═══════════════════════════════════════════════════════════════

# 49 — FIRST LIVE MICRO-CONTRACT TRADE

This is the first session where real money moves. Ibby is present in real
time. Opus monitors and synthesizes; Ibby decides.

## Self-check
- [ ] I am Opus 4.7.
- [ ] Ibby is present and in this session in real time.
- [ ] 48 all-PASS verdict.

## Pre-flight checklist

Read this aloud with Ibby. **Each box is checked manually by Ibby.** No
shortcuts.

```
[ ] Account equity confirmed: $______________
[ ] First-trade size committed at session 46: 1 micro M6E
[ ] Risk-of-ruin at this size: ______________% (acceptable per session 46)
[ ] All circuit breakers ARMED
[ ] Heartbeat green
[ ] Featureset hash matches
[ ] Strategy unchanged from sprint 33-validated state
[ ] 30-day paper window completed: yes / no — if no, HALT
[ ] Ibby has reviewed the most recent paper trade: yes / no — if no, do that first
[ ] London/NY overlap is open or about to open: ___ UTC
[ ] No major economic release in next 60 minutes
[ ] Manual confirmation flag set in execution config
[ ] Ibby's emotional readiness self-report: ready / nervous / not today
```

If any checkbox fails: HALT. Do not place trade. Reschedule.

## During the trade

If all pass: arm system; wait for first signal; observe one trade end-to-end. Whether it wins or loses is irrelevant — the success criterion is *the trade happened correctly*.

## Output

`runs/live/<strategy>/first-trade-record.md`:
- Pre-flight checklist signed (literal).
- Signal timestamp, signal strength, expected entry per backtest model.
- Submitted order ID, fill timestamp, fill price.
- Slippage observed.
- Exit timestamp, exit price.
- Realised P&L (dollars + ticks).
- Comparison to paper-trading shadow.

## After-action

Opus three-persona pass: did anything surprise us? Any near-miss with circuit breakers? Any clock drift?

**STOP TRADING FOR THE DAY.** Do not place a second live trade until session 50 evaluates the first.

## Acceptance
- [ ] Pre-flight checklist signed and committed.
- [ ] One trade observed end-to-end.
- [ ] First-trade record committed.
- [ ] After-action persona pass committed.
- [ ] Trading halted for the day.
- [ ] Handoff: `docs/execution/handoffs/49-handoff.md`.
- [ ] current-state.md: 49 → DONE; 50 → READY.

## What you must NOT do
- Place a second trade.
- Override a failed pre-flight checkbox.
- Allow size > 1 micro M6E.
- Skip the after-action.
