# Phase 2 — 30-day paper window → live small money trading

This phase covers sessions 39–55. The plan-level detail is in
[`../../plan/product-roadmap-to-live.md`](../../plan/product-roadmap-to-live.md).
This README is the per-session navigation.

## Routing matrix

| Spec ID | File | Model | Calendar slot | Effort |
|---|---|---|---|---|
| 39 | [`39-week-1-review.md`](39-week-1-review.md) | Opus 4.7 | Phase 1 +5 days | M |
| 40 | [`40-conditional-cleanup.md`](40-conditional-cleanup.md) | Sonnet 4.6 | Phase 1 +10 days, IF needed | M |
| 41 | [`41-week-2-review.md`](41-week-2-review.md) | Opus 4.7 | Phase 1 +12 days | M |
| 42 | [`42-cost-model-recalibration.md`](42-cost-model-recalibration.md) | Sonnet 4.6 | Phase 1 +15 days, IF needed | M |
| 43 | [`43-week-3-review.md`](43-week-3-review.md) | Opus 4.7 | Phase 1 +19 days | M |
| 44 | [`44-end-of-window-evaluation.md`](44-end-of-window-evaluation.md) | Opus + Sonnet | Phase 1 +30 days | L |
| 45 | [`45-live-readiness-gate.md`](45-live-readiness-gate.md) | Opus + all personas | After 44 PROCEED | L |
| 46 | [`46-risk-of-ruin.md`](46-risk-of-ruin.md) | Opus + Ibby | After 45 READY | M |
| 47 | [`47-ts-live-api.md`](47-ts-live-api.md) | Sonnet 4.6 | After 46 | L |
| 48 | [`48-killswitch-drill-real-broker.md`](48-killswitch-drill-real-broker.md) | Sonnet + Opus | After 47 | L |
| 49 | [`49-first-live-trade.md`](49-first-live-trade.md) | Opus + Ibby together | After 48 | M |
| 50 | [`50-post-trade-scaling-rule.md`](50-post-trade-scaling-rule.md) | Opus 4.7 | After 49 | M |
| 51 | [`51-second-strategy-paper.md`](51-second-strategy-paper.md) | Sonnet 4.6 | After 50 + 5 trading days | M |
| 52 | [`52-second-strategy-continued.md`](52-second-strategy-continued.md) | Sonnet 4.6 | Continuation | M |
| 53 | [`53-second-strategy-review.md`](53-second-strategy-review.md) | Opus 4.7 | After 52 | M |
| 54 | [`54-second-strategy-live.md`](54-second-strategy-live.md) | Sonnet 4.6 | After 53 + own 30-day window | L |
| 55 | [`55-multi-strategy-decision.md`](55-multi-strategy-decision.md) | Opus 4.7 | Open-ended | M |

## Phase 2 entry criterion

All of:
- Phase 1 (sessions 29–38) DONE.
- Sprint 38d readiness verdict: READY across all three personas.
- 30-day paper discipline window OPEN.

## Hard rules across Phase 2A (sessions 39–44)

1. No knob changes during the window.
2. No new strategies bolted on.
3. Cleanup must not change strategy behaviour.
4. A losing streak is not a bug — don't fix what's working as designed.

## Phase 2 sub-phases

- **2A — Paper window operations (39–44):** ~30 calendar days, ~6 sessions.
- **2B — Live readiness gate (45–46):** ~2 days intensive.
- **2C — Live execution plumbing + drill (47–48):** ~3 days.
- **2D — First live trades + scaling (49–50):** ~2 days + ongoing observation.
- **2E — Multi-strategy expansion (51–55):** open-ended.
