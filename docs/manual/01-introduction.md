# Chapter 1 — Introduction

> **Chapter status:** [EXISTS] — every section describes a design decision
> or scope boundary already in force at v1.0. No code work is needed.

---

## 1.0 What this chapter covers

This chapter introduces the platform: what it is, who it was built for,
what it will never be, how data travels from vendor to report, and what
"done" means for v1.0. It is the shortest chapter in the manual and the
most important to read first, because every design decision in later
chapters traces back to the scope constraints stated here.

---

## 1.1 What this platform is

The Trading Research Platform is a personal research bench for designing,
validating, and eventually running futures-based trading strategies. It was
built for a single operator who brings decades of market experience and
wants honest tools — not tools that sell hope.

The platform has one job: to tell the operator whether the evidence behind
a strategy hypothesis is real. Not whether the strategy will make money
(that's the market's decision), but whether the backtested result is an
artifact of honest methodology or an artifact of leakage, overfitting, and
favorable data selection. The distinction matters because the first kind can
survive into production and the second kind cannot.

The current instruments are CME Treasury and FX futures: ZN (10-year
Treasury note), 6E (Euro), 6A (Australian dollar), 6C (Canadian dollar),
and 6N (New Zealand dollar). The architecture is instrument-agnostic; adding
a new futures contract requires a configuration entry, not a code change.

The platform's north star is *computable honesty*: every result the
platform produces must be checkable, reproducible, and tagged with the data
and code that generated it. If a backtest cannot be reproduced from its
logged parameters, the result is not trustworthy. If a metric is reported
without a confidence interval, its precision is not stated. If an indicator
was computed with look-ahead, the backtest is measuring a trading strategy
that could not have been executed. The platform is designed to make all of
these failures visible before they reach the operator's decision desk.

---

## 1.2 Who it's for

One operator. Retired, trading personal capital. Background: 25 years of
trading experience across asset classes, 30 years in IT, former CISO.
He knows markets, he knows systems, and he knows when something is being
sold to him.

This matters architecturally: the platform is a *single-user research tool*,
not a multi-user service, not a fund's shared infrastructure. There is no
authentication layer, no access control, no role-based permission system,
no multi-account support. Every design decision that would be necessary for
those features is explicitly not made here, because making them would add
complexity without adding value for a single-operator use case.

The platform is designed to support an operator who:

- Arrives after a variable absence (days, weeks, months) and needs a fast
  path back to working state without relying on memory
- Prefers CLI-first operation: typing a command and reading structured output
  is faster than navigating a GUI for someone comfortable with a terminal
- Wants reproducibility over convenience: a strategy result from three months
  ago should be exactly reproducible, not "probably the same"
- Holds to a pessimistic-fills and honest-metrics discipline: the platform
  should never flatter a strategy by using generous fill assumptions

Everything in the platform's design — the manifest system, the CLI-as-API
contract, the three-layer data model, the trial registry — serves this
single-operator context.

---

## 1.3 What it is not

**Not a strategy discovery service.** The platform does not search for
profitable strategies. It tests operator-authored hypotheses. There is no
genetic algorithm, no grid search over arbitrary features, no reinforcement
learning loop proposing trades. The operator brings the hypothesis; the
platform runs the test.

**Not a black-box optimiser.** No component of the platform takes an
objective function and minimises it against historical data without the
operator's awareness of what is being varied. Parameter sweeps are
operator-configured (see Chapter 31) and their deflation implications are
surfaced explicitly (see Chapter 23).

**Not a tutorial system.** The manual describes what the platform does and
how to operate it. It does not teach quantitative finance from first
principles. A reader who does not already understand what a Sharpe ratio is,
what a stop-loss is, or what a futures roll is will not find that explanation
here.

**Not a live execution system.** In v1.0, the platform ends at paper trading.
There is no order routing to a broker, no real-time feed ingestion, no
position reconciliation against a live account. The boundary between v1.0
(research, backtesting, paper validation) and the future live-execution phase
is explicit in §1.4. When the live-execution work begins, it will be a
separate phase with its own design and a separate section of this manual.

**Not a multi-instrument portfolio manager.** The platform's backtest engine
runs one strategy on one instrument per backtest. Portfolio-level analytics
(correlation, combined drawdown, capital allocation) are available as
post-hoc analysis tools (Part VIII), but the backtester itself does not
simulate simultaneous multi-instrument execution.

---

## 1.4 Pipeline at a glance

The platform's research lifecycle has ten stages. The boundary between v1.0
scope (stages 1–9) and the future live-execution phase (stage 10) is explicit.

```
Stage 1   Pull historical 1-minute bar data from TradeStation, including
          buy/sell volume where available.

Stage 2   Validate the data against the exchange trading calendar. No
          silent gaps, no holiday confusion.

Stage 3   Store as parquet conforming to the canonical bar schema
          (data/raw/ and data/clean/).

Stage 4   Compute indicators from the 1-minute base. Higher-timeframe
          views are built by resampling, never by re-downloading.

Stage 5   Build feature matrices (data/features/) with the indicator
          stack defined by a versioned feature-set config.

Stage 6   Design and configure strategies (YAML first, Python templates
          when YAML cannot express the logic).

Stage 7   Backtest with pessimistic defaults and full trade-log forensics.
          Statistical rigor: walk-forward validation, bootstrap CIs,
          deflated Sharpe.

Stage 8   Visually verify trades in the interactive replay app.
          The replay app shows trigger-bar and fill-bar separately — the
          forensic detail that other systems don't offer.

Stage 9   Forward-test on paper for an agreed period. The strategy's
          paper performance must match backtest expectations within
          tolerance before any capital is at risk.

── v1.0 boundary ──────────────────────────────────────────────────────

Stage 10  Live execution with hard kill switches at the strategy,
          instrument, and account levels. Idempotent order routing.
          Broker fill reconciliation. This phase is out of scope for v1.0
          and is referenced in Chapter 48 for planning purposes only.
```

These stages map to the manual's parts: Part II covers stages 1–5, Part III
covers stage 6, Part IV covers stage 7, and Part IX covers the full
exploration-to-paper-trading validation gate.

---

## 1.5 What "complete" means for v1.0

The platform is declared v1.0-complete when:

1. Every chapter in this manual is marked **[EXISTS]** — no chapter
   describes a feature that does not yet exist in code (except the chapters
   in Parts XI–XII that are explicitly tagged as post-v1.0).

2. The cold-start runbook works. An operator returning after six months
   can follow Chapter 54 from a clean clone to a published backtest report
   without agent assistance and without relying on memory.

3. The `validate-strategy` CLI command ships. A strategy YAML can be
   linted before any backtest runs, catching name-resolution failures and
   expression errors early.

4. The `status` CLI command ships. One command shows the current state of
   the data layer, the last five backtests, and the registered strategies.

These criteria are the acceptance gate for the v1.0 tag on `main`. Work
that does not meet all four criteria is not v1.0. Work that meets all four
criteria and then adds features is post-v1.0.

The current gap list — items that must be completed before v1.0 is tagged —
is in the Table of Contents (`docs/manual/TABLE-OF-CONTENTS.md`), under
"Gap List — the platform-completion backlog."

---

*End of Chapter 1. Next: Chapter 2 — System Architecture.*
