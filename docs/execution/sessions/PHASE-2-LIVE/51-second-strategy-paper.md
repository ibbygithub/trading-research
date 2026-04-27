═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           51
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  50 (DONE) + 5 successful live trading days at 1 contract on 6E
Hand off to:       52
Branch:            session-51-second-strategy-paper
═══════════════════════════════════════════════════════════════

# 51 — Second strategy on 6A or 6C in paper

The 6E strategy continues live throughout. **No interference with live 6E.**

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 50 DONE; 5 successful live trading days at 1 contract on 6E.
- [ ] 6E strategy continues running live.

## What you implement

### Choice
Pick 6A or 6C based on session 33 escape verdict (if 33 forced a pivot, 6A/C work may have already begun) or based on session 44 follow-up. Document choice with reasoning.

### Pipeline
- Add chosen instrument to `configs/instruments.yaml` (already free per Track A).
- Run sprint 28-equivalent stationarity analysis.
- IF stationary: register `vwap-reversion-v1-6A` (or 6C) template tuned for new instrument.
- Run sprint 30-equivalent backtest with cost sensitivity.

## Critical constraint
- Live 6E strategy continues unchanged.
- New code is on a separate branch and does NOT modify shared `engine.py` behaviour for live 6E.

## Acceptance
- [ ] Stationarity report for new instrument.
- [ ] If stationary: backtest run with cost sensitivity.
- [ ] If not stationary: documented finding; 52 reroutes.
- [ ] Live 6E unaffected (verify by checking 6E live logs continued without errors).
- [ ] Handoff: `docs/execution/handoffs/51-handoff.md`.
- [ ] current-state.md: 51 → DONE; 52 → READY.

## What you must NOT do
- Touch live 6E execution code.
- Halt live 6E.
- Promote second strategy to live in this sprint.
