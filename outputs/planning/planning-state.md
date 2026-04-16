# Planning State — trading-research
Last updated: 2026-04-14

## Project Summary
A personal quant trading research lab building a full pipeline from raw futures data through honest backtesting and eventual live execution via TradeStation. Primary goal: grow $25k account to $35k then take regular draws — capital preservation with consistent income, not maximum return. Single-instrument ZN mean reversion is the first strategy; FX pairs (6A/6C/6N) add a second income stream once ZN is validated. Pipeline: RAW → CLEAN → FEATURES → visual cockpit → backtest engine (portfolio-aware) → strategy → paper → live.

## Active Work
| Item | Description | Phase | Status | Last Updated |
|------|-------------|-------|--------|--------------|
| Session 06 | CLI automation: verify, rebuild clean/features, backfill-manifests, inventory | Ground floor | COMPLETE | 2026-04-14 |
| Session 07 | Visual cockpit: Dash 4-pane MTF replay app | Floor 1 | Spec written, ready to execute | 2026-04-14 |

## Open Decisions
- None blocking sessions 06 or 07
- Session 08 scope (backtest engine + portfolio risk) to be specced after session 07 delivers

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
| Session 06 plan | docs/session-plans/session-06-plan.md | Approved, ready to execute |
| Session 07 plan | docs/session-plans/session-07-plan.md | Written, awaiting session 06 completion |
| Pipeline reference | docs/pipeline.md | Active |
| Data architecture decision record | docs/architecture/data-layering.md | Active |
