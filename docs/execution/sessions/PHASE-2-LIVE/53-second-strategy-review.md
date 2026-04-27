═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           53
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  52 (DONE)
Hand off to:       54 (after second-strategy 30-day paper window completes)
Branch:            session-53-second-review
═══════════════════════════════════════════════════════════════

# 53 — Second-strategy paper review (gate-equivalent)

## Self-check
- [ ] I am Opus 4.7.
- [ ] 52 DONE.
- [ ] Live 6E continues.

## What you produce

Three-persona review applying sprint 33's seven gate criteria to the second strategy:

| # | Criterion |
|---|---|
| G1 | ≥6/10 folds positive AND binomial p<0.10 |
| G2 | Bootstrap CI lower bound on Calmar ≥ 1.5 |
| G3 | DSR over full second-strategy cohort excludes zero |
| G4 | Max consecutive losses 95th percentile ≤ 8 |
| G5 | Per-fold stationarity preserved |
| G6 | Cost robustness at 2-tick slippage |
| G7 | Cohort consistency |

Verdict: PASS → open second-strategy 30-day paper window. FAIL → escape per shape.

## Acceptance
- [ ] Three persona verdicts.
- [ ] Final verdict explicit.
- [ ] If PASS: paper window for second strategy OPENS (parallel to live 6E).
- [ ] Handoff: `docs/execution/handoffs/53-handoff.md`.
- [ ] current-state.md: 53 → DONE; 54 → BLOCKED until second-strategy 30-day window completes.

## What you must NOT do
- Promote second strategy live in this sprint.
- Modify live 6E parameters.
