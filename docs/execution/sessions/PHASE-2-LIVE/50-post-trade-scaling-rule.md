═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           50
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  49 (DONE)
Hand off to:       51 (after 5 successful live trading days)
Branch:            session-50-scaling-rule
═══════════════════════════════════════════════════════════════

# 50 — Post-first-trade review + scaling rule + halt rule

## Self-check
- [ ] I am Opus 4.7.
- [ ] 49 DONE; first live trade record exists.

## What you produce

### Three-persona evaluation of first live trade
- Mentor: market behaviour during the trade. Slippage realism.
- Data Scientist: live trade inside sprint 33 + session 44 CIs?
- Architect: any operational surprises? Reconciliation clean?

### Scaling rule (mentor's pre-commitment)
Write `scaling-rule.md` literally:

```
After 1 successful trade with no operational issues: continue at 1 contract for next 5 trading days.
After 5 consecutive trading days at 1 contract with no operational issues: scale to 2 contracts.
After 10 consecutive trading days at 2 contracts: scale to a number determined by re-running risk-of-ruin calc with larger sample.
Any operational issue (broker silence, circuit breaker firing, fill surprise, account state mismatch): scale RESETS to 1.
```

This rule is committed BEFORE any scaling discussion happens. It is not revisable mid-stream without a full session-50-style review.

### Halt rule (mentor's pre-commitment)
Write to `halt-rule.md`:

```
If realised Calmar's lower CI bound is below 0.0 over a 40-trade rolling window,
the strategy is paused for review.

If max consecutive losses exceeds the 95th percentile from the bootstrap distribution
(threshold: ___ from session 33), the strategy is paused for review.

If any operational issue happens twice within 10 trading days, the strategy is paused
pending architecture review.

A pause is not a stop. It is a review trigger.
```

### Recovery rituals (mentor §4.9)
Write to `recovery-rituals.md` what Ibby does on a bad week:
- Review every trade for execution mistakes.
- Look for missed exits.
- Look for over-trading.
- DO NOT change strategy.
- DO NOT increase size to "make it back."
- DO NOT add discretionary trades.

## Acceptance
- [ ] Three persona evaluation committed.
- [ ] Scaling rule committed (literal text above).
- [ ] Halt rule committed (literal text above with thresholds filled in).
- [ ] Recovery rituals committed.
- [ ] Decision: continue at 1 contract through next 5 trading days.
- [ ] Handoff: `docs/execution/handoffs/50-handoff.md`.
- [ ] current-state.md: 50 → DONE; 51 → READY (after 5 successful live days).

## What you must NOT do
- Modify the scaling rule or halt rule values without explicit Ibby override in writing.
- Recommend scaling now.
- Skip a persona.
