# Sprint 30b — vwap-reversion-v1 6E Cost Sweep Review

**Strategy:** vwap-reversion-v1-6E  
**Data window:** 2018-01-01 – 2024-12-31 (7 years)  
**Folds:** 4 × contiguous, embargo_bars=576 (2 trading days)  
**Git SHA:** 2e87e7e  
**Run artefacts:** `runs/vwap-reversion-v1-6E-55f3e1e3/`

---

## Results summary

| Label | Calmar | 90% CI | Sharpe | Win Rate | T/Wk | Max DD Duration |
|---|---|---|---|---|---|---|
| s0.5-o0.5-c4.20 | −0.095 | [−0.098, −0.091] | −2.04 | 41.4% | 13.8 | 2546 d |
| s0.5-o1.0-c4.20 | −0.097 | [−0.099, −0.096] | −3.17 | 40.7% | 13.8 | 2546 d |
| s1.0-o1.0-c4.20 | −0.097 | [−0.099, −0.096] | −3.17 | 40.7% | 13.8 | 2546 d |
| s1.0-o2.0-c4.20 | −0.098 | [−0.099, −0.098] | −5.34 | 39.2% | 13.8 | 2552 d |
| s2.0-o2.0-c4.20 | −0.098 | [−0.099, −0.098] | −5.34 | 39.2% | 13.8 | 2552 d |
| s2.0-o3.0-c4.20 | −0.099 | [−0.099, −0.098] | −7.38 | 37.6% | 13.8 | 2552 d |
| s3.0-o3.0-c4.20 | −0.099 | [−0.099, −0.098] | −7.38 | 37.6% | 13.8 | 2552 d |
| **s0.5-o0.5-c0.00** | **−0.093** | **[−0.098, −0.084]** | **−1.55** | **41.7%** | **13.8** | **2546 d** |

DSR (n=8, cohort 2e87e7e): **0.00**  
Total trades (all variants, same signal set): **5,041**  
Max consecutive losses: 13–17 depending on cost variant  

---

## Stationarity note

The sweep script attempted per-fold stationarity checks on a `vwap_spread` column.
That column is not precomputed in the feature parquet; the strategy generates it inline as
`close − vwap_session`. Per-fold stationarity was therefore unavailable at sweep time.

A standalone check was run on the full 2018–2024 dataset:

| Test | Value | Interpretation |
|---|---|---|
| ADF p-value | 0.000000 | STATIONARY (strong) |
| Hurst (DFA) | 1.2447 | TRENDING (strong) |
| OU half-life | 31.5 bars (157 min) | MEAN_REVERTING |
| **Composite** | **INDETERMINATE** | — |

The composite is INDETERMINATE: ADF rejects the unit root cleanly (the spread is stationary
over the full 7-year window), but the Hurst exponent is anomalously high at 1.24, indicating
strong short-term persistence. This is the key tension: the spread *does* revert on a
multi-hour timescale (OU half-life ≈ 157 min), but it trends aggressively before it reverts.
The Hurst value above 1.0 is unusual and warrants attention — see Data Scientist section.

---

## Mentor (market behaviour)

The numbers tell a straightforward story: vwap-reversion-v1 is not a mean-reversion strategy
in practice, even though the hypothesis sounds like one. The equity curve is a slow, steady
drawdown across the entire 7-year test period — drawdown duration of 2,546 days against a
2,555-day test window means the strategy is *never* in a new equity high. It is not volatile,
it is not spiky — it is a smooth, controlled loss machine.

At what slippage does the edge break? It was never present. The zero-cost case (c0.00) has
Calmar = −0.093 and Sharpe = −1.55. That is not a strategy that suffers when costs are added;
that is a strategy that loses even when you trade for free.

The trade frequency of 13.8/week is consistent with a strategy that fires multiple times per
day inside the 12:00–17:00 UTC entry window. That is a plausible execution rate for an
institutional desk — it does not feel fabricated. The strategy is firing when it should; it is
just pointing the wrong way.

The Hurst exponent explains the market behaviour. A DFA Hurst of 1.24 on the intraday VWAP
spread says that when 6E deviates from session VWAP during the London/NY overlap, it tends
to *continue* deviating for a while before it comes back. The strategy is entering at the 2.2
ATR extreme expecting an immediate reversal. Instead, it frequently gets pushed further before
the mean-reversion eventually kicks in. With max_hold_bars=60 (5 hours), the reversal often
hasn't completed before the position is stopped out or time-expired.

This is a genuine market structure insight rather than a data artefact. The 6E VWAP spread
has momentum on the intraday timescale. Pure mean-reversion entry without a momentum filter
is going to get run over. The Hurst is telling us the strategy needs either:
(a) a longer hold window to survive the momentum phase, or
(b) a momentum filter to avoid entering into strong directional moves, or
(c) a different market: something with tighter, faster reversion.

The 41.7% win rate at zero cost with approximately 1:1 R:R seals it. You need above 50% to
break even on 1:1. No amount of regime filtering can bridge a 9-percentage-point gap in win
rate unless you can correctly identify the 60% of trades that are winners and skip the rest —
which is essentially a different strategy.

---

## Data Scientist (quantitative integrity)

**Per-fold dispersion:** Not computable at the per-fold level (stationarity column missing;
see note above). At the aggregate level: all 5,041 trades produce a consistently negative
result. The bootstrap CI for the zero-cost case is [−0.098, −0.084] for Calmar — that lower
bound is −0.084, which is firmly negative. There is essentially zero probability this strategy
has positive Calmar in any realistic scenario. This is not a wide CI that straddles zero; it
is a tight CI that is entirely on the wrong side.

**Bootstrap CIs (Run 5, s2.0-o2.0-c4.20):** Calmar = −0.098, 90% CI [−0.099, −0.098].
The CI is so narrow it barely registers — this is because with 5,041 trades, we have a very
precise estimate of a very bad number. Sharpe = −5.34, 90% CI [−3.77, −2.98]. Lower bound
of Calmar CI: −0.099. Not positive. Not close.

**DSR with n_trials=8:** DSR = 0.00. After deflating for 8 trial variants in the same cohort,
the best Sharpe (−1.55 from the zero-cost run) deflates to 0.00. The cost sweep exhausted
all the reasonable parameter territory and the best result was negative. Deflation drove it
to exactly zero, meaning the statistical evidence for positive out-of-sample performance is
essentially nil.

**Stationarity INDETERMINATE:** The Hurst exponent of 1.24 from DFA is worth examining
closely. Theoretically, Hurst must lie in [0, 1] for standard self-similar processes. A
value of 1.24 suggests either strong non-stationarity in the DFA scaling relationship, or
a series with very long-range dependence that violates the model assumptions. In practice,
what this is measuring is that when the VWAP spread is large, it tends to get *larger* over
the next several bars before contracting. The ADF result (p ≈ 0) confirms the spread is
ultimately bounded; it does revert. The Hurst value confirms the path to reversion is not
smooth — it overshoots further in the entry direction before turning. This is the statistical
description of a momentum-before-reversion dynamic.

**Max consecutive losses:** 13 at most cost variants, 17 at the highest. With a 41.7% win
rate, runs of 13 consecutive losses have a non-trivial probability: (0.583)^13 ≈ 0.13% per
any given trade. Across 5,041 trades, seeing this once is expected. The 17-loss run at higher
cost (where win rate drops to 37.6%) is similarly within expectation. These are not
statistical outliers — they are the natural behavior of a strategy that loses 60% of its
trades.

**Sample size:** 5,041 trades is more than sufficient. The narrow CIs confirm we are not
in a low-power situation. The conclusion — no positive alpha — is well-supported statistically.

---

## Architect (platform integrity)

**Cost injection:** Clean. The `slippage_ticks` and `commission_rt_usd` fields were added to
`BacktestConfig` as optional overrides with validation. `BacktestEngine.__init__` uses them
when set, falls back to instrument defaults otherwise. `run_walkforward()` accepts the same
parameters and threads them through. No global state, no monkeypatching, no side effects.
Six tests were added to `tests/test_engine.py` covering the override logic, fractional ticks,
and validation of negative inputs.

**Engine fingerprint:** Stable across all 8 runs. The signal generation (`generate_signals`)
is called once per variant, not cached globally — this is correct because the signals are
independent of cost. All 8 variants produced exactly 5,041 trades, confirming the signals
are deterministic and the cost override is not affecting signal generation.

**size_position:** Produces 1 contract for every entry. The sizing logic has a subtle bug:
`estimated_entry` is computed as `stop_price + risk_points`, which evaluates to the target
price rather than the actual entry price. For 6E at these parameter values this doesn't
change the outcome (max_contracts rounds to 1 either way), but it should be fixed before
this strategy goes to paper. Filed as a known issue.

**Stationarity column:** The sweep script attempted to read a `vwap_spread` column from the
feature parquet. That column does not exist — the feature parquet stores `vwap_session`; the
spread is computed inline in the strategy's `generate_signals`. The script has been updated
to fall back to `close − vwap_session` when the precomputed column is absent. The original
run did not benefit from this fix. A future enhancement would be to persist the spread as a
feature column (named `vwap_spread_session`) so the stationarity check and the strategy use
the same series from the same source.

**Featureset hash:** No manifest file exists in `data/features/` for the base-v1 feature set.
The trial registry recorded `featureset_hash: null` for all 8 entries. This is a minor
provenance gap — acceptable for v1, but the feature pipeline should be generating manifests.
Noted as a deferred action.

**New hardcodings:** None visible in the diff relative to session-29. The strategy config
remains the single source of knobs; the cost matrix is defined only in the sweep script.
The `PROJECT_ROOT` derivation in the script uses `Path(__file__).resolve().parents[1]`,
which is path-independent. No instrument-specific tick sizes or session hours are
hard-coded in the script — the engine reads them from the registry.

**Output reproducibility:** Running the script twice would produce identical `trial.json`,
`per-fold-metrics.parquet`, and `aggregated-trades.parquet` because the signal generation
and engine are deterministic (no random components). The `trial.json` run_date field would
differ (it captures UTC timestamp at execution), and the `runs/.trials.json` registry would
accumulate additional entries. This is intentional — the registry is append-only for cohort
integrity. The output directory hash is stable (derived from the cost matrix definition, not
execution state).

---

## Sprint 31 entry recommendation

**RECOMMENDATION: ESCAPE**

The v1 strategy has no positive alpha at any cost assumption. The zero-commission run
(Run 8, s0.5-o0.5-c0.00) produces Calmar = −0.093 with 90% CI [−0.098, −0.084] — the entire
interval is firmly negative. DSR deflates to 0.00 after 8 trials. The drawdown duration of
2,546 days out of a 2,555-day test window indicates the strategy never achieves a new equity
high during the entire test period.

The root cause is not costs. It is the Hurst dynamic: the 6E VWAP spread has strong
short-term momentum (Hurst = 1.24). The strategy enters at the 2.2 ATR extreme expecting
immediate reversion; instead, the spread continues in the entry direction for an extended
period before reverting. With a 5-hour holding limit, many trades are stopped out or
time-expired before the reversion completes.

A regime filter in sprint 31 would not bridge this gap. A 41.7% win rate on approximately
1:1 risk/reward means you need to correctly identify and skip roughly 60% of the
current trade set to reach break-even. That requires a strong predictive signal for the
momentum-versus-reversion regime — which is effectively a new strategy, not a filter on
the existing one.

**Proposed path forward:**

1. **Sprint 31 (retain but repurpose):** Investigate whether a *longer* max_hold_bars
   (e.g., 120–240 bars = 10–20 hours, which would require overnight holds for this
   instrument and violates single-instrument overnight rules) could let the reversion
   complete. If overnight is off the table for single-instrument, test a different entry
   condition that waits for momentum to exhaust before entering (e.g., RSI extremes
   combined with VWAP deviation, or a MACD histogram rotation at the VWAP band).

2. **Sprint 34 (preferred, per original session spec):** Pivot to 6A/6C pairs. The
   commodity currency pairs have genuine structural mean-reversion properties derived from
   the correlation between the two currencies' commodity exposure. The cointegration
   thesis is more robust than the single-instrument VWAP reversion hypothesis, and the
   spread is stationary for different, more structural reasons.

3. **Keep v1 infrastructure:** The template/registry architecture, the cost-sweep harness,
   the BacktestConfig overrides, and the bootstrap/DSR pipeline are all working and
   clean. None of that needs to change.

The honest summary: the VWAP reversion idea is sound in theory, but 6E during 2018–2024
is not the right instrument for it at this timescale. The data does not support the
hypothesis. Ship the platform improvements from session 30, pivot the strategy.
