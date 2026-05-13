# Session 38 — Five Exploration Hypotheses

**Date:** 2026-05-04
**Author:** Quant Mentor persona + Platform Architect sign-off
**Status:** Active — governing document for session-38 sweeps

---

## Context

Sessions 34–37 built the research-lab tooling: 6A/6C pipelines, YAML strategy
authoring, parameter sweep, leaderboard, multi-TF join, composable regime filters.
Session 38 is the first payoff: run the tools against five real hypotheses and
produce a candidate shortlist.

Two hypotheses (H1, H2) extend work from session 34. Three are new (H3–H5).
All are tagged `mode: "exploration"`. None are being approved for capital.

---

## H1 — 6A 15m Session-VWAP Mean Reversion (deep sweep)

**Market thesis.** The Australian dollar futures contract has a daily range
that concentrates in the London/NY overlap (12:00–17:00 UTC). During this
window, 6A tends to revert to its session VWAP after overextensions, especially
when ADX confirms a range-bound regime. The default knobs were too conservative
(entry_atr_mult=1.5 waits for a large extension that rarely recovers cleanly).

**What we didn't explore.** The session-34 run used a single set of knobs.
The ADX cutoff, entry threshold, and stop distance interact: a tighter entry
threshold fires more trades but with worse R:R; a looser ADX allows more false
entries. We need a grid.

**Config:** `configs/strategies/6a-vwap-reversion-adx-yaml-v1.yaml`
**Timeframe:** 15m
**Sweep:**
```
entry_atr_mult = 1.0, 1.5, 2.0
stop_atr_mult  = 1.0, 1.5, 2.0
adx_max        = 18, 22, 28
```
**Variants:** 3 × 3 × 3 = 27

**What would make this interesting.** A cluster of profitable variants at
low entry_atr_mult (1.0–1.25) + tight stop (1.0×ATR) would suggest the edge
is in fast, tight fades. A cluster at high entry_atr_mult (2.0) would suggest
only deep dislocations are tradeable. Either pattern is real information.

**What would kill it.** Uniform losses across all 27 variants means there's
no edge in this structure for 6A at 15m. We'll know definitively.

---

## H2 — 6C 60m Donchian Breakout (deep sweep)

**Market thesis.** The Canadian dollar tracks crude oil and has sustained
directional moves that can last 2–5 days. A breakout above/below the prior
20-bar high/low, confirmed by daily EMA(50)/EMA(200) trend alignment, should
catch the early part of these moves. The session-34 run had a 33% win rate —
mathematically close to break-even on 2:1 R:R but with an average loss that
exceeded average win.

**What we didn't explore.** The R:R ratio. At 3:1 target (target_atr_mult=3.0)
and 1.5:1 stop, the strategy needs a 33% win rate to break even. With 33%
actual win rate, it loses to slippage. Loosening the target (4:1) captures
bigger moves but fires fewer trades. Tightening the stop (1.0×ATR) raises win
rate but cuts the profitable runs short. We need the grid.

**Config:** `configs/strategies/6c-donchian-breakout-yaml-v1.yaml`
**Timeframe:** 60m
**Sweep:**
```
target_atr_mult = 1.5, 2.0, 2.5, 3.0, 4.0
stop_atr_mult   = 1.0, 1.5, 2.0
```
**Variants:** 5 × 3 = 15

**What would make this interesting.** Variants at 2:1 or 4:1 R:R outperforming
the default 2:1 would identify the natural holding structure of 6C moves.

**What would kill it.** Losses across all R:R ratios means the trend filter
isn't cleanly separating trending from ranging periods.

---

## H3 — 6A 15m Bollinger Band Mean Reversion

**Market thesis.** Bollinger Band extremes (bb_pct_b < 0.0 or > 1.0) mark
statistically significant dislocations relative to the recent 20-bar range.
When RSI confirms oversold/overbought conditions simultaneously, the probability
of reversion within a few bars is elevated. This is a tighter, more mechanical
version of the VWAP fade — no session anchor, just recent-range structure.

**Why RSI is the additional filter.** bb_pct_b alone fires frequently on
trending days. RSI below 35 (long) or above 65 (short) adds a secondary
oversold/overbought confirmation that filters out trend continuation breakouts.

**New config:** `configs/strategies/6a-bb-reversion-yaml-v1.yaml`
**Timeframe:** 15m
**Sweep:**
```
rsi_oversold   = 30, 35, 40
stop_atr_mult  = 1.0, 1.5, 2.0
target_atr_mult = 1.5, 2.0
```
**Variants:** 3 × 3 × 2 = 18
(rsi_overbought held at its default mirror of 100 - rsi_oversold via separate knob)

**What would make this interesting.** A narrow band of rsi_oversold=35–40
outperforming the more extreme 30 threshold would suggest the edge is in
moderately oversold conditions, not just extreme ones. That's a real market
finding.

**What would kill it.** Win rate stays below 40% across all variants.
Bollinger Band extremes on 6A at 15m might be more trend-continuation
than mean-reverting.

---

## H4 — 6A 60m Monthly VWAP Band Fade

**Market thesis.** Monthly VWAP anchors institutional cost basis for the
month's positioning. Prices at 2+ standard deviations from the monthly VWAP
represent significant institutional-level dislocations — the kind that attract
counter-trend flows as month-end approaches and positions are squared. This is
a longer-timeframe mean reversion on a longer anchor than session VWAP.

**Why 60m instead of 15m.** Monthly-VWAP dislocations develop over hours,
not minutes. Entering on 15m bars generates too many false starts before the
dislocation is confirmed. 60m bars are the right resolution.

**Why ADX filter.** Monthly-VWAP fades fail in strong directional months
(e.g. a sustained USD rally when the Fed is tightening). ADX below a threshold
limits entries to months where range-bound chop dominates.

**New config:** `configs/strategies/6a-monthly-vwap-fade-yaml-v1.yaml`
**Timeframe:** 60m
**Sweep:**
```
band_mult     = 1.5, 2.0, 3.0
stop_atr_mult = 1.0, 1.5, 2.0
adx_max       = 20, 25
```
**Variants:** 3 × 3 × 2 = 18

**What would make this interesting.** Variants at band_mult=2.0–3.0 with
a reasonable ADX cap (adx_max=20–25) posting positive Calmar would confirm
that institutional-anchor-level dislocations have real mean-reversion pull.

**What would kill it.** Monthly VWAP bands may be too slow-moving to be
useful intraday. The band value changes very slowly through the month;
a price touching the 2-sigma monthly band might be in a genuine trend that
lasts weeks. High max consecutive losses would be the signal.

---

## H5 — ZN 15m MACD Histogram Momentum

**Market thesis.** ZN definitively failed mean reversion (sprint 33 gate
verdict). But the stationarity analysis showed ZN has momentum structure —
it trends. The MACD histogram captures momentum acceleration: when histogram
is positive AND accelerating (slope > 0) AND price is above the daily 50-EMA
(trend-aligned), the bond is in a confirmed short-term momentum regime. This
is the opposite trade from anything we've tried on ZN.

**Why MACD histogram slope specifically.** The histogram level alone is too
slow — it turns positive after the move starts. The slope (first difference)
is a leading indicator of the histogram's direction, firing near the point of
momentum inflection. Combined with the daily trend filter, this should isolate
clean directional conditions.

**New config:** `configs/strategies/zn-macd-momentum-yaml-v1.yaml`
**Timeframe:** 15m
**Sweep:**
```
hist_min        = 0.0, 0.001, 0.005
stop_atr_mult   = 1.0, 1.5, 2.0
target_atr_mult = 1.5, 2.0
```
**Variants:** 3 × 3 × 2 = 18

**What would make this interesting.** Any positive Calmar across multiple
variants is significant because ZN has never produced a profitable strategy
in this project. Even Calmar > 0 with low confidence would justify promotion
to a validation run.

**What would kill it.** The MACD histogram is a lagging indicator on futures
with compressed intraday range (ZN's daily ATR is much smaller than it was
pre-2023). If hist_min=0.005 produces zero trades because the histogram never
reaches that threshold on 15m bars, we'll know the indicator is the wrong tool.

---

## Sweep summary

| Hyp | Instrument | TF | Config | Variants | New config? |
|-----|------------|----|--------|----------|-------------|
| H1  | 6A | 15m | `6a-vwap-reversion-adx-yaml-v1.yaml` | 27 | No |
| H2  | 6C | 60m | `6c-donchian-breakout-yaml-v1.yaml`   | 15 | No |
| H3  | 6A | 15m | `6a-bb-reversion-yaml-v1.yaml`        | 18 | Yes |
| H4  | 6A | 60m | `6a-monthly-vwap-fade-yaml-v1.yaml`   | 18 | Yes |
| H5  | ZN | 15m | `zn-macd-momentum-yaml-v1.yaml`       | 18 | Yes |

**Total: 96 exploration trials**

---

## What this session is NOT

- Not a validation gate run. No candidate is approved for capital here.
- Not a deployment review. The lab proves out; live capital is a separate decision.
- Not curve-fitting. Each hypothesis was designed from market structure reasoning
  before looking at any results. The post-sweep commentary will flag any result
  that looks suspiciously curve-fitted.
