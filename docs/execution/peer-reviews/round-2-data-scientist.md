# Round 2 — Data Scientist Review
Date: 2026-04-26
Question set: What product do we have at end of session 38? What can it do?
What can't it do? What's left to make it production-ready for live money trading?

---

## Q1 — At end of session 38, what product do I have?

You have a **statistically defensible research and paper-trading platform**
for futures strategies, with one strategy (6E intraday VWAP mean reversion)
either validated through a pre-committed seven-criterion gate or explicitly
escaped to a different path under documented rules.

Concretely on the methodology side:
- A walk-forward harness that distinguishes contiguous-test segmentation
  (parameters frozen ex-ante) from true rolling-fit walk-forward
  (parameters fitted on training window). The terminology is honest.
- A trial registry with cohort fingerprinting on `code_version` and engine
  fingerprint. Cross-cohort comparisons are blocked by design.
- Bootstrap CI machinery applied to every metric in every gate criterion.
  No point estimates dressed up as conclusions.
- Deflated Sharpe Ratio computed cohort-wide with `n_trials` named.
- Per-fold stationarity (ADF + Hurst + OU half-life) reported alongside
  per-fold P&L. Regime-fitting is detectable, not hidden.
- Benjamini-Hochberg multiple-testing correction available for any
  feature-selection or multi-strategy comparison.
- Mulligan freshness invariant enforced at the engine level — adverse-P&L
  averaging-down is a runtime exception.
- Featureset versioning with hash-based artifact provenance.

What this means in practice: **when you (Ibby) say "the strategy has
Calmar 1.5, deflated Sharpe 0.6," the platform can defend that statement.**
That was not true at start of sprint 29.

## Q2 — What can it do?

Things the platform reliably does at end of session 38:

1. **Run a strategy through walk-forward + cost-sensitivity + per-fold
   stationarity in a defensible way.** Outputs a report that names which
   metrics are inside their CIs and which aren't.
2. **Surface deflated Sharpe with cohort awareness.** If you tested 12
   variants, the DSR reflects that, not the cherry-picked best.
3. **Detect featureset version drift on the live data path.** Hard halt,
   not a silent recompute against a different feature set.
4. **Compare two trials side-by-side.** Cross-cohort warnings render when
   `cohort_label` differs.
5. **Catch Mulligan freshness violations** (and therefore averaging-down)
   at the engine level. The Strategy Protocol invariant is contract-tested.
6. **Report behavioural metrics with confidence intervals** — max
   consecutive losses 95th percentile, drawdown duration, trades per week.
   Point estimates alone are not allowed in gate decisions.
7. **Recompute the gate retroactively** if cost assumptions change. The
   trial registry stores enough that a session-42-style cost-model
   recalibration can revisit any prior gate.

These are not all the platform can do — those are the methodological
capabilities. Architect's review covers the system capabilities.

## Q3 — What can't it do?

These are real gaps, not nitpicks:

1. **Live capital evidence — none.** Every metric is from backtest +
   first day or two of paper. Without 30 trading days of paper, the
   confidence interval on live performance is the same as the backtest
   CI. That is not a small caveat; that is the whole purpose of the
   30-day window.
2. **Multi-strategy DSR.** The cohort scoping is per-strategy. If you run
   `vwap-reversion-v1` on 6E AND a future 6A strategy, there is no
   "portfolio DSR" that accounts for cross-strategy multiple testing. Track
   G/H work.
3. **Real-time regime detection.** The platform produces stationarity
   reports periodically (sprint 28 style). It does not continuously monitor
   the spread's stationarity during live trading. A regime shift mid-trade
   day is invisible until the EOD report.
4. **Concept drift detection on a strategy.** When the strategy starts
   underperforming its CIs in live, the platform reports the divergence
   but does not classify it (drift vs. variance vs. structural break).
   That's a Phase 2 + Track G capability.
5. **Confidence intervals on the live cost model.** Sprint 30 produced
   bootstrap CIs for the *backtest* trade-return distribution under fixed
   cost assumptions. Live realised slippage is one observation per trade.
   You need ~30 trades of paper before the cost-model CI is meaningful.
   That's session 44's job.
6. **Sensitivity analysis on the regime filter threshold.** Sprint 31's
   filter threshold is selected per the pre-commitment rule (path A or B).
   The platform reports what happened with that threshold. It does not
   sensitivity-analyse around the threshold (a 10% deviation in either
   direction). That sensitivity is implicit in the bootstrap CIs but not
   surfaced explicitly in the report.
7. **Statistical evidence that the strategy works on out-of-sample data
   the strategy designer has never seen.** Even the hold-out paper window
   only tests against data Ibby could have looked at in design. There
   is no air-gap "data Ibby has never seen" sample. There can't be — Ibby
   is the designer. The data scientist's "I just looked at it" trap is
   live in this project as it is in every project.

## Q4 — What's left to make it production-ready for live money trading?

In priority order, with the data scientist lens:

### 4.1 — 30 trading days of paper trading evidence
Currently 0–5 days at end of session 38. **This is the load-bearing
requirement.** Sessions 39–44 cover this.

Specifically the platform must demonstrate:
- Per-trade slippage stays inside the cost-model bound used at sprint 33.
- Trade-count-per-week stays inside sprint 33's bootstrap CI.
- Realised Calmar's CI excludes 1.0 (strictly profitable risk-adjusted)
  at end of window.
- No featureset hash drift incidents.

If any of those fail, live capital does not move. There is no shortcut.

### 4.2 — Live-vs-backtest cost-model reconciliation (session 42, 44)
After ~10 trades, recompute the cost model from realised slippage. If the
realised model is materially worse than sprint 30's pessimistic
configuration, the gate criterion G6 needs re-evaluation. The retrospective
re-evaluation is honest (we used the parameters we set ex-ante; we just
update our cost expectation for forward); a new gate decision based on the
updated cost model determines whether to proceed.

### 4.3 — Risk-of-ruin tied to actual account size (session 46)
The platform has volatility targeting (sized via `Strategy.size_position`
through sprint 29c). It does NOT compute risk-of-ruin for a given account
size and first-trade size. Session 46 adds this calculation:

- Inputs: account equity, strategy expectancy from session 44 paper data,
  strategy variance, Kelly fraction.
- Output: probability of hitting -X% drawdown before reaching +Y% gain at
  the chosen position size.

Default first-trade size is 1 micro M6E (Kelly-fractioned with 0.25× safety
factor, capped). The risk-of-ruin computation is the gate criterion L8.

### 4.4 — Stress test on adverse historical periods
Specifically:
- 2014 negative-rate ECB period (was outside the 2018+ backtest window).
- 2020 March COVID intervention.
- 2022 ECB rate cycle pivot.

Run the strategy through each as a regime stress test before live capital.
Currently the backtest spans 2018–2024 which includes 2020 and 2022 but
the per-fold breakdown should be examined for those quarters specifically.
Session 44 evaluation includes this.

### 4.5 — Multi-month forward stationarity sanity check
The OU half-life from session 28 was computed on 2024 data. A live trade
in 2026 implicitly assumes the half-life is durable. Run the stationarity
suite on rolling 6-month windows over 2018–2024 and look at how the
half-life evolves. If it shifts materially, that is a finding for session
44, not a blocker.

### 4.6 — Pre-committed rule for what to do when paper underperforms
"If realised Calmar's lower CI bound is below 0.5 by end of week 2, halt
the window and reconsider." This rule is in the master execution plan but
its specific thresholds need confirmation. Session 41/43 reviews check it.

### 4.7 — Audit trail to reconstruct any decision
A live trade in session 49 must be auditable in 2027 — what code, what
data, what featureset, what knobs, what cost model. The trial registry
captures this for the *backtest* layer; the *paper trading* layer captures
it via the engine fingerprint logged at session start. Confirm session 47
plumbing includes this in the LIVE path too.

---

## What I will sign off on

I will sign session 45's live-readiness gate (criterion L1, L2, L3, L7, L8)
on the condition that 4.1–4.6 above are satisfied with the rigor they
deserve. If any is hand-waved, I will not sign.

The platform at end of session 38 is statistically defensible for paper
trading. It is not yet statistically defensible for live capital, by the
load-bearing fact that we don't have live-capital-equivalent evidence yet.
The 30-day paper window is the only honest way to bridge that gap.
