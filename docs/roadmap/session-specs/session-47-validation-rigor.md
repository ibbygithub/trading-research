# Session 47 — Part V: Validation and Statistical Rigor (condensed)

**Status:** Spec
**Effort:** 1 session, ~22 pages across 12 chapters
**Model:** Mixed — Opus 4.7 for Ch 22 and 23; Sonnet 4.6 for the
rest at reference depth (1.5–2 pages per chapter)
**Depends on:** Sessions 41–46
**Workload:** v1.0 manual completion

## Goal

Author Part V at *condensed* depth. Twelve chapters covering the
statistical-rigor layer. Two chapters get full teaching depth on
Opus (Ch 22 walk-forward, Ch 23 deflated Sharpe — these are the
ones the operator needs to *understand*, not just look up). The
other ten are reference catalogs at 1.5–2 pages each: what's
computed, where the module lives, how to interpret the output, when
the metric lies. Lopez de Prado's book exists; the manual cites it
rather than re-teaches it.

## In scope

### Full teaching depth (Opus)

- **Chapter 22 — Walk-Forward Validation (~5 pages).** Why walk-
  forward beats single split; purged walk-forward (`run_walkforward`)
  vs rolling walk-forward (`run_rolling_walkforward`); gap and
  embargo; per-fold and aggregated metrics; the validation gate
  criterion and how to read it when the literal rule fails the
  spirit. The fold table is now in the HTML report (closed in
  session 46).
- **Chapter 23 — Deflated Sharpe (~4 pages).** The multiple-testing
  problem; the Lopez de Prado correction with formula; the trial
  registry's role; reading a deflated Sharpe; what a raw 1.8
  deflating to 0.4 actually means. DSR is now in the report header
  (closed in session 46).

### Reference depth (Sonnet, ~1.5–2 pages each)

- **Chapter 19 — Headline Metrics.** Calmar headline, Sharpe
  caveats, Sortino, profit factor, expectancy, win rate vs
  breakeven, drawdown depth/duration. Mostly tables.
- **Chapter 20 — Behavioural Metrics.** Trades per week, max
  consec losses, drawdown duration, MAE/MFE distributions.
- **Chapter 21 — Bootstrap Confidence Intervals.** What
  bootstrapping does; the metrics covered; reading a CI; sample-
  size implications.
- **Chapter 24 — Stationarity Suite.** ADF, Hurst, OU half-life;
  the `stationarity` CLI; module reference.
- **Chapter 25 — Distribution Analysis.** Skew, kurtosis, tail
  risk, VaR/CVaR; module reference.
- **Chapter 26 — Monte Carlo Simulation.** Trade-order MC; what
  it catches that bootstrap doesn't; module reference.
- **Chapter 27 — Regime Metrics & Classification.** Splits
  supported; classifier; module reference.
- **Chapter 28 — Subperiod Analysis.** Year/month/DoW/hour
  splits; module reference.
- **Chapter 29 — Drawdown Forensics.** Per-drawdown decomposition;
  recovery curves; ulcer index; module reference.
- **Chapter 30 — Event Studies & Blackout Filtering.** Blackout
  calendars; wiring into a strategy; event-conditioned performance;
  module reference.

## Out of scope

- New statistical modules — every chapter describes existing code.
- Ch 33 (multiple-testing correction in feature selection) — that
  goes in Part VI session 48.

## Hand-off after this session

- Part V drafted: Chapters 22 and 23 at full teaching depth, the
  other ten at reference depth.
- Next session: 48 (Parts VI, VII, VIII — exploration, risk,
  portfolio, all condensed).
