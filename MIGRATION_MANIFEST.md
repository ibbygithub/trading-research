# Migration Manifest — trading-research

**Prepared:** 2026-04-16
**Source host:** ibbytech-laptop (Windows 11, `C:\Trading-research`)
**Target agent:** Gemini / Antigravity
**Purpose:** Hand-off package for migrating active development to a second agent surface without losing architectural context or re-doing validated work.

---

## 1. Architecture Summary

### Stack

- **Language/runtime:** Python 3.12 managed by `uv` (lockfile committed).
- **Data layer:** Parquet files in a strict three-layer model — `data/raw/` (immutable TradeStation downloads) → `data/clean/` (canonical OHLCV, calendar-validated, **no indicators**) → `data/features/` (flat matrices with indicators and HTF bias). Rule is load-bearing: **CLEAN never contains indicators.** See `docs/pipeline.md` and `docs/architecture/data-layering.md`.
- **Calendar/validation:** `pandas-market-calendars` (CBOT_Bond for ZN, CMEGlobex_FX for 6A/6C/6N). Quality reports written as `.quality.json` sidecars.
- **Backtest engine:** `src/trading_research/backtest/engine.py`. Next-bar-open default fill, pessimistic TP/SL resolution (stop wins ambiguous bars), EOD-flat for single-instrument, MAE/MFE captured per trade.
- **Reporting:** Self-contained Plotly HTML via Jinja2 (`eval/report.py`, `eval/templates/report_v1.html.j2`) — offline-renderable, dark theme, 15 sections, 8.6 MB typical.
- **Replay:** Dash app in `src/trading_research/replay/` with 1m/5m/15m/60m/1D focus toggles and trade markers snapped via `project_trades_to_tf()`.
- **CLI:** `uv run trading-research <subcommand>` via `src/trading_research/cli/`.
- **Logging:** `structlog` → JSON lines. No `print()`.
- **Config:** YAML only. Strategies in `configs/strategies/`, instruments in `configs/instruments.yaml`, feature-sets in `configs/featuresets/` (versioned, e.g. `base-v1.yaml`).

### Risk module — current state

- **Location:** `src/trading_research/risk/`
- **Status:** **Scaffold only.** `__init__.py` exists; no live position sizing, vol targeting, daily/weekly loss limits, or kill switches yet.
- **Standing rules (from `CLAUDE.md`) that the module must eventually enforce:**
  - Default sizing = volatility targeting (not Kelly). Kelly requires explicit override.
  - Averaging down without a fresh signal is forbidden; planned re-entries on a fresh pre-defined signal are permitted with combined risk/target set up-front.
  - Daily and weekly loss limits are required for any strategy that moves to paper or live.
  - Pairs strategies must compute both theoretical CME/CBOT reduced-spread margin *and* actual broker margin (TradeStation/IBKR retail do **not** honor reduced intercommodity spread margins — the retail number is 5×+ the exchange number).
  - Kill switches required at strategy, instrument, and account levels.
- **Implication for migration:** risk enforcement is greenfield. No logic to verify — only the rule-set above must be carried into any ported implementation.

### ML / analytics — current state

- **Location:** No dedicated `ml/` module yet. ML-adjacent analytics are planned in Session 12 (regime tagging, winner/loser classifier, permutation importance, SHAP, meta-labeling, trade clustering).
- **Feature engineering:** `src/trading_research/indicators/features.py` builds flat feature matrices for strategies and future ML use. Every indicator has a look-ahead freedom unit test (enforced in Session 05).
- **Standing rules for any ML work:**
  - Rule-based baseline must exist and be tested before ML is layered on — "ML on top of a real edge amplifies the edge; ML on top of nothing launders the nothing."
  - **Purged k-fold walk-forward** with an embargo gap is the minimum validation bar for any ML model (Lopez de Prado, 2018).
  - **Deflated Sharpe** reported alongside raw Sharpe whenever multiple variants tested. The trials registry (Session 11) is what makes deflation honest.
  - Benjamini-Hochberg (not Bonferroni) for multiple-testing correction in feature selection.
  - Linear baseline required before any tree/boosting model — if the linear model captures 80% of the nonlinear model's performance at 5% the complexity, the linear one wins.

### Strategy inventory

- `strategies/zn_macd_pullback.py` — fixture strategy used for Session 09 pipeline smoke test and as the trade-log source for Sessions 10–13 reporting build-out. **Treat as a fixture, not a candidate for optimization.** The data scientist's characterization at Session 11's end is expected to be "statistically indistinguishable from zero" and that is fine for downstream reporting purposes.
- `strategies/example.py` — zero-signal skeleton demonstrating the `generate_signals(df)` interface.

### Data inventory (in repo, gitignored)

- `data/raw/` — ~143 MB of headers + per-contract TradeStation pulls plus the 16-year ZN pull (`ZN_1m_2010-01-01_2026-04-11.parquet`, 5.24M rows).
- `data/clean/` — back-adjusted ZN 1m (4.67M rows), 5m (1.06M), 15m (369k), 60m (98k), 240m (26k), 1D (4.2k). All with manifests.
- `data/features/` — 5m and 15m `base-v1` feature parquets (42 columns each).
- `data/` total: **~795 MB.** `runs/` total: **31 MB.**

---

## 2. Pending Roadmap (Sessions 11–13)

Full plans in `docs/session-plans/session-11-plan.md` … `session-13-plan.md`. No strategy changes across any of these; `zn_macd_pullback` stays as the fixture trade log.

### Session 11 — Reporting v2: Risk Officer's View + Walk-Forward

**Objective:** answer "is this edge real, and is it robust?" with honest numbers.

- **`src/trading_research/eval/stats.py`** (new module). Functions:
  - `bootstrap_metric(values, stat_fn, n_iter=10_000, ci=0.95)` → `(point, lo, hi)`.
  - `deflated_sharpe_ratio(returns, n_trials, skew, kurtosis)` — Lopez de Prado (2014).
  - `probabilistic_sharpe_ratio(sharpe, n_obs, skew, kurtosis, sr_benchmark=0)`.
  - `mar_ratio`, `ulcer_index`, `ulcer_performance_index`, `recovery_factor`, `pain_ratio`, `tail_ratio`, `omega_ratio`, `gain_to_pain_ratio`.
- **Walk-forward runner:** `uv run trading-research walkforward <config>` with purged k-fold + embargo gap over the 16-year ZN dataset. Output embedded in HTML report.
- **Trials registry:** persistent record of every backtest variant run, so deflated Sharpe has the correct `n_trials`.
- **Drawdown forensics, Monte Carlo trade-order shuffle, subperiod stability** — all added to the report.

### Session 12 — Reporting v3: Regime & ML Analytics

**Objective:** answer "when does this strategy work and when doesn't it?" and "what features separate winners from losers?" All analytics are **descriptive, not prescriptive** — they analyze the existing trade log without altering the strategy.

- Per-trade regime tags: volatility, trend, calendar, Fed-cycle, econ-release.
- Per-regime metric breakdowns in the report.
- Winner/loser classifier with purged k-fold CV.
- Permutation importance + SHAP per trade.
- Meta-labeling readout (would a classifier improve the base strategy by filtering signals?).
- Event studies: Fed days, CPI days, NFP days.
- Trade clustering: K-means or HDBSCAN on entry-bar feature vector.

### Session 13 — Reporting v4: Portfolio & Multi-Strategy

**Objective:** lift reporting from single-strategy to multi-strategy.

- `uv run trading-research portfolio <run-id-1> <run-id-2> ...` produces a separate portfolio-level HTML report.
- Correlation matrix of strategy daily P&L.
- Portfolio-level drawdown with per-strategy attribution.
- Sizing comparisons: equal-weight / vol-target / risk-parity / inverse-DD.
- Kelly fraction reference calcs (clearly flagged as *reference*, never as sizing recommendation — per mentor persona's disclaimer).
- Capital efficiency: return on margin, return on peak capital, return on max DD.
- `configs/broker_margins.yaml` new file: TradeStation + IBKR retail margins for ZN, 6A, 6C, 6N and the retail penalty on intercommodity spreads.
- If only one real strategy exists by this point, create two synthetic parameter variants clearly labeled as such for demonstration.

### Beyond Session 13 (implied by `CLAUDE.md`)

- First real rule-based ZN mean-reversion strategy (the `zn_macd_pullback` fixture is explicitly not this).
- Risk module build-out: vol targeting, daily/weekly loss limits, kill switches.
- Paper-trading infrastructure against TradeStation.
- Live-execution layer with idempotent orders and broker reconciliation.

---

## 3. Hallucination / Risk Log

Areas where math, logic, or claims remain unverified or speculative. An inheriting agent should treat each of these as an audit item, not a settled fact.

### Unverified — math/statistics

- **Deflated Sharpe implementation (Session 11 deliverable).** The Lopez de Prado (2014) formula is well-specified but error-prone: getting the `n_trials` count honest depends on the trials registry also being honest. Until the registry is populated retroactively from git history of `configs/strategies/`, any deflated Sharpe reported is **optimistic** (understated `n_trials` → understated deflation).
- **Probabilistic Sharpe Ratio.** Requires higher-moment estimates (skew, kurtosis) of the return distribution. Mean-reversion strategies have notoriously non-normal returns; finite-sample skew/kurt estimates are high-variance. CIs on PSR itself are not planned in Session 11 and should be added.
- **Bootstrap CI for Sharpe on low trade counts.** The Session 09 fixture has 11,887 trades — fine. Any future strategy with <200 trades will produce CIs so wide that "Sharpe 2" and "Sharpe 0" are statistically indistinguishable. Sample-size guardrails in the report have not been spec'd.
- **Walk-forward purge gap sizing.** Session 11 spec mentions "purge and embargo" but does not fix a default. The correct gap depends on the strategy's holding period — for an intraday EOD-flat strategy on 5m bars, 1 trading day is likely sufficient; for multi-day pair holds, longer. The inheriting agent should not default to a constant without thinking about the strategy class.
- **Monte Carlo trade-order shuffle.** Shuffling preserves the trade return *distribution* but destroys path dependence (drawdown sequence). The resulting MC drawdown distribution is therefore a **lower bound** on real-world drawdown risk, not an unbiased estimate. Any report visualization must label this accurately.

### Unverified — logic/engine

- **Fill model under gappy overnight bars.** The pessimistic TP/SL resolver was unit-tested at Session 08 on synthetic bars. Behavior on real overnight gaps (e.g., Fed surprise between RTH close and Globex reopen) has not been characterized.
- **EOD-flat enforcement across DST transitions.** `CLAUDE.md` mandates tz-aware UTC storage and America/New_York display. There is an untested edge around the 02:00 America/New_York spring-forward / fall-back boundary for strategies that straddle that hour.
- **`project_trades_to_tf()` snapping at the day boundary.** The Session 10 fix wired markers to 60m and 1D charts. The snapping convention at the 18:00 ET trade-date boundary (CME convention) has not been spot-checked on a trade that spans the boundary. A trade opened at 17:55 ET and closed at 18:05 ET may render on the wrong trade-date bar on the 1D chart.
- **Back-adjusted continuous contract at rolls.** Session 04 built the ZN continuous across 66 contracts with cumulative adjustment of −27.52 points. Sessions that generate metrics from this series are valid for P&L but **invalid for any price-level condition** (support/resistance, fixed percentage stops from absolute price). No unit test currently flags a strategy that uses absolute price levels against a back-adjusted series.
- **Indicator look-ahead tests.** Session 05 added look-ahead freedom tests for each indicator. These tests verify that indicator value at bar T does not peek at bar T+k for k>0, but they do **not** verify that the indicator at bar T only uses data through bar T-1 under a next-bar-open fill model. That is a stricter condition and is not currently tested.

### Unverified — data integrity

- **September 2023 @ZN roll artifact.** Diagnosed at Session 04 as a TYU23 near-expiry illiquidity event; `known_outages.yaml` updated. The back-adjusted series was validated at Session 05 to confirm the RTH gaps are gone on the adjusted side, but the unadjusted side still has them. Strategies that load unadjusted will hit these. There is no linter flag for "strategy loaded unadjusted and this session is in the outage list."
- **Buy/sell volume coverage.** Session 03 reports 100% coverage on the 14-year ZN pull. This was not re-verified after the Session 04 back-adjustment merge across 66 contracts. A sample audit is warranted before any order-flow strategy consumes the CLEAN layer.
- **Manifest staleness.** Pre-Session-04 CLEAN files were backfilled with manifests in Session 06. Any file mtime-based staleness check that compares against the backfilled manifest timestamp will report a false "not stale" — the manifest is newer than the data it describes.

### Unverified — risk / execution (future)

- **Retail margin penalty on intercommodity spreads.** `CLAUDE.md` claims TradeStation and IBKR do not honor CME/CBOT reduced spread margins and that the retail number is "5×+ the exchange number." This is directionally correct as of 2024–2025 but the exact multiplier varies by broker and by month. `configs/broker_margins.yaml` (Session 13) must be sourced from live broker pages at the time of the session, not copied from documentation.
- **Kill-switch semantics.** Required by `CLAUDE.md` at strategy / instrument / account level. No implementation, no tests, no integration with TradeStation's actual order-cancel endpoint. Entirely speculative until built.
- **Idempotent live orders.** Specified in `CLAUDE.md` as a requirement for any live order. The idempotency scheme (client order ID namespace, replay-on-disconnect semantics, reconciliation loop) is **undesigned.**

### Speculative — strategy claims

- The `zn_macd_pullback` fixture is **not** claimed to have edge. Anyone porting this project must not interpret the 11,887-trade backtest as evidence of a tradeable strategy. It is a fixture for reporting infrastructure and its deflated Sharpe is expected to be low-to-zero.

---

## 4. Gemini Briefing — Executive Summary for the Antigravity Agent

> **You are inheriting a disciplined, honest quant-research codebase — not a production trading system.**
>
> The human (Ibby) is a 25-year trader, 30-year IT, former CISO. He wants a peer, not a chatbot. Two personas live in `.claude/rules/` and load automatically: a **quant mentor** (20-year veteran, blunt, market-structure-aware) and a **data scientist** (statistical integrity officer, allergic to leakage). They are designed to **disagree productively** in front of him. Do not paper over their disagreements to seem cohesive. Ibby synthesizes.
>
> **What is built (through Session 10):**
> 1. Full data pipeline: TradeStation auth → raw pulls → calendar-validated CLEAN layer → versioned FEATURES layer. 16 years of ZN 1m bars, back-adjusted across 66 contracts, resampled to 5m/15m/60m/240m/1D. FX pairs (6A, 6C, 6N) registered but not yet pulled at full history.
> 2. Indicator library with look-ahead freedom tests: ATR, RSI, Bollinger, MACD, SMA, Donchian, ADX, OFI, VWAP. Feature-set YAML (`base-v1`) declares which indicators land in a given FEATURES parquet.
> 3. Backtest engine: next-bar-open fills, pessimistic TP/SL, EOD-flat, MAE/MFE per trade. Fixture strategy `zn_macd_pullback` produces 11,887 trades.
> 4. Reporting v1: 15-section self-contained HTML report (offline, 8.6 MB, dark Plotly), pipeline integrity audit, data dictionary.
> 5. Replay Dash app with 1m/5m/15m/60m/1D toggles and properly-snapped trade markers.
> 6. 307 passing tests.
>
> **What is not built:**
> 1. Risk module (scaffold only — no sizing, no limits, no kill switches).
> 2. ML/regime analytics (Session 12).
> 3. Portfolio reporting (Session 13).
> 4. Walk-forward runner + deflated Sharpe + trials registry (Session 11 — the next work).
> 5. Paper/live execution.
> 6. Any validated tradeable strategy. The fixture strategy is a fixture.
>
> **Five load-bearing rules that, if violated, will rot this project:**
> 1. **CLEAN never contains indicators.** Indicators live in FEATURES only.
> 2. **1-minute bars are the canonical base resolution.** Higher TFs are always resampled, never re-downloaded.
> 3. **Pessimistic defaults.** Next-bar-open fills, stop-wins-ambiguous-bar, pessimistic slippage/commission. Overrides must be logged loudly in config.
> 4. **No threshold fit on the test set.** Any cutoff computed from data that is then used to make a decision evaluated on that same data is leakage. The data-scientist persona will flag this unprompted.
> 5. **Agents do the work; the human provides judgment, credentials, and consent.** Do not ask Ibby to run a command for you. If you have a tool that can do it, do it. The only things he must do personally are: provide secrets, confirm destructive ops, authorize real-money actions, look at screens you cannot see.
>
> **Three pitfalls an inheriting agent is likely to hit:**
> 1. Treating the `zn_macd_pullback` fixture as a candidate for optimization. It is not. It is scaffolding for the reporting build-out.
> 2. Using absolute price conditions against the back-adjusted ZN continuous. Back-adjusted price levels are not real price levels — cumulative adjustment is −27.52 points and non-stationary over the series. P&L math is fine; support/resistance math is not.
> 3. Computing deflated Sharpe with an understated `n_trials`. Until the trials registry is built (Session 11) and retroactively populated, any deflated-Sharpe number is optimistic by an unknown factor.
>
> **Start here:** read `CLAUDE.md`, the two persona files in `.claude/rules/`, `docs/pipeline.md`, and `docs/session-plans/session-11-plan.md`. Then resume at Session 11.
