# Trading Research Platform — Status Report
**Date:** 2026-04-19 (end of Session 22)
**Purpose:** Briefing document for Opus planning conversation.
**Audience:** Ibby + Opus model. This document stands alone — no prior session context needed.

---

## What this platform is

A personal quant trading research desk built on CME futures. The ambition:
pull historical bars from TradeStation, validate and store them, design and backtest
strategies with honest statistics, forensically review trades, eventually paper-trade
and go live. Single-instrument mean reversion first (ZN = 10-year Treasury futures),
FX pairs second (6A/6C/6N = AUD, CAD, NZD futures).

22 sessions of Claude Code work. Python 3.12, managed by `uv`. All code on
`develop` branch; nothing merged to `main` yet (main is reserved for
"passing backtest + paper-trade period" gate).

---

## Session 22 Results — ZN VWAP Reversion v2

The v1 strategy (MACD histogram pullback) failed definitively in session 19:
3.9% win rate, Sharpe -21.3, Calmar -0.04, 10/10 walk-forward folds negative.
Root cause: no RTH filter (75% of trades overnight), MACD zero-cross exit is
not a price exit.

Session 22 redesigned the strategy hypothesis entirely — Candidate B:
**VWAP structural mean reversion**. Entry when price breaches session VWAP ± 2σ
band, daily MACD direction as bias filter, no MACD confirmation on the 5m frame,
exit when price returns to session VWAP, stop at 2x ATR.

**v2 backtest result (2010–2024, 14 years, 2,579 trades):**

| Metric | v1 | v2 | Direction |
|---|---|---|---|
| Total trades | 10,631 | 2,579 | RTH filter working |
| Win rate | 3.9% | 23.2% | Meaningful improvement |
| Max consec. losses | 300 | 27 | Structural improvement |
| Sharpe | -21.32 | -9.10 | Still negative |
| Calmar | -0.04 | -0.05 | Flat |
| Expectancy/trade | -$64 | -$61 | Marginally better |
| Profit factor | — | 0.27 | Not there yet |

**Session 22 goal was >40% win rate and Calmar >0. Neither achieved.**

**Diagnosis of v2 failure:**

The band touch is a necessary condition for the trade but not sufficient.
Avg MFE (best favorable move during trade): +0.07 pts.
Avg MAE (worst adverse move during trade): -0.09 pts.
These are nearly symmetric — we're entering with no directional edge.

On mean-reverting days, ZN hits the 2σ band and snaps back within 30-45 minutes.
On trending days (Fed reaction, flight-to-quality, big rates surprise), ZN hits 2σ
and keeps walking. The strategy cannot distinguish these two regimes. The band alone
is not enough. Win rate of 23.2% (vs 3.9% for a broken hypothesis) means the
structural level is real — roughly 1 in 4 band touches reverts. We need to get to
1 in 2.

**Next step for the strategy (not the platform):** Regime filter — likely ADX gate
(`daily_adx_14 < threshold`). Low ADX = directional force is weak = mean reversion
more likely. ADX is already in the feature set. Threshold is a free parameter that
must be declared before the backtest.

---

## Platform Status Table

Status definitions:
- **WORKING** — implemented, tested, in production use
- **HAS ISSUES** — implemented but known bugs or limitations
- **PLANNED** — scope defined, not started
- **NEW / NO PLAN** — idea identified, no design or scope yet

### Data Layer

| Component | Status | Notes |
|---|---|---|
| TradeStation API auth + token refresh | WORKING | OAuth2, refresh token flow; docs in `docs/tradestation-api/` |
| Historical bar downloader (1m OHLCV) | WORKING | Pulls 1m bars for any TS symbol; ZN has 2010–2026 |
| Buy/sell volume download | HAS ISSUES | Field nullable; API returns it for some dates only |
| RAW layer (immutable parquet + manifest) | WORKING | Fully implemented for ZN |
| CLEAN layer (validated, resampled) | WORKING | ZN: 1m/5m/15m/60m/240m/1D |
| FEATURES layer (indicators + HTF bias) | WORKING | ZN: 5m and 15m, base-v1 feature set |
| Back-adjustment (Panama method) | WORKING | Roll log tracked and committed |
| Calendar-based gap validation | WORKING | CME awareness via `pandas-market-calendars` |
| Manifest / provenance tracking | WORKING | Every parquet has sibling manifest.json |
| **Instrument generalization (non-ZN)** | **HAS ISSUES** | 3 ZN-specific hardcodings remain (OI-010/011/012); partially fixed session 20 |
| 6A pipeline | HAS ISSUES | RAW sample present; full pipeline blocked on OI-010/011/012 |
| Self-service new instrument download | NEW / NO PLAN | No UI or CLI; user must know symbol + date range |
| Historical news calendar (beyond FOMC/CPI/NFP) | PLANNED | FOMC/CPI/NFP done; earnings, USDA, OPEC, BOJ/ECB not built |

### Backtest & Validation

| Component | Status | Notes |
|---|---|---|
| Backtest engine | WORKING | Next-bar-open fill, pessimistic TP/SL, real commissions |
| EOD flat | WORKING | Closes all positions at 15:00 ET |
| Walk-forward validator | WORKING | Purged with embargo gap; 10-fold default |
| Event-day blackout filter | WORKING | FOMC/CPI/NFP; wired into signal generation |
| Backtest output (terminal summary) | WORKING | Prints to console with bootstrap CIs |
| Backtest output (HTML report) | WORKING | 24-section report; `report` CLI command |
| Backtest report UI / browser interface | NEW / NO PLAN | Currently: CLI → HTML file on disk. No web UI. |
| Backtesting playground | NEW / NO PLAN | No interactive parameter exploration UI |
| Walk-forward HTML visualization | WORKING | Included in 24-section report |
| Trial registry (deflated Sharpe tracking) | WORKING | Tracks variants; DSR computed across trials |
| Same-bar fill override | WORKING | Requires written justification in config |
| OFI-based TP/SL resolution | WORKING | Opt-in per strategy |
| Multi-strategy portfolio engine | WORKING | Multi-strategy position tracking, combined margin |
| Paper trading simulation | NEW / NO PLAN | Not built |

### Visual & Forensics

| Component | Status | Notes |
|---|---|---|
| Replay cockpit (Dash app) | WORKING | 4-pane MTF: 5m/15m/60m/1D, synced crosshairs |
| Trade markers on replay charts | WORKING | Entry/exit/stop overlaid from trade log |
| OFI subplot | WORKING | Order flow imbalance visible in replay |
| VWAP + Bollinger overlays | WORKING | All three VWAP flavors (session/weekly/monthly) |
| Strategy selector in replay UI | NEW / NO PLAN | Replay hardcoded to ZN; no dropdown for strategy or instrument |
| Browser-based dashboard / nav | NEW / NO PLAN | No unified UI; user runs CLI commands |
| Mobile / tablet view | NEW / NO PLAN | No responsive design planned |

### Statistical Rigor

| Component | Status | Notes |
|---|---|---|
| Sharpe, Sortino, Calmar | WORKING | All reported with bootstrap CIs |
| Deflated Sharpe (DSR) | WORKING | Bug fixed session 17 (kurtosis convention) |
| Probabilistic Sharpe (PSR) | WORKING | |
| Bootstrap confidence intervals | WORKING | 1,000 resamples by default |
| Monte Carlo simulation | WORKING | Included in 24-section report |
| Regime breakdown | WORKING | Per-regime metrics in report |
| Stationarity checks (ADF, Hurst, OU half-life) | PLANNED | Defined in design; not implemented |
| Feature importance / SHAP | HAS ISSUES | OI-013: numba JIT crash on Windows; test skipped |
| Multiple testing correction (Benjamini-Hochberg) | PLANNED | Design defined; not coded |

### Strategy Work

| Component | Status | Notes |
|---|---|---|
| ZN MACD pullback v1 | HAS ISSUES | Hypothesis wrong; definitively failed (session 19) |
| ZN VWAP reversion v2 | HAS ISSUES | 23.2% win rate, Calmar -0.05; needs regime filter |
| ZN v2 regime filter (ADX gate) | PLANNED | Next step; ADX already in features |
| ZN strategy at target (>40% WR, Calmar >0) | NOT YET | Session 22 goal not achieved |
| Walk-forward validation of any ZN strategy | NOT YET | Blocked on positive strategy first |
| Paper trading period (ZN) | NOT YET | Blocked on positive walk-forward first |
| 6A / pairs strategy | NEW / NO PLAN | No design started; blocked on 6A pipeline + ZN success |

### Machine Learning

| Component | Status | Notes |
|---|---|---|
| Feature engineering framework | WORKING | base-v1 feature set: MACD, ATR, RSI, VWAP, ADX, OFI, EMA/SMA |
| Meta-labeling (precision/recall/F1) | WORKING | Added session 18 |
| Purged walk-forward CV (for ML) | WORKING | Proper gap/embargo wired in |
| ML model training (any model) | PLANNED | Framework exists; no model trained yet |
| SHAP feature importance | HAS ISSUES | Windows crash (OI-013) |
| Hyperparameter tuning | NEW / NO PLAN | No design |
| Model versioning + registry | NEW / NO PLAN | No design |
| ML → signal generation pipeline | NEW / NO PLAN | How ML output becomes a trading signal |
| Re-training cadence / concept drift detection | NEW / NO PLAN | |

### Infrastructure & Dev Experience

| Component | Status | Notes |
|---|---|---|
| Python environment (uv, pyproject.toml) | WORKING | `uv sync` + `uv run pytest` works clean |
| Test suite | WORKING | 401 tests pass, 1 skipped (OI-013), 0 failed (updated session 22) |
| Git structure (develop → main gate) | WORKING | Feature branches off develop; main gated |
| CI / automated test runs | NEW / NO PLAN | No GitHub Actions or CI pipeline |
| SHAP / numba Windows crash | HAS ISSUES | OI-013; low priority until ML is active |
| settings.local.json tracked in git | HAS ISSUES | OI-003; cosmetic, not blocking |
| docs/pipeline.md completeness | HAS ISSUES | Core data sections accurate; sessions 11–19 additions not yet documented |

### Live Execution

| Component | Status | Notes |
|---|---|---|
| TradeStation order API review | PLANNED | API docs exist in repo; no code written |
| Order idempotency + reconciliation | NEW / NO PLAN | |
| Kill switches (strategy / instrument / account) | NEW / NO PLAN | |
| Position sizing engine | WORKING | Volatility targeting implemented; Kelly is opt-in |
| Daily / weekly loss limits | PLANNED | Design in CLAUDE.md; not coded |
| Live order submission | NEW / NO PLAN | Nothing built |
| Paper trading via TS SIM environment | NEW / NO PLAN | TS has sim environment; not wired up |

---

## Open Technical Debt (known bugs, not yet fixed)

| ID | Description | Severity | Blocking |
|---|---|---|---|
| OI-003 | settings.local.json tracked in git | Low | No |
| OI-010 | RTH window hardcoded for ZN in validate.py | Medium | 6A pipeline |
| OI-011 | Hardcoded "ZN" in continuous.py output paths | Medium | 6A pipeline |
| OI-012 | last_trading_day_zn() misleading name | Low | No |
| OI-013 | SHAP/numba JIT crash on Windows | Low | ML feature importance only |
| — | Blackout filter: 6 overnight trades slip through event-day morning | Low | No |
| — | docs/pipeline.md missing sessions 11–19 content | Low | No |
| — | 6A full pipeline not yet run end-to-end | Medium | 6A strategy work |

---

## Honest Assessment: When is the platform ready to trade?

This is the question as a customer. Here is the answer with no softening.

**Today the platform is a research sandbox, not a trading desk.**

What works end-to-end: download ZN data → validate → build features → run a
backtest → review a 24-section HTML report → forensically replay trades in a Dash
app. All of that works and is tested. The plumbing is real.

What does not work yet, specifically for the "try a trade idea" use case:

1. **No working strategy.** v1 failed. v2 is at 23.2% win rate. Nothing has
   cleared the gate to paper trading. This is the expected place to be at this
   stage — finding a bad strategy is progress, not failure.

2. **No self-service instrument onboarding.** To add a new instrument, Ibby
   would need to: know the TradeStation symbol, know the date range, run 3 CLI
   commands in sequence, confirm the pipeline output. That is doable but not
   friendly. There is no "add instrument" button.

3. **No interactive backtest UI.** Results come out as terminal text and an
   HTML file on disk. There is no web app for Ibby to compare runs, change
   parameters, or explore trade-by-trade performance interactively.

4. **No ML pipeline.** The feature engineering is ready. No model has ever been
   trained. The SHAP tooling crashes on Windows. ML is genuinely 0% built.

5. **No live or paper execution.** The kill switches, daily loss limits, order
   reconciliation, and paper-trading loop don't exist.

**Gate to "try a trade idea":** a working strategy with positive walk-forward results
is the prerequisite for everything downstream. That is the right sequencing. The
platform infrastructure is solid enough to validate a strategy honestly; the remaining
work is finding one that passes.

---

## What Sessions 23–50 Look Like

This is not a plan — it is a rough sequencing of what needs to happen in what order.
Exact session scope is Ibby's call.

**Block 1: Get a working strategy (sessions 23–28)**

The platform is built. The problem is finding a hypothesis that passes honest
walk-forward validation. That is strategy iteration work, not platform work.

| Approx session | Topic |
|---|---|
| 23 | ZN v2 regime filter: ADX gate. Run backtest + walk-forward. |
| 24 | If ADX gate doesn't work: time-of-day analysis, band width variants, or confirm the structural level is just not predictive enough without additional filters. |
| 25 | First positive ZN walk-forward result (assumed by here; if not, continue iterating). Paper trading setup begins. |
| 26 | ZN paper trading period starts. Evaluation framework for live P&L vs backtest expectations. |
| 27–28 | ZN paper trading runs. Session work shifts to 6A pipeline + pairs strategy design. |

**Block 2: Second instrument + pairs (sessions 27–34)**

| Approx session | Topic |
|---|---|
| 27 | 6A pipeline: fix OI-010/011/012, run end-to-end, verify. |
| 28 | 6A historical data pull (full history), feature build, first look at 6A price structure. |
| 29–30 | Pairs strategy design: 6A/6C correlation, spread construction, OU half-life, stationarity. |
| 31–32 | Pairs backtest + walk-forward. CBOT spread margin vs TradeStation retail margin reality check. |
| 33–34 | Pairs paper trading setup if positive. |

**Block 3: ML pipeline (sessions 33–40)**

This block assumes at least one working rule-based strategy is in paper trading.
ML on top of a real edge; ML on nothing produces nothing.

| Approx session | Topic |
|---|---|
| 33 | Stationarity checks (ADF, Hurst, OU) for ZN and 6A features. |
| 34 | Feature selection with Benjamini-Hochberg correction. |
| 35 | First ML model (logistic regression baseline). Purged walk-forward. |
| 36 | Gradient boosting model. Compare to baseline and rule-based. |
| 37 | SHAP fix (OI-013) or workaround. Feature importance visualization. |
| 38 | ML → signal pipeline: how model output becomes a trading signal. |
| 39–40 | ML walk-forward at production quality. Model registry basics. |

**Block 4: Platform UX + reporting UI (sessions 38–45)**

This is the "trading desk" experience Ibby described: instrument selection,
parameter exploration, report browsing, session navigation — all in a web UI
rather than CLI commands.

| Approx session | Topic |
|---|---|
| 38 | Instrument onboarding UI: select symbol, pull data, see validation results. |
| 39 | Backtesting playground: select strategy, adjust parameters in a form, see results. |
| 40 | Backtest report browser: compare runs side by side, drill into trades. |
| 41 | News/events calendar UI: overlay economic events on charts. |
| 42–43 | Full dashboard: strategy list, instrument list, status indicators, navigation. |
| 44–45 | Mobile-friendly design if desired. |

**Block 5: Live execution (sessions 44–50)**

| Approx session | Topic |
|---|---|
| 44 | TradeStation order API integration. Paper execution via TS SIM. |
| 45 | Kill switches: strategy-level, instrument-level, account-level. |
| 46 | Daily / weekly loss limits. Automated position sizing. |
| 47 | Order idempotency + fill reconciliation. |
| 48 | Live execution: first real trade, small size. |
| 49–50 | Monitoring, alerts, post-trade review workflow. |

---

## Bottom line for the Opus conversation

The platform engine is real and honest. The data pipeline, backtest engine,
walk-forward validator, and reporting suite are production-quality for a personal
trading desk. The replay cockpit works. The statistical rigor is correct.

The strategy layer is where the work is. v2 improved meaningfully over v1 (23.2%
win rate vs 3.9%, max consec losses 27 vs 300) but hasn't cleared the bar yet.
The next session is a regime filter (ADX gate). If that works, everything downstream
unblocks.

The ML pipeline, live execution, and UX are genuinely not started. They are 3–4
blocks of work, probably 15–25 sessions depending on complexity and how much the
strategy iteration extends.

The platform is ready for Ibby to iterate on strategy ideas. It is not yet ready
for a non-technical user to sit down and start trading. That is the right place
to be at session 22.
