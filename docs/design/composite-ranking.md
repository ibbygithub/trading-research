# Composite Strategy Ranking — Design Notes

**Implemented:** Session 27
**Author:** Data Scientist persona
**Status:** Active

---

## Purpose

When multiple strategy variants have been backtested (different parameter sets,
different instruments, different timeframes), you need a single score to rank
them. Sorting by Sharpe alone is wrong: Sharpe penalises upside volatility,
rewards frequent small winners that will be destroyed by slippage in live trading,
and gives no weight to sample size. A strategy with Sharpe 2.1 from 40 trades
is not better than Sharpe 1.4 from 600 trades — but raw Sharpe treats it as
though it is.

The composite score addresses this by combining:
1. **Edge quality** — profit factor, log-compressed
2. **Drawdown** — multiplicative penalty that scales with pain
3. **Sample reliability** — log-scale bonus for larger trade counts, with a hard
   floor below the minimum

---

## Formula

```
score = ln(PF) × (1 − DD) × (1 + log₁₀(N / N_min))
```

where:

| Symbol | Meaning |
|---|---|
| `PF` | Profit factor (gross profit / gross loss); clipped to ≥ 1e-6 |
| `DD` | Max drawdown as a fraction of peak equity, ∈ [0, 1) |
| `N` | Total completed trades |
| `N_min` | Minimum trade threshold (default 100) |

Strategies with `N < N_min` or `DD ≥ 1.0` receive score = −∞ and are excluded.

---

## Component rationale

### Profit factor (PF)

Log-compression prevents a single outlier from dominating the ranking.
The difference between PF=3 and PF=4 should not be as large as the difference
between PF=1 and PF=2.  Using `ln(PF)`:

- PF < 1.0: negative component (strategy is a loser)
- PF = 1.0: component = 0 (break even)
- PF = 1.5: component ≈ 0.41
- PF = 2.0: component ≈ 0.69
- PF = 3.0: component ≈ 1.10

PF is preferred over Sharpe here because Sharpe penalises upside volatility
and depends on the return distribution shape in ways that are particularly
misleading for mean-reversion strategies (high win rate, occasional large losers).

### Drawdown penalty (DD)

Multiplicative: a 20% drawdown reduces the score to 80% of its pre-penalty
value. A 50% drawdown halves the score. A 90% drawdown leaves 10%.

At 100% (full blowup), the score is −∞ regardless of PF.

This is a practitioner decision, not a pure Calmar-style ratio. Calmar = return
/ max_DD is appropriate as a standalone metric but doesn't compose cleanly with
PF and trade count in a single ranking score. The multiplicative penalty is more
interpretable and numerically stable.

### Trade count bonus

```
bonus = 1 + log₁₀(N / N_min)
```

At `N = N_min` (100 trades): bonus = 1.0 (no adjustment)
At `N = 10 × N_min` (1,000 trades): bonus = 2.0 (doubles the score)
At `N = 100 × N_min` (10,000 trades): bonus = 3.0

The log₁₀ compression ensures that going from 100 to 1,000 trades is
worth the same as going from 1,000 to 10,000 trades — reflecting diminishing
returns to sample size (confidence intervals narrow as 1/√N).

### Hard floor

Strategies with fewer than `N_min` trades get score = −∞ and are excluded
from all rankings. A strategy with Sharpe 2.5 from 40 trades has wide enough
confidence intervals that its ranking position is meaningless — it's not better
than most of the strategies with 200 trades, it just happened to be observed on
fewer, potentially unrepresentative, trades. Excluding it prevents it from
bloating the top of a table it doesn't deserve to be in.

---

## Example scores

| PF | Max DD | Trades | Score | Notes |
|---|---|---|---|---|
| 2.5 | 10% | 500 | ≈ 1.31 | Good strategy |
| 1.8 | 20% | 400 | ≈ 0.52 | Modest edge, acceptable DD |
| 1.5 | 20% | 100 | ≈ 0.33 | Threshold trade count, no bonus |
| 3.0 | 50% | 300 | ≈ 0.72 | Strong PF but deep drawdown |
| 0.8 | 20% | 200 | ≈ −0.18 | Losing strategy (score < 0) |
| 2.0 | 20% | 50 | −∞ | Excluded: below min_trades |
| 2.0 | 100% | 300 | −∞ | Excluded: full blowup |

---

## Implementation

`src/trading_research/eval/ranking.py`:
- `composite_score(profit_factor, max_dd_pct, trade_count, min_trades=100) → float`
- `top_x_strategies(trials, x=10, min_trades=100) → list`
- `render_composite_ranking_html(summaries, x=10, min_trades=100) → str`
- `apply_bh_to_feature_table(feature_df, p_col='p_value', alpha=0.05) → pd.DataFrame`

`src/trading_research/eval/report.py`:
- `generate_multi_run_report(run_dirs, output_path, x=10, min_trades=100) → Path`

---

## Limitations and future work

**Weights are not calibrated.** The three components (PF, DD, N) are combined
without empirical calibration. A different practitioner might weight DD more
heavily, or PF less. The formula is intended as a reasonable default, not a
production-tuned optimiser.

**PF vs Calmar.** Using PF as the quality metric means the score doesn't
directly capture time-weighted returns. A strategy that makes 10% per year
with PF=2.0 ranks below one that makes 5% per year with PF=2.5. Whether this
is correct depends on the context; for strategy comparison within the same
instrument and timeframe, PF comparisons are clean.

**Normality.** The bonus uses log₁₀ which has no particular statistical
foundation — it's a practical choice to compress the range. If stricter
theoretical grounding is needed, replace it with a function of the standard
error on the Sharpe estimate (which scales as 1/√N).

**No regime adjustment.** A strategy that produced PF=2.0 in a trending
regime may produce PF=1.1 in a mean-reversion regime. The composite score
takes the backtest result at face value. Subperiod analysis (section S22 in
the HTML report) addresses this separately.

---

## When to apply BH alongside composite ranking

The composite ranking sorts strategies by quality but doesn't address multiple
testing bias. If you tested 30 variants and picked the best one, the composite
score of that best variant is biased upward — you optimised over noise as well
as signal.

The correct complement to composite ranking is **Deflated Sharpe Ratio** (DSR),
which is already implemented in `eval/stats.py` and displayed in section S17 of
the HTML report. DSR explicitly accounts for the number of trials in the same
cohort.

**Benjamini-Hochberg (BH)** is appropriate when you have a table of p-values
from feature significance tests — e.g. "which of these 20 indicators are
statistically predictive?" BH controls the false-discovery rate across that
table. It is NOT appropriate for ranking strategies by composite score, because
composite scores are not p-values.

See `src/trading_research/stats/multiple_testing.py` for the BH implementation.
