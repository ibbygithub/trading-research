# 6A and 6C — Strategy Designs

**Author:** Quant Mentor (in voice)
**Session:** 34
**Date:** 2026-05-03
**Mode:** Exploration — these are hypotheses, not validated edges
**Status:** Design committed; implementation in this same session

---

## Mentor's framing — read this first

Two strategies. One per instrument. Different mechanics on purpose.

I'm picking these because they reflect what I actually believe about how
6A and 6C trade. They're not parameter twists on the failed
`vwap-reversion-v1`. They use different timeframes, different mechanics, and
they target different regimes. If both work, you've got two complementary
strategies. If one works, you have a winner. If neither works, you've
learned something real about these markets that the data didn't tell you
upfront.

These are exploration runs. **Do not run the validation gate on them.** Run
them, look at the trade logs, look at them on the chart, see what they
actually do. The data scientist will compute Calmar, Sharpe, max DD, win
rate, profit factor, time-in-trade — those are the numbers we look at to
decide whether the idea is interesting. We are not asking "is this ready
for capital." We are asking "is this onto something."

Why these two and not five? Because writing five strategies in one session
and running them all is exactly the kind of activity that makes the data
scientist nervous about multiple-testing bias. Two well-thought-out designs
beat ten lazy ones. We can sweep variants on the winners after session 35
when the sweep tool exists.

---

## Strategy 1 — 6A Session-VWAP Mean Reversion with ADX Trend Filter

**Strategy ID:** `6a-vwap-reversion-adx-v1`
**Module:** `trading_research.strategies.fx_vwap_reversion_adx`
**Instrument:** 6A (Australian Dollar futures, root @AD)
**Timeframe:** 15-minute bars
**Default tag:** `mode: "exploration"`

### Market thesis

6A — the Aussie dollar — is a risk-on currency. It moves with three things:
RBA rate expectations, China demand (iron ore and coal), and global risk
sentiment. Within an intraday session, it tends to mean-revert around
session VWAP *when there's no dominant story driving directional flow*.
When there *is* a story — a Chinese PMI surprise, an RBA hike, a risk-off
shock — the same VWAP reversion logic gets you run over because the spread
keeps widening as the move continues.

This is exactly what killed `vwap-reversion-v1` on 6E. The strategy didn't
know the difference between "spread is wide because the market is choppy
and will mean-revert" and "spread is wide because there's a trend that's
about to continue." Mean reversion in an FX trend is a great way to get
chopped to pieces.

ADX is the mentor's standard "how much trend is there" gauge. ADX < 20 is
weak trend / range-bound. ADX > 25 is meaningful trend. Between 20 and 25
is ambiguous. The filter says: only fade VWAP when ADX confirms there's
no real trend. This isn't a perfect filter — ADX is lagging — but it's the
class of filter that should have been on `vwap-reversion-v1` from day one.

I'm using **15-minute bars** instead of 5-minute. Session 28 measured the
6E VWAP-spread mean-reversion half-life at ~165 minutes. The same half-life
order of magnitude applies to 6A — these are FX pairs with similar session
structure. A 15-minute bar gives the trade room to breathe. Five-minute
bars on a 165-minute half-life is overtrading the noise.

I'm using **session VWAP** as the anchor. Weekly and monthly VWAP are
useful for swing setups but not for an intraday mean-reversion play. The
session-anchored VWAP resets at the session boundary and the price's
distance from it is meaningful within the session.

### Entry rules

**LONG** — all three conditions must be true on the signal bar's close:

1. `close < (vwap_session - entry_atr_mult × atr_14)`
   Price has fallen meaningfully below the session anchor.
2. `adx_14 < adx_max`
   No strong trend in either direction. Fading is safe.
3. Bar timestamp falls in the **London/NY overlap window** (12:00–17:00 UTC).
   This is when 6A liquidity is best and intraday mean reversion is most
   reliable. Asian session moves on different drivers (overnight news,
   Australian morning data) and is choppier.

**SHORT** — mirror image:

1. `close > (vwap_session + entry_atr_mult × atr_14)`
2. `adx_14 < adx_max`
3. Bar in 12:00–17:00 UTC.

### Exit rules

- **Target:** session VWAP. Mean-reversion plays target the mean, not a
  fixed-tick distance. If the spread reverts, take it.
- **Stop:** `signal_bar_close ∓ stop_atr_mult × atr_14`. ATR-based stop
  scales with realised volatility; 1.5× ATR is the default starting point.
- **Time stop:** EOD flatten. The engine handles this with `eod_flat: true`.
  Single-instrument 6A positions do not stay open overnight — too much gap
  risk on RBA / Chinese-data / overnight-headline events. (See `CLAUDE.md`
  standing rule on overnight gap risk.)

### Default knobs

```yaml
entry_atr_mult: 1.5    # spread width that triggers entry
stop_atr_mult: 1.5     # stop distance in ATR units
adx_max: 22            # below this, classify as range-bound
overlap_start_utc: "12:00"
overlap_end_utc: "17:00"
```

### Honest expectations

- Win rate likely 50–60% (mean reversion strategies typically have high
  win rate but smaller average winner than loser).
- Max consecutive losses likely 5–10 in normal conditions, can spike to
  15+ during sustained trending regimes that the ADX filter catches late.
- Expected trades: ~20–40/month given the time-of-day filter and ATR-based
  entry threshold.
- Calmar target: > 1.0 for "interesting." > 2.0 for "shortlist for validation."

### What would make this fail

- ADX filter is too lagging — by the time it confirms "no trend," the move
  is already done. Symptom: low win rate, getting filled near the bottom
  of moves that then continue.
- 6A simply trends more than I'm assuming during 2010–2025. Symptom: ADX
  filter gates out most setups, trade count is too low to be meaningful.
- Session VWAP is the wrong anchor for 6A. Maybe weekly VWAP is the
  meaningful mean for a currency pair. Symptom: trades hit stop frequently
  before reverting; target rarely hit.

If any of these show in the results, we iterate — different filter, different
anchor, different timeframe. The point of the lab is to find out.

---

## Strategy 2 — 6C Donchian Breakout with Daily EMA Trend Confirmation

**Strategy ID:** `6c-donchian-breakout-ema-v1`
**Module:** `trading_research.strategies.fx_donchian_breakout`
**Instrument:** 6C (Canadian Dollar futures, root @CD)
**Timeframe:** 60-minute bars
**Default tag:** `mode: "exploration"`

### Market thesis

6C — the Canadian dollar — is a petro-currency. Its dominant driver is
crude oil (WTI). When oil moves meaningfully, CAD moves with it; when oil
is range-bound, CAD often is too. The result is **bimodal regime structure**:
long stretches of low-volatility chop punctuated by directional regime
shifts that last days to weeks.

A mean-reversion strategy on 6C would die in the directional regimes.
A breakout strategy would die in the chop. The trick is to only take
breakouts when there's a confirmed longer-term trend supporting the move.
That's what the daily-EMA filter does.

I'm using **60-minute bars** because oil-driven CAD moves play out over
hours-to-days, not minutes. A 5-minute breakout strategy on 6C is fishing
in noise. A 60-minute breakout signal that aligns with a 50/200 daily EMA
trend says: "the market just made a new 20-hour high, and the longer-term
trend agrees with that direction." That's a meaningful signal.

I'm using **Donchian(20)** as the breakout indicator. 20 bars at 60m =
20 hours = roughly two trading sessions. That's the timescale on which
oil-driven moves typically play out. Shorter Donchian periods are too
twitchy; longer periods miss the move.

I'm using **daily EMA(50) vs EMA(200)** as the trend filter — the classic
"golden cross / death cross" alignment. This is unfashionable to mention
because every retail trader knows it, but it works for a reason: it filters
out chop while letting through real trends. The base-v1 features layer
already projects daily EMAs onto every intraday bar with a 1-bar shift to
prevent look-ahead, so this is essentially free to use.

### Entry rules

**LONG** — both conditions on the signal bar's close:

1. `close > donchian_upper.shift(1)`
   The current bar made a new 20-bar high (shifted by 1 to compare current
   close against the prior 20 bars' max high — without including the
   current bar in its own benchmark).
2. `daily_ema_50 > daily_ema_200`
   Long-term trend is up.

**SHORT** — mirror:

1. `close < donchian_lower.shift(1)` — new 20-bar low.
2. `daily_ema_50 < daily_ema_200` — long-term trend is down.

### Exit rules

- **Target:** `signal_bar_close ± target_atr_mult × atr_14`. Breakout
  targets are ATR-multiples, not VWAP. 3× ATR is the default starting point.
- **Stop:** `signal_bar_close ∓ stop_atr_mult × atr_14`. 1.5× ATR.
  This gives a 2:1 reward:risk ratio (3 ATR target / 1.5 ATR stop), which
  is the minimum for a breakout strategy with sub-50% win rate to be
  profitable after costs.
- **Time stop:** `max_holding_bars: 48` (i.e. 48 hours = ~2 trading days
  on 60m). Breakouts that don't extend within 2 days probably won't.
- **EOD flat:** `false`. Breakouts can hold overnight when a multi-day
  oil move is in progress. The risk of overnight gaps is offset by the
  longer-term trend confirmation. This is an explicit override of the
  default single-instrument-flat-by-EOD rule, justified because the
  thesis itself is multi-day.

### Default knobs

```yaml
donchian_period: 20        # bars for high/low calc
target_atr_mult: 3.0       # take-profit distance
stop_atr_mult: 1.5         # stop distance — 2:1 reward:risk
max_holding_bars: 48       # time stop in bars (~2 trading days at 60m)
```

### Honest expectations

- Win rate likely 35–45% (typical for breakout strategies).
- Max consecutive losses likely 6–12. Breakouts have streaky losers in
  ranging markets.
- Expected trades: ~5–15/month — much sparser than the mean-reversion
  strategy because the EMA filter has to be aligned and the market has
  to actually break out. This is fine. Breakout strategies are supposed
  to be sparse.
- Calmar target: > 1.5 for "interesting." > 2.5 for "shortlist."
- Profit factor target: > 1.5. The reward:risk math means even a 40% win
  rate at 2:1 R:R produces PF ≈ 1.33; we want a margin of safety.

### What would make this fail

- 6C doesn't trend reliably even when oil does. The link is real but
  noisy and could be insufficient for breakout statistics. Symptom:
  high false-breakout rate, target rarely hit, average winner ≈ average
  loser.
- Daily EMA filter is too coarse — it stays "bullish" for weeks while the
  intraday market is actually rangebound. Symptom: many long signals during
  EMA-bullish chop that immediately reverse and stop out.
- ATR target is wrong because oil-driven moves are larger than 3× ATR
  when they happen. Symptom: targets get hit early on what would have been
  bigger winners; trailing-stop variant might be needed.
- Overnight hold causes ugly gap fills on Mondays after weekend headlines.
  Symptom: fat-left-tail in the equity curve that the metrics smooth over.

If overnight hold turns out to be the killer, we revisit with EOD flat
and shorter timeframe. The breakout thesis can still work intraday on
oil-driven days; the 60m + overnight choice is the more aggressive form.

---

## Why these two together

The two strategies are deliberately complementary:

| Property | Strategy 1 (6A VWAP MR) | Strategy 2 (6C Donchian BO) |
|---|---|---|
| Mechanic | Mean reversion | Breakout (trend continuation) |
| Timeframe | 15m | 60m |
| Hold style | Intraday | Multi-day (up to 48h) |
| Hold direction | Counter-move (fade) | With-move (continuation) |
| Regime that helps | Chop / no trend | Oil-driven trend |
| Regime that hurts | Trending FX moves | Range-bound oil |
| Win rate target | 55% | 40% |
| Trade frequency | ~30/month | ~10/month |

If both work, they don't correlate — they win in different market regimes.
That's the kind of pair that becomes a real portfolio once they each survive
validation independently. If only one works, you have a candidate. If
neither works, you have learned something concrete about why FX intraday
mean reversion or breakout doesn't pay on these instruments and you go
back to the lab.

---

## What this is NOT

- This is not a sweep. Each strategy gets one default-knob backtest in this
  session. Sweeps come in session 38 after the sweep tool exists in 35.
- This is not a validation run. We are not running the seven-criterion gate
  from sprint 33. We are looking at trade logs, equity curves, and the
  basic metric panel.
- This is not a commitment. If the trade log looks ugly when we click
  through it on the replay app, the design gets revised. That's the point.

---

## Mentor's signature

> These are honest first attempts. They use the indicators we have, the
> instruments we just downloaded, and the timeframes that match how
> these markets actually move. They might work. They might not. The
> point of having a research lab is finding out cheaply.
>
> If either one shows promise on the first run, the next session's job is
> to sweep parameters and see if the edge is robust. If neither shows
> promise, that's also data — it tells us something about 2010–2025 FX
> structure that we then incorporate into the next round of designs.
>
> Run them. Show me the trade logs. We'll talk.
>
> — Quant Mentor, 2026-05-03
