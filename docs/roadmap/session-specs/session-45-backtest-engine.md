# Session 45 — Part IV: Backtesting

**Status:** Spec
**Effort:** 1 session, ~22 pages
**Model:** Mixed — Opus 4.7 for Chapter 14; Sonnet 4.6 for 15, 16, 18
**Depends on:** Sessions 41–44 (Parts I, II, III done — Part IV
depends on the strategy-authoring grammar being settled)
**Workload:** v1.0 manual completion

## Goal

Author Part IV. Chapter 14 (backtest engine semantics) needs
teaching prose and gets Opus — the engine's design choices (fill
models, EOD flat, max-holding-bars, Mulligan controller) are
load-bearing for every later validation chapter and the prose has
to make them stick. Chapters 15, 16, 18 are reference work on
Sonnet.

Chapter 17 (Trader's Desk Report) is *not* in this session — it's
session 46, bundled with the report-rigor-surfacing code work
because the chapter has [PARTIAL] items that the code closes.

## In scope

- **Chapter 14 — The Backtest Engine (~6 pages, Opus).** Engine
  design principles (bar-by-bar walk, no vectorisation, auditability
  over speed); fill models (next_bar_open default, same_bar
  justification); cost model; TP/SL pessimistic resolution; EOD
  flat; max holding bars; the Mulligan controller; what the engine
  does *not* do. Cite `src/trading_research/backtest/engine.py`,
  `fills.py`, `mulligan.py`.
- **Chapter 15 — Trade Schema & Forensics (~4 pages, Sonnet).**
  TRADE_SCHEMA from `src/trading_research/data/schema.py`; the two
  pairs of timestamps per trade and what they enable in replay;
  exit reasons (`target`/`stop`/`signal`/`eod`/`time_limit`/
  `mulligan`); MAE/MFE; reading a trade log.
- **Chapter 16 — Running a Single Backtest (~4 pages, Sonnet).**
  The `backtest` CLI command with full option reference; output
  artefacts (`trades.parquet`, `equity_curve.parquet`,
  `summary.json`); reading the summary table; the trial-registry
  side-effect.
- **Chapter 18 — The Replay App (~3 pages, Sonnet).** What replay
  shows; launching it; when to use it (pre-backtest sanity vs
  post-backtest forensics); layout reference.

## Out of scope

- Chapter 17 (Trader's Desk Report) — bundled with rigor-surfacing
  code in session 46.
- Implementation of any backtest engine change. Chapter 14
  describes the engine that exists.
- Daily loss limit hook in BacktestEngine — code lands in session
  52, chapter spec is in §35.2 (touched in session 48).

## Hand-off after this session

- Part IV minus Ch 17 drafted at quality bar.
- Next session: 46 (Chapter 17 + report rigor-surfacing code).
