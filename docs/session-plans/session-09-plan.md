# Session 09 — First Real Strategy: ZN MACD Pullback

## Objective

Build, test, and honestly evaluate the first real ZN strategy:
a multi-timeframe MACD histogram pullback mean-reversion entry.

By end of session:
- `uv run trading-research backtest --strategy configs/strategies/zn-macd-pullback-v1.yaml`
  produces a real trade log with genuine P&L, not zero trades
- Performance summary is printed with bootstrap confidence intervals
- A sample of trades is viewable in the replay cockpit
- Mentor and data scientist have reviewed the results and spoken up

**Nothing gets optimised this session.** The strategy parameters are
set once before the backtest runs and do not change in response to
what the results look like. That discipline is the point.

---

## Entry Criteria

- Session 08 complete: backtest engine, CLI, TRADE_SCHEMA all working
- `data/features/` has valid ZN 5m base-v1 parquet (confirmed: 1,064,432 rows)
- `data/clean/` has ZN 60m backadjusted parquet (needed for HTF filter)
- `src/trading_research/strategies/example.py` shows the interface contract

---

## Strategy Specification

### Name
`zn-macd-pullback-v1`

### Logic — Long Entry

All five conditions must be true on the signal bar (bar T):

| # | Condition | Column / Source | Rule |
|---|---|---|---|
| 1 | Daily bias bullish | `daily_macd_hist` (5m features) | `> 0` |
| 2 | 60m bias bullish | `htf_60m_macd_hist` (loaded from 60m CLEAN) | `> 0` |
| 3 | 60m not declining | `htf_60m_macd_hist_slope` (derived from 60m) | `>= 0` (current bar ≥ previous bar) |
| 4 | 5m histogram below zero | `macd_hist` | `< 0` |
| 5 | 5m pullback exhausting | `macd_hist_decline_streak` | `>= 3` (3+ consecutive bars of rising histogram while negative) |

Entry fires on bar T+1 open (next-bar-open default).

### Logic — Short Entry

Mirror image:

| # | Condition | Column / Source | Rule |
|---|---|---|---|
| 1 | Daily bias bearish | `daily_macd_hist` | `< 0` |
| 2 | 60m bias bearish | `htf_60m_macd_hist` | `< 0` |
| 3 | 60m not declining further | `htf_60m_macd_hist_slope` | `>= 0` (stabilising or recovering) |
| 4 | 5m histogram above zero | `macd_hist` | `> 0` |
| 5 | 5m bounce exhausting | `macd_hist_decline_streak` | `<= -3` (3+ consecutive declining bars while positive) |

### Exit Conditions (in priority order)

1. **Stop hit:** Price level = entry_price ± (atr_stop_mult × atr_14), pessimistic fill
2. **Target hit:** Price level = vwap_session at time of signal
3. **EOD flat:** Engine closes at RTH session close (15:00 ET). `exit_reason = "eod"`

Target and stop are price levels set at signal time and do not move
(no trailing stops in v1). Stop is relative to the signal bar's close
as a proxy for entry (true entry is next-bar-open, close is close enough
for stop placement purposes at 5m resolution).

### Parameters (all in strategy YAML, no hardcoding)

| Parameter | Default | Notes |
|---|---|---|
| `streak_bars` | 3 | Consecutive bars required for entry condition 5 |
| `atr_stop_mult` | 2.0 | ATR multiplier for stop distance |
| `macd_fast` | 12 | MACD fast EMA period (applies to 60m computation) |
| `macd_slow` | 26 | MACD slow EMA period |
| `macd_signal` | 9 | MACD signal EMA period |

Do not tune these this session. They are set once and the backtest
reports what it reports. Tuning them is session 10 territory.

---

## MACD Histogram Alignment — 60m HTF

The 5m features file has `daily_macd_hist` (already baked in via the
daily HTF projection). It does **not** have a 60m equivalent — the
base-v1 featureset only projects daily bias.

For this session: compute 60m MACD in the strategy module directly.

```
data/clean/ZN_backadjusted_60m_*.parquet
```

Procedure in `generate_signals()`:
1. Load 60m CLEAN parquet
2. Compute MACD histogram (same (12, 26, 9) params)
3. Compute slope: `macd_hist.diff()` (bar-to-bar change)
4. Shift both columns by 1 bar: `shift(1)` — look-ahead prevention
5. `merge_asof` onto the 5m index using `direction="backward"` (each
   5m bar sees the most recent completed 60m bar's values)

**Why not rebuild features?** The base-v1 tag is immutable once parquets
are built. Adding 60m bias would require base-v2 and a full rebuild.
That's the right long-term pattern; session 09 does it the straightforward
way first and confirms the strategy has edge before spending the rebuild cost.

**Look-ahead check:** The shift(1) on 60m data means the 5m bars within
a 60m period all see the *previous* 60m bar's MACD, not the current
one. This is correct and conservative. Document this in code.

---

## Step 1 — Strategy config (`configs/strategies/zn-macd-pullback-v1.yaml`)

```yaml
strategy_id: zn-macd-pullback-v1
symbol: ZN
timeframe: 5m
description: >
  Multi-timeframe MACD histogram pullback. HTF (daily + 60m) must align.
  5m pulls back against trend, then exhausts (3-bar streak). Entry on
  next-bar-open. Stop at 2x ATR, target at session VWAP, flat by EOD.

signal_module: trading_research.strategies.zn_macd_pullback
signal_params:
  streak_bars: 3
  atr_stop_mult: 2.0
  macd_fast: 12
  macd_slow: 26
  macd_signal_period: 9

backtest:
  fill_model: next_bar_open
  same_bar_justification: ""
  eod_flat: true
  max_holding_bars: null
  use_ofi_resolution: false
  quantity: 1
```

---

## Step 2 — Strategy module (`src/trading_research/strategies/zn_macd_pullback.py`)

`generate_signals(df, *, streak_bars, atr_stop_mult, macd_fast, macd_slow,
                  macd_signal_period) -> pd.DataFrame`

The function receives the 5m features DataFrame (index = timestamp_utc UTC).

```
Internal steps:
1. Load and align 60m MACD (see alignment procedure above)
2. Compute long/short boolean masks from the five conditions
3. Compute stop and target price levels for each signal bar:
     long_stop   = close - atr_stop_mult × atr_14
     short_stop  = close + atr_stop_mult × atr_14
     target      = vwap_session  (price level at signal time)
4. Return DataFrame with columns: signal (int8), stop (float), target (float)
```

**Streak filter implementation note:**
`macd_hist_decline_streak` is already computed in the features:
- Positive integer = N consecutive rising bars (histogram increasing)
- Negative integer = N consecutive declining bars (histogram decreasing)

Long condition 5: `macd_hist_decline_streak >= streak_bars` while `macd_hist < 0`
Short condition 5: `macd_hist_decline_streak <= -streak_bars` while `macd_hist > 0`

No need to recompute the streak — use the pre-computed column.

**Edge cases to handle explicitly:**
- `vwap_session` is NaN at the first bar of each session — skip entry if target is NaN
- `atr_14` is NaN in the warm-up window — skip entry if stop is NaN
- `daily_macd_hist` is NaN at the start of the history — skip entry
- `htf_60m_macd_hist` is NaN before 26 slow-period 60m bars have elapsed — skip entry

Any bar where stop or target would be NaN must emit `signal = 0`.

---

## Step 3 — Tests (`tests/test_strategy_zn_macd_pullback.py`)

Test the signal logic on synthetic data, not on the real parquets.
Build a minimal DataFrame with the required columns and verify:

- All five long conditions met → signal == +1, stop and target set
- All five short conditions met → signal == -1
- Any single condition missing → signal == 0
- Streak of 2 (not 3) → signal == 0
- Streak of 4 → signal == +1 (at least 3)
- Streak breaks and restarts → only triggers after fresh 3-bar count
- NaN atr_14 → signal == 0 (no entry, stop cannot be set)
- NaN vwap_session → signal == 0 (no entry, target cannot be set)
- Stop is below entry for long, above for short
- Target is session VWAP at signal time

Do NOT test against the real parquet data in unit tests.

---

## Step 4 — Run the backtest

```
uv run trading-research backtest \
    --strategy configs/strategies/zn-macd-pullback-v1.yaml \
    --from 2018-01-01 \
    --to 2023-12-31
```

Use 2018–2023 as the initial evaluation window. This leaves 2024–2026
as unseen data. Do not look at 2024–2026 results until the strategy
has been evaluated on 2018–2023 and a decision has been made about
whether to proceed.

**What to look at first (before any metric):**
- Total trades: if fewer than 100, the strategy fires too infrequently
  to evaluate. If more than 2,000/year, something is wrong with the logic.
- Any trades with entry_price == exit_price — bug indicator
- Any trades with exit_reason distribution: what fraction are stop / target / eod?
  A strategy that is 95% eod exits is not a strategy, it's a time stop.

---

## Step 5 — Bootstrap confidence intervals (`src/trading_research/eval/bootstrap.py`)

Add `bootstrap_summary(result, n_samples=1000) -> dict` alongside the
existing `compute_summary`.

For each metric: resample the trade-level net_pnl_usd with replacement
n_samples times, compute the metric on each sample, return the 5th and
95th percentile as the 90% CI.

Key metrics to bootstrap:
- `sharpe` → CI: [sharpe_p5, sharpe_p95]
- `calmar` → CI: [calmar_p5, calmar_p95]
- `win_rate` → CI: [win_rate_p5, win_rate_p95]
- `expectancy_usd` → CI: [expectancy_p5, expectancy_p95]

Print alongside point estimates in the summary table:
```
Calmar [headline]    1.84    90% CI: [0.91, 2.73]
```

The data scientist will interpret these. A strategy with Calmar 1.84
CI [0.91, 2.73] is worth continuing. A strategy with Calmar 1.84
CI [-0.12, 3.54] is noise.

File: `src/trading_research/eval/bootstrap.py`
Tests: smoke test on 100-trade synthetic log, verify CI contains point estimate.

---

## Step 6 — Mentor and data scientist review

After the backtest runs, both personas speak to the results before
any decision is made. Specifically:

**Data scientist checks:**
- Trade count: is the sample size meaningful?
- CI width: is the point estimate distinguishable from zero?
- Trades per week: does it fire at a sensible frequency?
- Max consecutive losses: can Ibby stomach the worst streak?
- Exit reason distribution: what fraction are stop / target / eod?

**Mentor checks:**
- Does the equity curve make sense given ZN market structure?
- Are there obvious regime periods where the strategy fails (2020 Covid,
  2022 rate shock)? If so, is that expected?
- Does the stop size (2× ATR) feel right for ZN at 5m?
- Is the target (session VWAP) sensible, or does it set targets that
  are already behind the market at signal time?

Neither persona optimises parameters based on what they see.
The question is: "is there something real here worth continuing?" not
"what parameters make the Calmar go up?"

---

## Step 7 — Visual spot-check in replay

Open the cockpit on a sample window with trades overlaid:

```
uv run trading-research replay \
    --symbol ZN \
    --from 2022-06-01 \
    --to 2022-06-30 \
    --trades runs/zn-macd-pullback-v1/<latest>/trades.parquet
```

Look for:
- Do entry arrows appear where the conditions should have triggered?
- Do exit arrows make sense — stop at the right level, VWAP target visible?
- Any trades that look wrong visually

---

## Out of Scope for Session 09

- Parameter optimisation or tuning (session 10)
- Walk-forward validation (session 10)
- Deflated Sharpe / multiple-testing correction (session 10 — requires variants)
- base-v2 featureset with 60m bias baked in (do when the strategy is confirmed worth continuing)
- Any second strategy (one at a time)

---

## Success Criteria

| Item | Done when |
|---|---|
| Strategy config | `configs/strategies/zn-macd-pullback-v1.yaml` exists and loads cleanly |
| Strategy module | `generate_signals()` returns valid SignalFrame, all edge cases handled |
| Tests | All new tests pass; full suite still green |
| Backtest runs | `backtest` CLI completes on 2018–2023 with > 50 trades |
| Bootstrap CIs | CI printed alongside every headline metric |
| Mentor review | Speaks to the equity curve and whether the setup respects ZN structure |
| Data scientist review | Speaks to sample size, CI width, exit distribution |
| Replay spot-check | At least one trade visually verified in the cockpit |
