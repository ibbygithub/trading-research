# Table of Contents

**Trading Research Platform — Operator's Manual, v0.1-draft**

This is the comprehensive Table of Contents for the operator's manual. Every
chapter and every section in every chapter is listed below with a short
description and a status marker:

- **[EXISTS]** — feature is implemented; the chapter documents what is there
- **[PARTIAL]** — feature exists in code but is not surfaced in user-facing
  artifacts; documenting requires both writing the chapter and exposing the
  feature in the report or CLI
- **[GAP]** — feature does not exist yet; the chapter is a specification

A consolidated list of **[GAP]** and **[PARTIAL]** items appears at the end —
this is the platform-completion backlog.

---

## Front Matter (~ 6 pages)

- Title page, copyright, document version
- Change log (every revision dated)
- Foreword from the operator
- Document conventions (audience, marking conventions, code references, schemas)
- How to read this manual (different paths for different needs)
- **Quick-start guide** (one page) — the five commands a user runs most, with
  enough context to proceed without reading the full manual. Lives in
  `docs/manual/00-quick-start.md` and is the entry point for new readers
  and for the operator after long absence
- Quick reference card (one page, every CLI command and its one-line purpose)

---

# Part I — Concepts and Architecture (~ 18 pages)

## Chapter 1 — Introduction (~ 4 pages)

1.1 What this platform is **[EXISTS]** — a research bench for futures strategies,
honest backtesting, and forward validation; explicitly not a live execution
system in v1.0.

1.2 Who it's for **[EXISTS]** — a single experienced operator. Multi-user,
multi-account, role-based access are not goals.

1.3 What it is *not* **[EXISTS]** — not a tutorial system, not a strategy
discovery service, not a black-box optimiser. The operator brings the
hypotheses; the platform tells him whether the evidence supports them.

1.4 Pipeline at a glance **[EXISTS]** — the ten stages from "pull bars" to
"go live," with the explicit boundary at stage 9 between this version of
the platform (research, backtesting, paper) and the future live-execution
phase.

1.5 What "complete" means for v1.0 **[EXISTS]** — the criterion for
declaring the platform done: every chapter in this manual marked
**[EXISTS]**, the cold-start runbook works, and the validate-strategy and
status CLIs ship.

## Chapter 2 — System Architecture (~ 8 pages)

2.1 Component map **[EXISTS]** — modules: data, indicators, strategies,
backtest, eval, replay, risk, stats, core, gui, pipeline, cli, with a one-
sentence purpose for each.

2.2 Data flow diagram **[EXISTS]** — TradeStation → RAW → CLEAN → FEATURES →
strategy → backtest → trade log → eval → report. Where each layer lives,
what writes it, what reads it.

2.3 The three-layer data model **[EXISTS]** — the architectural decision
record (ADR-001) summarised: RAW immutable, CLEAN canonical OHLCV, FEATURES
disposable indicator matrices. The load-bearing rule that CLEAN never
contains indicators.

2.4 Technology stack **[EXISTS]** — Python 3.12, uv, parquet/pyarrow,
pandas, structlog, typer, dash, pandas-market-calendars, pydantic. Why
each was chosen.

2.5 Where state lives **[EXISTS]** — `data/`, `runs/`, `outputs/`, `configs/`,
`.venv/`, `runs/.trials.json`. What's committed, what's rebuilt, what's
ignored.

2.6 The CLI surface **[EXISTS]** — fourteen subcommands organised by
purpose; this is the operator's entry point to everything. Detailed
reference is in Appendix D.

## Chapter 3 — Operating Principles (~ 6 pages)

3.1 The honesty bar **[EXISTS]** — the standing rules from CLAUDE.md
codified: pessimistic fills, leakage prevention, deflated Sharpe over
raw, Calmar as the headline metric, behavioural metrics surfaced.

3.2 The standing rules in detail **[EXISTS]** — each rule with the reason
behind it: 1m base resolution, calendar validation gate, instrument-spec
single source of truth, threshold-fitting on test set is a bug, MAE/MFE
recorded per trade.

3.3 What the platform refuses to do **[EXISTS]** — implicit averaging
down, uncalibrated re-entries, same-bar fills without justification, EOD
flat overrides without override, indicator columns in CLEAN.

3.4 Reasoning by personas (mentor, data scientist, architect) **[EXISTS]** —
how the three persona files in `.claude/rules/` shape every conversation
and why each persona owns a different question.

3.5 What changes in live **[GAP]** — the boundary between research and
live; what the platform will *additionally* require before any real money
is routed: idempotent orders, kill switches, broker reconciliation, daily
loss limits enforced at the broker.

3.6 The CLI-as-API design contract **[EXISTS]** — every operation in the
platform is reachable as a single CLI invocation with clear inputs and
outputs. This is the design contract that keeps a future GUI cheap: a
graphical front-end is a thin shell that calls subprocess on the existing
CLI commands, never a re-implementation. Implications: every command must
exit cleanly, return parseable output (JSON or tabular), and never depend
on an interactive prompt.

---

# Part II — Data Foundation (~ 24 pages)

## Chapter 4 — Data Pipeline & Storage (~ 10 pages) *[sample chapter, written]*

4.1 The three layers in detail
4.2 Directory layout
4.3 Filename conventions
4.4 Manifest schema and staleness rules
4.5 The CME trade-date convention
4.6 The look-ahead rule for HTF projections
4.7 Cold-start checklist
4.8 Adding a new timeframe (worked example)
4.9 What not to do
4.10 Related references

## Chapter 5 — Instrument Registry (~ 5 pages)

5.1 The InstrumentSpec contract **[EXISTS]** — what every instrument must
declare: tick size, tick value, point value, contract size, session hours,
RTH window, calendar, roll convention, default costs.

5.2 Currently registered instruments **[EXISTS]** — ZN, 6E, 6A, 6C, 6N
with full specifications and notes on why each was chosen and why others
(GC) were excluded.

5.3 The TradeStation symbol mapping problem **[EXISTS]** — CME root vs
TradeStation root: ZN→TY, 6E→EC, 6A→AD, 6C→CD, 6N→NE1. Where this lives
in the code and why it matters.

5.4 Adding a new instrument **[EXISTS]** — the procedure: edit
`configs/instruments.yaml`, download contracts, run `rebuild clean
--symbol`, then `rebuild features --symbol`. What can fail and where.

5.5 Calendar awareness **[EXISTS]** — the `pandas-market-calendars`
calendars used (CBOT_Bond, CMEGlobex_FX), what they validate, and what
they don't.

## Chapter 6 — Bar Schema & Calendar Validation (~ 4 pages)

6.1 The canonical 1-minute bar schema **[EXISTS]** — `BAR_SCHEMA` in
`src/trading_research/data/schema.py:53`: required fields, nullable
fields, units, timezones.

6.2 Why two timestamp columns **[EXISTS]** — `timestamp_utc` for compute,
`timestamp_ny` for display; never derive one from the other at read time.

6.3 The validation gate **[EXISTS]** — what `validate_bar_dataset` checks:
duplicate timestamps, negative volumes, inverted high/low, missing bars
against the calendar, buy/sell volume coverage. What is fatal and what is
informational.

6.4 Reading a quality report **[EXISTS]** — the structure of the report
dict and how to interpret each field.

6.5 Schema evolution **[GAP]** — the policy for changing the schema: bump
SCHEMA_VERSION, write a migration, never edit in place. Currently the
migration tooling does not exist; this section specifies it.

## Chapter 7 — Indicator Library (~ 8 pages)

7.1 Catalogue of indicators in base-v1 **[EXISTS]** — eight indicator
families: ATR, RSI, Bollinger, MACD (with derived columns), SMA, Donchian,
ADX, OFI. For each: definition, formula, parameters, the columns produced.

7.2 ATR — Average True Range **[EXISTS]** — formula, default period 14,
typical use as stop distance and volatility scale.

7.3 RSI — Relative Strength Index **[EXISTS]** — formula, default period
14, common thresholds, distributional caveats.

7.4 Bollinger Bands **[EXISTS]** — `bb_mid`, `bb_upper`, `bb_lower`,
`bb_pct_b`, `bb_width`. Standard 20/2.0 default.

7.5 MACD with derived columns **[EXISTS]** — `macd`, `macd_signal`,
`macd_hist`, plus four derived: `hist_above_zero`, `hist_slope`,
`bars_since_zero_cross`, `hist_decline_streak`. Each defined and motivated.

7.6 SMA — Simple Moving Average **[EXISTS]** — period 200 by default.

7.7 Donchian Channels **[EXISTS]** — `donchian_upper`, `donchian_lower`,
`donchian_mid`. Period 20.

7.8 ADX — Average Directional Index **[EXISTS]** — period 14, what
"trend strength" means and what it doesn't.

7.9 OFI — Order-Flow Imbalance **[EXISTS]** — definition based on
buy_volume/sell_volume; null handling; common pitfalls.

7.10 VWAP family **[EXISTS]** — session, weekly, monthly VWAP plus their
1.0σ, 1.5σ, 2.0σ, 3.0σ standard-deviation bands. How each resets.

7.11 Higher-timeframe projections **[EXISTS]** — daily EMA(20/50/200),
daily SMA(200), daily ATR(14), daily ADX(14), daily MACD histogram. The
look-ahead rule: prior session's value, never current.

7.12 Adding a new indicator **[EXISTS]** — file location, registration,
unit-test requirement (no look-ahead), feature-set tag bump.

## Chapter 8 — Feature Sets (~ 5 pages)

8.1 What a feature set is **[EXISTS]** — a versioned, tagged YAML defining
which indicators run, which HTF columns project, which timeframes are built.

8.2 The base-v1 specification **[EXISTS]** — full annotation of
`configs/featuresets/base-v1.yaml`.

8.3 The base-v2 specification **[EXISTS]** — what changed and why
(verify and fill in).

8.4 Forking a feature set **[EXISTS]** — copy YAML, change tag, build,
delete when done. Why tags must be immutable.

8.5 Feature set audit trail **[EXISTS]** — git history of
`configs/featuresets/` is the audit log; how to read it.

8.6 The available feature inventory **[PARTIAL]** — for each registered
instrument and each target timeframe, what feature parquets actually exist
on disk, with date ranges. Currently surfaced manually via inventory CLI;
chapter spec includes a feature-set freshness table in `status` output.

---

# Part III — Strategy Authoring (~ 26 pages)

## Chapter 9 — Strategy Design Principles (~ 4 pages)

9.1 Rules first, ML second **[EXISTS]** — the project's standing position
on complexity. Why a rule-based version must work before any ML wraps it.

9.2 Parameter discipline **[EXISTS]** — the test for whether something
should be a knob, a regime filter, or hard-coded. The cost of every knob
in deflation terms.

9.3 The overfitting smell **[EXISTS]** — when adding a filter is solving a
real problem versus fitting recent losers. Concrete diagnostics: gradient
shape, fold variance, win-rate confidence interval.

9.4 Three dispatch paths **[EXISTS]** — `entry:` (YAML template),
`template:` (registered StrategyTemplate), `signal_module:` (legacy Python
module). When to use each.

9.5 Why YAML by default **[EXISTS]** — the ExprEvaluator design intent: a
non-programmer-readable form that still has type-safety and look-ahead
prevention, with strategy provenance tracked through git.

## Chapter 10 — YAML Strategy Authoring (~ 8 pages)

10.1 Strategy YAML anatomy **[EXISTS]** — top-level keys: `strategy_id`,
`symbol`, `timeframe`, `description`, `feature_set`, `knobs`, `entry`,
`exits`, `backtest`, `higher_timeframes`, `regime_filter`,
`regime_filters`, `time_window`.

10.2 The `entry` block **[EXISTS]** — `long`, `short`, `time_window`,
the `all`/`any` combinators, conflict resolution.

10.3 The `exits` block **[EXISTS]** — `stop` and `target`, long/short
expressions, what NaN does (suppresses entry).

10.4 The `backtest` block **[EXISTS]** — `fill_model`, `eod_flat`,
`max_holding_bars`, `use_ofi_resolution`, `quantity`,
`same_bar_justification`. Defaults and overrides.

10.5 Knobs and parameterization **[EXISTS]** — when to use a knob,
naming conventions, how knobs interact with the sweep tool.

10.6 Time windows **[EXISTS]** — the `entry.time_window` block, UTC-only
times, common patterns.

10.7 Multi-timeframe references **[EXISTS]** — `higher_timeframes` list,
column-name prefixing, what `join_htf` does.

10.8 A complete worked strategy **[EXISTS]** — line-by-line walkthrough
of `configs/strategies/6a-monthly-vwap-fade-yaml-v2b.yaml`.

10.9 Strategy templates (Python path) **[EXISTS]** — when a YAML can't
express what's needed, the `StrategyTemplate` Protocol and how to register
a Python template.

## Chapter 11 — The Expression Evaluator (~ 6 pages)

11.1 Supported expression syntax **[EXISTS]** — column names, knob names,
numeric literals, `+ - * /`, `< > <= >= == !=`, unary minus, parentheses,
`shift(col, n)`. What is rejected and why.

11.2 Name resolution rules **[EXISTS]** — column first, then knob, then
error. Why this order; what happens when a column and a knob share a name.

11.3 Comparison NaN handling **[EXISTS]** — comparisons against NaN
short-circuit to False. The implication for indicator warm-up periods.

11.4 The `shift()` function **[EXISTS]** — exact semantics; why integer
constants only; how to express "previous bar" comparisons.

11.5 What the evaluator refuses **[EXISTS]** — function calls (other than
shift), attribute access, subscripts, lambdas, imports. The security
posture.

11.6 Common patterns **[EXISTS]** — VWAP-band fades, MACD zero crosses,
ATR-scaled stops, Bollinger reversions. Snippets of valid YAML for each.

11.7 Common errors and how to read them **[PARTIAL]** — the evaluator
raises `ValueError` with context; the `validate-strategy` CLI should
surface these before any backtest runs. Currently you see them only when
you run a backtest. **[GAP — to be built in `validate-strategy` CLI]**

## Chapter 12 — Composable Regime Filters (~ 4 pages)

12.1 What a regime filter is **[EXISTS]** — a fitted condition that gates
entries. Why filters are a separate concept from `entry` conditions.

12.2 Built-in filters **[EXISTS]** — `volatility-regime` (percentile of
ATR over a lookback). Parameters and behaviour.

12.3 Inline vs `include` syntax **[EXISTS]** — when to define a filter
inline in the strategy YAML vs reference a shared one in
`configs/regimes/`.

12.4 The `fit_filters` lifecycle **[EXISTS]** — auto-fit on full dataset
in non-rolling backtests; per-fold fit in `run_rolling_walkforward`. The
data-leakage implications.

12.5 Composing multiple filters **[EXISTS]** — list semantics in
`regime_filters`, AND combinator over filters.

12.6 Adding a new regime filter type **[EXISTS]** — implementing the
`RegimeFilter` Protocol, registering with `build_filter`, the
`vectorized_mask` optimisation hook.

## Chapter 13 — Strategy Configuration Reference (~ 4 pages)

13.1 Complete YAML key reference **[EXISTS]** — every legal key in a
strategy YAML, alphabetised, with type, default, and one-sentence purpose.

13.2 Cross-key validation **[EXISTS]** — combinations that are rejected
(`template` AND `entry` is an error), or that produce warnings.

13.3 The default-filling order **[EXISTS]** — what happens when a key is
omitted: code default, YAML default, error.

13.4 Configuration linting **[GAP]** — `validate-strategy` CLI command
specification: load the YAML, evaluate expressions on a 100-bar synthetic
dataset, report any name-resolution failures, expected trade count, key
problems.

---

# Part IV — Backtesting (~ 22 pages)

## Chapter 14 — The Backtest Engine (~ 6 pages)

14.1 Engine design principles **[EXISTS]** — bar-by-bar walk, no
vectorisation in the simulator, auditability over speed.

14.2 Fill models **[EXISTS]** — `next_bar_open` (default) and `same_bar`
(requires justification string).

14.3 Cost model **[EXISTS]** — slippage in ticks per side, commission in
USD per side; defaults from `instruments.yaml`; per-config overrides.

14.4 TP/SL resolution **[EXISTS]** — pessimistic by default (stop wins
when both inside the bar's range); optional OFI-based resolution
(`use_ofi_resolution`).

14.5 EOD flat **[EXISTS]** — what the session-close logic does, when it
fires, why default-on for intraday.

14.6 Max holding bars **[EXISTS]** — the time-stop fallback; how
`max_holding_bars: null` differs from a large number.

14.7 The Mulligan controller **[EXISTS]** — `MulliganController` in
`strategies/mulligan.py`. Re-entries on a fresh signal vs averaging down,
the combined-risk computation, the `MulliganViolation` exit reason.

14.8 What the engine does not do **[EXISTS]** — multi-position sizing,
portfolio-level position limits, broker reconciliation. These are out of
scope for v1.0.

## Chapter 15 — Trade Schema & Forensics (~ 4 pages)

15.1 The TRADE_SCHEMA contract **[EXISTS]** — every field defined in
`src/trading_research/data/schema.py:107`. Trigger vs fill timestamps,
slippage and commission attribution, MAE/MFE.

15.2 Why two pairs of timestamps per trade **[EXISTS]** — entry_trigger_ts
(signal bar) vs entry_ts (fill bar), exit_trigger_ts vs exit_ts. What this
lets the replay app show that other systems can't.

15.3 Exit reasons **[EXISTS]** — `target`, `stop`, `signal`, `eod`,
`time_limit`, `mulligan`. The semantics of each.

15.4 MAE/MFE — Maximum Adverse / Favourable Excursion **[EXISTS]**
formula, how each is tracked from fill bar to exit bar.

15.5 Reading a trade log **[EXISTS]** — the parquet file structure, how
to load it in pandas, what to look for first.

## Chapter 16 — Running a Single Backtest (~ 4 pages)

16.1 The `backtest` CLI command **[EXISTS]** — full option reference,
date filters, output directory.

16.2 Output artefacts **[EXISTS]** — `trades.parquet`,
`equity_curve.parquet`, `summary.json`. What's in each, where they go.

16.3 Reading the summary table **[EXISTS]** — every line in the
`format_with_ci` output explained.

16.4 The trial registry side-effect **[EXISTS]** — every `backtest` run
records a trial in `runs/.trials.json`; what's recorded.

16.5 Common errors and resolutions **[PARTIAL]** — feature parquet
not found, calendar mismatch, knob name typo, expression error. Currently
the error messages are good but scattered; the chapter consolidates them.

## Chapter 17 — The Trader's Desk Report (~ 5 pages)

17.1 What the report shows **[EXISTS]** — sections: equity curve, drawdown
curve, monthly heatmap, trade distribution, MAE/MFE scatter, per-fold
walkforward, statistical headline.

17.2 Generating a report **[EXISTS]** — the `report <run_id>` CLI command,
auto-resolving the latest timestamp directory.

17.3 The pipeline integrity audit **[EXISTS]** — what the audit checks:
data freshness, indicator look-ahead, manifest staleness, code commit at
backtest time.

17.4 The data dictionary **[EXISTS]** — what
`pipeline_integrity.generate_pipeline_integrity_report` produces and how
the manual operator should read it.

17.5 Headline statistical reporting **[PARTIAL]** — currently the report
shows raw Sharpe, Calmar, win-rate point estimates. Deflated Sharpe is
computed in `eval/stats.py` but not in the report header. CIs are computed
but only on demand. **[GAP — surface DSR, CI flags, fold variance in the
report header]**

## Chapter 18 — The Replay App (~ 3 pages)

18.1 What replay shows **[EXISTS]** — bar chart, trade markers (trigger
vs fill), indicator overlays, P&L by date.

18.2 Launching replay **[EXISTS]** — the `replay --symbol` command, port
options, date windows.

18.3 When to use replay **[EXISTS]** — pre-backtest sanity (does my entry
logic look reasonable on the chart?) and post-backtest forensics (why did
this trade lose?).

18.4 Layout reference **[EXISTS]** — the controls in the Dash UI; how
each reacts to date filters and trade-id selection.

---

# Part V — Validation and Statistical Rigor (~ 30 pages)

## Chapter 19 — Headline Metrics (~ 4 pages)

19.1 Why Calmar is the headline **[EXISTS]** — annual return / max
drawdown; why this is more honest than Sharpe for retail mean-reversion.

19.2 Sharpe and what it misses **[EXISTS]** — penalises upside vol; assumes
normal returns; sensitive to sample size. Why we report it but don't
centre it.

19.3 Sortino — the downside-only Sharpe **[EXISTS]** — formula; when it
matters; not the headline because Calmar already addresses the same
concern.

19.4 Profit factor and expectancy **[EXISTS]** — gross_wins / gross_losses
and average net P&L per trade. What each tells you that the others don't.

19.5 Win rate and the breakeven threshold **[EXISTS]** — the formula
WR_be = avg_loss / (avg_win + avg_loss); margin above breakeven as the
key edge metric.

19.6 Drawdown depth and duration **[EXISTS]** — max_drawdown_usd,
max_drawdown_pct, drawdown_duration_days. Why duration is often the more
brutal number.

## Chapter 20 — Behavioural Metrics (~ 3 pages)

20.1 Trades per week **[EXISTS]** — what too-many and too-few both mean.
Tradeable bands by strategy class.

20.2 Max consecutive losses **[EXISTS]** — what counts (zero-P&L trades),
why this matters psychologically.

20.3 Drawdown duration in trading days **[EXISTS]** — the recovery clock;
what an "unrunnable" duration looks like.

20.4 MAE and MFE distributions **[EXISTS]** — what the average MAE tells
you about stop placement; what the average MFE tells you about exit
discipline.

## Chapter 21 — Bootstrap Confidence Intervals (~ 3 pages)

21.1 What bootstrapping does **[EXISTS]** — resampling trade-level returns
with replacement; computing the metric distribution; reporting (p5, p95).

21.2 The metrics bootstrapped **[EXISTS]** — Sharpe, Calmar, win_rate,
expectancy, profit_factor, Sortino. Why these and not others.

21.3 Reading a CI **[EXISTS]** — width matters more than centre; CI
including zero is the kill criterion; small samples produce wide CIs.

21.4 Sample size implications **[EXISTS]** — at 50 trades the CI is so
wide as to be uninformative; at 200 trades it's defensible; at 1000 it's
robust. The trade-count line in the headline.

## Chapter 22 — Walk-Forward Validation (~ 5 pages)

22.1 Why walk-forward **[EXISTS]** — a single train/test split is the
weakest validation; sliding windows test regime robustness.

22.2 Purged walk-forward **[EXISTS]** — `run_walkforward`: signals on
full dataset, splits into folds with gap and embargo. When this is the
right choice (rule-based strategies with no fitted parameters).

22.3 Rolling walk-forward **[EXISTS]** — `run_rolling_walkforward`: per-
fold strategy fit on train window, evaluation on test window. Required
for any strategy with regime-filter thresholds.

22.4 Gap and embargo **[EXISTS]** — the purge between train and test;
the embargo at the start of test; why both, and how to size them.

22.5 Per-fold and aggregated metrics **[EXISTS]** — the per-fold table
(`walkforward.parquet`); the aggregated trade log; what fold variance
tells you.

22.6 The validation gate criterion **[EXISTS]** — "OOS Calmar > 0 across
majority of folds" — and the cases when the literal rule fails the
spirit (huge fold variance, sub-50% WR fold). How to read the gate.

22.7 Walk-forward report integration **[PARTIAL]** — fold table is in
the parquet but not in the HTML report. **[GAP — add fold-variance
section to the Trader's Desk report]**

## Chapter 23 — Deflated Sharpe (~ 4 pages)

23.1 The multiple-testing problem **[EXISTS]** — when N variants are
tested and the best is selected, the raw Sharpe is biased upward.

23.2 The Lopez de Prado correction **[EXISTS]** — the formula for DSR;
inputs (raw Sharpe, number of trials, trial group); the deflation
behaviour as N grows.

23.3 The trial registry's role **[EXISTS]** —
`runs/.trials.json` records every variant; DSR consults this to count
trials within a group. The `parent_sweep_id` field, the `mode` field
("exploration" vs "validation").

23.4 Reading a deflated Sharpe **[EXISTS]** — what a raw 1.8 deflating
to 0.4 actually means; when to walk away.

23.5 Surfacing DSR in reports **[PARTIAL]** — the metric is computed in
`eval/stats.py` but is not in the `format_with_ci` output or the HTML
report header. **[GAP — surface DSR alongside raw Sharpe in headline
output]**

## Chapter 24 — Stationarity Suite (~ 3 pages)

24.1 Why stationarity matters **[EXISTS]** — mean reversion assumes the
spread or indicator returns to a mean; non-stationary series will fail
silently.

24.2 ADF test — Augmented Dickey-Fuller **[EXISTS]** — null hypothesis,
interpretation of the p-value, common pitfalls.

24.3 Hurst exponent **[EXISTS]** — H<0.5 mean-reverting, H=0.5 random
walk, H>0.5 trending. The estimator used and its limitations.

24.4 Ornstein-Uhlenbeck half-life **[EXISTS]** — fitting the OU process
and extracting the half-life of mean reversion. When the estimate is
trustworthy.

24.5 The `stationarity` CLI command **[EXISTS]** — running the suite,
reading the output: the parquet, JSON, and Markdown report.

## Chapter 25 — Distribution Analysis (~ 3 pages)

25.1 Return distribution diagnostics **[EXISTS]** — skew, kurtosis,
normality tests; when Sharpe lies because of fat tails.

25.2 Tail-risk metrics **[EXISTS]** — VaR, expected shortfall (CVaR);
what these add over max-drawdown.

25.3 The `eval/distribution.py` module **[EXISTS]** — what it computes,
how to invoke it programmatically.

## Chapter 26 — Monte Carlo Simulation (~ 3 pages)

26.1 Trade-order Monte Carlo **[EXISTS]** — shuffling the realised trade
sequence to estimate the distribution of P&L paths and drawdowns.

26.2 What this catches that bootstrap doesn't **[EXISTS]** — path
dependence (a strategy's worst drawdown depends on trade order, not just
the trade set).

26.3 The `eval/monte_carlo.py` module **[EXISTS]** — invocation, outputs,
report integration.

## Chapter 27 — Regime Metrics & Classification (~ 3 pages)

27.1 Regime-conditioned performance **[EXISTS]** — splitting backtest
results by external regime (volatility, trend, day of week, hour) and
reporting per-regime metrics.

27.2 The `eval/regime_metrics.py` module **[EXISTS]** — what splits are
supported, how to add a new one.

27.3 Regime classifier **[EXISTS]** — `eval/classifier.py`, what it
labels, how to consume the labels in regime filters.

## Chapter 28 — Subperiod Analysis (~ 2 pages)

28.1 Performance by year, month, day-of-week, hour **[EXISTS]** — the
splits and what each surface.

28.2 The `eval/subperiod.py` module **[EXISTS]** — invocation and output.

## Chapter 29 — Drawdown Forensics (~ 2 pages)

29.1 Per-drawdown decomposition **[EXISTS]** — every drawdown's start,
trough, recovery; depth and duration.

29.2 Recovery curves and ulcer index **[EXISTS]** — what the ulcer
index tells you that max drawdown alone doesn't.

29.3 The `eval/drawdowns.py` and `portfolio_drawdown.py` modules
**[EXISTS]** — when to use which; correlation of drawdowns across
strategies.

## Chapter 30 — Event Studies & Blackout Filtering (~ 2 pages)

30.1 The blackout calendars **[EXISTS]** — FOMC, CPI, NFP dates in
`configs/calendars/`. Manually verified; how to update.

30.2 Wiring blackout into a strategy **[EXISTS]** — the
`event_blackout` module; how to express in YAML; entry vs exit
behaviour on event days.

30.3 Event-conditioned performance **[EXISTS]** — `eval/event_study.py`:
how a strategy performs around events; how to read the output.

---

# Part VI — Parameter Exploration (~ 12 pages)

## Chapter 31 — The Sweep Tool (~ 4 pages)

31.1 When to sweep **[EXISTS]** — exploring a knob's effect on a clean
gradient; mapping a tradeable region.

31.2 When NOT to sweep **[EXISTS]** — searching for "the best parameter"
on the same data you'll evaluate on. The deflated Sharpe consequence.

31.3 The `sweep` CLI command **[EXISTS]** — `--param key=v1,v2,v3`
syntax; cartesian-product expansion; how knobs override the YAML config.

31.4 Sweep ID tracking **[EXISTS]** — every sweep gets a hex ID; trials
share the `parent_sweep_id`; how to filter the leaderboard by sweep.

31.5 Reading a sweep gradient **[EXISTS]** — monotonic vs non-monotonic;
gradient slope as evidence; flat negative as a signal-quality verdict.

31.6 Common sweep mistakes **[EXISTS]** — sweeping too many dimensions
at once; sweeping after the validation gate; not recording the rationale.

## Chapter 32 — Trial Registry & Leaderboard (~ 4 pages)

32.1 The trial JSON format **[EXISTS]** — every recorded field; how
records are appended; the dedup question (currently no dedup).

32.2 Mode tagging **[EXISTS]** — `exploration` vs `validation` mode;
why this matters for DSR.

32.3 The `leaderboard` CLI command **[EXISTS]** — filter by any field,
sort by any metric, write HTML.

32.4 Leaderboard CI surfacing **[PARTIAL]** — currently raw metrics
only; the leaderboard should show CI ranges per row. **[GAP — add CI
columns to leaderboard table and HTML]**

32.5 Migrating older trials **[PARTIAL]** — eighteen pre-session-35
trials have `mode="unknown"`; a `migrate_trials` helper exists. **[GAP
— bind to a CLI subcommand, document]**

## Chapter 33 — Multiple-Testing Correction (~ 2 pages)

33.1 Why correction matters **[EXISTS]** — testing 50 features and
picking the lowest p-value inflates false-discovery rate.

33.2 Bonferroni vs Benjamini-Hochberg **[EXISTS]** — when each applies;
the trade-offs.

33.3 The `stats/multiple_testing.py` module **[EXISTS]** — invocation
and output.

## Chapter 34 — Composite Ranking (~ 2 pages)

34.1 Why composite ranking **[EXISTS]** — when no single metric tells
the full story; the design from `docs/design/composite-ranking.md`.

34.2 The `eval/ranking.py` module **[EXISTS]** — how strategies are
scored across multiple metrics; the weights; when to override defaults.

---

# Part VII — Risk and Position Sizing (~ 14 pages)

## Chapter 35 — Risk Management Standards (~ 3 pages)

35.1 The standing rules **[EXISTS]** — daily and weekly loss limits;
position limits; kill switches at strategy/instrument/account level.

35.2 What the platform enforces today **[PARTIAL]** — backtest engine
honours per-trade risk via stops; loss limits not enforced in the
simulator. **[GAP — daily loss limit hook in BacktestEngine]**

35.3 What the platform will enforce in live **[GAP]** — broker-side
limits, kill switches with audit trail, idempotent reconciliation.

## Chapter 36 — Position Sizing (~ 4 pages)

36.1 Volatility targeting (default) **[EXISTS]** — sizing to a target
dollar volatility; the formula; the ATR input.

36.2 Fixed quantity **[EXISTS]** — `quantity: 1` in the YAML; the right
default for early backtests.

36.3 Kelly sizing **[EXISTS]** — `eval/kelly.py`; full and half Kelly;
when this is appropriate; why it's never the default.

36.4 The `eval/sizing.py` module **[EXISTS]** — sizing helpers and the
recipe for a custom sizer.

36.5 Sizing in walk-forward and live **[GAP]** — sizing must adapt to
realised volatility, not in-sample volatility. Specification for the
adaptive sizer.

## Chapter 37 — Capital Allocation (~ 2 pages)

37.1 Per-strategy capital **[EXISTS]** — `eval/capital.py`; allocating
notional capital per strategy.

37.2 Portfolio-level constraints **[EXISTS]** — the helpers in
`eval/portfolio.py`; what's enforced today.

37.3 Capital allocation in live **[GAP]** — the spec for live capital
allocation: account-level constraints, broker margin reconciliation.

## Chapter 38 — Re-entries vs Averaging Down (~ 3 pages)

38.1 The distinction **[EXISTS]** — fresh-signal re-entry (legitimate)
vs price-based add (the cardinal sin).

38.2 The Mulligan controller **[EXISTS]** — `strategies/mulligan.py`,
how a re-entry is gated, the combined-risk computation.

38.3 Authoring a re-entry strategy **[EXISTS]** — YAML pattern;
configuration; what the trade log shows.

38.4 What the platform refuses **[EXISTS]** — averaging down; how the
Mulligan check fires `MulliganViolation`.

## Chapter 39 — Pairs and Spread Trading (~ 2 pages)

39.1 Pairs strategy structure **[GAP]** — the YAML extension required
for pairs (two symbols, weight ratio, spread definition); not yet
supported in the YAML grammar.

39.2 Spread margin reality **[EXISTS]** — exchange-spread margins do
not apply at TradeStation/IBKR retail; broker margin must be computed
separately.

39.3 The `configs/broker_margins.yaml` reference **[EXISTS]** — what's
recorded today, how to extend.

---

# Part VIII — Portfolio Analytics (~ 12 pages)

## Chapter 40 — Portfolio Reports (~ 3 pages)

40.1 What the portfolio report shows **[EXISTS]** — the
`portfolio` CLI command; aggregated equity, per-strategy contribution,
correlation, drawdown.

40.2 The `eval/portfolio_report.py` module **[EXISTS]** — invocation,
output structure.

40.3 Reading the portfolio data dictionary **[EXISTS]** —
`eval/data_dictionary_portfolio.py` output and conventions.

## Chapter 41 — Correlation Analysis (~ 2 pages)

41.1 Strategy correlation **[EXISTS]** — `eval/correlation.py`; what's
correlated (returns, drawdowns, regime exposure).

41.2 The diversification myth **[EXISTS]** — when "uncorrelated"
strategies are correlated in tail events.

## Chapter 42 — Portfolio Drawdown (~ 2 pages)

42.1 Aggregated drawdown analysis **[EXISTS]** — `eval/portfolio_drawdown.py`.

42.2 Recovery characteristics **[EXISTS]** — multi-strategy recovery
curves; when correlated drawdowns destroy the case for the portfolio.

## Chapter 43 — Strategy Clustering (~ 2 pages)

43.1 Clustering by performance fingerprint **[EXISTS]** —
`eval/clustering.py`; UMAP-based clustering; reading the output.

43.2 SHAP-based feature attribution **[EXISTS]** — `eval/shap_analysis.py`;
when this is useful (ML strategies); pitfalls.

## Chapter 44 — Meta-Labelling (~ 2 pages)

44.1 The Lopez de Prado approach **[EXISTS]** — `eval/meta_label.py`;
training a secondary model on the primary signal's confidence.

44.2 When to consider meta-labelling **[EXISTS]** — only after a primary
strategy passes the validation gate; never as a substitute for a real
signal.

---

# Part IX — The Validation Gate (~ 10 pages)

## Chapter 45 — The Gate Workflow (~ 3 pages)

45.1 Exploration to candidate to gate **[EXISTS]** — the three-stage
research lifecycle the project follows; what each stage produces.

45.2 The mode field **[EXISTS]** — `exploration` vs `validation`; how
this changes deflation, reporting, and what the leaderboard shows.

45.3 Pre-gate checklist **[EXISTS]** — data quality report current,
strategy YAML linted, sweep gradient consistent, walk-forward complete.

## Chapter 46 — Pass/Fail Criteria (~ 3 pages)

46.1 Backtest criteria **[EXISTS]** — net positive after costs, trade
count >= 100, drawdown duration < 2 years.

46.2 Walk-forward criteria **[EXISTS]** — OOS Calmar > 0 in majority
of folds; aggregated Calmar > 0.1; fold variance bounded.

46.3 Statistical criteria **[EXISTS]** — DSR > 0.5; bootstrap CI on
Calmar above zero; PSR > 0.95.

46.4 Behavioural criteria **[EXISTS]** — max consec losses < 10;
trades/week < 40; drawdown duration psychologically tolerable.

46.5 The override path **[EXISTS]** — when a metric fails but the
strategy is still promoted, the override must be in writing in the
trader's-desk report.

## Chapter 47 — Promoting to Paper (~ 2 pages)

47.1 What changes at promotion **[GAP]** — the strategy moves from
`runs/<id>/` to a paper-trading queue; the broker connection becomes
relevant.

47.2 Paper-trading expectations **[GAP]** — minimum duration, kill
switches active, daily monitoring requirements.

47.3 Promotion record **[GAP]** — the artefact that records "this
strategy was promoted on date X with config Y at code commit Z."

## Chapter 48 — The Live Gate (~ 2 pages)

48.1 Pre-live checklist **[GAP]** — paper performance matches backtest
within tolerance; daily/weekly loss limits configured; reconciliation
verified.

48.2 What goes live, what doesn't **[GAP]** — kill switches, idempotent
order routing, broker fill reconciliation. The live system architecture
is out of scope for v1.0 and is referenced here only for completeness.

---

# Part X — Reference (~ 26 pages)

## Chapter 49 — CLI Command Reference (~ 12 pages)

49.1 `verify` **[EXISTS]** — option list, behaviour, exit codes.
49.2 `backfill-manifests` **[EXISTS]**
49.3 `rebuild clean` **[EXISTS]**
49.4 `rebuild features` **[EXISTS]**
49.5 `pipeline` **[EXISTS]**
49.6 `inventory` **[EXISTS]**
49.7 `replay` **[EXISTS]**
49.8 `backtest` **[EXISTS]**
49.9 `report` **[EXISTS]**
49.10 `walkforward` **[EXISTS]**
49.11 `stationarity` **[EXISTS]**
49.12 `portfolio` **[EXISTS]**
49.13 `sweep` **[EXISTS]**
49.14 `leaderboard` **[EXISTS]**
49.15 `validate-strategy` **[GAP]** — full specification for
implementation.
49.16 `status` **[GAP]** — full specification for implementation.

Each subsection includes: synopsis, options, examples, exit codes,
output format, common errors, see-also.

## Chapter 50 — Configuration Reference (~ 6 pages)

50.1 `configs/instruments.yaml` schema **[EXISTS]**
50.2 `configs/featuresets/<tag>.yaml` schema **[EXISTS]**
50.3 `configs/strategies/<name>.yaml` schema **[EXISTS]**
50.4 `configs/regimes/<name>.yaml` schema **[EXISTS]**
50.5 `configs/calendars/<event>_dates.yaml` schema **[EXISTS]**
50.6 `configs/broker_margins.yaml` schema **[EXISTS]**

## Chapter 51 — File Layout Reference (~ 3 pages)

51.1 The repository tree **[EXISTS]**
51.2 What's committed, what's rebuilt, what's ignored **[EXISTS]**
51.3 Run output structure (`runs/<strategy_id>/<ts>/`) **[EXISTS]**
51.4 Outputs structure (`outputs/`) **[EXISTS]**
51.5 The `.trials.json` file **[EXISTS]**

## Chapter 52 — Logging & Observability (~ 4 pages)

52.1 Structured logging with structlog **[PARTIAL]** — structlog is
imported and used in roughly 10 of the platform's 80+ modules
(`backtest/engine.py`, `backtest/walkforward.py`, `backtest/fills.py`,
`backtest/multiframe.py`, `cli/sweep.py`, `eval/leaderboard.py`,
`eval/ranking.py`, `eval/trials.py`, `strategies/mulligan.py`,
`utils/logging.py`). Hot paths in `data/`, `indicators/`, `pipeline/`,
`replay/`, `eval/` mostly do not log. The standing rule says "structlog,
not print()" but enforcement is partial. **[GAP — bring all hot-path
modules under structlog with a consistent field schema: run_id, symbol,
timeframe, stage, action, outcome]**

52.2 Run IDs and correlation **[PARTIAL]** — backtest runs are tagged
with a timestamp directory; sweep runs share a `sweep_id`; but there is
no single `run_id` that flows through all pipeline stages from data
download → backtest → report. **[GAP — define a run_id field in the
shared log schema]**

52.3 Log file locations **[GAP]** — structlog currently logs to stderr
only. There is no rotating file logger and no retention policy.
**[GAP — add a configurable file logger with rotation and a retention
policy; default 30 days]**

52.4 The observability ladder **[GAP]** — what a v1.0-quality
observability layer looks like: stage-level event log, per-run summary
log, errors-only log, plus a `tail-log` CLI subcommand that filters by
run_id and field.

## Chapter 53 — Schema Reference (Appendices A–C) (~ 3 pages)

A. BAR_SCHEMA in full **[EXISTS]**
B. TRADE_SCHEMA in full **[EXISTS]**
C. Manifest schema in full **[EXISTS]**

---

# Part XI — Operations and Troubleshooting (~ 12 pages)

## Chapter 54 — Cold-Start Procedure (~ 4 pages)

54.1 Pre-flight checks **[GAP — to be written for v1.0]** — what to
verify before doing anything: uv installed, Python 3.12, git clean,
TradeStation credentials in env.

54.2 The seven-step cold start **[EXISTS]** — from the existing
`docs/pipeline.md` cold-start checklist; reformatted for the manual.

54.3 The 30-minute first run **[GAP]** — the canonical "from clean
clone to first published report" path that proves the platform works
without agent assistance.

## Chapter 55 — Common Errors & Resolutions (~ 4 pages)

55.1 Data-layer errors **[EXISTS]** — missing manifests, stale
sources, calendar mismatches, gap-validation failures.

55.2 Strategy-layer errors **[EXISTS]** — name resolution, expression
syntax, regime-filter not fitted, dispatch ambiguity.

55.3 Backtest-layer errors **[EXISTS]** — invalid signals, missing
columns, fill-model misuse, EOD edge cases.

55.4 Statistical-layer errors **[EXISTS]** — too few trades for CI,
walk-forward fold too small, deflation undefined.

55.5 Environment errors **[EXISTS]** — uv not found, Python version
mismatch, dependency conflicts.

## Chapter 56 — Maintenance (~ 4 pages)

56.1 Adding a new instrument **[EXISTS]** — the procedure, where to
verify, what to watch for. Cross-reference to the GC worked example in
§4.12.

56.2 Rebuilding features after an indicator change **[EXISTS]** — when
to bump the feature-set tag, when to extend in place (never).

56.3 Migrating after a schema change **[GAP]** — the migration tooling
spec; currently absent.

## Chapter 56.5 — Storage Management & Cleanup (~ 6 pages)

> Why this chapter exists: in 30 days the project went from ~1.5 GB to
> 4+ GB and from a few hundred files to over 21,000 files (counting
> sweep run outputs, trial registry growth, and per-contract RAW files).
> The platform has no automated cleanup. This chapter specifies what
> should be retained, what should be reaped, and the CLI commands that
> enforce the policy.

56.5.1 Per-instrument disk footprint **[EXISTS — to document]** — each
fully-built instrument (16-year history, all timeframes, base-v1 features)
costs roughly **900 MB to 1 GB** on disk. Worked example: at four
instruments (ZN, 6E, 6A, 6C) the platform uses 3.7 GB. Adding one
instrument (e.g., ES, GC, CL) at the same coverage adds approximately
the same amount. The detailed breakdown by layer is in §4.13.

56.5.2 What grows over time **[EXISTS — to document]** —

- `data/raw/contracts/` grows by one parquet per quarterly contract per
  instrument per year (~4 files/instrument/year). Plus manifest sidecars.
- `data/clean/` grows by one file per instrument per timeframe per
  refresh date (currently the date suffix changes when the source range
  extends). Old date-stamped files are not auto-deleted.
- `data/features/` grows the same way per feature-set tag.
- `runs/` grows by one timestamped directory per backtest, per walk-
  forward, per sweep variant. Each contains `trades.parquet`,
  `equity_curve.parquet`, `summary.json`, and (for `report`) the HTML
  artefacts.
- `runs/.trials.json` grows by one entry per trial; never pruned.
- `outputs/` grows with leaderboards, exploration results, work logs.

56.5.3 Cleanup CLI commands **[GAP]** — specification for what's needed:

- **`trading-research clean runs --strategy <id> --keep-last N`** — keep
  the N most recent run timestamps for a strategy, archive the rest to
  `outputs/archive/runs/<strategy_id>/<YYYY-MM>.tar.gz`, delete the
  originals.
- **`trading-research clean runs --older-than 90d`** — bulk archive runs
  older than the cutoff.
- **`trading-research clean canonical --keep-latest`** — for each
  (symbol, timeframe, adjustment) tuple, keep only the parquet whose
  date suffix is the most recent and reap the older date-stamped
  variants. Manifest-aware: refuses to delete a file whose manifest is
  cited as a source in a non-deleted FEATURES manifest.
- **`trading-research clean features --tag <tag>`** — delete all
  FEATURES files for a feature-set tag (use when retiring an experiment
  tag).
- **`trading-research clean trials --keep-mode validation`** — prune
  exploration-mode trials older than N days; preserve validation-mode
  trials indefinitely.
- **`trading-research clean dryrun`** mode (default) — print what would
  be deleted, including total bytes reclaimed, without acting.

56.5.4 Retention policy (default) **[GAP]** —

- RAW: never automatically deleted (re-download cost is high).
- CLEAN: keep the latest date-stamped variant per (symbol, timeframe,
  adjustment); archive older variants to `outputs/archive/clean/`.
- FEATURES: keep the latest per (symbol, timeframe, feature-set-tag);
  archive others.
- runs/: keep last 10 runs per strategy + every validation-gate run;
  archive the rest after 90 days.
- trials/: keep validation-mode trials forever; prune exploration-mode
  trials > 180 days old (they still appear in the archive).
- outputs/work-log/: keep all (these are the project's narrative history;
  small).
- outputs/archive/: cold storage; never deleted by automated policy.

56.5.5 Intermediate-file inventory **[EXISTS — to verify]** — the
pipeline's stages largely write directly to the canonical parquet path
without intermediate temp files. Exceptions to verify and document:
the data downloader (does it stream to a temp before atomic rename?),
the back-adjuster (does it accumulate in memory or scratch?). Any temp
files identified should land under `data/.tmp/` and be cleaned at end
of run.

56.5.6 The growth-rate forecast table **[EXISTS — to document]** — for
each registered instrument, expected disk usage at full coverage
(16-year history, 1m base, 5/15/60/240/1D CLEAN, 4 timeframes of base-v1
FEATURES). Forecast columns: contracts/year × years × bytes/contract,
rolled-up totals. Allows the operator to plan disk capacity before
adding ES, NQ, GC, CL, RB, ZB, etc.

56.5.7 What never gets cleaned **[EXISTS]** — RAW contracts, manifest
sidecars (until the parquet they describe is deleted), `outputs/
work-log/`, `runs/.trials.json` validation-mode entries, the
`outputs/archive/` cold-storage tree.

## Chapter 57 — Versioning and Compatibility (~ 2 pages)

## Chapter 57 — Versioning and Compatibility (~ 2 pages)

57.1 Code versioning policy **[EXISTS]** — feature branches, develop,
main; the rule about who merges to main.

57.2 Feature-set versioning **[EXISTS]** — tags are immutable.

57.3 Schema versioning **[GAP — schema migration tooling needed]** —
SCHEMA_VERSION conventions; the migration policy.

57.4 Manual versioning **[EXISTS]** — this manual versions
independently of code; what triggers a manual revision.

---

# Part XII — Extension and Integration (~ 14 pages)

> Why a separate part: the chapters in Parts I–XI describe the platform
> as it operates today. Part XII is the spec for two large extension
> capabilities the operator has flagged as important for long-term
> usability — bringing in indicators authored elsewhere, and wrapping
> the CLI in a friendlier launcher. Both are post-v1.0 work that must
> not block v1.0 acceptance, but that are architecturally significant
> enough to warrant manual chapters now.

## Chapter 58 — TradingView Indicator Import (~ 8 pages)  **[GAP]**

58.1 Why this matters **[GAP]** — TradingView's Pine Script community
publishes hundreds of indicators per week. Many are subtle variations
on standard patterns (different smoothing, different breakout
definition, different volatility regime). Being able to bring a Pine
Script indicator into the platform without rewriting it from scratch
expands the testable hypothesis space substantially.

58.2 Scope: what's supported, what's not **[GAP]** — the realistic
target for v1.0-of-this-feature is a translation layer that handles
standard Pine Script primitives: `ta.sma`, `ta.ema`, `ta.rsi`,
`ta.macd`, `ta.atr`, `ta.bb`, `ta.cross`, `ta.crossover`, `ta.pivothigh`,
`ta.pivotlow`, basic arithmetic, comparison, conditional, plot/plotshape.
*Not* supported in v1.0 of the feature: drawing primitives, complex
state machines, custom security() calls across timeframes, Pine v5+
matrix types. Unsupported constructs produce a clear error pointing to
which Pine line is the problem.

58.3 The intake workflow **[GAP]** — the operator pastes Pine Script
into a markdown file at `imports/tradingview/<name>.md`. The
`trading-research import-pine <file>` command parses it, translates
supported constructs to Python, and writes
`src/trading_research/indicators/imported/<name>.py` plus a registration
entry. The translation is deterministic and the generated file includes
a reference comment to the source markdown.

58.4 Verifying a translated indicator **[GAP]** — the auto-generated
file includes a unit-test stub that loads a known reference dataset and
checks the indicator output against expected values. The first run of
the indicator on a small reference set is the operator's chance to
verify the translation matches the Pine original; differences (e.g.,
TradingView's repaint behaviour vs the platform's strict no-look-ahead
rule) are flagged as comments in the generated code.

58.5 What this does NOT do **[GAP]** — does not import full Pine Script
strategies (only indicators); does not preserve TradingView-specific
visualisation (plots, colours, alerts); does not auto-register the
indicator in any feature set (the operator decides whether the new
indicator belongs in the canonical feature set or in an experimental
tag).

58.6 Eventual end state — direct TradingView connector **[GAP, post-v1.0]**
— the operator is interested in exploring a Claude-Code → TradingView
connector that pulls indicator code directly via API. This is a
research item, not a v1.0 deliverable, and is captured here so it is not
lost.

## Chapter 59 — Interactive Launcher / GUI Wrapper (~ 6 pages)  **[GAP]**

59.1 Why this is post-v1.0 (and why it's worth building) **[GAP]** —
the platform's CLI is the right primitive for power users and for
agents, but for a returning operator after long absence it imposes a
memory tax. Remembering whether a run wants `--from`, `--start`, or
`--from-date`, or whether the leaderboard filter syntax is `key=value`
or `key:value`, is friction that a launcher removes. The launcher must
be additive to the CLI, never a replacement.

59.2 Form factors considered **[GAP]** —

- **`trading-research interactive`** — text user interface (TUI) using
  `textual` or `prompt_toolkit`. Menu-driven; arrow keys; renders
  current data inventory, last 5 runs, and a command picker. Each
  selection translates to a CLI invocation that is logged and shown.
  This is the recommended v1 form because it preserves the CLI-as-API
  design and ships in a single Python process without a browser
  dependency.

- **Web GUI (Dash or FastAPI + small SPA)** — browser-served front-end
  with the same calls. Dash is already a dependency for the replay
  app, so reusing it for the launcher is cheap. This is the v2 form,
  appropriate when the operator wants the GUI accessible from another
  machine on the LAN.

- **Desktop app** — out of scope. The browser form gives the same
  ergonomics with much less packaging overhead.

59.3 Specification: the v1 TUI **[GAP]** — top-level menu has six
items: **(1) Data**, **(2) Strategy**, **(3) Backtest**, **(4) Validate**,
**(5) Reports**, **(6) Maintenance**. Each opens a sub-menu that maps
to the relevant CLI commands. Every action prints the equivalent CLI
command before executing it, so the operator learns the CLI and can
script later if desired.

59.4 What the launcher does NOT do **[GAP]** — re-implement business
logic; hold strategy state; provide live-trading controls. It is a
shell over the existing `trading-research <subcommand>` invocations.

59.5 Logging and audit **[GAP]** — every action initiated through the
launcher is logged with `source=interactive` so the run history
distinguishes launcher-initiated runs from script-initiated runs.

---

# Appendices (~ 12 pages)

- **Appendix A** — Bar schema (full) **[EXISTS]**
- **Appendix B** — Trade schema (full) **[EXISTS]**
- **Appendix C** — Manifest schema (full) **[EXISTS]**
- **Appendix D** — CLI command reference (full output of `--help` for each) **[EXISTS]**
- **Appendix E** — Configuration reference (every YAML key, type, default) **[EXISTS]**
- **Appendix F** — Glossary **[EXISTS — to be compiled]**
- **Appendix G** — Index **[EXISTS — to be compiled]**

---

# Gap List — the platform-completion backlog

The following items are marked **[GAP]** or **[PARTIAL]** in the chapter
descriptions above. Each entry names the chapter it appears in and the work
required.

### [GAP] — features that do not yet exist

| Chapter | Item | Work required | Sessions | Priority |
|---------|------|---------------|----------|----------|
| 5 | Consolidate instrument loaders | Migrate `data.instruments` reads off `configs/instruments.yaml`; both code paths read from `configs/instruments_core.yaml`; delete `configs/instruments.yaml` and the legacy nested-schema loader | 0.5 | v1.0 |
| 6.5 | Schema migration tooling | Migration helper + tests; backfill policy | 1 | v1.0 |
| 11.7 / 13.4 / 49.15 | `validate-strategy` CLI | Lint a YAML, dry-run on 100 bars, report | 1 | v1.0 |
| 49.16 | `status` CLI | Show data freshness, last 5 backtests, registered strategies | 0.5 | v1.0 |
| 35.2 | Daily loss limit in BacktestEngine | Hook into engine, fail-fast trade rejection | 0.5 | v1.0 |
| 52.1–52.4 | Logging coverage + run_id + file logger | Bring all hot-path modules under structlog; consistent fields; rotating file logger; tail-log subcommand | 1 | v1.0 |
| 56.5.3 | Storage cleanup CLI subcommands (`clean runs/clean/features/trials`) | Implement five `clean` subcommands with dry-run default, archive-then-delete behaviour, manifest-aware safety | 1 | v1.0 |
| 56.5.6 | Per-instrument growth-rate forecast | Document and surface in `status` output | 0.25 | v1.0 |
| 56.3 | Schema migration runbook | Procedure documentation post-tooling | 0.25 | v1.0 |
| 54.1 / 54.3 | Cold-start runbook | `docs/usage.md` written + verified end-to-end | 0.5 | v1.0 |
| Front matter | Quick-start guide | One-page entry point | 0.25 | v1.0 |
| 17.5 / replay | Trade-overlay charts in backtest report | Integrate replay app charts into HTML report; trades visible on price chart | 1 | post-v1.0 (low priority) |
| 39.1 | Pairs/spread strategy support | YAML extension, second-symbol loader, spread eval | 1.5 | post-v1.0 |
| 47 / 48 | Paper-trading and live-execution path | Out of scope for v1.0 — separate phase | — | post-v1.0 |
| 58 | TradingView Pine Script indicator import | Pine→Python translator for supported subset; `import-pine` CLI | 2–3 | post-v1.0 |
| 58.6 | Direct TradingView API connector | Research and prototype only; integration with Claude Code | — | post-v1.0 (research) |
| 59 | Interactive launcher (TUI) | `trading-research interactive` menu wrapper over CLI | 1.5 | post-v1.0 |
| 59 | Web GUI (Dash) | Browser front-end calling CLI commands | 2 | post-v1.0 (v2 form factor) |

### [PARTIAL] — features computed but not surfaced

| Chapter | Item | Work required | Sessions |
|---------|------|---------------|----------|
| 8.6 | Feature inventory in `status` | Surface in `status` CLI output | (with status) |
| 16.5 / 55 | Common-error consolidation | Documentation only | 0.25 |
| 17.5 | DSR / fold variance / CI flags in report header | Modify `eval/report.py` template | 1 |
| 22.7 | Walk-forward fold table in report | Add section to HTML report | (with 17.5) |
| 23.5 | DSR in `format_with_ci` headline | Add line to bootstrap.py output | 0.25 |
| 32.4 | CI columns in leaderboard | Modify `eval/leaderboard.py` and HTML | 0.5 |
| 32.5 | `migrate-trials` CLI binding | Wire existing helper to a subcommand | 0.25 |

### Summary — total estimated remaining work

**v1.0 code-only work** (everything marked v1.0 priority above):
approximately **6–7 focused sessions**.

The post-v1.0 items (pairs/spread, paper/live, TradingView import, GUI
launcher, trade-overlay charts) are explicitly out of scope for v1.0
acceptance and should not block it.

The v1.0 backlog, in priority order:

1. **Surface the existing statistical rigor** (chapters 17.5, 22.7, 23.5,
   32.4, 8.6) — one session.
2. **Ship the deferred CLIs** `validate-strategy`, `status`,
   `migrate-trials` (chapters 49.15, 49.16, 32.5) — one session.
3. **Storage management & cleanup** (chapter 56.5: clean CLI subcommands,
   retention policy, growth-rate forecast) — one session.
4. **Logging and observability** (chapter 52: structlog hot-path coverage,
   run_id, rotating file logger, tail-log) — one session.
5. **Cold-start runbook + quick-start guide** (chapters 54, front matter) —
   one session.
6. **Schema migration tooling and daily loss limit** (chapters 6.5, 35.2,
   56.3) — one session.
7. **Manual writing** — one session per 30 pages, approximately seven
   sessions to complete every chapter at the quality bar of Chapter 4
   (the chapter count grew with the additions in this revision).

A reasonable interpretation: **13–14 sessions to v1.0 of the platform
with manual, including the manual itself**. If the manual is written
separately, the code-only work compresses to **6–7 sessions**.

Post-v1.0 (separate phase): TradingView Pine import (2–3 sessions),
interactive launcher TUI (1.5), web GUI (2), pairs strategy support
(1.5), trade-overlay charts in report (1), then the eventual paper-
trading and live-execution phase, which is its own multi-session
project and is not estimated here.
