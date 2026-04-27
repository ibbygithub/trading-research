# Session 36 — First paper trade + 30-day discipline window opens

**Status:** Spec — reframed per mentor §6
**Effort:** 1 day, two sub-sprints (M+M)
**Depends on:** Sprint 35 (paper-trading loop ready)
**Unblocks:** Sprint 37 (hardening pass)
**Personas required:** Mentor (market-structure pass), Data Scientist (divergence interpretation)

## Important framing

This sprint is **not** "first paper trade and we move on to live." It is the
**start of a 30-day paper-trading discipline window** during which the
strategy runs continuously, drawdowns happen in real time, and Ibby
psychologically watches what the strategy does. CLAUDE.md and the roadmap
both require ≥30 trading days of paper before any live capital. Sprint 38
does not advance to live; it confirms the platform can carry the rest of
that window.

## Goal

Fire the paper-trading loop on real-time SIM (or TV) data. Capture the first
closed trade and produce a live-vs-backtest comparison report. Begin the
30-day window with telemetry that lets sprint 37 cleanup target real,
observed issues rather than imagined ones.

## In scope

### 36a — First-trade scaffolding + reconciliation (Sonnet 4.6, ~3 hr)

**Outputs:**
- `src/trading_research/execution/daily_reconcile.py`:
  - End-of-day routine: load live trade log, load shadow-backtest log,
    pair trades by `signal_id`, compute per-trade divergence (entry-price
    diff, exit-price diff, P&L diff).
- `runs/paper-trading/<strategy-id>/day-NN/` directory layout:
  - `live-trades.jsonl`
  - `shadow-backtest-trades.jsonl`
  - `divergence-report.html`
  - `equity-curve-day-NN.parquet`
- `src/trading_research/execution/comparison_report.py` — generates the
  HTML divergence report.

**Acceptance for the first day:**
- At least one closed paper trade with both live and shadow records.
- Divergence report generates without error.
- Daily P&L reconciles between trade-log sum and broker account-state delta.

### 36b — Divergence interpretation + 30-day window opens (Opus 4.7, ~2 hr)

**Three-persona pass:**

**Mentor:**
- Does the actual market behaviour during the trade match the backtest's
  assumed structure? (London/NY overlap activity? Realised volatility?)
- Is the trigger-vs-entry separation behaving as designed (the OU inertia
  pattern from session 28)?
- Any war-story signals — does the equity curve "feel right" for 6E
  reversion?

**Data Scientist:**
- Per-trade divergence: entry-price slippage vs sprint 30 cost model.
- If realised slippage is consistently outside sprint 30's pessimistic
  bound, the cost model needs updating.
- Trade count per week within the bootstrap CI from sprint 30?
- Featureset hash on every load was the expected one (no silent drift)?

**Architect:**
- Did the heartbeat fire? Falsely or correctly?
- Any reconciliation mismatches?
- Loss-limit headroom — how close did we come to a circuit breaker?

**Deliverable:** `36b-paper-day-1-review.md` with:
- All three persona observations.
- Initial divergence verdict: "within tolerance" / "needs cost-model update" /
  "structural problem — pause and investigate."
- **Opens the 30-day discipline window:** acceptance is that the strategy
  is now running continuously; sprints 37–38 do not stop it.

## Acceptance

- [ ] At least one closed paper trade with full record (live + shadow).
- [ ] Divergence report generated and reviewed.
- [ ] All three persona observations recorded.
- [ ] Per-trade divergence inside sprint 30 cost-model tolerance, OR a
      cost-model update is queued for sprint 37.
- [ ] 30-day discipline window declared open in work log with start date.
- [ ] Strategy continues running into sprint 37 — do not halt for cleanup.

## Out of scope

- Going live (Track I).
- Multi-strategy.
- Strategy parameter changes mid-paper (would invalidate the 30-day window).

## Hard rules during the 30-day window

These apply across sprints 36–38 and beyond:

1. **No knob changes** during the window unless a circuit breaker fires or a
   structural bug is discovered. Any change re-starts the 30-day clock.
2. **No new strategies bolted on.** The window is for *this* strategy's
   discipline.
3. **Sprint 37 hardening MUST NOT change strategy behaviour.** Cleanup is
   for telemetry, logs, reports, code clarity — not for tuning.
4. **Sprint 38 readiness review explicitly does not advance to live.** Live
   capital requires ≥30 trading days of paper *plus* the readiness sign-off.

These rules are why the mentor's reframing matters. Skipping the window
because the first day looked good is the failure mode that kills traders.

## References

- CLAUDE.md "Execution" standing rules
- `outputs/planning/peer-reviews/quant-mentor-review.md` §6
- `docs/roadmap/sessions-23-50.md` Track E
