# Next Actions
**Last updated:** Session 19 (2026-04-19)

The blackout filter is done. The first backtest ran and the v1 strategy failed definitively.
The walk-forward confirmed the failure across all 10 folds, 2010–2024.

**Before any code work in the next session, a strategy redesign conversation is required.**

---

## Immediate: Strategy Redesign Conversation

The quant-mentor and data-scientist have both weighed in on the v1 failure (see Session 19 work log). The core issues:

1. **No RTH filter** — 75.5% of entries are overnight (globex session). The signal code doesn't know what time it is. Every bar in the 5m parquet can fire a signal, including 11pm to 8am ET when ZN is thinly traded and spread-driven. Fix: zero out all signals outside 13:20–20:00 UTC (8:20am–3pm ET ZN RTH).

2. **MACD zero-cross exit is not a price exit** — The histogram can cross zero while price is below entry. The strategy needs either (a) a price target (VWAP reversion, prior swing, fixed ticks), or (b) a different entry trigger that already has confirmed momentum.

3. **The "enter before confirmation" hypothesis failed** — Entering when the histogram is fading toward zero means entering when momentum is uncertain. The evidence: the entry is correct direction 11% of the time. A coin flip would be 50%. The market is actively moving against these entries.

**Questions to resolve before next code session:**
- Should v1 be patched (add RTH filter + price exit) or replaced with a different hypothesis?
- The quant-mentor's suggestion: flip the entry — trigger on confirmed zero-cross (momentum has turned) rather than fading pullback (momentum is uncertain). Exit at session VWAP or ATR multiple.
- Does the 60m + daily bias alignment still make sense as a filter?

---

## Step 1A (if patching v1): Add RTH Filter

Add an RTH session filter to `generate_signals()` in `zn_macd_pullback.py`:
- Zero out all signals (both entries and exits) outside 13:20–20:00 UTC
- This eliminates 75.5% of the trade noise
- Then re-run backtest to isolate whether RTH-only performance can be improved

The RTH filter is necessary regardless of the hypothesis.

## Step 1B (if redesigning): New Strategy Hypothesis

Candidate revision: enter on MACD zero-cross (histogram turns positive from below, or negative from above) rather than on fading pullback.

- Entry: histogram crosses zero with daily + 60m alignment
- Stop: 2x ATR from signal bar
- Target: fixed tick (e.g., session VWAP) — not another MACD event
- RTH only: 13:20–20:00 UTC

This gives the strategy a directional confirmation (histogram is already above zero) rather than a prediction (it's approaching zero and might cross).

---

## Backlog (Unchanged from Session 18)

In priority order:

1. **6A pipeline generalization** (OI-010, OI-011, OI-012) — ~4 hours.
   Fix hardcoded ZN paths in `continuous.py` and RTH window in `validate.py`.
   Then run 6A historical download. Blocked on ZN validation being meaningful first.

2. **OI-013: SHAP JIT crash on Windows** — pin compatible numba + llvmlite.

3. **OI-009: unadjusted ZN roll consumption audit** — verify all load paths consume back-adjusted parquets.

---

## Low-Priority Cleanup

- OI-003: `git rm --cached .claude/settings.local.json` then commit
- OI-004: `rm -rf "C:Trading-researchconfigsstrategies/"` and other mangled dir
- OI-005: Move `prep_migration_samples.py` to `Legacy/` or delete
- OI-002: Retire `outputs/planning/planning-state.md` (stale since sessions 06–07)
- Blackout filter minor edge case: 6 overnight trades leaked on event-day mornings (signal bar on eve, entry on event day AM). Fix: check entry bar date (T+1) instead of signal bar date (T) in the blackout mask. Low priority given strategy redesign is pending.
