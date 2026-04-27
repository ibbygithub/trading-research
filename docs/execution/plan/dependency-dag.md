# Dependency DAG — Sub-sprint sequencing
Last updated: 2026-04-26

This is the source of truth for "what runs when." A dispatcher reads this
plus [`../handoffs/current-state.md`](../handoffs/current-state.md) to pick
the next eligible sub-sprint.

## Conventions

- Sub-sprints are identified by Spec ID (e.g., `29a`, `30b`, `D1`, `B1`, `F2`).
- An arrow `A → B` means B is entry-blocked by A.
- A line on the same level means parallel-eligible (subject to the symmetric
  parallel-OK check in [`../policies/dispatcher-routing-rules.md`](../policies/dispatcher-routing-rules.md)).
- Phase 1 is sessions 29–38. Phase 2 is sessions 39+ (paper window → live).

## Phase 1 DAG (sessions 29–38)

```
[Track A complete]
        │
        ▼
       29a ──────────── (Opus, day 1 morning)
        │
        ├──► 29b (Sonnet, day 1 afternoon)  ──parallel──► D1 (Sonnet, day 1)
        │       │
        │       ▼
        │      29c (Sonnet, day 2 morning) ──parallel──► 29d (Gemini, day 2)
        │       │                                          │
        │       └────────────┬─────────────────────────────┘
        │                    │
        │                    ▼
        │                  [29 DONE — registry coupling, sizing, OU bounds, naming]
        │                    │
        ▼                    ▼
       30a (Sonnet) ──parallel──► D2 (Sonnet)
        │
        ▼
       30b (Opus, persona review)
        │
        ▼
       31a (Opus) ──parallel──► D3 (Sonnet)
        │
        ▼
       31b (Sonnet, walk-forward begins here)
        │
        ▼
       32a (Opus) ──parallel──► D4 (Sonnet) ──parallel──► F2 (Gemini)
        │
        ▼
       32b (Sonnet)
        │
        ▼
       33a (Sonnet) ──parallel──► F1 (Gemini), B1 (Gemini)
        │
        ▼
       33b (Opus, the gate)
        │
        ├──[PASS]──► 34a (Opus) ──► 34b (Sonnet, E1 or E1') ──parallel──► F3 (Gemini)
        │             │
        │             ▼
        │           [Track D complete]
        │             │
        │             ▼
        │            35a (Sonnet, paper loop)
        │             │
        │             ▼
        │            35b (Opus, failure-mode review)
        │             │
        │             ▼
        │            35c (Sonnet, gap fixes)
        │             │
        │             ▼
        │            36a (Sonnet, first paper trade scaffolding)
        │             │
        │             ▼
        │            36b (Opus, divergence review + 30-day window opens)
        │             │
        │             ▼
        │            37a (Opus, punch-list)
        │             │
        │             ▼
        │            37b (Sonnet, top of list) ──parallel──► 37c (Gemini, fan-out)
        │             │
        │             ▼
        │            38a (Opus, gui audit + UX design)
        │             │
        │             ▼
        │            38b (Sonnet, status + linter) ──parallel──► 38c (Gemini, polish)
        │             │
        │             ▼
        │            38d (Opus, three-persona readiness)
        │             │
        │             ▼
        │           [Phase 1 DONE]
        │
        └──[FAIL]──► escape rule applied per 33b
                    (re-routes 34a; 35–38 may reflow per pivot path)
```

## Phase 2 DAG (sessions 39–55, paper window → live)

```
[Phase 1 DONE — 30-day paper window OPEN]
        │
        ▼
       39 (Opus, week-1 paper review)              [calendar day +5]
        │
        ▼
       40 (Sonnet, mid-window cleanup IF needed)   [calendar day +10]
        │
        ▼
       41 (Opus, week-2 paper review)              [calendar day +12]
        │
        ▼
       42 (Sonnet, mid-window cost-model recalibration IF needed)
        │
        ▼
       43 (Opus, week-3 paper review)              [calendar day +19]
        │
        ▼
       44 (Opus, week-4 + end-of-window evaluation)[calendar day +30]
        │
        ▼
       45 (Opus + all personas, LIVE READINESS GATE)
        │
        ├──[NOT READY]──► 39-44 cycle repeats; window restarts if knobs changed
        │
        └──[READY]──► 46 (Opus, risk-of-ruin + first-trade size)
                       │
                       ▼
                      47 (Sonnet, TS LIVE API plumbing — distinct from SIM)
                       │
                       ▼
                      48 (Sonnet + Opus mid, kill-switch DRILL against real broker)
                       │
                       ▼
                      49 (Opus + Ibby, FIRST LIVE MICRO-CONTRACT TRADE)
                       │
                       ▼
                      50 (Opus, post-first-trade review + scaling rule)
                       │
                       ▼
                      51-52 (Sonnet, second strategy on 6A or 6C — paper)
                       │
                       ▼
                      53 (Opus, second-strategy paper review)
                       │
                       ▼
                      54 (Sonnet, second-strategy live promotion after own 30-day window)
                       │
                       ▼
                      55 (Opus, multi-strategy ops + Track G/H decision point)
```

Phase 2 sessions are described in [`product-roadmap-to-live.md`](product-roadmap-to-live.md).

## Parallel-eligibility matrix (symmetric)

The dispatcher checks both halves before scheduling parallel work.

| Spec | Parallel-OK with |
|---|---|
| 29b | D1 |
| 29c | 29d |
| 30a | D2 |
| 31a | D3 |
| 31b | D3 |
| 32a | D4, F2 |
| 32b | D4, F2 |
| 33a | F1, B1 |
| 34b | F3 |
| 35a | — (owns the day) |
| 35b | — |
| 35c | — |
| 36 | — |
| 37b | 37c |
| 38b | 38c |
| D1 | 29b, 29c |
| D2 | 30a, 30b |
| D3 | 31a, 31b |
| D4 | 32a, 32b, F2 |
| F1 | 33a |
| F2 | 32a, 32b, D4 |
| F3 | 34b |
| B1 | 33a |

If a sub-sprint is not in this table, treat it as exclusive (no parallel
work).

## Hard constraints

- **Track D (D1–D4) must be complete before sprint 35.** 35 wires the
  paper-trading loop and depends on every circuit breaker and reconciler.
- **Sprint 29 must be fully complete before sprint 30.** All four sub-sprints
  must be DONE; partial completion is not enough because 30 depends on
  registry, sizing, and OU bounds simultaneously.
- **Sprint 33 PASS or pre-committed escape verdict** is required before 34
  begins. A FAILED 33b blocks 34 unconditionally.
- **The 30-day paper window** is calendar time, not session time. Sessions
  39–44 are scheduled across ~30 calendar days.
- **No knob change during the 30-day window** (sprint 36 hard rule). If a
  cleanup session inadvertently changes strategy behaviour, the window
  clock resets.

## Escape paths (pre-committed at sprint 33)

| 33 verdict | Next routing |
|---|---|
| PASS all 7 criteria | 34a → E1 (TS SIM) or E1' (TV) per 34a decision |
| FAIL G1 (fold dispersion) | 34a routes to "pivot to 6A/6C single-instrument" — 35+ rescoped |
| FAIL G2/G3 (negative aggregate) | 34a routes to "switch strategy class" — 35+ rescoped |
| FAIL G6 (cost only, June 30 pressure) | 34a routes to E1' (TV Pine port) |
| FAIL G5 (stationarity flip) | 34a holds focused decision; mentor + DS pick path |
| FAIL G7 (cohort consistency) | Sprint 33 redo |
