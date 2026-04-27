═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           31b-sonnet
Required model:    Sonnet 4.6
Required harness:  Claude Code
Phase:             1
Effort:            M (~3 hr)
Entry blocked by:  31a (DONE)
Parallel-OK with:  D3
Hand off to:       32a-opus
Branch:            session-31-regime-filter
═══════════════════════════════════════════════════════════════

# 31b — Regime filter implementation + true walk-forward

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 31a DONE; `regime-filter-spec.md` exists.
- [ ] Stub test file `tests/strategies/test_regime_filter.py` exists.

## What you implement

### 1. Composable regime module
- `src/trading_research/strategies/regime/__init__.py` — base class /
  Protocol; chainable filter API; AND-of-filters semantics.
- One concrete filter per 31a's chosen filter type.

### 2. Strategy template integration
- `vwap-reversion-v1` template gains `regime_filters: list[str]` knob.
- `generate_signals` short-circuits when any filter rejects.

### 3. True walk-forward harness
- Rolling-fit window of 18 months, test window of 6 months, slide forward.
- Embargo 576 bars.
- ~10 folds across 2018-2024.
- IF Path A (market-structure) chosen by 31a: no fitting; the same
  pre-committed threshold applies in every fold.
- IF Path B (hold-out): fit on training window of each fold, evaluate on
  test window.

### 4. Two trial records
- With filter enabled.
- Without filter (re-runs sprint 30 cost-variant 4 baseline for direct comparison).

### 5. Implement test bodies
`tests/strategies/test_regime_filter.py` — fill in stubbed assertions per 31a.

## Acceptance checks
- [ ] Walk-forward report shows rolling-fit folds, with vs without filter.
- [ ] ≥6/10 folds positive AND binomial p<0.10 vs null p=0.5.
- [ ] Bootstrap CI lower bound on aggregated Calmar > 1.0.
- [ ] Filter is reusable (no 6E-specific code in regime module).
- [ ] Both trials recorded with cohort fingerprint.
- [ ] All `test_regime_filter.py` cases pass.
- [ ] Handoff: `docs/execution/handoffs/31b-handoff.md`.
- [ ] current-state.md updated: 31b → DONE; 32a → READY.

## What you must NOT do
- Iterate the threshold within this sprint. If acceptance fails, surface
  the failure; do NOT keep tuning.
- Add new filters not specified in 31a's spec.

## References
- 31a handoff and `regime-filter-spec.md`.
- Original spec §31b.
