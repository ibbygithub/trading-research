# Execution Hub
Last updated: 2026-04-26

This directory is the **single source of truth** for sprint execution.
If a planning artifact is not in this tree, it is either historical or
out-of-scope. Older planning files under `outputs/planning/` are kept on
disk as historical record but no longer authoritative.

## Who reads this and why

**You (Ibby)** — read [`plan/master-execution-plan.md`](plan/master-execution-plan.md) for the full plan, [`peer-reviews/round-2-synthesis.md`](peer-reviews/round-2-synthesis.md) for what you'll have at end of session 38 and what's still missing for live trading.

**A dispatching agent** — read [`policies/dispatcher-routing-rules.md`](policies/dispatcher-routing-rules.md) first. Then read the next-eligible sub-sprint per [`plan/dependency-dag.md`](plan/dependency-dag.md). Route the model-specific spec file to the matching model. **Never** route a multi-section session spec at the model directly — always route the per-model file.

**A model receiving work** — the file you receive starts with a routing header that names the required model. If you are not that model, halt and emit a `MISROUTE` report per [`policies/dispatcher-routing-rules.md`](policies/dispatcher-routing-rules.md). Do not extrapolate.

## Tree layout

```
docs/execution/
├── README.md                     ← this file
├── plan/
│   ├── master-execution-plan.md  ← the plan (replaces all prior v1/v2 plans)
│   ├── dependency-dag.md         ← what blocks what; what runs in parallel
│   ├── product-roadmap-to-live.md← sessions 39-55: paper → live small money
│   └── risk-register.md          ← live risk register
├── policies/
│   ├── dispatcher-routing-rules.md   ← harness-readable routing contract
│   ├── multi-model-handoff-protocol.md
│   └── gemini-validation-playbook.md
├── peer-reviews/
│   ├── round-1-summary.md        ← pointer back to outputs/planning/peer-reviews/
│   ├── round-2-data-scientist.md ← answers product questions Q1-Q4
│   ├── round-2-architect.md
│   ├── round-2-mentor.md
│   └── round-2-synthesis.md
├── sessions/
│   ├── 29-strategy-foundation/   ← README + 29a-opus + 29b/c-sonnet + 29d-gemini
│   ├── 30-6e-backtest-v1/        ← README + 30a-sonnet + 30b-opus
│   ├── 31-regime-filter/         ← README + 31a-opus + 31b-sonnet
│   ├── 32-mulligan/
│   ├── 33-track-c-gate/
│   ├── 34-bridge-pick/
│   ├── 35-paper-loop/
│   ├── 36-first-paper-trade/
│   ├── 37-hardening/
│   ├── 38-traders-desk/
│   ├── B1-timeframe-catalog/     ← Gemini
│   ├── D1-loss-limits/ D2 D3 D4  ← Sonnet, parallel-eligible
│   ├── F1-html-enhancements/ F2 F3   ← Gemini
│   └── PHASE-2-LIVE/             ← sessions 39-55: paper window → live
└── handoffs/
    └── current-state.md          ← live state, updated every sub-sprint
```

## How a session executes (mechanical)

1. Dispatcher reads [`plan/dependency-dag.md`](plan/dependency-dag.md) and [`handoffs/current-state.md`](handoffs/current-state.md).
2. Dispatcher identifies the next-eligible sub-sprint (entry criteria all DONE).
3. Dispatcher reads the sub-sprint's per-model spec file (e.g., `sessions/29-strategy-foundation/29a-opus.md`).
4. Dispatcher confirms the routing header's required model, then routes to that model.
5. Model executes the checklist in the spec.
6. Model updates [`handoffs/current-state.md`](handoffs/current-state.md) at completion.
7. Dispatcher repeats from step 2.

This is the loop. The point of the structure is that step 4 is unambiguous —
the file name and the routing header agree, and a wrong model receiving the
file halts.

## What's no longer authoritative

The following files remain on disk but are **superseded**:
- `outputs/planning/sprints-29-38-plan.md` (v1)
- `outputs/planning/sprints-29-38-plan-v2.md` (v2 — content lifted into [`plan/master-execution-plan.md`](plan/master-execution-plan.md))
- `outputs/planning/sprints-29-38-risks*.md`
- `docs/roadmap/session-specs/session-{29..38,B1,F1,F2,F3}*.md` — content split per-model into `sessions/<id>/<sub>-<model>.md`. The originals stand as readable reference; the per-model files are the dispatch unit.

The active references for execution are everything under `docs/execution/`.
