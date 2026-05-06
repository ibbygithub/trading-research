# Chapter 7 — Indicator Library

> **Chapter status:** [EXISTS] — all indicators documented here are
> implemented and included in base-v1 (and where noted, base-v2).
> Cite paths are stable at v1.0.

---

## 7.0 What this chapter covers

The platform computes indicators in one place — the feature builder in
[`src/trading_research/indicators/`](../../src/trading_research/indicators/)
— and serves them through FEATURES parquets to strategies and backtests.
Strategy code does not compute indicators; it reads columns from a flat
matrix.

After reading this chapter you will:

- Know every indicator in base-v1, its formula, its parameters, and
  the column names it produces
- Understand the VWAP family — session, weekly, monthly — and their
  standard-deviation bands
- Understand the higher-timeframe (HTF) projection design and the
  look-ahead rule that makes it honest
- Be able to add a new indicator without contaminating existing feature
  sets

This chapter is roughly 8 pages. It is referenced by Chapter 8 (Feature
Sets), Chapter 10 (YAML Strategy Authoring), Chapter 11 (Expression
Evaluator), and Chapter 7.12 (adding indicators).

---

## 7.1 Catalogue of indicators in base-v1

Eight indicator families compute on the bar's native timeframe. Three
VWAP flavors compute on the 1-minute frame and are sampled at each
bar's close timestamp. Seven HTF columns project daily-bar values
forward onto the intraday frame, shifted by one session to prevent
look-ahead.

| Family | Module | Columns produced | In base-v1 | In base-v2 |
|--------|--------|-----------------|-----------|-----------|
| ATR | `atr.py` | `atr_14` | Yes | Yes (inherited) |
| RSI | `rsi.py` | `rsi_14` | Yes | Yes |
| Bollinger | `bollinger.py` | `bb_mid`, `bb_upper`, `bb_lower`, `bb_pct_b`, `bb_width` | Yes | Yes |
| MACD + derived | `macd.py` | 7 columns (see §7.5) | Yes | Yes |
| SMA | `sma.py` | `sma_200` | Yes | Yes |
| Donchian | `donchian.py` | `donchian_upper`, `donchian_lower`, `donchian_mid` | Yes | Yes |
| ADX | `adx.py` | `adx_14` | Yes | Yes |
| OFI | `ofi.py` | `ofi_14` | Yes | Yes |
| EMA | `ema.py` | `ema_9`, `ema_20` | No | Yes (added in v2) |
| CCI | (registered) | `cci_14` | No | Yes (added in v2) |
| VWAP session | `vwap.py` | 5 columns (see §7.10) | Yes | Yes |
| VWAP weekly | `vwap.py` | 5 columns | Yes | Yes |
| VWAP monthly | `vwap.py` | 5 columns | Yes | Yes |
| HTF projections | `features.py` | 7 daily columns (see §7.11) | Yes | Yes |

---

## 7.2 ATR — Average True Range

**Module:** [`src/trading_research/indicators/atr.py`](../../src/trading_research/indicators/atr.py)

**Formula.** True Range is the maximum of three quantities:

```
TR = max(high − low,
         |high − prev_close|,
         |low  − prev_close|)
```

ATR is the Wilder EMA of True Range: `alpha = 1/period`, equivalent to
`ewm(span=2*period−1)`. The first `period` rows are set to NaN (the
initial bar has no previous close, making TR unreliable).

**Column produced:** `atr_14` (with default `period=14`)

**Parameters:** `period` (default 14)

**Common use.** ATR is the primary volatility scale in base-v1. It
appears in stop expressions (`close - stop_atr_mult * atr_14`),
entry-distance conditions, and position sizing. A 14-period ATR at
the 5-minute timeframe for ZN is typically 0.06–0.12 points (6–12
ticks), depending on the volatility regime.

> *Interpretation note:* ATR tells you the recent range, not the
> direction. A rising ATR means wider bars — more opportunity and
> more risk. A falling ATR (the "squeeze") often precedes a breakout;
> Bollinger `bb_width` is the complement for detecting squeezes in
> percentage terms.

---

## 7.3 RSI — Relative Strength Index

**Module:** [`src/trading_research/indicators/rsi.py`](../../src/trading_research/indicators/rsi.py)

**Formula.** Wilder smoothed:

```
delta    = close.diff()
avg_gain = Wilder EMA of max(delta, 0)
avg_loss = Wilder EMA of max(−delta, 0)
RS       = avg_gain / avg_loss
RSI      = 100 − 100 / (1 + RS)
```

When `avg_loss == 0` (all gains in the lookback), RSI returns 100
by convention. First `period` rows are NaN.

**Column produced:** `rsi_14`

**Parameters:** `period` (default 14)

**Common use.** RSI is an oscillator bounded in [0, 100]. The
standard mean-reversion interpretation: RSI > 70 indicates
overbought conditions; RSI < 30 indicates oversold. These thresholds
are *distributions*, not binary triggers — a strategy that uses them
as the sole entry condition is almost certainly under-constrained. In
base-v1 strategies, RSI most commonly appears in conjunction with
a price-based condition (VWAP distance, Bollinger band position).

> *Distributional caveat (data scientist):* RSI's distribution in
> trending markets is not symmetric around 50. In a strong uptrend,
> RSI can stay above 70 for extended periods without mean-reverting.
> ADX (§7.8) is the correct companion — use ADX < 20 as a regime
> gate before treating RSI extremes as mean-reversion signals.

---

## 7.4 Bollinger Bands

**Module:** [`src/trading_research/indicators/bollinger.py`](../../src/trading_research/indicators/bollinger.py)

**Formula:**

```
bb_mid   = SMA(close, period)
bb_upper = bb_mid + num_std × rolling_std(close, period)
bb_lower = bb_mid − num_std × rolling_std(close, period)
bb_pct_b = (close − bb_lower) / (bb_upper − bb_lower)
bb_width = (bb_upper − bb_lower) / bb_mid
```

First `period − 1` rows are NaN.

**Columns produced:** `bb_mid`, `bb_upper`, `bb_lower`, `bb_pct_b`,
`bb_width`

**Parameters:** `period` (default 20), `num_std` (default 2.0)

**Common use.** `bb_pct_b` is the primary mean-reversion signal: 0
means price is at the lower band, 1 means at the upper band, 0.5 at
the midline. Values outside [0, 1] mean price has closed beyond the
band. A typical fade entry: `bb_pct_b < 0.0` (below lower band) for
a long.

`bb_width` is the squeeze detector: low values mean the bands are
compressed relative to the midline, which often precedes a directional
move. A squeeze alone is not a directional signal — it is a regime
indicator that modulates the ATR scaling.

---

## 7.5 MACD with derived columns

**Module:** [`src/trading_research/indicators/macd.py`](../../src/trading_research/indicators/macd.py)

**Formula:**

```
EMA_fast    = EMA(close, fast=12)
EMA_slow    = EMA(close, slow=26)
macd        = EMA_fast − EMA_slow
macd_signal = EMA(macd, signal=9)
macd_hist   = macd − macd_signal
```

Warm-up: first `slow + signal − 1 = 34` rows are NaN for all MACD
columns.

**Columns produced:**

| Column | Type | Description |
|--------|------|-------------|
| `macd` | float | MACD line |
| `macd_signal` | float | Signal line (9-bar EMA of MACD) |
| `macd_hist` | float | Histogram: macd − macd_signal |
| `macd_hist_above_zero` | bool | `True` when histogram > 0 |
| `macd_hist_slope` | float | First difference of histogram (histogram[i] − histogram[i−1]) |
| `macd_hist_bars_since_zero_cross` | Int64 | Bars since histogram last crossed zero; resets on sign flip |
| `macd_hist_decline_streak` | Int64 | Signed streak (see below) |

**`macd_hist_decline_streak` encoding.** This column captures the
"fading momentum" pattern that motivates many of the platform's
mean-reversion entries:

- A positive value (+N) means the histogram magnitude has been
  *growing* for N consecutive bars (momentum strengthening).
- A negative value (−N) means the histogram magnitude has been
  *shrinking* for N consecutive bars (momentum fading).
- Resets to ±1 when the direction of the magnitude change reverses.
- Resets to +1 on a zero crossing (first bar of a new sign regime).

The canonical pattern for a short entry: `macd_hist_above_zero == True`
(histogram positive) AND `macd_hist_decline_streak <= -3` (magnitude
has been shrinking for at least 3 bars). In YAML expression form:

```yaml
- "macd_hist_above_zero == True"
- "macd_hist_decline_streak <= -3"
```

**Parameters:** `fast` (default 12), `slow` (default 26), `signal`
(default 9). The defaults are kept at the conventional 12/26/9 on
every timeframe — adjusting settings per timeframe means reacting to a
picture nobody else is looking at.

---

## 7.6 SMA — Simple Moving Average

**Module:** [`src/trading_research/indicators/sma.py`](../../src/trading_research/indicators/sma.py)

**Formula:** `SMA(close, period) = rolling mean of close over period bars`

**Column produced:** `sma_200` (with default `period=200`)

**Parameters:** `period` (default 200)

**Common use.** The 200-bar SMA on the native timeframe is a
trend-orientation filter. At 5-minute bars, 200 bars is roughly two
full RTH sessions — a medium-term trend indicator on the intraday
chart. At 15-minute bars, 200 bars is approximately 10 RTH sessions
(two weeks).

> *Platform note:* for trend orientation relative to the *daily* bar,
> use `daily_sma_200` or `daily_ema_200` from the HTF projections
> (§7.11). The native-timeframe `sma_200` is a different object — it
> moves faster and is appropriate for intraday regime filtering, not
> for daily bias.

---

## 7.7 Donchian Channels

**Module:** [`src/trading_research/indicators/donchian.py`](../../src/trading_research/indicators/donchian.py)

**Formula:**

```
donchian_upper = rolling_max(high, period)
donchian_lower = rolling_min(low, period)
donchian_mid   = (donchian_upper + donchian_lower) / 2
```

First `period − 1` rows are NaN.

**Columns produced:** `donchian_upper`, `donchian_lower`, `donchian_mid`

**Parameters:** `period` (default 20)

**Common use.** Donchian channels mark the `period`-bar high/low range.
In a mean-reversion context, price touching or breaching `donchian_upper`
or `donchian_lower` can be an entry trigger for a fade. They also serve
as dynamic stop references: for a long entered near `donchian_lower`, a
stop below `donchian_lower` is semantically cleaner than an ATR-based
stop.

---

## 7.8 ADX — Average Directional Index

**Module:** [`src/trading_research/indicators/adx.py`](../../src/trading_research/indicators/adx.py)

**Formula.** Wilder's directional movement system:

```
TR           = max(high−low, |high−prev_close|, |low−prev_close|)
+DM          = high−prev_high if > down_move and > 0, else 0
-DM          = prev_low−low if > up_move and > 0, else 0
smoothed_TR  = Wilder EMA of TR
+DI          = 100 × Wilder_EMA(+DM) / smoothed_TR
-DI          = 100 × Wilder_EMA(-DM) / smoothed_TR
DX           = 100 × |+DI − -DI| / (+DI + -DI)
ADX          = Wilder EMA of DX
```

Two warm-up phases: first `2 × period` rows are NaN.

**Column produced:** `adx_14`

**Parameters:** `period` (default 14)

**Interpretation:**

| ADX range | Regime interpretation |
|-----------|----------------------|
| < 20 | Ranging; mean-reversion strategies are in their element |
| 20–25 | Borderline; proceed with caution |
| > 25 | Trending; mean-reversion entries should be gated or stopped |
| > 40 | Strong trend; fading is high-risk |

ADX measures trend *strength*, not direction. A rising ADX means
directional movement is strengthening — whether long or short is
determined by +DI / -DI, not by ADX itself. The platform uses ADX
primarily as a regime gate: `adx_14 < 20` as a condition on mean-
reversion entries.

---

## 7.9 OFI — Order Flow Imbalance

**Module:** [`src/trading_research/indicators/ofi.py`](../../src/trading_research/indicators/ofi.py)

**Formula:**

```
raw_ofi = (buy_volume − sell_volume) / (buy_volume + sell_volume)
ofi_14  = rolling_mean(raw_ofi, period)   [min_periods=period]
```

Range: [−1, +1]. +1 = 100% buy-side pressure for the period. −1 =
100% sell-side.

**Column produced:** `ofi_14`

**Parameters:** `period` (default 14)

**Null handling.** If `buy_volume` or `sell_volume` is null for a bar
(see §6.1.1), that bar's `raw_ofi` is NaN, and the rolling mean
returns NaN whenever the period has insufficient non-null values. Any
strategy that uses `ofi_14` must handle the null case explicitly —
typically by adding `ofi_14 > threshold` as an entry condition (which
short-circuits to False when the column is NaN, suppressing the entry).

This is not optional. The platform's buy/sell volume coverage is
94%+ for ZN going back to 2010, but it is lower for older windows of
some FX instruments. A strategy that assumes `ofi_14` is always
non-null is wrong and will produce different results depending on what
data range it runs against.

> *OFI as a confirmation signal:* raw OFI is noisy at 1m resolution.
> The 14-bar rolling mean smooths the signal considerably. In 5m bars,
> `ofi_14` covers 70 minutes of order flow; in 15m bars, it covers 3.5
> hours. Use OFI as a confirmation for price-based entries, not as a
> primary signal.

---

## 7.10 VWAP family

**Module:** [`src/trading_research/indicators/vwap.py`](../../src/trading_research/indicators/vwap.py)

All three VWAP variants are computed on the **1-minute** base frame
and sampled at the close timestamp of each target-timeframe bar. The
formula uses close price as the "typical price" (the OHLC average is
not used, for simplicity) weighted by bar volume:

```
vwap = cumsum(close × volume) / cumsum(volume)
vwap_std = sqrt( cumsum(close² × volume) / cumsum(volume) − vwap² )
```

Each VWAP variant generates five columns: the VWAP itself and its
standard-deviation bands at 1.0σ, 1.5σ, 2.0σ, and 3.0σ.

### 7.10.1 Session VWAP

**Reset trigger:** whenever the gap between consecutive 1-minute
timestamps exceeds 60 minutes. This detects session boundaries without
requiring an explicit calendar lookup — a gap > 60 minutes is always
between sessions in Globex instruments.

**Columns:** `vwap_session`, `vwap_session_std_1_0`, `vwap_session_std_1_5`,
`vwap_session_std_2_0`, `vwap_session_std_3_0`

**Common use.** The session VWAP is the dominant mean-reversion anchor
for intraday strategies. Price more than 1.5σ–2.0σ below session VWAP
is the canonical long entry zone for the platform's ZN strategies;
the symmetric condition applies for shorts. The VWAP bands define
where "stretched" is.

### 7.10.2 Weekly VWAP

**Reset trigger:** first 1-minute bar of each ISO week, determined by
trade_date using the CME +6h convention (§4.5.1).

**Columns:** `vwap_weekly`, `vwap_weekly_std_1_0`, `vwap_weekly_std_1_5`,
`vwap_weekly_std_2_0`, `vwap_weekly_std_3_0`

**Common use.** The weekly VWAP captures institutional positioning over
the week. A strategy that sells the session VWAP but buys the weekly
VWAP — when those two levels are close together — has a double anchor
and a more defensible entry.

### 7.10.3 Monthly VWAP

**Reset trigger:** first 1-minute bar of each calendar month, by
trade_date.

**Columns:** `vwap_monthly`, `vwap_monthly_std_1_0`, `vwap_monthly_std_1_5`,
`vwap_monthly_std_2_0`, `vwap_monthly_std_3_0`

**Common use.** Monthly VWAP is a slower-moving anchor. At the start
of the month it is anchored to the open; by month-end it has absorbed
the full month's price action and volume distribution. It is most
useful as a regime filter — strategies that fade within the month VWAP
band are operating in a defined reference frame.

---

## 7.11 Higher-timeframe projections

The `htf_projections` block in a feature-set YAML specifies columns
computed on the daily bar and projected forward onto the intraday
frame. The projection is **shift(1)**: every intraday bar in session T
sees the daily indicator value through session T−1 (the prior day's
close), never session T's own close. This is the look-ahead prevention
described in Chapter 4, §4.6.

**Base-v1 HTF columns** (source: `1D` daily CLEAN parquet):

| Column | Formula | Description |
|--------|---------|-------------|
| `daily_ema_20` | EMA(close, 20) shifted 1 session | Daily 20-day EMA from prior session |
| `daily_ema_50` | EMA(close, 50) shifted 1 session | Daily 50-day EMA from prior session |
| `daily_ema_200` | EMA(close, 200) shifted 1 session | Daily 200-day EMA from prior session |
| `daily_sma_200` | SMA(close, 200) shifted 1 session | Daily 200-day SMA from prior session |
| `daily_atr_14` | ATR(14) shifted 1 session | Daily ATR from prior session |
| `daily_adx_14` | ADX(14) shifted 1 session | Daily ADX regime indicator from prior session |
| `daily_macd_hist` | MACD(12,26,9) histogram shifted 1 session | Daily momentum direction from prior session |

All seven columns appear in every FEATURES parquet that uses base-v1
(or base-v2, which inherits them). Within a session, all intraday bars
share the same HTF values — the join is by trade_date.

**Common use patterns:**

- `daily_ema_20 > daily_ema_50`: daily EMAs in bullish alignment —
  bias long entries.
- `daily_adx_14 < 20`: daily ADX in ranging regime — condition for
  mean-reversion entries.
- `daily_macd_hist > 0`: daily momentum positive — confirms the
  bullish intraday bias.
- ATR-scaled stop relative to the daily ATR: `entry_price − 2.0 ×
  daily_atr_14` — a stop that is calibrated to the day's expected
  range rather than the intraday bar's range.

---

## 7.12 Adding a new indicator

Adding an indicator follows a strict four-step procedure. The procedure
is designed to be safe — no existing FEATURES file changes until the
operator explicitly rebuilds with a new tag.

### Step 1 — Implement and test

Create `src/trading_research/indicators/<name>.py`. The function
signature follows the convention `compute_<name>(df: pd.DataFrame,
**params) -> pd.Series | pd.DataFrame`. The return type is a Series
(single column) or DataFrame (multiple columns).

Write a unit test in `tests/indicators/test_<name>.py` that covers:

1. **Basic correctness** — the indicator value matches a reference
   implementation on a known input.
2. **No look-ahead** — the indicator at row T uses only data available
   through T. The test fixture generates synthetic bars for two sessions,
   computes the indicator, and asserts that the value at the last bar of
   session 1 does not change when session 2 bars are appended. If this
   test fails, the indicator has a look-ahead bug and must not be
   registered.
3. **NaN warm-up** — the first `warm_up_rows` values are NaN and the
   first non-NaN value is in the expected position.
4. **Null input handling** — if the indicator uses nullable columns
   (`buy_volume`, `sell_volume`), verify that NaN input produces NaN
   output (not a crash or a silently wrong number).

### Step 2 — Register

Add the indicator name to the dispatch table in
`src/trading_research/indicators/features.py` (the `_INDICATOR_BUILDERS`
dict or equivalent dispatch point). An unregistered indicator name in
a feature-set YAML will raise a `KeyError` at build time — which is the
correct failure mode (loud, early).

### Step 3 — Fork a feature set

Never add a new indicator to an existing feature-set YAML. The tag is
immutable once a parquet has been built against it. Instead:

```
cp configs/featuresets/base-v2.yaml configs/featuresets/base-v3.yaml
```

Edit `tag: base-v3` and add the new indicator entry to the `indicators:`
list. Update `description:` to note what changed and why.

### Step 4 — Build and verify

```
uv run trading-research rebuild features --symbol ZN --set base-v3
uv run trading-research verify
```

The feature parquet for `base-v3` appears alongside the `base-v1` and
`base-v2` parquets. Strategies that want the new indicator reference
`feature_set: base-v3` in their YAML; existing strategies are
unaffected.

---

## 7.13 Related references

### Code

- [`src/trading_research/indicators/`](../../src/trading_research/indicators/)
  — all indicator modules; `features.py` is the feature builder.
- [`src/trading_research/data/schema.py`](../../src/trading_research/data/schema.py)
  — `BAR_SCHEMA`; the nullable fields that affect OFI null handling.

### Tests

- [`tests/indicators/`](../../tests/indicators/) — indicator unit tests.
- [`tests/test_features_lookahead.py`](../../tests/test_features_lookahead.py)
  — the HTF look-ahead regression test.

### Configuration

- [`configs/featuresets/base-v1.yaml`](../../configs/featuresets/base-v1.yaml)
  — base-v1 indicator list and HTF projections.
- [`configs/featuresets/base-v2.yaml`](../../configs/featuresets/base-v2.yaml)
  — base-v2 additions (EMA-9, EMA-20, CCI-14).

### Other manual chapters

- **Chapter 4, §4.6** — the look-ahead rule for HTF projections;
  the unit test that enforces it.
- **Chapter 8** — Feature Sets: the YAML grammar for wiring indicators
  into a feature-set build.
- **Chapter 11** — Expression Evaluator: column-name resolution in YAML
  strategy expressions; how to reference indicator columns.

---

*End of Chapter 7. Next: Chapter 8 — Feature Sets.*
