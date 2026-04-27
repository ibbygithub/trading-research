═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           30b-opus
Required model:    Opus 4.7
Required harness:  Claude Code
Phase:             1 (hardening)
Effort:            S (~1 hr)
Entry blocked by:  30a (DONE)
Parallel-OK with:  none (review owns the focus)
Hand off to:       31a-opus
Branch:            session-30-6e-backtest-v1
═══════════════════════════════════════════════════════════════

# 30b — Three-persona review of v1 backtest

## Self-check

- [ ] I am Opus 4.7.
- [ ] 30a is DONE; trial records exist in `runs/.trials.json`.
- [ ] HTML report at `runs/vwap-reversion-v1-6E-*/report.html` exists.

## What you produce

A single file `runs/vwap-reversion-v1-6E-*/30b-review.md` with three
persona verdict blocks and a sprint-31 entry recommendation.

### Mentor verdict block

Read 30a outputs. Address:
- Does the equity curve respect London/NY structure (entries cluster in window)?
- Cost sensitivity: at what slippage does the strategy stop paying?
- Are there cost configurations where the edge is real but the costs are unrealistic?
- War-story check: does this look like real-desk EUR/USD reversion P&L?

### Data Scientist verdict block

Address:
- Per-fold dispersion: is aggregate P&L driven by 1–2 folds?
- Per-fold stationarity: any fold flips classification?
- Bootstrap CI widths: is "Calmar 1.5" actually [0.4, 2.6]?
- DSR with `n_trials=8`: still distinguishable from luck?
- Confidence interval on max consecutive losses meaningful?

### Architect verdict block

Address:
- Did sprint 29's coupling hold under load? Engine fingerprint stable across 8 runs?
- Featureset hash recorded correctly?
- Did `size_position` produce sensible position sizes (no zeros, no overflow)?
- Any new hardcodings that crept in? (Diff vs sprint 29 baseline.)

### Sprint-31 entry recommendation (synthesis)

One of three:
- "PROCEED to regime filter" — v1 is genuinely close.
- "PROCEED to regime filter with pre-defined caution" — v1 is far; filter
  unlikely to bridge the gap; consider pivoting before sinking sprint 31 in.
- "ESCAPE — costs destroy the edge" — pivot at sprint 34.

## Acceptance checks

- [ ] Three verdict blocks committed.
- [ ] Sprint-31 recommendation explicit.
- [ ] Handoff: `docs/execution/handoffs/30b-handoff.md`.
- [ ] current-state.md updated: 30b → DONE; 31a → READY.

## What you must NOT do

- Implement code changes. This is review only.
- Author the regime filter spec (that's 31a).

## References
- Original spec: [`../../../roadmap/session-specs/session-30-6e-backtest-v1.md`](../../../roadmap/session-specs/session-30-6e-backtest-v1.md) §30b
