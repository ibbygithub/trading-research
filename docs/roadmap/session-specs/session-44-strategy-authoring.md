# Session 44 — Part III: Strategy Authoring

**Status:** Spec
**Effort:** 1 session, ~22 pages
**Model:** Mixed — Opus 4.7 for Chapter 11; Sonnet 4.6 for the rest
**Depends on:** Sessions 41, 42 (Parts I and II done — strategy
chapters cross-reference indicators, feature sets, and operating
principles)
**Workload:** v1.0 manual completion

## Goal

Author all of Part III — the strategy-authoring chapters. Five
chapters covering design principles, YAML grammar, the expression
evaluator, regime filters, and the configuration reference. Chapter
11 (expression evaluator) is the conceptually-loaded one and gets
Opus; the other four are describe-what-exists work and run on
Sonnet.

## In scope

- **Chapter 9 — Strategy Design Principles (~4 pages, Sonnet).**
  Rules first / ML second; parameter discipline; the overfitting
  smell; the three dispatch paths; why YAML by default. Mostly
  drawn from `CLAUDE.md` and the persona files.
- **Chapter 10 — YAML Strategy Authoring (~8 pages, Sonnet).**
  Anatomy of a strategy YAML, the `entry`/`exits`/`backtest`
  blocks, knobs, time windows, multi-timeframe references. Worked
  walkthrough of `configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml`.
- **Chapter 11 — The Expression Evaluator (~6 pages, Opus).**
  Supported syntax, name resolution, NaN handling, `shift()`
  semantics, what the evaluator refuses, common patterns. The
  teaching prose for *why* the evaluator is restricted (security
  posture + look-ahead prevention) is the load-bearing part.
- **Chapter 12 — Composable Regime Filters (~4 pages, Sonnet).**
  What a filter is, built-in `volatility-regime`, inline vs
  `include` syntax, the `fit_filters` lifecycle, composing
  multiple, adding a new filter type.
- **Chapter 13 — Strategy Configuration Reference (~4 pages,
  Sonnet).** Complete YAML key reference (alphabetised), cross-key
  validation, default-filling order. §13.4 (`validate-strategy`
  CLI) is documented as the spec for the code in session 49.

## Out of scope

- Implementation of `validate-strategy` CLI (session 49)
- Pairs-strategy YAML extension (post-v1.0)

## Hand-off after this session

- Part III drafted at quality bar.
- Next session: 45 (Part IV — backtesting chapters).
