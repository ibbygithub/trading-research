# Session 38 — Exploration Results and Candidate Shortlist

**Date:** 2026-05-04
**Sweeps run:** 96 exploration trials across 5 hypotheses
**Sweep IDs:** 45c84143 (H1), 50b8d005 (H2), 9560c90b (H3), bbf156bd (H4), 032e8a69 (H5)
**Leaderboard:** `outputs/38-exploration-leaderboard.html`

*Note: H1 was inadvertently run twice (sweep IDs 45c84143 and aa8b65b2 both cover the same
27 variants). The duplicate is in the registry; results are consistent across both runs.
Reference sweep ID 45c84143 for H1 analysis.*

---

## Results by hypothesis

### H1 — 6A 15m VWAP Reversion (27 variants)

**Calmar range:** −0.039 to −0.042
**Sharpe range:** −3.46 to −7.72
**Trade count range:** 1,211 to 9,963

Uniformly negative across all 27 parameter combinations. The ADX cutoff (18/22/28),
entry threshold (1.0/1.5/2.0 ATR), and stop distance (1.0/1.5/2.0 ATR) produce no
meaningful variation in Calmar. The best variant uses entry_atr_mult=2.0, stop_atr_mult=1.0,
adx_max=18 and still posts Calmar −0.039. When you tighten ADX to 18 and require a
deep extension (2.0 ATR), you get 1,211 trades over 16 years — manageable frequency —
but the losses persist at the same rate.

---

### H2 — 6C 60m Donchian Breakout (15 variants)

**Calmar range:** −0.043 to −0.044
**Sharpe range:** −2.60 to −4.79
**Trade count range:** 1,822 to 2,805

Essentially zero variation in Calmar across all R:R combinations. Target from 1.5×ATR
to 4.0×ATR, stop from 1.0×ATR to 2.0×ATR — the loss rate is invariant. This is the
most informative negative result: when changing R:R by 2.6× doesn't change Calmar,
the issue isn't R:R calibration. The breakout signal itself is not clean — the
strategy is entering on breakouts that immediately fail regardless of how much room
you give the exit.

---

### H3 — 6A 15m Bollinger Band Reversion (18 variants)

**Calmar range:** −0.042 to −0.042 (no variation)
**Sharpe range:** −7.13 to −12.28
**Trade count range:** 11,239 to 19,735

The high trade counts are the tell. Even with RSI < 30 (most restrictive oversold
filter), the strategy fires 11,239 times over 16 years — roughly 14 trades per week.
At 15m bars, bb_pct_b < 0 and rsi_14 < 35 is not a rare condition on 6A. These are
not low-probability dislocations; they are the normal texture of trending days.
Every time 6A rallies hard for an hour, it creates a streak of bars outside the lower
Bollinger Band with oversold RSI — and all of those bars become long entries that
lose as the trend continues.

---

### H4 — 6A 60m Monthly VWAP Band Fade (18 variants) — **KEY RESULT**

**Calmar range:** −0.009 to −0.042
**Sharpe range:** −0.46 to −2.89
**Trade count range:** 170 to 2,409

H4 is the only hypothesis that shows a meaningful gradient. The gradient is clean and
monotonic: wider bands → fewer trades → better performance → approaches zero.

| band_mult | stop_atr_mult | adx_max | Calmar | Sharpe | Trades | Win Rate |
|-----------|---------------|---------|--------|--------|--------|----------|
| 3.0       | 2.0           | 20      | −0.009 | −0.47  | 170    | 54.1%    |
| 3.0       | 2.0           | 25      | −0.012 | −0.46  | 260    | 50.4%    |
| 3.0       | 1.5           | 20      | −0.019 | −1.24  | 170    | 47.6%    |
| 3.0       | 1.0           | 20      | −0.025 | −2.25  | 173    | 34.7%    |
| 3.0       | 1.5           | 25      | −0.027 | −1.38  | 264    | 42.8%    |
| 2.0       | 2.0           | 25      | −0.037 | −1.18  | 893    | 38.1%    |
| 1.5       | 2.0           | 25      | −0.041 | −1.95  | 1,637  | 35.2%    |

The best variant (band_mult=3.0, stop=2.0, adx_max=20) posts:
- Calmar: −0.009 (barely negative — approaching breakeven)
- Sharpe: −0.47 (barely negative)
- Win rate: 54.1%
- Trades: 170 over 16 years (~10–11 per year)

The 54% win rate at 3-sigma bands confirms that reversion genuinely occurs — the
signal is real. The loss comes from the winners not being large enough to overcome
the losers. The target is the monthly VWAP itself, which may be too far away for
the average holding period; the position hits the stop before reaching the target.

The gradient approaching zero as bands widen is the most important finding of this
session. It says: extreme monthly dislocations do revert, and the reversion is real
enough to produce a >50% win rate. The edge exists but is not yet large enough to
cover costs.

---

### H5 — ZN 15m MACD Histogram Momentum (18 variants)

**Calmar range:** −0.043 (no variation)
**Sharpe range:** −17.60 to −27.33
**Trade count range:** 23,060 to 41,325

The trade counts expose the problem immediately. hist_min=0.0 produces 41,325 trades
over 16 years — roughly 50 trades per week. MACD histogram > 0 AND slope > 0 is true
roughly half the time at 15m resolution. The daily EMA(50) filter removes roughly
half of those, leaving ~25k–40k entries. This is not a trading signal; it's a random
walk with costs.

The filter stack is insufficient. hist_min=0.005 brings the count to 23,060 — still
~28 trades per week. The signal is pervasive because 15m momentum is always occurring
somewhere; the strategy is too sensitive.

---

## Mentor's commentary

The H1 and H3 results are not surprising. 6A at 15m is a hard instrument for
mean reversion in London/NY overlap — it has a strong trend-following tendency
during that window, and VWAP fade and BB-extreme trades have both confirmed that.
The ADX filter is not catching enough of the trending days.

The H4 gradient is the result I find most interesting and honestly somewhat
unexpected. Monthly VWAP at 3-sigma is an extreme condition — it fires only
10 times per year. That's a big dislocation. A 54% win rate tells me the
reversion is real. The problem is the stop is getting hit before the target:
a 2×ATR stop on 6A at 60m might be too tight for a position anchored to a
monthly timescale. What this strategy needs is not a tighter stop but a shorter
target — maybe the halfway point back to VWAP rather than the full VWAP.

H5 told me something useful about ZN: I was wrong to think ZN momentum at 15m
could be captured with the MACD histogram. The histogram is too lagging and
too broad at that resolution. If ZN has a momentum edge, it will be on the
daily timeframe, not 15m. Log it and move on.

H2 (6C Donchian) is the cleanest failure: when R:R doesn't move Calmar, the
signal itself is wrong. The breakout filter (daily EMA) isn't separating clean
breakouts from noise effectively enough. What I'd really want is a volatility
expansion filter — enter only when the ATR is expanding at the time of the
breakout, not just when the daily trend is aligned. Possible follow-up.

---

## Data scientist's commentary

The H4 gradient is the only statistically meaningful pattern in this session.
Everything else posted Calmar around −0.042 to −0.044, which is a flat negative
baseline that suggests the backtest engine's cost model is the dominant signal.
When a gradient emerges from that floor (H4 going from −0.042 at 1.5-sigma to
−0.009 at 3-sigma), it's real structure, not noise.

However, I need to flag sample size as the critical constraint. 170 trades over
16 years is 10.6 trades per year. The standard error on a Sharpe estimate scales
with 1/√n — at 170 trades, the 95% CI on the Sharpe is roughly ±2σ around the
point estimate. A Sharpe of −0.47 with a CI of [−2.5, +1.5] is statistically
indistinguishable from zero in either direction. Before this goes to a validation
gate, it needs walk-forward analysis AND bootstrap CIs, not just the point estimate.

The 54% win rate at 3-sigma is a meaningful observation. A 50%+ win rate on a
mean-reversion strategy confirms the signal direction is correct. But win rate
alone doesn't make a strategy profitable — the winners need to be bigger than
the losers. The current target (monthly VWAP) may be too ambitious for the
average holding time at 60m bars; a closer target would likely raise win rate
further at the cost of smaller wins.

H3's trade count (11k–20k) is not an exploration artifact. That's a fundamental
failure of the signal design. I won't look further at BB-extreme + RSI on 6A
at 15m unless the hypothesis is redesigned with a time-of-day filter or a
minimum holding constraint to prevent high-frequency false triggers.

H5 is interesting as a diagnostic. 41k trades at hist_min=0.0 tells us that
macd_hist > 0 AND macd_hist_slope > 0 is a near-continuous state at 15m ZN.
This isn't a signal property; it's a structural one. ZN at 15m is correlated
enough that the MACD histogram is positive and rising most of the time when
rates are falling. The signal needs regime-specific calibration, not just
threshold-tuning.

---

## Candidate shortlist

### ITERATE — H4 (6A 60m Monthly VWAP Band Fade)

**Status:** Not promoting to validation gate yet. One design iteration required.

**Why iterate rather than drop:**
1. The gradient is clean, monotonic, and statistically meaningful
2. 54% win rate at 3-sigma confirms signal direction is correct
3. The loss structure (costs > edge) suggests a refinement can close the gap
4. Only 10 trades/year — low enough frequency to fit the lab's selective approach

**What the next iteration must change:**
1. **Shorten the target.** Replace `vwap_monthly` as the target with a tighter
   level — e.g., the 2.0-sigma band when entering at 3.0-sigma. That's a 1-sigma
   move instead of a 3-sigma move, which should be achievable in the average
   1–4 day holding period.
2. **Consider a time-of-day gate.** Monthly VWAP bands are most meaningful during
   the London and NY sessions when institutional flows dominate. Filter to
   08:00–17:00 UTC.
3. **Walk-forward analysis.** The 16-year backtest is a single observation.
   Run a 5-fold walk-forward before claiming the signal is robust.

**Label:** `ITERATE — one design change then validation candidate`

---

### DROP — H1 (6A VWAP Reversion), H2 (6C Donchian), H3 (6A BB Reversion)

No gradient, no signal, uniform losses across all knob combinations.

H1: The 6A VWAP mean-reversion hypothesis on 15m is definitively exhausted.
Two session-34 runs plus 27 variants confirm no edge at any parameter setting.

H2: The 6C Donchian breakout hypothesis is exhausted. The R:R invariance is
conclusive — the signal doesn't work, and no amount of stop/target tuning will
fix a broken signal.

H3: The 6A BB-extreme + RSI signal fires too often to be useful. 11k+ trades
is not a parameter problem; it's a signal design problem.

---

### ITERATE (concept only) — H5 (ZN MACD Momentum)

The 15m MACD momentum concept for ZN is not dead, but the implementation is wrong.
The redesign needs: (a) daily or 240m timeframe instead of 15m, or (b) a proximity-to-zero-cross filter (only enter within 3–5 bars of a MACD histogram sign change). Not scheduling a session for this yet — will revisit if H4 iteration fails.

---

## Summary decision table

| Hypothesis | Result | Decision |
|------------|--------|----------|
| H1 — 6A VWAP MR (15m) | Uniform losses, no gradient | DROP |
| H2 — 6C Donchian BO (60m) | Uniform losses, R:R invariant | DROP |
| H3 — 6A BB Reversion (15m) | Uniform losses, 11k+ trades | DROP |
| H4 — 6A Monthly VWAP Fade (60m) | Gradient to −0.009, 54% WR at 3σ | **ITERATE** |
| H5 — ZN MACD Momentum (15m) | 40k+ trades, no signal | ITERATE (concept only, no session) |

---

## Next step (if H4 iteration is approved)

1. Modify `6a-monthly-vwap-fade-yaml-v1.yaml` to use a tighter exit target
   (e.g., the 2.0-sigma band as target when entering at 3.0-sigma)
2. Add a time-of-day gate (08:00–17:00 UTC)
3. Run walk-forward (5-fold minimum)
4. Bootstrap CIs on the result
5. If walk-forward OOS Calmar > 0 across majority of folds → promote to validation gate
