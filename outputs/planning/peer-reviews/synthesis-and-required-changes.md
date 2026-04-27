# Peer-Review Synthesis — Sprints 29–38 Plan
Date: 2026-04-26
Reviews: data-scientist-review.md, architect-review.md, quant-mentor-review.md

This is the consolidated change-list from all three persona reviews. v2 of the
plan and v2 of the risk register incorporate every item below. Items are tagged
with the persona that surfaced them; some are surfaced by more than one (those
are the load-bearing ones — fix them first).

## Structural changes (all three personas agree)

| # | Change | Surfaced by | Sprint |
|---|---|---|---|
| S1 | Walk-forward terminology fixed; true walk-forward required when any parameter is fitted on prior fold results | DS, A | 30, 31, 33 |
| S2 | Strategy.size_position wired into engine; `BacktestConfig.quantity` becomes fallback only | A | 29 (new 29c) |
| S3 | Walkforward consumes TemplateRegistry (Option A staged) — single strategy system | A | 29 (29a decision, 29b impl) |
| S4 | OU bounds migrate to instrument registry — single source of truth | DS, A | 29d |
| S5 | Cost model + slippage sensitivity in sprint 30 | M | 30a |
| S6 | Bootstrap CI required on every numeric acceptance threshold | DS | 30, 31, 33 |
| S7 | Trial recording mandatory for every variant (failed or not) | DS | 30, 31, 32 |
| S8 | Engine fingerprint logged on every trial; cohort consistency check at 33b | A | 30–33 |
| S9 | Per-fold stationarity check baked into backtest reports | DS | 30, 33 |
| S10 | Featureset hash check on live-trading data path | A | 35 |
| S11 | Mulligan freshness invariant promoted to Protocol-level rule | DS | 32 (Protocol doc), all future strategies |
| S12 | Naming convention for templates and strategy instances | A | 29a |
| S13 | Sprint 38 audits gui/ + replay/ before building new HTML | A | 38a |
| S14 | Sprint 36 reframed as "first paper trade + 30-day discipline window opens" — does not advance to live | M | 36, 38 |
| S15 | Cohort DSR includes all variants tested in sprints 30–32 | DS | 33b |

## Substance corrections (mentor)

| # | Change | Sprint |
|---|---|---|
| M1 | `entry_threshold_atr` default 2.2 (not 1.5); range 1.8–3.0 | 29b knobs |
| M2 | `entry_blackout_minutes_after_session_open: 60` knob added | 29b knobs |
| M3 | Flatten time derived from instrument settlement, not hardcoded 21:00 UTC | 29b, 35 |
| M4 | Mulligan directional-price-relationship gate (long re-entry only at higher price) | 32a |
| M5 | Sprint 33 escape paths pre-committed by trigger condition | 33b body |
| M6 | Max consecutive losses gate tightened from 20 to 8 | 33b |

## Test-fidelity corrections (data scientist + architect)

| # | Change | Where |
|---|---|---|
| T1 | Canonical-method parity test pattern codified as repo-level playbook | new file |
| T2 | Spec author writes the test fixture; Gemini fills implementation only | playbook |
| T3 | Golden artifacts (small JSON/parquet fixtures) for every public statistical method | 29d, B1 |
| T4 | Contract test files added at every coupling boundary | 29, 35 |
| T5 | Multi-model handoff protocol formalised, including the spec→test→impl ordering | new file |

## Effort and timeline impact

The reviews substantively expand sprint 29:
- 29a: M (architectural decisions added)
- 29b: M (registry coupling + 6E template)
- 29c: M (size_position wiring) — **new**
- 29d: M (OU bounds migration) — **upgraded from S**

That is M+M+M+M = effectively two working days, not one. The daily-throughput table
in plan v2 reflects this: sprint 29 spans days 1–2, everything after shifts by one
calendar day. We still finish sprint 38 on day 11, not day 10. That is the cost of
honesty about the actual code state. It is cheaper than discovering these gaps in
sprint 35.

## What v2 of the plan will look like

`outputs/planning/sprints-29-38-plan-v2.md` (new) — replaces v1.
`outputs/planning/sprints-29-38-risks-v2.md` (new) — replaces v1.

New supporting documents:
- `outputs/planning/multi-model-handoff-protocol.md` — the spec→test→impl ordering rule, plus how Sonnet and Gemini receive specs.
- `outputs/planning/gemini-validation-playbook.md` — canonical-method parity patterns with worked examples (BH, ADF, OU, OHLCV resampling).
- `docs/roadmap/session-specs/session-29-strategy-foundation.md` — full sub-sprint specs for 29a–d.
- `docs/roadmap/session-specs/session-30-6e-backtest-v1.md` — full spec including cost model, CI requirements, trial recording.
- `docs/roadmap/session-specs/session-33-track-c-gate.md` — pre-committed gate procedure with escape paths.

v1 plan and risks are kept on disk as historical record; v2 supersedes for execution.

## Approval gate

I (the planning skill, on behalf of the three personas) recommend Ibby red-line
v2 before any sprint 29 work begins. The most consequential decisions — Walkforward
coupling option, OU-bounds location, knob defaults — are 29a deliverables, but the
*plan-level* commitments (S1–S15, M1–M6, T1–T5) need Ibby's approval first. They
shape the spec 29a starts from.
