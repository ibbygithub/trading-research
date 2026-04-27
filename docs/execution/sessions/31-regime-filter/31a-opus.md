═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           31a-opus
Required model:    Opus 4.7
Required harness:  Claude Code
Phase:             1
Effort:            M (~2 hr)
Entry blocked by:  30b (DONE)
Parallel-OK with:  D3
Hand off to:       31b-sonnet
Branch:            session-31-regime-filter
═══════════════════════════════════════════════════════════════

# 31a — Regime filter design (pre-commitment)

## Self-check
- [ ] I am Opus 4.7.
- [ ] 30b DONE; v1 trial records and persona review available.
- [ ] I have read 30b's sprint-31 entry recommendation.

## What you produce

A spec document `regime-filter-spec.md` (committed in this branch) covering:

### Pre-commitment path (DS rule §1)

Pick ONE of:

**Path A — Market-structure justification.** The threshold is justified
qualitatively from market knowledge. Examples:
- Time-of-day gate: no entries 12:00–13:00 UTC (ECB fixing).
- Calendar gate: no entries within ±30 min of US CPI/NFP/ECB rate decision.
- Volatility-regime gate: no entries when realised σ over last N bars
  exceeds 90th percentile of trailing 90-day distribution.

**Path B — Hold-out calibration.** The threshold is fitted on data the v2
evaluation does NOT touch:
- Pre-2018 data (outside the 2018-2024 backtest window).
- OR sprint 30 folds 1–2, evaluate on folds 3–10 in sprint 33.

### Spec contents

- Filter type (time-gate / calendar-gate / vol-regime / composite).
- Path A justification OR Path B calibration window.
- Filter API: `def is_tradeable_regime(bars, features, instrument, ts) -> bool`.
- Knob ranges (for sensitivity in walk-forward, NOT for fitting).
- Stub test files spec'd:
  - `tests/strategies/test_regime_filter.py` with described cases.

## Acceptance
- [ ] `regime-filter-spec.md` committed with path explicit.
- [ ] Stub test file from spec committed (Sonnet implements bodies in 31b).
- [ ] Handoff: `docs/execution/handoffs/31a-handoff.md`.
- [ ] current-state.md updated: 31a → DONE; 31b → READY.

## What you must NOT do
- Implement filter code. 31b's job.
- Pick a threshold value by data-mining sprint 30 fold-by-fold results — that's leakage.

## References
- DS leakage rule: [`outputs/planning/peer-reviews/data-scientist-review.md`](../../../../outputs/planning/peer-reviews/data-scientist-review.md) §1.
- Original spec: [`../../../roadmap/session-specs/session-31-regime-filter.md`](../../../roadmap/session-specs/session-31-regime-filter.md).
