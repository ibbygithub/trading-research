# Session 30 — 6E backtest v1 (cost-sensitive, full provenance)

**Status:** Spec — ready to execute after sprint 29
**Effort:** 1 day, two sub-sprints (L+S)
**Depends on:** Sprint 29 complete (registry + size_position + OU bounds)
**Unblocks:** sprint 31 (regime filter), sprint 33 (Track C gate)
**Personas required:** Mentor, Data Scientist, Architect (30b)

This is the first run of `vwap-reversion-v1` with parameters frozen. **It is
not walk-forward.** It is contiguous-test segmentation with embargo, parameters
fixed ex-ante. Calling it walk-forward is a terminology error the project will
pay for at the gate.

## Goal

A defensible v1 result for `vwap-reversion-v1` on 6E, with:
- Cost-sensitivity sweep across realistic slippage assumptions.
- Bootstrap CIs on every reported metric.
- Per-fold stationarity check (regime-fitting detection).
- Full trial-registry provenance.

The result either supports proceeding to sprint 31 (regime filter), supports
pivoting (if v1 is hopeless even with regime help), or supports escape (if
costs alone destroy the edge).

## In scope

### 30a — Backtest run + reporting

**Model:** Sonnet 4.6 | **Effort:** L (~4 hr)

**Run configuration:**
- Strategy: `vwap-reversion-v1` with knob defaults from sprint 29b.
- Data: `data/features/6E_backadjusted_5m_features_base-v1_*.parquet`.
- Window: 2018-01-01 to 2024-12-31 (skipping the documented Q3 2015 – Q1 2017 gap).
- Folds: 4 contiguous test segments, embargo 576 bars (= 2 trading days at 5m).
- Fill model: `next_bar_open` (project default).
- Sizing: vol-targeted via `Strategy.size_position`, target_daily_vol_pct=0.5
  (conservative for new strategy).

**Cost sensitivity sweep:**
Run the full backtest **8 times** with the following slippage / commission combos:

| Run | Slippage (quiet) | Slippage (overlap) | Commission |
|---|---|---|---|
| 1 | 0.5 tick | 0.5 tick | $4.20/RT |
| 2 | 0.5 tick | 1.0 tick | $4.20/RT |
| 3 | 1.0 tick | 1.0 tick | $4.20/RT |
| 4 | 1.0 tick | 2.0 tick | $4.20/RT |
| 5 | 2.0 tick | 2.0 tick | $4.20/RT |
| 6 | 2.0 tick | 3.0 tick | $4.20/RT |
| 7 | 3.0 tick | 3.0 tick | $4.20/RT |
| 8 | 0.5 tick | 0.5 tick | $0 (idealised) |

The "overlap" window is 12:00–17:00 UTC (entry window) — slippage is higher
during high-activity hours.

Run #8 is the optimistic ceiling; runs 5–7 are the realistic floor; runs 1–4
are the sensitivity grid.

**Metrics + CIs (bootstrap, 2000 resamples, seed=20260426):**

For each cost configuration, report:
- Calmar (point + 95% CI)
- Sharpe (point + 95% CI)
- Deflated Sharpe (full cohort, with `n_trials` named)
- Max drawdown duration (days)
- Max consecutive losses (point + 95th percentile from bootstrap)
- Trades per week (point + range)
- Win rate (point + 95% CI)
- Average R:R achieved
- Per-fold equity curve

**Per-fold stationarity check:**
For each fold, compute on the test-fold data:
- ADF p-value on `vwap_spread`
- OU half-life (bars)
- Hurst (DFA)
- Classification under instrument's bounds (TRADEABLE / TOO_FAST / TOO_SLOW / NONSTATIONARY)

Report as a row in the per-fold table next to the fold's P&L. **If
classification flips between folds, that is a finding the report must surface
in red text.**

**Provenance:**
Each of the 8 runs produces a Trial record:

```python
record_trial(
    strategy_id="vwap-reversion-v1-6E-{config-hash-short}",
    config_hash=blake2b_short(yaml.dump(knobs + cost_config)),
    code_version=git_short_sha(),
    engine_fingerprint=blake2b_short_of_module(backtest.engine),
    featureset_hash=load_featureset_hash("base-v1"),
    cohort_label=git_short_sha(),
    sharpe=sharpe_value,
    n_obs=number_of_trades,
    skewness=trade_returns_skew,
    kurtosis_pearson=trade_returns_kurt,
    trial_group="v1-cost-sweep",
)
```

**Outputs:**
- `runs/vwap-reversion-v1-6E-{hash}/` directory containing:
  - `trial.json` — full trial record + 8 cost variants
  - `report.html` — single-page report with cost-sensitivity table at top
  - `per-fold-metrics.parquet`
  - `aggregated-trades.parquet`
  - `equity-curves/` — one parquet per cost variant
- Trial entries in `runs/.trials.json`.

### 30b — Three-persona review

**Model:** Opus 4.7 | **Effort:** S (~1 hr)

Read 30a outputs. Produce written review covering:

**Mentor — market behaviour:**
- Does the equity curve respect London/NY structure (entries cluster in window)?
- Cost-sensitivity verdict: at what slippage does the strategy stop paying?
- Are there cost configurations where the edge is real but the costs are unrealistic?
- War-story check: does this look like a real-desk EUR/USD reversion P&L profile?

**Data Scientist — evidence honesty:**
- Per-fold dispersion: is the aggregate P&L driven by 1–2 folds?
- Per-fold stationarity: any fold flips classification? If so, regime-fitting risk is live.
- Bootstrap CI widths: is "Calmar 1.5" actually [0.4, 2.6]?
- DSR with `n_trials=8` accounts for the cost sweep — is the v1 result still distinguishable from luck?
- Confidence interval on max consecutive losses — does the realised number even matter?

**Architect — coupling integrity:**
- Did sprint 29's registry coupling hold under load? Engine fingerprint stable across all 8 runs?
- Featureset hash recorded correctly?
- Did `size_position` produce sensible position sizes (no zeros, no overflow)?
- Any new hardcodings that crept in? (Code review of diff vs. sprint 29 baseline.)

**Sprint output:** a single `30b-review.md` file with each persona's verdict
and a recommendation for sprint 31:
- "PROCEED to regime filter" — v1 is genuinely close; filter likely makes it pass.
- "PROCEED to regime filter with pre-defined caution" — v1 is far; regime filter is unlikely to bridge the gap; consider pivoting before sinking sprint 31 into it.
- "ESCAPE — costs destroy the edge" — pivot to 6A/6C or class change at sprint 34.

## Out of scope

- Regime filter implementation (sprint 31).
- Mulligan logic (sprint 32).
- Walk-forward refitting (sprint 31 introduces it).
- ML / meta-labeling.
- Live order semantics.

## Acceptance tests

- [ ] `runs/.trials.json` contains 8 new trials in cohort `<git-sha>`.
- [ ] HTML report has cost-sensitivity table on page 1.
- [ ] Per-fold stationarity row visible per fold per cost variant.
- [ ] Bootstrap CI bars on Calmar, Sharpe.
- [ ] DSR row reports `n_trials` count.
- [ ] If any fold's stationarity classification flips, the row is highlighted.
- [ ] `30b-review.md` committed with all three persona verdicts.

## Definition of done

- [ ] 8 trial records in registry.
- [ ] Report HTML accessible at `runs/<trial-id>/report.html`.
- [ ] Persona review committed.
- [ ] Sprint 31 ENTRY criterion clearly stated in 30b review (proceed / proceed-with-caution / escape).
- [ ] Branch `session-30-6e-backtest-v1`.

## References

- `outputs/planning/sprints-29-38-plan-v2.md`
- `docs/analysis/6e-strategy-class-recommendation.md`
- `src/trading_research/eval/{trials,bootstrap,summary}.py`
- `src/trading_research/backtest/walkforward.py` (post sprint 29 retrofit)
