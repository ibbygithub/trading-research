═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           30a-sonnet
Required model:    Sonnet 4.6
Required harness:  Claude Code
Phase:             1 (hardening)
Effort:            L (~4 hr)
Entry blocked by:  29a, 29b, 29c, 29d (all DONE)
Parallel-OK with:  D2
Hand off to:       30b-opus
Branch:            session-30-6e-backtest-v1
═══════════════════════════════════════════════════════════════

# 30a — 6E v1 backtest with cost sensitivity

## Self-check

- [ ] I am Sonnet 4.6.
- [ ] All four 29 sub-sprints DONE per current-state.md.
- [ ] `vwap-reversion-v1` is registered; `Strategy.size_position` is on engine call path; OU bounds in instrument registry.

## What you produce

### 1. Eight-variant backtest run

Per the original spec, run 8 cost variants:

| Run | Slippage (quiet) | Slippage (overlap) | Commission |
|---|---|---|---|
| 1 | 0.5 | 0.5 | $4.20/RT |
| 2 | 0.5 | 1.0 | $4.20/RT |
| 3 | 1.0 | 1.0 | $4.20/RT |
| 4 | 1.0 | 2.0 | $4.20/RT |
| 5 | 2.0 | 2.0 | $4.20/RT |
| 6 | 2.0 | 3.0 | $4.20/RT |
| 7 | 3.0 | 3.0 | $4.20/RT |
| 8 | 0.5 | 0.5 | $0 |

Backtest config: 4-fold contiguous-test segmentation (NOT walk-forward —
parameters frozen ex-ante), embargo=576 bars, fill_model=next_bar_open,
window 2018-01-01 to 2024-12-31, sizing via `Strategy.size_position` with
`target_daily_vol_pct=0.5`.

### 2. Bootstrap CIs on every metric

Use `eval/bootstrap.py` with 2000 resamples, seed=20260426. Compute and
report CIs for: Calmar, Sharpe, max_consecutive_losses, win_rate.

### 3. Per-fold stationarity check

For each fold, compute on the test-fold data:
- ADF p-value on `vwap_spread`
- OU half-life (bars)
- Classification under instrument bounds

Report as a row in the per-fold table. **If classification flips between
folds, the row is highlighted in the HTML report.**

### 4. Trial registry record per cost variant

```python
record_trial(
    strategy_id="vwap-reversion-v1-6E-{config-hash-short}",
    config_hash=blake2b_short(yaml.dump(knobs + cost_config)),
    code_version=git_short_sha(),
    engine_fingerprint=blake2b_short_of_module_source(backtest.engine),
    featureset_hash=load_featureset_hash("base-v1"),
    cohort_label=git_short_sha(),
    sharpe=sharpe_value,
    n_obs=number_of_trades,
    skewness=trade_returns_skew,
    kurtosis_pearson=trade_returns_kurt,
    trial_group="v1-cost-sweep",
)
```

Engine fingerprint helper: hash of `backtest.engine` module source via
`blake2b(open('src/trading_research/backtest/engine.py').read().encode()).hexdigest()[:12]`.

### 5. Outputs

- `runs/vwap-reversion-v1-6E-{hash}/` directory:
  - `trial.json` — full record with 8 cost variants.
  - `report.html` — single-page report with cost-sensitivity table on top.
  - `per-fold-metrics.parquet`
  - `aggregated-trades.parquet`
  - `equity-curves/` — one parquet per cost variant.
- 8 entries appended to `runs/.trials.json`.

## Acceptance checks

- [ ] 8 trials recorded in `runs/.trials.json` under cohort `<git-sha>`.
- [ ] HTML report has cost-sensitivity table on page 1.
- [ ] Per-fold stationarity row visible per fold per cost variant.
- [ ] Bootstrap CI columns on Calmar, Sharpe, max-consecutive-losses.
- [ ] DSR row reports `n_trials` count (= 8 + any prior variants in cohort).
- [ ] Stationarity classification flips highlighted (red text or warning row).
- [ ] Handoff: `docs/execution/handoffs/30a-handoff.md` written.
- [ ] current-state.md updated: 30a → DONE; 30b → READY.

## What you must NOT do

- Re-tune any knob. Cost variants ONLY change cost assumptions, not strategy params.
- Change the strategy implementation.
- Skip a cost variant "to save time."
- Author the persona review (that's 30b-opus).

## References

- Original session 30 spec: [`../../../roadmap/session-specs/session-30-6e-backtest-v1.md`](../../../roadmap/session-specs/session-30-6e-backtest-v1.md)
- Mentor on cost sensitivity: [`outputs/planning/peer-reviews/quant-mentor-review.md`](../../../../outputs/planning/peer-reviews/quant-mentor-review.md) §7
- DS on bootstrap CIs: [`outputs/planning/peer-reviews/data-scientist-review.md`](../../../../outputs/planning/peer-reviews/data-scientist-review.md) §3
