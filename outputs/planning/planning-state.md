# Planning State — trading-research
Last updated: 2026-04-25

## Project Summary
A personal quant trading research lab building a full pipeline from raw futures data through honest backtesting and eventual live execution via TradeStation. Primary goal: grow $25k account to $35k then take regular draws — capital preservation with consistent income, not maximum return. Pivoted from ZN to 6E (Euro FX) as primary instrument at session 23. Pipeline: RAW → CLEAN → FEATURES → visual cockpit → backtest engine (portfolio-aware) → strategy → paper → live.

## Active Work
| Item | Description | Phase | Status | Last Updated |
|------|-------------|-------|--------|--------------|
| Track A (sessions 23–28) | Hardening sprint — Protocols, suite, BH, 6E pipeline | Done | COMPLETE | 2026-04-25 |
| Execution tree at `docs/execution/` | Multi-model dispatch-ready specs for sessions 29–55 | Planning | Drafted, awaiting Ibby red-line | 2026-04-26 |
| Phase 1 (sessions 29–38) | Hardening + paper-trading ready | Planning | Per-model specs ready | 2026-04-26 |
| Phase 2 (sessions 39–55) | 30-day paper window → live small money | Planning | Per-session specs ready | 2026-04-26 |

## Open Decisions
- **Plan-level commitments awaiting Ibby red-line.** See [`docs/execution/plan/master-execution-plan.md`](../../docs/execution/plan/master-execution-plan.md) "Plan-level commitments requiring Ibby red-line." Ten items.
- **Track E option pick (sprint 34):** TradeStation SIM vs TradingView Pine port. Pre-committed escape rules apply.
- **Track G/H decision (session 55):** ML, pairs, or stay simple. Open-ended.

## Active execution state
See [`docs/execution/handoffs/current-state.md`](../../docs/execution/handoffs/current-state.md). Next eligible: 29a (Opus 4.7).

## Technology Registry
| Technology | Role in this project | Rationale | Date |
|------------|----------------------|-----------|------|
| Python 3.12 + uv | Language and package management | Project default | Session 02 |
| TradeStation API | Historical bar downloads, eventual live execution | Only broker with CME futures access in use | Session 02 |
| Parquet + manifest sidecars | Data storage layer (RAW/CLEAN/FEATURES) | Column-oriented, fast, schema-enforceable | Session 02 |
| pandas-market-calendars | Calendar-aware gap validation | CBOT_Bond and CMEGlobex_FX support | Session 03 |
| Typer | CLI framework for `trading-research` entry point | Cleaner subcommand help; no new dep needed (already planned) | Session 06 plan |
| Dash + Plotly | Visual cockpit (replay app, forensics, eventually live dashboard) | Pure Python, first-class financial charts, local browser-based, no JS required | 2026-04-14 |
| structlog | Logging | Project standard for all scripts | Project default |

## Decision Log
### Back-adjusted continuous series for ZN — Session 04
- Capability need: multi-year ZN data without contract gaps
- Options considered: single continuous download vs. per-contract stitching
- Decision: per-contract stitching (66 quarterly contracts TYH10–TYM26) with cumulative back-adjustment
- Reasoning: eliminates artificial gaps at roll; roll log JSON captured for audit
- Risk accepted: back-adjustment introduces synthetic prices; unadjusted 1m parquet preserved alongside

### Typer for CLI — Session 06 plan
- Capability need: CLI entry point with subcommands
- Options considered: Typer vs. argparse
- Decision: Typer
- Reasoning: cleaner help output, subcommand ergonomics; no new dependency (was already planned)
- Risk accepted: none material

### Dash + Plotly for visual cockpit — 2026-04-14
- Capability need: interactive multi-timeframe chart display with synced crosshairs, indicator overlays, trade markers
- Options considered: Dash+Plotly, mplfinance, Bokeh, Streamlit, PyQtGraph
- Decision: Dash + Plotly
- Reasoning: pure Python (same codebase), first-class candlestick/OHLC charts, Dash callbacks handle synced crosshairs cleanly, runs locally in browser, already planned as the replay module since session 02
- Risk accepted: none material; path to live dashboard via WebSocket extensions if/when needed

### Floor ordering — 2026-04-14
- Question: build visual cockpit (Floor 1) before or concurrent with backtest engine (Floor 2)?
- Decision: Floor 1 first. Visual forensics before backtest engine.
- Reasoning: seeing the data and indicators visually catches problems before they contaminate backtest results; cockpit is also needed to review backtest trade output once Floor 2 exists

### Backtest engine architecture — 2026-04-14
- Question: single-instrument first, portfolio added later vs. portfolio-aware from day one?
- Decision: Portfolio-aware architecture from day one; first backtest runs ZN only
- Reasoning: portfolio margin and account-level daily loss limit cannot be cleanly modeled without a Portfolio Manager layer; retrofitting it later means rewriting the risk module and equity curve calculations
- Design: Portfolio Manager holds N strategy instances, each single-instrument; PM handles combined margin, account-level P&L, and daily loss limit (config-driven, not hard-coded)

### VPS "Split-Brain" architecture — 2026-04-14
- Proposed by: external review (Gemini PRD)
- Decision: REJECTED / DEFERRED
- Reasoning: no strategy exists yet, no paper trading period completed; VPS adds operational complexity before the house has walls; if live execution eventually requires remote execution, the home lab's brainnode-01 is the natural candidate; decision to be revisited at penthouse phase

## Floor Plan (Canonical Roadmap)
```
PENTHOUSE  Live Execution
           Kill switches (strategy / instrument / account level)
           Connection heartbeat + alert
           Idempotent orders, broker fill reconciliation

FLOOR 4    Paper Trading + Draw Tracking
           Forward-test scaffold (same engine as backtest, live data feed)
           Account equity tracker, draw log
           Minimum 30 trading days paper period before any live capital

FLOOR 3    First Strategy + Forensic Report
           ZN mean reversion (MACD divergence + OFI confirmation)
           Walk-forward validation (not single train/test split)
           One-page HTML report: Calmar/DSR/Ulcer + confidence intervals

FLOOR 2    Backtest Engine + Portfolio Risk
           BacktestEngine: next-bar-open fills, pessimistic TP/SL, time-stop
           Portfolio Manager: N strategy instances, combined margin tracking
           Risk module: account-level daily loss limit (YAML config), EOD flatten

FLOOR 1    Visual Forensics — The Cockpit         [SESSION 07]
           Dash + Plotly replay app
           4-pane MTF: 5m / 15m / 60m / 1D
           Synced crosshairs, OFI subplot, VWAP+Bollinger overlays
           Windowed data load (30-90 days around anchor date)
           Trade marker overlay (optional --trades JSON for backtest output)

GROUND     CLI Automation                          [SESSION 06 — IN PROGRESS]
           verify / rebuild clean / rebuild features / inventory

FOUNDATION Data Pipeline                           [DONE — sessions 02-05]
           RAW/CLEAN/FEATURES for ZN, 14 years, 154 tests passing
```

Annex (parallel / deferred):
- FX data pipeline: 6A, 6C, 6N through same RAW→CLEAN→FEATURES pipeline (no new code needed)
- Pairs framework: after ZN strategy validated
- News scraper / blackout calendar: after paper trading baseline established
- ML layer: after rule-based strategy validated

## Backlog
- FX instrument data pull (6A, 6C, 6N) — can run parallel to Floor 1
- Pairs strategy framework — Floor 3+
- ML layer — after rule-based baseline
- News scraper / blackout calendar automation — Floor 4+
- Live execution kill switches — Penthouse

## Planning Documents
| Document | Path | Status |
|----------|------|--------|
| Session 06 plan | docs/session-plans/session-06-plan.md | Historical |
| Session 07 plan | docs/session-plans/session-07-plan.md | Historical |
| Roadmap sessions 23–50 | docs/roadmap/sessions-23-50.md | Active |
| Sprints 29–38 plan v1 | outputs/planning/sprints-29-38-plan.md | Superseded |
| Sprints 29–38 plan **v2** | outputs/planning/sprints-29-38-plan-v2.md | **Draft — awaiting Ibby red-line** |
| Sprints 29–38 risks **v2** | outputs/planning/sprints-29-38-risks-v2.md | Active |
| Peer review — Data Scientist | outputs/planning/peer-reviews/data-scientist-review.md | Active |
| Peer review — Architect | outputs/planning/peer-reviews/architect-review.md | Active |
| Peer review — Quant Mentor | outputs/planning/peer-reviews/quant-mentor-review.md | Active |
| Peer-review synthesis | outputs/planning/peer-reviews/synthesis-and-required-changes.md | Active |
| Multi-model handoff protocol | outputs/planning/multi-model-handoff-protocol.md | Policy — load-bearing |
| Gemini validation playbook | outputs/planning/gemini-validation-playbook.md | Policy — load-bearing |
| Session 29 spec | docs/roadmap/session-specs/session-29-strategy-foundation.md | Ready |
| Session 30 spec | docs/roadmap/session-specs/session-30-6e-backtest-v1.md | Ready |
| Session 31 spec | docs/roadmap/session-specs/session-31-regime-filter.md | Ready |
| Session 32 spec | docs/roadmap/session-specs/session-32-mulligan.md | Ready |
| Session 33 gate spec | docs/roadmap/session-specs/session-33-track-c-gate.md | Ready (pre-committed) |
| Session 34 bridge spec | docs/roadmap/session-specs/session-34-bridge-pick.md | Ready (3-branch) |
| Session 35 paper-loop spec | docs/roadmap/session-specs/session-35-paper-loop.md | Ready |
| Session 36 first-paper-trade spec | docs/roadmap/session-specs/session-36-first-paper-trade.md | Ready |
| Session 37 hardening spec | docs/roadmap/session-specs/session-37-hardening.md | Ready |
| Session 38 trader's-desk spec | docs/roadmap/session-specs/session-38-traders-desk.md | Ready |
| Session F1 (Gemini) | docs/roadmap/session-specs/session-F1-html-report-enhancements.md | Ready |
| Session F2 (Gemini) | docs/roadmap/session-specs/session-F2-cli-template-subcommands.md | Ready |
| Session F3 (Gemini) | docs/roadmap/session-specs/session-F3-trial-comparison-report.md | Ready |
| Session B1 (Gemini, existing) | docs/roadmap/session-specs/session-B1-timeframe-catalog.md | Ready |
| Track D circuit breakers (existing) | docs/roadmap/session-specs/track-D-circuit-breakers.md | Ready |
| Track D v2 alignment | docs/roadmap/session-specs/track-D-alignment-with-plan-v2.md | Ready |
| 6E strategy class recommendation | docs/analysis/6e-strategy-class-recommendation.md | Active |
| Pipeline reference | docs/pipeline.md | Active |
| Data architecture decision record | docs/architecture/data-layering.md | Active |
