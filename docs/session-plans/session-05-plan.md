# Session 05 — Indicator Layer + Multi-Timeframe Framework

## Objective

Build the indicator module with full multi-timeframe support: intraday (5m, 15m, 60m, 240m) and daily, plus VWAP at session/weekly/monthly reset frequencies. By the end of this session, `data/features/` contains ZN feature files at 5m and 15m (and optionally 60m/240m) tagged `base-v1`, each with price + all indicators + higher-timeframe bias columns projected down to the intraday bars.

Session 05 also adopts the **three-layer data architecture** (see `docs/architecture/data-layering.md` and `docs/pipeline.md`) by convention: every file written gets a `.manifest.json` sidecar, feature files use the feature-set-tag naming scheme, and the "CLEAN never contains indicators" rule is held manually. The CLI automation that *enforces* these conventions is session 06's job — this session forms the habits before they're automated.

The pipeline after this session:

```
data/clean/ZN_1m_backadjusted...parquet
    ├── resample → 60m, 240m, 1D parquets in data/clean/ (manifests attached)
    └── indicators + HTF bias (feature-set base-v1) →
        data/features/ZN_backadjusted_5m_features_base-v1.parquet   (+ manifest)
        data/features/ZN_backadjusted_15m_features_base-v1.parquet  (+ manifest)
```

---

## Required reading before starting

1. `docs/architecture/data-layering.md` — the decision record. Ten minutes.
2. `docs/pipeline.md` — the living reference. The layer rules, the trade-date convention, the HTF look-ahead rule, the worked 13-minute example.
3. `configs/featuresets/base-v1.yaml` — the feature-set spec this session builds against.

If those three documents don't exist when you start this session, stop — this plan assumes they're in place.

---

## Context: where we are

| Asset | State |
|-------|-------|
| `data/clean/ZN_1m_backadjusted_...parquet` | 4,673,993 rows, clean |
| `data/clean/ZN_backadjusted_5m_...parquet` | 1,064,432 rows |
| `data/clean/ZN_backadjusted_15m_...parquet` | 369,388 rows |
| `src/trading_research/data/resample.py` | Works for sub-hour freqs; daily needs a small trade-date helper |
| `src/trading_research/indicators/__init__.py` | Empty package stub |
| `data/features/` | Does not exist yet |
| Manifests | No files have manifest sidecars yet — session 06 backfills the pre-existing ones; this session writes manifests for everything **new** |

---

## Design decisions — locked

All locked during session 05 planning. No debate this session, just execution.

### D1 — Daily bar = CME trade-date convention

Daily bars are aggregated by **trade_date**, defined as:

```python
df["trade_date"] = (df["timestamp_ny"] + pd.Timedelta(hours=6)).dt.date
```

The +6h offset shifts the 18:00 ET session open to midnight, so all bars in a single Globex session share one `trade_date`. This matches TradeStation, TradingView, Bloomberg, and CME's own settlement convention. No session-gap detection, no session_id — it's a groupby.

See `docs/pipeline.md` for the full rationale and the 3-line implementation.

### D2 — HTF bias look-ahead rule

`shift(1)` on the daily indicator series before left-joining onto the intraday frame by trade_date. An intraday bar with trade_date `T` sees only daily indicator values computed from bars with trade_date strictly less than `T`. This is the most important unit test in the feature builder (see Step 5).

### D3 — VWAP reset flavors

Three flavors, all computed on the 1-minute frame and sampled at the bar close for higher timeframes:
- **Session VWAP** — resets on gap > 60 min between consecutive bars
- **Weekly VWAP** — resets at the first session of each ISO week (by trade_date)
- **Monthly VWAP** — resets at the first session of each trade_date month

### D4 — Indicator suite (from `configs/featuresets/base-v1.yaml`)

On each target timeframe:
- ATR(14)
- RSI(14)
- Bollinger(20, 2)
- MACD(12, 26, 9) — full line, signal, histogram, plus derived histogram features
- SMA(200)
- Donchian(20)
- ADX(14)
- OFI(14)

Plus session/weekly/monthly VWAP.

### D5 — MACD settings are fixed at 12/26/9 on every timeframe

Reflexive value argument: traders react to the consensus chart. Changing MACD settings per timeframe creates a strategy that reacts to a picture nobody else is looking at. Adjust the timeframe, not the settings.

### D6 — MACD histogram derived features

Beyond `macd`, `macd_signal`, `macd_hist`:
- `macd_hist_above_zero` (bool) — current histogram > 0
- `macd_hist_slope` (float) — first difference of histogram
- `macd_hist_bars_since_zero_cross` (int) — bars since last sign flip
- `macd_hist_decline_streak` (signed int) — positive = rising streak, negative = declining streak

The `decline_streak` feature is the encoding of the pattern: *MACD histogram is above zero, but each bar is smaller than the last for 3–4 bars → look to short*. A strategy can filter on `macd_hist_above_zero & macd_hist_decline_streak <= -3`.

### D7 — ADX(14) as regime classifier

Trending regime filter. Mean-reversion strategies should down-weight or disable in high-ADX regimes. Included in the feature file on every timeframe so the filter is a column read, not a runtime compute.

### D8 — Fat feature files

Each feature file contains its own-timeframe indicators **plus** HTF bias columns projected from the daily bar. Strategies and future ML code read a single flat matrix per observation. See `docs/architecture/data-layering.md` for the "why."

---

## Step 1 — Validate the back-adjusted series

Run the existing validator against `data/clean/ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet`.

Expected results:
- **September 2023 RTH failures: zero** (TYZ23 had full coverage; the roll artifact is gone)
- **Remaining RTH failures:** Hurricane Sandy 300-bar gap (Oct 29, 2012) — already documented in `known_outages.yaml`
- **Overnight failures:** CME July 2024 outage, year-end extended closures — all known

Deliverable: `data/clean/ZN_1m_backadjusted_2010-01-01_2026-04-11.quality.json`

The validator may need a `--skip-structural` flag or a clean-series mode since back-adjusted series don't match raw download expectations on all structural checks.

---

## Step 2 — Extend resample to 60m, 240m, and 1D

### 2a — 60m and 240m

The existing `resample_bars()` handles these with no changes. Run them, write with manifests:

- `data/clean/ZN_backadjusted_60m_....parquet` + `.manifest.json`
- `data/clean/ZN_backadjusted_240m_....parquet` + `.manifest.json`

Verify row counts are plausible (~78,000 and ~19,500 respectively).

### 2b — Daily bars via trade-date grouping

Add to `resample.py`:

```python
def resample_daily(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 1m bars into daily bars using CME trade-date convention.

    A daily bar's trade_date corresponds to the Globex session that
    closes on that ET calendar date at 17:00. Session open is 18:00 ET
    the prior day.
    """
    df = df_1m.copy()
    df["trade_date"] = (df["timestamp_ny"] + pd.Timedelta(hours=6)).dt.date

    agg = {
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum",
        "buy_volume": ("sum", {"min_count": 1}),
        "sell_volume": ("sum", {"min_count": 1}),
        "up_ticks": ("sum", {"min_count": 1}),
        "down_ticks": ("sum", {"min_count": 1}),
        "total_ticks": ("sum", {"min_count": 1}),
    }
    daily = df.groupby("trade_date", sort=True).agg(agg)
    daily["timestamp_utc"] = df.groupby("trade_date")["timestamp_utc"].first()
    daily["timestamp_ny"] = daily["timestamp_utc"].dt.tz_convert("America/New_York")
    return daily.reset_index(drop=True)
```

Output: `data/clean/ZN_backadjusted_1D_....parquet` + `.manifest.json`. Approximately 4,200 rows.

---

## Step 3 — Implement indicators

All indicators follow the same interface contract:
- `compute_<name>(df: pd.DataFrame, **params) -> pd.Series | pd.DataFrame`
- No mutation of input
- Output length == input length, same index
- Look-ahead freedom verified by test (see Step 5)
- First N rows NaN where the calculation requires N bars of history

### 3a — ATR(14) — `src/trading_research/indicators/atr.py`

- True Range = max(high−low, |high−prev_close|, |low−prev_close|)
- ATR = Wilder EWM smoothing (alpha = 1/period)
- Output: `pd.Series` named `"atr_14"`
- First `period` rows NaN

### 3b — RSI(14) — `indicators/rsi.py`

- Wilder smoothing for avg gain/loss
- Output 0–100 named `"rsi_14"`

### 3c — Bollinger(20, 2) — `indicators/bollinger.py`

Output `pd.DataFrame` columns: `bb_mid`, `bb_upper`, `bb_lower`, `bb_pct_b`, `bb_width`.
`bb_pct_b = (close − lower) / (upper − lower)` is the primary mean-reversion signal.

### 3d — MACD(12, 26, 9) — `indicators/macd.py`

Output `pd.DataFrame` columns:
- Core: `macd`, `macd_signal`, `macd_hist`
- Derived: `macd_hist_above_zero` (bool), `macd_hist_slope` (float), `macd_hist_bars_since_zero_cross` (int), `macd_hist_decline_streak` (signed int)

Derivation rules:
- `hist_slope[i] = hist[i] - hist[i-1]`
- `bars_since_zero_cross[i]` = count of bars since `sign(hist)` last flipped. Reset to 0 at each flip; increments by 1 otherwise. NaN until first valid histogram.
- `decline_streak[i]`:
  - If `sign(hist[i]) != sign(hist[i-1])`: reset to `sign(hist[i]) * 1`
  - Else if `hist_slope[i] > 0`: if previous streak > 0, streak + 1; else reset to `+1 * sign(hist[i])`... wait, this gets tangled. Concrete rule:
    - When above zero (`hist > 0`): streak is positive while each bar is larger than last, negative while each bar is smaller than last, resets to ±1 on direction flip.
    - When below zero (`hist < 0`): mirror — positive streak means increasingly negative (getting stronger bearish), negative streak means shrinking negative (fading).
  - Write this in one small helper with a table-driven unit test. See Step 5.

### 3e — SMA(200) — `indicators/sma.py`

Straight rolling mean. One-liner wrapper around `pd.Series.rolling(period).mean()`.

### 3f — Donchian(20) — `indicators/donchian.py`

Output columns: `donchian_upper`, `donchian_lower`, `donchian_mid`. Rolling high/low over `period` bars.

### 3g — ADX(14) — `indicators/adx.py`

Standard Wilder ADX. Output `pd.Series` named `"adx_14"`. Used as regime filter.

### 3h — OFI(14) — `indicators/ofi.py`

- Raw OFI per bar = `(buy_volume - sell_volume) / (buy_volume + sell_volume)`, range [−1, +1]
- Rolling OFI = rolling mean over `period` bars
- Null `buy_volume` → NaN; rolling mean skips NaN with `min_periods=period`

### 3i — VWAP (three flavors) — `indicators/vwap.py`

All three take the **1-minute** frame and return a `pd.Series`:
- `compute_session_vwap(df_1m)` — group boundary = gap > 60 min
- `compute_weekly_vwap(df_1m)` — group boundary = ISO week change of trade_date
- `compute_monthly_vwap(df_1m)` — group boundary = month change of trade_date

Accumulation: `vwap = cumsum(close * volume) / cumsum(volume)` within each group.

For sampling onto higher timeframes: the VWAP value at the last 1m bar within each bucket is the VWAP as of the bucket close. No look-ahead.

### 3j — Generic EMA — `indicators/ema.py`

`compute_ema(series: pd.Series, period: int) -> pd.Series`. Used by MACD internally and by the daily HTF bias columns.

---

## Step 4 — Build feature files

### 4a — Feature build function

`src/trading_research/indicators/features.py`:

```python
def build_features(
    price_path: Path,          # data/clean/ZN_backadjusted_5m_...parquet
    price_1m_path: Path,       # data/clean/ZN_1m_backadjusted_...parquet
    daily_path: Path,          # data/clean/ZN_backadjusted_1D_...parquet
    output_dir: Path,          # data/features/
    symbol: str,
    feature_set_tag: str = "base-v1",
    feature_set_config: Path | None = None,
) -> Path:
    ...
```

Algorithm:

1. Load the target-timeframe price parquet.
2. Load the 1m parquet for VWAP computation. Compute session/weekly/monthly VWAP on 1m, then sample at the target bar's close timestamp via merge_asof.
3. Compute all own-timeframe indicators listed in the feature-set config on the target frame.
4. Load the daily parquet. Compute all daily-level indicators (EMA 20/50/200, SMA 200, ATR 14, ADX 14, MACD hist).
5. For each daily indicator column, create a shifted version: `col_shifted = col.shift(1)`.
6. Compute `trade_date` on the target frame via the same +6h trick.
7. Left-join the shifted daily columns onto the target frame by trade_date.
8. Write parquet: `data/features/{symbol}_{adjustment}_{tf}_features_{tag}.parquet`.
9. Write sidecar `.manifest.json` per the FEATURES schema in `docs/pipeline.md`:
   - `layer`, `symbol`, `timeframe`, `row_count`, `date_range`, `built_at`, `code_commit`
   - `sources`: price_path, price_1m_path, daily_path (each with its row_count and built_at)
   - `feature_set_tag`, `feature_set_config`
   - `indicators`: full list with parameters
   - `htf_projections`: list of shifted daily columns included

### 4b — Feature file schema

| Column group | Columns |
|---|---|
| BAR_SCHEMA passthrough | `timestamp_utc`, `timestamp_ny`, `open`, `high`, `low`, `close`, `volume`, `buy_volume`, `sell_volume`, `up_ticks`, `down_ticks`, `total_ticks` |
| Own-TF ATR / RSI | `atr_14`, `rsi_14` |
| Own-TF Bollinger | `bb_mid`, `bb_upper`, `bb_lower`, `bb_pct_b`, `bb_width` |
| Own-TF MACD | `macd`, `macd_signal`, `macd_hist`, `macd_hist_above_zero`, `macd_hist_slope`, `macd_hist_bars_since_zero_cross`, `macd_hist_decline_streak` |
| Own-TF SMA / Donchian / ADX | `sma_200`, `donchian_upper`, `donchian_lower`, `donchian_mid`, `adx_14` |
| Own-TF OFI | `ofi_14` |
| VWAP | `vwap_session`, `vwap_weekly`, `vwap_monthly` |
| HTF bias (all `shift(1)` of daily) | `daily_ema_20`, `daily_ema_50`, `daily_ema_200`, `daily_sma_200`, `daily_atr_14`, `daily_adx_14`, `daily_macd_hist` |

All `daily_*` columns are constant within a trade_date and change only at session boundaries. No look-ahead.

### 4c — Deliverables

- `data/features/ZN_backadjusted_5m_features_base-v1.parquet` + manifest
- `data/features/ZN_backadjusted_15m_features_base-v1.parquet` + manifest

Optional: 60m and 240m feature files if time permits. Not required for green.

---

## Step 5 — Tests

### Look-ahead freedom helper

`tests/indicators/conftest.py`:

```python
def assert_no_lookahead(fn, df, n_warmup=50, **kwargs):
    """Compute indicator on full df, then on df[:n_warmup+1]. The last
    value of the partial computation must equal full[n_warmup]. If they
    differ, the indicator is reading future data."""
    full = fn(df, **kwargs)
    partial = fn(df.iloc[:n_warmup + 1], **kwargs)
    last_full = full.iloc[n_warmup]
    last_partial = partial.iloc[-1]
    if isinstance(last_full, pd.Series):  # DataFrame indicator row
        pd.testing.assert_series_equal(last_full, last_partial, check_names=False)
    else:
        assert last_full == pytest.approx(last_partial, rel=1e-6)
```

Applied to every indicator.

### Per-indicator tests (minimum 3 each)

| Indicator | Tests |
|---|---|
| ATR | look-ahead; constant range → ATR = range after warmup; first row NaN |
| RSI | look-ahead; ascending → near 100; descending → near 0; first 14 rows NaN |
| Bollinger | look-ahead; `bb_pct_b == 0.5` when close == SMA; `bb_pct_b < 0` when below lower band |
| MACD core | look-ahead; hist > 0 when fast > slow; first 35 rows NaN |
| MACD derived | table-driven: known histogram sequence produces known decline_streak and bars_since_zero_cross |
| SMA | look-ahead; constant series → SMA = constant after warmup |
| Donchian | look-ahead; upper = max(high) over window |
| ADX | look-ahead; strongly trending synthetic series → ADX > 25 |
| OFI | look-ahead; all-buy → +1; all-sell → −1; null buy_volume → NaN |
| Session VWAP | resets on gap > 60 min; first bar of session = that bar's close; look-ahead |
| Weekly VWAP | resets at ISO week boundary |
| Monthly VWAP | resets at trade_date month boundary |
| Daily EMA | look-ahead; standard EMA values on known inputs |

### HTF bias projection test (critical)

```python
def test_htf_bias_uses_prior_session():
    """An intraday bar with trade_date T must see the daily EMA
    computed from daily bars with trade_date strictly < T."""
    # Synthetic daily bars with known closes:
    #   trade_date 2024-01-02 close=110.0, EMA20 = 110.0
    #   trade_date 2024-01-03 close=112.0, EMA20 = 110.2
    #   trade_date 2024-01-04 close=114.0, EMA20 = 110.56
    #
    # Intraday bars on trade_date 2024-01-03 must see EMA20 = 110.0
    # Intraday bars on trade_date 2024-01-04 must see EMA20 = 110.2
    # Intraday bars on trade_date 2024-01-05 must see EMA20 = 110.56
```

This is the test that proves the pipeline is honest. If it's wrong, every backtest that uses daily bias is leaking.

### Feature-build integration test

One end-to-end test that builds a feature file from a synthetic 1m series with a known daily bias and verifies the output file has the right columns, right row count, right manifest.

---

## Step 6 — Manifest writing (manual this session)

Every new parquet this session writes a `.manifest.json` sidecar following the schema in `docs/pipeline.md`. Utility:

```python
# src/trading_research/data/manifest.py  (new, small)

def write_manifest(parquet_path: Path, layer: str, sources: list[dict],
                   parameters: dict, **extra) -> Path:
    """Write a sidecar .manifest.json next to a parquet."""
```

One function, ~30 lines. Session 06 builds the `verify` and `rebuild` CLI on top of this foundation.

Session 05 does **not**:
- Backfill manifests for existing (pre-session-05) files in `data/raw/` and `data/clean/`. That's session 06.
- Build the `uv run trading-research` CLI. Also session 06.
- Auto-detect staleness. Also session 06.

Session 05 **does**:
- Write manifests for every new file (60m, 240m, 1D CLEAN parquets; all feature files).
- Use the feature-set-tag naming scheme for feature files.
- Respect the "CLEAN never contains indicators" rule absolutely.

---

## Extended parquets produced this session

| File | Approx rows | Layer |
|---|---|---|
| `data/clean/ZN_backadjusted_60m_...parquet` | ~78,000 | CLEAN |
| `data/clean/ZN_backadjusted_240m_...parquet` | ~19,500 | CLEAN |
| `data/clean/ZN_backadjusted_1D_...parquet` | ~4,200 | CLEAN |
| `data/features/ZN_backadjusted_5m_features_base-v1.parquet` | ~1,064,000 | FEATURES |
| `data/features/ZN_backadjusted_15m_features_base-v1.parquet` | ~369,000 | FEATURES |

Each with a `.manifest.json` sidecar.

---

## Out of scope for session 05

- CLI scaffolding (`rebuild`, `verify`) → session 06
- Manifest backfill for pre-existing files → session 06
- Strategy implementation → session 07+
- Backtest engine → session 07+
- FX instrument feature files → after ZN is validated
- New experimental indicators (Ichimoku, Supertrend, etc.) → session 07+
- Walk-forward feature computation → session 07+
- Replay app → later

---

## Success criteria

| Item | Done when |
|---|---|
| Back-adjusted validated | `.quality.json` written, Sept 2023 RTH failures = 0 |
| 60m / 240m / 1D CLEAN | Parquets + manifests in `data/clean/`, row counts plausible |
| Daily bar helper | `resample_daily()` implemented, trade-date grouping, one test |
| ATR / RSI / Bollinger / MACD core | Tests pass, look-ahead free |
| MACD derived features | Table-driven test passes on known histogram sequence |
| SMA / Donchian / ADX / OFI | Tests pass, look-ahead free |
| Session / Weekly / Monthly VWAP | Tests pass, reset behavior verified |
| EMA helper | Tests pass |
| HTF bias projection | `test_htf_bias_uses_prior_session` green |
| Feature files | 5m + 15m `base-v1` parquets in `data/features/` with correct columns |
| Manifests | Every new file has a `.manifest.json` sidecar matching the schema |
| Full test suite | Green (target: ≥110 tests total) |
