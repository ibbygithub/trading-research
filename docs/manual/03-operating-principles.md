# Chapter 3 — Operating Principles

> **Chapter status:** [EXISTS] — every principle described here is in
> force at v1.0. The standing rules are code-enforced defaults; some
> may be overridden by explicit operator configuration, but not silently.

---

## 3.0 What this chapter covers

This chapter codifies the platform's non-negotiable defaults: the rules
that govern how data is handled, how backtests are filled, how results are
reported, and how risk is managed. These rules are the answer to the
question "why does the platform work this way?" — and they are the
constraints any future development must respect.

The chapter is also an introduction to the platform's three built-in
reasoning personas, which shape every agent-assisted session: what each
persona owns, where the personas disagree, and how that disagreement is
useful.

---

## 3.1 The honesty bar

The platform's primary design constraint is what the operator calls the
*honesty bar*: every result the platform produces must be a honest
representation of what a strategy would have earned under realistic trading
conditions, not a best-case approximation.

The honesty bar is not a philosophical statement. It is a set of specific,
code-enforced defaults:

- **Fills are pessimistic.** The default fill model is next-bar-open: if a
  signal fires on bar T, the fill is at bar T+1's open. Same-bar fills are
  available but require an explicit `same_bar_justification` string in the
  strategy YAML. A same-bar fill without a justification is a linting error.

- **TP/SL resolution is pessimistic.** When a bar's range contains both the
  stop price and the target price — the "ambiguous bar" problem — the platform
  resolves in favor of the stop hitting first. This penalises the strategy by
  the full difference between the target and the stop on those bars. An OFI-
  based resolution (using order-flow imbalance to infer direction within the
  bar) is opt-in via `use_ofi_resolution: true` and requires a justification.

- **Costs are pessimistic.** Slippage and commission defaults in
  `configs/instruments_core.yaml` are set higher than TradeStation's actual
  published rates. The operator can tighten them once live execution provides
  empirical fill-quality data.

- **The headline metric is Calmar, not Sharpe.** Calmar ratio — annual return
  divided by maximum drawdown — is the platform's primary risk-adjusted
  metric. Sharpe is reported alongside it but is not the decision metric.
  The reason: Sharpe penalises upside volatility and assumes normal return
  distributions. Mean-reversion strategies have non-normal distributions with
  occasional large losers; on those distributions, Sharpe flatters the strategy
  relative to what the operator will actually experience in drawdown.

- **Deflated Sharpe is reported alongside raw Sharpe** whenever the trial
  registry records multiple variants of the same strategy (see Chapter 23).
  A raw Sharpe of 1.8 from 30 variants may deflate to 0.4; the platform
  surfaces both numbers.

- **Confidence intervals are required.** Every headline metric has a bootstrap
  confidence interval. A strategy with Calmar 2.0 and 95% CI [0.8, 3.1] is
  a very different claim from one with Calmar 2.0 and 95% CI [1.6, 2.4]. The
  platform does not allow results to be discussed as point estimates only.

---

## 3.2 The standing rules in detail

These rules have no exceptions at the platform level. An individual strategy
may override a default (e.g., `same_bar_justification`, `use_ofi_resolution`),
but the override is always explicit, always justified in writing, and always
visible in the output. The rule about what the platform's defaults are is
separate from the rule about what an individual strategy may do.

### 3.2.1 1-minute bars are the canonical base resolution

Historical data is acquired and stored at 1-minute resolution. All higher
timeframes (5m, 15m, 60m, 240m, 1D) are produced by resampling the 1-minute
base. They are never downloaded separately.

*Why this:* downloading 5-minute data directly from TradeStation introduces
subtle bar-boundary differences depending on TradeStation's session template.
Building all timeframes from the same 1-minute source ensures that a 5m bar
and the equivalent 15m bar are always resampled with identical session
boundaries, roll handling, and gap treatment. Any discrepancy between
timeframes is a bug in the resampler, not a vendor choice.

### 3.2.2 Every dataset passes a calendar-aware quality check before strategy code can consume it

The quality gate (`data.validate.validate_bar_dataset`) is not optional and
is not bypassed by the pipeline under normal operation. It checks:

- No duplicate timestamps
- No bars with negative volume
- No bars where high < low
- Coverage of buy/sell volume (informational if partial)
- Missing bars against the exchange trading calendar (informational for back-
  adjusted continuous contracts where roll seams introduce expected gaps)

Structural failures abort the pipeline. Gap reports are informational.
The gate cannot be bypassed in code; the pipeline CLI enforces it between
the CLEAN and FEATURES rebuild stages.

### 3.2.3 The canonical bar schema includes buy_volume and sell_volume as nullable fields

Buy and sell volume (order-flow attribution from TradeStation) are first-class
citizens in the bar schema, not optional extras. Strategies that use them must
handle the null case explicitly — TradeStation's coverage is partial for older
contracts and complete for recent ones.

The schema is defined in
[`src/trading_research/data/schema.py`](../../src/trading_research/data/schema.py).
Appendix A is the full field listing.

### 3.2.4 Instrument specs come from the registry

Tick size, tick value, contract size, session hours, RTH window, settlement
time, calendar, roll convention, and cost defaults are all defined in
[`configs/instruments_core.yaml`](../../configs/instruments_core.yaml) and
loaded into a frozen `Instrument` model by `core.instruments.InstrumentRegistry`.
Hard-coding any of these values in strategy, indicator, backtest, sizing, or
evaluation code is forbidden and will be flagged in code review.

*Why this:* a strategy that hard-codes ZN's tick value produces wrong P&L the
moment ZN's tick value changes (or the strategy is adapted for 6E). A strategy
that reads the tick value from the registry produces correct P&L for any
registered instrument automatically. This is the difference between a platform
that generalises and one that accretes per-instrument special cases.

### 3.2.5 Threshold parameters fit on the test set are leakage

Any parameter — a percentile cutoff, a regime-filter threshold, a hold-out
window boundary — that was determined by looking at the test set and then
used to evaluate strategy performance on that same test set inflates the
result. The platform's persona-driven reasoning (see §3.4) flags this whenever
it appears. The technical consequence: any strategy with a regime filter must
use rolling walk-forward validation, where each fold's filter is fitted only
on that fold's training data.

### 3.2.6 Trade logs capture trigger and fill separately

Each trade in the log records four timestamps: entry trigger (the bar where
the signal fired), entry fill (the bar where the position opened), exit trigger
(the bar where the exit condition was met), and exit fill (the bar where the
position closed). This is not just bookkeeping — it is what allows the replay
app to show the difference between "the signal said enter here" and "the engine
filled here," which is the most important forensic distinction in debugging a
strategy.

The trade schema is defined in
[`src/trading_research/data/schema.py:107`](../../src/trading_research/data/schema.py).
Appendix B is the full field listing.

---

## 3.3 What the platform refuses to do

Some operations are structurally prevented by the platform. Others are allowed
but only through an explicit override path that makes the choice visible.

**Averaging down without a fresh signal.** The Mulligan controller in
`strategies/mulligan.py` allows a second entry into an existing position only
when a new, pre-defined entry signal fires. A re-entry triggered by "the
position moved against me and I want to average the cost basis down" is not a
fresh signal; it is averaging down, which the backtest engine detects and
rejects with a `MulliganViolation` exit reason. The distinction between a
legitimate scale-in and averaging down is the trigger: a new signal fires,
or it doesn't. See Chapter 38 for the full re-entry design.

**Indicator columns in CLEAN parquets.** The pipeline's rebuild logic never
writes indicator columns to CLEAN; indicators only appear in FEATURES. If a
code change causes an indicator to appear in a CLEAN file, it is a bug.

**Same-bar fills without justification.** The engine accepts `fill_model:
same_bar` only when the strategy YAML includes a non-empty
`same_bar_justification` string. An empty or absent justification causes a
configuration validation error before the backtest runs.

**Uncalibrated re-entries.** A re-entry under the Mulligan controller must
have combined risk (stop distance for the combined position) and a combined
target computed before the second entry is placed. The engine rejects
re-entries that would leave the combined position without a stop.

**EOD flat override in production without acknowledgment.** Intraday
strategies default to `eod_flat: true` — all positions are closed at the
session's RTH close. Disabling EOD flat on a single-instrument intraday
strategy requires an explicit YAML override and produces a warning in the
backtest output.

---

## 3.4 Reasoning by personas

Every agent-assisted session in this project loads three reasoning personas
from `.claude/rules/`. These are not roleplay; they are structured
perspectives that speak to different layers of the platform and whose
disagreements surface trade-offs the operator needs to see.

### The Quant Mentor (`quant-mentor.md`)

A 20-year trading veteran who thinks in terms of market structure: is this
strategy responding to a real phenomenon or fitting noise? Does the exit
discipline match the asset class? Is the fill model realistic for the
instrument's liquidity profile? The mentor pushes back on ML-before-rules,
on strategies that compete on HFT's turf, and on overnight exposure that
makes sense for pairs but not for single-instrument intraday work.

The mentor speaks when: a strategy hypothesis is being designed or evaluated;
a market-structure question needs a practitioner's frame; a backtest result
looks implausibly good.

### The Data Scientist (`data-scientist.md`)

A quantitative integrity officer who defends every claim the platform makes.
Is the train/test split clean? Is the confidence interval honest? Is the
sample size large enough to trust the Calmar estimate? Was deflated Sharpe
computed with the right trial count? The data scientist is deliberately
pedantic about these questions, because they are the questions that separate
strategies that work in production from strategies that only work in backtest.

The data scientist speaks when: a statistical claim is being made about a
backtest result; a validation methodology is being designed; any parameter
was selected by looking at out-of-sample data.

### The Platform Architect (`platform-architect.md`)

An infrastructure engineer who thinks about the cost of the next change.
When a new instrument is added, does the code break or does it generalise
automatically? When the feature-set schema changes, how many files break?
When a new indicator is added, where does it live, and does the feature-
builder pick it up without special cases? The architect's standing question
is: "When we add the fifth instrument, does this file change?"

The architect speaks when: a new module is being designed; a code change
would affect multiple components; a shortcut is being considered that will
cost more later.

### How the personas interact

The three personas disagree productively. The mentor wants to prototype a
strategy idea now. The data scientist wants another two weeks of out-of-
sample data. The architect wants the feature-builder interface settled before
either of those conversations happens. All three observations are correct
about different things; the operator synthesises.

When the personas visibly disagree in a session transcript, that is not a
failure of the reasoning framework. It is the framework surfacing a real
trade-off. The operator's job is to decide; the personas' job is to make the
trade-off visible.

---

## 3.5 What changes in live

> **[GAP — post-v1.0]**

Live execution adds a layer of requirements that v1.0 does not implement.
This section is a placeholder; the full specification will be written when
the paper-trading phase concludes and live execution work begins.

The categories of change at the live boundary:

- **Idempotent order routing.** Every order submitted to the broker must be
  tagged with a unique ID and checked for duplicate submission before sending.
  The backtest engine's trade log is the source of truth for intent; the
  broker API's fill confirmation is the source of truth for execution.

- **Kill switches.** At minimum three levels: strategy-level (stop this
  strategy, close its positions), instrument-level (no more trades in this
  instrument), account-level (close everything, stop all strategies). Each
  must be triggerable without restarting the process.

- **Broker fill reconciliation.** Actual fills will differ from the simulated
  fills in the backtest. The live layer must record both the intended fill
  (from strategy logic) and the actual fill (from broker confirmation) and
  accumulate the slippage delta for empirical model calibration.

- **Daily and weekly loss limits enforced at the broker.** Backtests enforce
  stop-based per-trade risk. Live trading additionally enforces daily and
  weekly P&L loss limits that halt the strategy before a bad day becomes a
  bad week. These limits are defined in the strategy config and checked
  against broker P&L, not simulated P&L.

These capabilities are out of scope for v1.0 and are referenced in
Chapters 47 and 48 for planning purposes.

---

## 3.6 The CLI-as-API design contract

Every operation the platform supports is reachable as a single
`uv run trading-research <subcommand>` invocation. This is not a convenience
feature; it is a binding design contract with architectural consequences.

**The contract, stated precisely:** an operation that cannot be expressed as a
single CLI invocation with clear inputs and outputs is not a platform
operation — it is a notebook-level experiment that belongs in `notebooks/`,
not in `src/`. If an operation needs to be a platform capability, it must be
wrapped in a CLI command before it can be considered part of the platform.

**Why this matters for a future GUI.** A graphical front-end (see Chapter 59,
post-v1.0) is a thin shell that calls `subprocess.run(["uv", "run",
"trading-research", ...])` or the equivalent, captures the output, and
renders it. It does not re-implement any business logic. If the CLI command
produces structured output (tabular or JSON), the GUI can parse it. If the
CLI command exits cleanly with a non-zero code on failure, the GUI can report
the error. This design means that every improvement to the CLI automatically
improves the GUI, and the GUI cannot diverge from the CLI's behaviour by
having its own implementation of the same logic.

**Implications for command design:**

- Every command must accept all configuration as CLI options. No command reads
  from stdin interactively during normal operation; batch input is via file
  path options.
- Every command must exit cleanly with a meaningful exit code: 0 (success),
  1 (runtime error), 2 (usage error or invalid input).
- Output that is meant for humans is tabular with headers. Output that is
  meant for scripting is `--json`. The `--json` flag is not required on every
  command; it is required on every command whose output will plausibly be
  consumed by another program.
- Error messages go to stderr; data output goes to stdout. This separation
  allows the operator to pipe output to other tools without capturing error
  messages as data.
- A command that reads configuration from a YAML file accepts the YAML path
  as an argument, not as a hardcoded lookup. This makes it testable without
  a live config directory.

The CLI is the contract. The code is the implementation. When they diverge,
the CLI wins: if a command's documentation (in `--help` and in Chapter 49)
describes behaviour X, the code must implement X. The reverse is not true:
a code behaviour not documented in the CLI reference is not a platform
feature, it is an implementation detail.

---

## 3.7 Related references

### Persona files

- [`.claude/rules/quant-mentor.md`](../../.claude/rules/quant-mentor.md)
  — full text of the quant mentor persona.
- [`.claude/rules/data-scientist.md`](../../.claude/rules/data-scientist.md)
  — full text of the data scientist persona.
- [`.claude/rules/platform-architect.md`](../../.claude/rules/platform-architect.md)
  — full text of the platform architect persona.

### Configuration

- [`configs/instruments_core.yaml`](../../configs/instruments_core.yaml) —
  the single source of truth for instrument economics and session schedules.
  Chapter 5 is the annotated reference.
- [`CLAUDE.md`](../../CLAUDE.md) — the project-level operating contract.
  The standing rules in §3.2 are the manual's rendering of the rules in
  CLAUDE.md's "Standing rules" section.

### Manual chapters

- **Chapter 5** — Instrument Registry: the registry that enforces §3.2.4.
- **Chapter 14** — Backtest Engine: the fill models referenced in §3.1.
- **Chapter 22** — Walk-Forward Validation: the methodology that prevents
  the leakage described in §3.2.5.
- **Chapter 23** — Deflated Sharpe: the multiple-testing correction
  referenced in §3.1.
- **Chapter 38** — Re-entries vs Averaging Down: the Mulligan controller
  referenced in §3.3.
- **Chapter 49** — CLI Reference: the full specification of every CLI
  command introduced in §2.6.

---

*End of Chapter 3. Next: Chapter 4 — Data Pipeline & Storage.*
