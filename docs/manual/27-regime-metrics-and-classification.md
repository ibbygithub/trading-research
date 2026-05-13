# Chapter 27 — Regime Metrics & Classification

> **Chapter status:** [EXISTS] — regime breakdown in
> [`eval/regime_metrics.py`](../../src/trading_research/eval/regime_metrics.py),
> winner/loser classifier in
> [`eval/classifier.py`](../../src/trading_research/eval/classifier.py).
> Regime breakdowns appear in the §14 Market Context block of the
> Trader's Desk Report.

---

## 27.0 What this chapter covers

A strategy's average performance hides which regimes it wins in and
which it loses in. Regime conditioning splits the trade log along
external tags (volatility, trend, session, day of week, event days)
and reports per-regime metrics. The classifier adds a more general
tool: a LightGBM model that predicts trade outcomes from entry-bar
context and surfaces feature importance. After reading this chapter
you will:

- Know which regime splits the platform supports out of the box
- Understand the classifier's role and its purging discipline
- Know how to consume regime labels in YAML strategy filters

This chapter is roughly 3 pages. It is referenced by Chapters 12, 17,
24.

---

## 27.1 Regime-conditioned performance

[`breakdown_by_regime`](../../src/trading_research/eval/regime_metrics.py:12)
takes a trade log and a `regime_column` (any column already attached
to the trades), groups by the distinct values, and computes per-group
summaries:

```python
results.append({
    "regime": str(name),
    "count": count,
    "total_pnl": float(pnl.sum()),
    "avg_pnl": float(pnl.mean()),
    "win_rate": float(win_rate),
    "calmar": ...,
    "sharpe": ...,
    "trades_per_week": count / (span_years * 52),
})
```

The Sharpe and Calmar within a regime are computed from a daily P&L
series restricted to that regime — not from the trade-level series
directly. This is the right convention because Sharpe and Calmar are
both daily-aggregate metrics in the rest of the platform; conditioning
on regime should not change the metric definition.

Trades with `NaN` in the regime column are excluded from the
breakdown. Strategy templates that tag every trade with the regime
in force at entry get a clean breakdown; those that leave gaps get
partial coverage. The report surfaces the included-trade count
alongside each regime row.

### 27.1.1 Standard splits

The platform's strategy templates attach the following regime columns
to the trade log when applicable:

| Column | Values | Source |
|---|---|---|
| `direction` | `long`, `short` | Trade direction |
| `entry_dow` | `Mon`–`Fri` | Entry-day-of-week |
| `entry_hour` | 0–23 | Entry hour, ET |
| `session_regime` | `pre_rth`, `rth_open`, `rth_mid`, `rth_close`, `post_rth` | Session window at entry |
| `vol_regime` | `low`, `mid`, `high` | ATR percentile at entry |
| `trend_regime` | `down`, `flat`, `up` | HTF bias at entry |
| `fomc_regime` | `blackout`, `non_blackout` | Event blackout (Chapter 30) |

Not every strategy attaches every column; the report iterates over
whichever columns are present.

> *Why these particular splits:* they map to the questions the mentor
> persona asks most often. "Does this strategy work as well shorting
> as it does going long?" → `direction`. "What does it do on FOMC
> days?" → `fomc_regime`. "Is the edge concentrated in low-vol
> environments?" → `vol_regime`. The other splits exist by analogy.

---

## 27.2 Reading a regime breakdown

The single most useful pattern: a strategy whose aggregate Calmar is
1.8 with one regime showing Calmar 4.5 and another showing Calmar
-0.5 is *not* a strategy with Calmar 1.8. It is a regime-conditional
strategy that should be deployed only in the favourable regime, or
not deployed at all if the regime cannot be detected in real time.

Three readings to watch for:

1. **Asymmetry between long and short.** A mean-reversion strategy
   that prints Calmar 3.0 long and Calmar 0.2 short is almost always
   capturing a trend filter the strategy designer didn't intend to
   build in. The "edge" is the long bias, not the reversion logic.
2. **One regime dominates.** When one regime accounts for >60% of
   total P&L on <40% of trades, the strategy is a specialist. That
   specialist might be deployable; it requires a real-time regime
   detector (Chapter 12 covers regime filters).
3. **A regime shows good rate-metrics but small count.** A regime
   with 11 trades, Calmar 4.2, win rate 73% is a noise reading. Read
   the count first; the metrics second.

---

## 27.3 The winner/loser classifier

[`train_winner_classifier`](../../src/trading_research/eval/classifier.py:53)
trains a LightGBM binary classifier on the entry-bar features of each
trade, predicting whether the trade was a winner. The output is not a
"trade-selection model" — that would be a strategy in its own right —
but a *feature-importance diagnostic*: which entry-context features
have the strongest relationship with trade outcome?

The features used:

```python
[
    "rsi_14", "adx_14", "atr_14", "sma_200",
    "atr_14_pct_rank_252",
    "daily_range_used_pct",
    "vwap_distance_atr",
    "htf_bias_strength",
    "entry_hour",
    "hold_minutes",
]
```

plus the categorical regime columns (`direction`, `session_regime`,
etc.) when present.

### 27.3.1 Purged cross-validation

The classifier uses purged walk-forward CV
([`classifier.py:94`](../../src/trading_research/eval/classifier.py))
following Lopez de Prado's AFML Chapter 7 discipline:

- 5-fold KFold with `shuffle=False` (strict temporal order).
- For each test fold starting at `val_start`, the training data is
  `[0, val_start - purge_bars)`. The purge prevents labels from
  overlapping into the test window — a trade whose outcome was
  realised within `purge_bars` of `val_start` is excluded from
  training.
- The next fold's `val_start` is `val_end + gap`, so the gap acts as
  the embargo between folds.

Permutation importance is computed on the held-out fold (never on
the training data), preventing the optimism that comes from
measuring importance against the data the model has memorised.

> *Why permutation importance:* feature importance from a tree
> model's split counts is biased toward high-cardinality features
> and toward features that interact heavily. Permutation importance
> — shuffle one feature, measure the score drop — is closer to the
> question the operator actually wants answered: "if I removed this
> feature, how much worse would the model be?"

### 27.3.2 When to use this and when not to

The classifier is a diagnostic, not a strategy. Three uses:

1. **Validate that a strategy's claimed edge is in the features the
   strategy uses.** A volatility-regime strategy whose top-importance
   features are `atr_14_pct_rank_252` and `vwap_distance_atr` is
   coherent. A volatility-regime strategy whose top-importance feature
   is `entry_dow` is using volatility regime as cover for a
   day-of-week bias.
2. **Detect curve-fit features.** Features that show high
   importance only on a small subset of trades and zero importance
   elsewhere are usually overfit. The cross-validated permutation
   importance with confidence bands surfaces this when it happens.
3. **Spot non-features.** If the AUC is below 0.55 across folds, no
   features in the feature set distinguish winners from losers at
   the entry bar. That is not necessarily bad — the strategy's edge
   may live in the exit rules — but it tells the operator where the
   edge is not.

The classifier is *not* a signal-generator and should not be wired
into a strategy as such. Doing so would launder a feature-importance
diagnostic into a trading rule, which is the path to the worst kind
of curve-fit. The data-scientist persona is the right voice when the
operator is tempted to do this.

---

## 27.4 Consuming regime labels in YAML

A strategy that wants to gate entries on a regime label does so
through a regime filter (Chapter 12), not by reading the trade log
post-hoc. The flow:

1. The feature builder attaches a regime column to FEATURES (e.g.
   `vol_regime` from ATR percentile).
2. The strategy YAML declares a `regime_filter` that consumes the
   column.
3. The backtest engine evaluates the filter at signal time, so the
   regime label is on the trade as `vol_regime` automatically.
4. The report's regime breakdown then reads from the column.

This loop — feature → filter → trade tag → report — is the standard
way to incorporate a new regime split. Adding a new regime is
documented in Chapter 12 (`build_filter` extension).

---

## 27.5 Related references

### Code modules

- [`src/trading_research/eval/regime_metrics.py`](../../src/trading_research/eval/regime_metrics.py)
  — `breakdown_by_regime` (the per-regime aggregator).
- [`src/trading_research/eval/regimes.py`](../../src/trading_research/eval/regimes.py)
  — regime-labelling helpers consumed by the trade tagger.
- [`src/trading_research/eval/classifier.py`](../../src/trading_research/eval/classifier.py)
  — `train_winner_classifier` with purged walk-forward CV.

### Other manual chapters

- **Chapter 12** — Composable Regime Filters: how regime labels are
  produced and gated.
- **Chapter 17** — Trader's Desk Report: §14 Market Context (where
  regime breakdowns surface).
- **Chapter 22** — Walk-Forward Validation: regime decay over folds.
- **Chapter 24** — Stationarity Suite: complementary diagnostic for
  whether the underlying series is still mean-reverting.
- **Chapter 28** — Subperiod Analysis: time-based regime splits
  (year/month/day/hour).

---

*End of Chapter 27. Next: Chapter 28 — Subperiod Analysis.*
