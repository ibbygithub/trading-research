═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           42
Required model:    Sonnet 4.6
Effort:            M (~3 hr) — CONDITIONAL: only if 41 surfaced cost drift
Entry blocked by:  41 (DONE) with verdict "cost-model recalibration needed"
Hand off to:       43
Branch:            session-42-cost-recalibration
═══════════════════════════════════════════════════════════════

# 42 — Mid-window cost-model recalibration IF needed

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 41 verdict is "cost-model recalibration needed."
- [ ] Strategy is RUNNING. I will NOT halt it.

## Critical scope rule

The strategy continues with original parameters. **You update the cost model
in the EVALUATION tooling — NOT in the running strategy.** This is
retrospective analysis, not a strategy change.

## What you do
- Compute realised slippage distribution from ~10+ paper trades.
- Update cost-model fixture in `eval/cost_model.py` (or equivalent).
- Re-run sprint 33 gate criterion G6 against the updated cost model.
- Output: either "strategy still passes G6 under updated costs" OR a finding for sprint 44 evaluation.

## Acceptance
- [ ] Cost-model fixture updated.
- [ ] G6 retrospective re-evaluation report.
- [ ] Strategy parameters UNCHANGED.
- [ ] Strategy still RUNNING.
- [ ] Handoff: `docs/execution/handoffs/42-handoff.md`.

## What you must NOT do
- Change running strategy parameters.
- Halt the strategy.
