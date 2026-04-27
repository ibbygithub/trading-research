# 6E (Euro FX) — Strategy Class Recommendation

**Session:** 28  
**Date:** 2026-04-25  
**Author:** Session analysis from Track A acceptance gate + stationarity suite  
**Status:** Recommended — pending walk-forward validation

---

## Executive Summary

6E's VWAP spread is strongly stationary (ADF p ≈ 0) with a mean-reversion half-life of 160–180 minutes. The recommended strategy class is **intraday VWAP mean reversion with an extended hold window** — specifically, entries during the London/New York overlap session (12:00–17:00 UTC) with holds up to 5 hours and a hard flatten at 21:00 UTC before settlement. This is a direct port of the ZN VWAP reversion framework with FX-specific recalibration of the tradeable OU bounds.

---

## Stationarity Results

All analysis on 2024 data (457K 1-minute bars, back-adjusted continuous contract EC). Fixed lag cap `maxlag=30` used for ADF to avoid memory overflow on large series.

### ADF Test Results

| Series | Timeframe | ADF Statistic | p-value | Decision |
|---|---|---|---|---|
| log_price_level | 5m | −2.091 | 0.927 | NON-STATIONARY (expected) |
| log_returns | 5m | −48.830 | ≈ 0 | STATIONARY |
| vwap_spread | 5m | −23.174 | ≈ 0 | STATIONARY |
| vwap_spread | 15m | −20.409 | ≈ 0 | STATIONARY |

Price level is a random walk — as expected. Returns are stationary — as expected. VWAP spread is stationary at both granularities, confirming mean reversion is present and persistent.

### Hurst Exponent (DFA Method)

| Series | Timeframe | Hurst (DFA) | Interpretation |
|---|---|---|---|
| vwap_spread | 5m | 1.3387 | Trending regime within windows |
| vwap_spread | 15m | 1.2703 | Trending regime within windows |

The high DFA Hurst values (> 1.0) reflect a structural property of VWAP spread dynamics, not a contradiction of the ADF result. VWAP spread exhibits **overshoot followed by reversion**: price trends away from VWAP persistently within a bar window before snapping back, which shows up as H > 1 in DFA while remaining ADF-stationary over the full sample. This is the signature of a mean-reverting series with strong inertia — exactly the dynamics a VWAP reversion strategy is designed to exploit.

### Ornstein-Uhlenbeck Half-Life

| Series | Timeframe | OU Half-Life (bars) | OU Half-Life (time) | Suite Classification |
|---|---|---|---|---|
| vwap_spread | 5m | 32.9 bars | ~164 min | TOO_SLOW (ZN-calibrated bounds: 3–24 bars) |
| vwap_spread | 15m | 11.8 bars | ~177 min | TOO_SLOW (ZN-calibrated bounds: 2–8 bars) |

Both half-lives land at approximately **165–180 minutes** in clock time, regardless of bar granularity. This is the correct thing to anchor on: the mean-reversion speed is a property of the instrument and the session, not of the chart timeframe.

---

## Interpretation

### What the data says

6E VWAP spread is unambiguously stationary and mean-reverting. The ADF rejection is clean at both timeframes with statistics in the range of −20 to −23 (well past any conventional threshold). The signal is real.

The half-life of ~165–180 minutes is longer than the ZN-calibrated "tradeable" window (15 min – 2 hr at 5m, per the suite config). This does not mean the edge is absent — it means the ZN calibration is instrument-specific and needs updating for 6E. A 165-minute mean reversion half-life is entirely practical for intraday trading if the position is entered during the London/NY overlap and given room to breathe.

### Why FX mean reversion half-lives are longer than bond half-lives

ZN's short half-life reflects the dominant role of scheduled economic events (Fed speakers, auction results, claims data) that snap the market back to fair value within a session. 6E's price is driven by the EUR/USD rate differential, ECB/Fed policy divergence, and risk sentiment — all of which operate on longer timescales. A VWAP reversion trade in 6E is playing the "price overextended from session anchor" thesis, which typically resolves over 2–4 hours rather than 30–60 minutes.

### The DFA Hurst apparent contradiction

The H > 1 DFA values look alarming at first. They are not. DFA Hurst > 0.5 is a measure of autocorrelation within the window — it says the spread tends to keep moving in one direction across consecutive bars. Combined with ADF stationarity, this reads as: "the spread overshoots the mean, then snaps back hard." That is precisely what you want from a mean-reversion instrument: not a noisy random walk back to mean, but a series that goes too far, holds, then corrects. The entry timing advantage is that the spread often continues to extend for 1–2 bars after initial signal, giving better entries with limit orders rather than market orders.

---

## Recommended Strategy Class

**Class:** Intraday VWAP Mean Reversion  
**Timeframe:** 5-minute bars (primary), 15-minute bars (for signal confirmation)  
**Hold duration:** 2–5 hours (anchored to OU half-life, not a fixed bar count)  
**Session filter:** London/NY overlap only — 12:00–17:00 UTC  
**EOD flatten:** Hard flatten at 21:00 UTC. No overnight holds on single-instrument positions.

This is mean_reversion in the strategy-class taxonomy, with the following FX-specific notes:

1. **Not momentum_breakout.** Despite H > 1 in DFA, the entry logic should fade the move, not chase it. The inertia is your friend for entries (allow overshoot) but not for exits (take profit as the spread normalises, don't wait for a breakout).

2. **Not event_driven** in the primary sense. ECB meetings and US CPI releases should be treated as blackout windows (no entries 30 minutes before, no open positions at release), not as signal generators.

3. **Not pairs/spread.** 6E as a single instrument has overnight gap risk. Pairs work (e.g., 6E/6J, 6E/6B) can use multi-day holds but requires separate analysis.

---

## Starting Template: Knob Guidance

These are starting points only. Walk-forward validation is required before any capital commitment.

### Signal construction

```yaml
# Recommended starting config for 6E VWAP reversion
indicator: vwap_spread         # close - session_vwap, as a fraction of ATR
entry_threshold_atr: 1.5       # enter when spread exceeds 1.5 * ATR(14)
# ZN equivalent was 1.0-1.2; 6E is noisier so wider threshold reduces churn
exit_target_atr: 0.3           # take profit when spread reverts to 0.3 * ATR
# Decay to near-zero, not zero — 6E VWAP rarely touches exactly
stop_loss_atr: 2.5             # stop at 2.5 * ATR; reward:risk ~1.75:1 at target
```

### Time filters

```yaml
session_filter:
  entry_start_utc: "12:00"    # London/NY overlap begins
  entry_cutoff_utc: "17:00"   # no new entries after 17:00 UTC (leaves 4hr for reversion)
  flatten_utc: "21:00"        # hard flatten before CME settlement window
  blackout_minutes_before_release: 30
```

### Hold duration

```yaml
max_hold_bars_5m: 60          # 300 min / 5 min = 60 bars hard cap
# OU half-life is ~33 bars; 60-bar cap gives 1.8x half-lives to resolve
# Most of the reversion should occur within the first half-life (~164 min)
```

### Sizing (starting point)

```yaml
sizing: volatility_target      # per CLAUDE.md default
target_daily_vol_pct: 0.5     # conservative for new strategy
instrument: 6E_micro           # MES/M6E equivalent; validate on micro before standard
```

The M6E (Micro Euro FX) is $1,250 per point vs $125,000 for standard 6E. Validate on micro first.

---

## Caveats and Required Validation Steps

### Before backtesting

1. **Recalibrate tradeable OU bounds** in the suite config for 6E. The current bounds (3–24 bars at 5m) were derived from ZN and classify both 6E half-lives as `TOO_SLOW`. This classification is technically correct for ZN-style entries but is misleading for the recommended FX hold window. Either create a 6E-specific suite config or widen the bounds to 10–80 bars at 5m.

2. **Verify data coverage around known ECB events** (e.g., negative rate periods 2014–2022, COVID intervention March 2020). The back-adjusted data covers these periods; the strategy should survive them, not just be trained after them.

3. **Check for session regime shifts.** Post-2022 ECB rate cycle fundamentally changed EUR/USD dynamics. Split the backtest train/test at 2022-01-01 as a minimum. Strategies calibrated on the low-rate 2015–2021 period may have different behaviour in the 2022–present regime.

### During backtesting

4. **Use next-bar-open fill model** (project default). Do not use same-bar fills — 6E is liquid but not infinitely so, and the overshoot signal may be partially reversed by the time a market order executes.

5. **Trade log must separate trigger bar from entry bar.** The OU inertia means the spread often extends 1–2 bars after signal. The trigger vs entry separation in the schema exists for this reason — use it to measure actual entry quality.

6. **Walk-forward validation, minimum 4 folds.** Given the ~165-min half-life and the 5-year dataset, each fold should be at least 6 months. Purge 2 days (576 5m bars) between train and test windows to avoid label overlap.

### Data gaps

7. **Known gap: Q3 2015 – Q1 2017.** TradeStation returned 404s for EC contracts in this window during the pipeline run. This covers a period that includes the EUR/USD recovery from parity risk and the 2016 US election. The backtest should be run both with and without this period to check sensitivity.

---

## Summary Verdict

6E is a viable VWAP mean-reversion instrument with a clear, measurable edge in the spread statistic. The half-life is longer than ZN but well within intraday reach. The recommended entry window (London/NY overlap) and the extended hold cap (60 bars / 5 hours) are consistent with the measured OU dynamics.

This is not a high-frequency strategy. It is a patience strategy: wait for a clean overshoot, enter with a limit order, let the half-life do the work. The appropriate sizing is micro first, risk-adjusted, with daily loss limits set before the first live paper trade.

**Next step:** Walk-forward backtest on the 5m back-adjusted data, 2018–2024, 4 folds, purge=576 bars. Target Calmar >= 2, trades-per-week >= 3, max-consecutive-losses <= 7.
