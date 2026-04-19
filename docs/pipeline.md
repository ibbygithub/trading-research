# Pipeline Reference

**Purpose:** The one document to read after a long absence. Explains the data layers, directory layout, naming conventions, manifest schema, and how to rebuild anything from scratch. If you're coming back to this project after three months, start here.

**Companion:** `docs/architecture/data-layering.md` is the decision record explaining *why* the pipeline looks like this. This document explains *how* to use it.

---

## The three layers

```
data/raw/         →    data/clean/       →    data/features/
(immutable)            (canonical OHLCV)      (indicators + HTF bias)
 ground truth           function of RAW        function of CLEAN
```

| Layer | Contains | Mutable? | Rebuildable from |
|-------|----------|----------|------------------|
| RAW | Per-contract downloads, exactly as TradeStation returned them | No, ever | Re-download only |
| CLEAN | Canonical OHLCV per (symbol, timeframe, adjustment) | Rebuildable | RAW + code |
| FEATURES | Flat per-bar matrices: price + indicators + HTF projections | Rebuildable | CLEAN + feature-set config |

**The load-bearing rule: CLEAN never contains indicators.** If a column is computable from price alone, it lives in FEATURES, not CLEAN.

---

## Directory layout

```
data/
├── raw/
│   ├── contracts/
│   │   ├── TYH10.parquet
│   │   ├── TYH10.parquet.manifest.json
│   │   ├── TYM10.parquet
│   │   ├── TYM10.parquet.manifest.json
│   │   ├── ... (66 quarterly TY contracts)
│   │   ├── ADH24.parquet                    # 6A contract (session 20)
│   │   ├── ADH24.parquet.manifest.json
│   │   └── ...
│   ├── ZN_1m_2010-01-01_2026-04-11.parquet         # original full pull
│   ├── ZN_1m_2010-01-01_2026-04-11.parquet.manifest.json
│   ├── 6A_1m_2024-01-01_2024-01-31.parquet         # 6A Jan 2024 sample (session 20)
│   └── 6A_1m_2024-01-01_2024-01-31.parquet.manifest.json
│
├── clean/
│   ├── ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet
│   ├── ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet.manifest.json
│   ├── ZN_1m_unadjusted_2010-01-01_2026-04-11.parquet
│   ├── ZN_backadjusted_5m_2010-01-03_2026-04-10.parquet
│   ├── ZN_backadjusted_15m_2010-01-03_2026-04-10.parquet
│   ├── ZN_backadjusted_60m_....parquet       # session 05
│   ├── ZN_backadjusted_240m_....parquet      # session 05
│   ├── ZN_backadjusted_1D_....parquet        # session 05
│   ├── ZN_roll_log_2010-01-01_2026-04-11.json
│   ├── 6A_backadjusted_1m_2024-01-01_2024-01-31.parquet  # 6A (session 20)
│   ├── 6A_backadjusted_1m_2024-01-01_2024-01-31.parquet.manifest.json
│   ├── 6A_backadjusted_5m_2024-01-01_2024-01-31.parquet
│   └── 6A_backadjusted_5m_2024-01-01_2024-01-31.parquet.manifest.json
│
└── features/
    ├── ZN_backadjusted_5m_features_base-v1.parquet
    ├── ZN_backadjusted_5m_features_base-v1.parquet.manifest.json
    ├── ZN_backadjusted_15m_features_base-v1.parquet
    ├── ZN_backadjusted_15m_features_base-v1.parquet.manifest.json
    ├── 6A_backadjusted_5m_features_base-v1.parquet      # 6A (session 20)
    └── 6A_backadjusted_5m_features_base-v1.parquet.manifest.json
```

### Filename conventions

**RAW:** `{ts_symbol}.parquet` for per-contract files; `{symbol}_{tf}_{start}_{end}.parquet` for bulk pulls.

**CLEAN:** `{symbol}_{adjustment}_{tf}_{start}_{end}.parquet`
- `adjustment` ∈ {`backadjusted`, `unadjusted`}
- `tf` ∈ {`1m`, `5m`, `15m`, `60m`, `240m`, `1D`}

**FEATURES:** `{symbol}_{adjustment}_{tf}_features_{feature-set-tag}.parquet`
- `feature-set-tag` is the filename of the YAML in `configs/featuresets/` without extension.
- Multiple tags coexist in the same directory.

---

## Manifest schema

Every file in RAW, CLEAN, and FEATURES has a sibling `.manifest.json`. The manifest is how the pipeline answers "where did this come from and is it still fresh?" without human memory.

### Common fields (all layers)

```json
{
  "schema_version": 1,
  "layer": "clean",
  "symbol": "ZN",
  "timeframe": "5m",
  "row_count": 1064432,
  "date_range": {
    "start": "2010-01-03T23:00:00+00:00",
    "end":   "2026-04-10T21:55:00+00:00"
  },
  "built_at": "2026-04-13T18:00:00+00:00",
  "code_commit": "a1b2c3d4",
  "sources": [
    {
      "path": "data/clean/ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet",
      "row_count": 4673993,
      "built_at": "2026-04-13T17:30:00+00:00"
    }
  ],
  "parameters": { "freq": "5min" }
}
```

### Layer-specific fields

**RAW manifest** adds:
```json
{
  "source": "tradestation",
  "ts_symbol": "TYM26",
  "download_session_id": "...",
  "vendor_response_metadata": { ... }
}
```

**CLEAN manifest** adds the list of RAW sources plus the transformation parameters (back-adjustment method, resample freq, etc.).

**FEATURES manifest** adds:
```json
{
  "feature_set_tag": "base-v1",
  "feature_set_config": "configs/featuresets/base-v1.yaml",
  "indicators": [
    {"name": "atr", "period": 14},
    {"name": "rsi", "period": 14},
    {"name": "macd", "fast": 12, "slow": 26, "signal": 9},
    ...
  ],
  "htf_projections": [
    {"source_tf": "1D", "columns": ["daily_ema_20", "daily_ema_50", "daily_ema_200", "daily_atr_14"]}
  ]
}
```

### Staleness rules

A file is **stale** if any of:
- Any source file listed in `sources` has a newer `built_at` than this file's `built_at`
- `code_commit` is older than the current HEAD and the relevant module changed since
- `parameters` don't match the config that generated them (for FEATURES: the feature-set YAML)

Session 06 adds a `verify` command that walks all manifests and reports stale files.

---

## Feature-set tags

A **feature set** is a named, versioned bundle of indicators and HTF projections. It lives in `configs/featuresets/<tag>.yaml`. The tag is the contract between the config, the filename, and the manifest.

**Rules:**
- Tags are immutable once a feature file is built. If you change the YAML, change the tag.
- `base-v1` is the canonical baseline. `base-v2` replaces it when the baseline shifts.
- Experimental tags (`experiment-13min`, `ofi-only`) live alongside the baseline until deleted.
- The git history of `configs/featuresets/` is the audit trail. Don't rename tags to "clean up" old experiments — delete the YAML and the parquets, git remembers.

See `configs/featuresets/base-v1.yaml` for the first feature set.

---

## The daily bar — CME trade-date convention

A ZN "daily bar" is a session, not a calendar day. The session runs from **18:00 ET** (prior calendar day) to **17:00 ET**, with a one-hour maintenance halt. This matches TradeStation, TradingView, Bloomberg, and CME's own settlement convention.

**Implementation (3 lines of pandas):**

```python
df["trade_date"] = (df["timestamp_ny"] + pd.Timedelta(hours=6)).dt.date
daily = df.groupby("trade_date").agg({
    "open": "first", "high": "max", "low": "min", "close": "last",
    "volume": "sum", "buy_volume": "sum", "sell_volume": "sum",
})
daily["timestamp_utc"] = df.groupby("trade_date")["timestamp_utc"].first()
```

Why +6 hours: the 18:00 ET session open becomes 24:00 ET = midnight of the trade date. All bars in that session now share a `trade_date`. DST is handled by pandas because `timestamp_ny` is tz-aware.

No session-gap detection, no session_id assignment, no edge-case machinery. It's a groupby.

---

## HTF bias — the look-ahead rule

Daily indicators projected onto intraday bars **must** use the prior session's daily value, not the current session's.

**Rule:** at any intraday bar with trade_date `T`, the daily indicator value seen is the one computed from daily bars with trade_date strictly less than `T`.

**Implementation:** `shift(1)` on the daily indicator series before the left-join back onto the intraday frame.

```python
daily["daily_ema_20_shifted"] = daily["daily_ema_20"].shift(1)
intraday = intraday.merge(
    daily[["daily_ema_20_shifted"]],
    left_on="trade_date", right_index=True, how="left"
)
```

This is the most important unit test in the feature builder. A synthetic test with known daily EMAs must verify that intraday bars in session N see the EMA computed through session N−1.

---

## Statistical Rigor Layer (Sessions 11–18)

The framework computes three core honest statistics alongside raw Sharpe and Calmar:

### Probabilistic Sharpe Ratio (PSR)

PSR answers: "What is the probability that the true Sharpe ratio is positive?"
- Uses the non-central t-distribution to account for small sample size and non-normal returns
- Corrects for kurtosis (Pearson convention: excess kurtosis = Fisher + 3)
- Values > 0.95 suggest the edge is real; < 0.50 suggests it's noise
- Always inspect the confidence interval alongside PSR — a point estimate is not a judgment

### Deflated Sharpe Ratio (DSR)

DSR corrects for multiple testing bias when a strategy was selected from variants.
- If you tested N variants and picked the best one, the raw Sharpe is biased upward
- DSR estimates the expected Sharpe *if you had tested only one variant and gotten that result honestly*
- The deflation is often brutal: raw Sharpe 1.8 from 30 trials may deflate to 0.4
- **Required input:** the trials registry (`runs/.trials.json`) must record how many variants were tested

### Bootstrap Confidence Intervals

Every key metric (Sharpe, Calmar, win rate, expectancy) is reported with a 95% confidence interval.
- Computed by resampling trade returns with replacement, recalculating the metric 1000 times
- Tells you the range of plausible values, not just a point estimate
- A Calmar of 2.0 with CI [1.2, 3.5] is much stronger than Calmar 2.0 with CI [0.1, 4.9]

### Trials Registry

Located at `runs/.trials.json`. Records every strategy variant tested, the backtest result (Sharpe, trade count, date range), and the commit hash of the code that generated it.

**Format:**
```json
{
  "trials": [
    {
      "strategy": "zn_macd_pullback",
      "variant": "v1_rth_only",
      "backtest_id": "20260419-143052-abc123",
      "raw_sharpe": 1.2,
      "trade_count": 147,
      "date_range": {"start": "2010-01-01", "end": "2026-04-19"},
      "code_commit": "a1b2c3d4e5f6"
    }
  ]
}
```

The trials registry is consulted whenever `report` is run. If multiple trials exist for the same strategy, DSR is computed across all variants. If only one trial exists, DSR equals raw Sharpe.

---

## Walk-Forward Validation (Session 12–13)

A single train/test split is the weakest form of validation. Walk-forward proves the strategy works across multiple non-overlapping periods.

### Purge and Embargo Gaps

When a strategy has multi-bar exits (e.g., target or stop hit on bar T+3), the label for bar T depends on bars T+1, T+2, T+3. To avoid label leakage from the training window into the test window:

- **Purge:** Remove all training bars that contribute to a label in the test window
- **Embargo:** Remove test-window bars that depend on training-window data
- Default: 5 bars for strategies with exits up to 4 bars forward

This is automatically handled by the walk-forward engine; it's non-negotiable for honest results.

### How to Run Walk-Forward

```bash
uv run trading-research walkforward --strategy configs/strategies/<name>.yaml
```

Output: per-fold breakdown with metrics for each fold (Sharpe, Calmar, trade count), plus an aggregate across all folds.

### Per-Fold Reporting

The HTML report includes a walk-forward table showing:
- Fold number and date range
- Trade count, win rate, Sharpe, Calmar per fold
- Whether each fold passed (Calmar > 0, Sharpe > 0)
- Any fold where the strategy breaks hints at regime-specific failure

A strategy that passes 8 of 10 folds is more believable than one that passes 10 of 10 (which suggests possible overfitting).

---

## Event-Day Blackout Filter (Session 19)

Major economic announcements (FOMC meetings, CPI, NFP) cause sudden volatility that breaks mean-reversion strategies. The framework provides an optional blackout filter.

### Blackout Calendars

Three YAML files in `configs/calendars/`:
- `fomc_dates.yaml` — FOMC meetings (2010–2025), including emergency inter-meeting actions
- `cpi_dates.yaml` — CPI announcement dates (2010–2025)
- `nfp_dates.yaml` — Non-farm payroll dates (2010–2025)

All dates are manually verified against official sources. The calendars live in the repo and travel with the code.

### The Blackout Module

`src/trading_research/strategies/event_blackout.py` exports a single function:

```python
def load_blackout_dates(event_types: List[str]) -> FrozenSet[date]:
    """Load blackout dates. event_types ∈ ["fomc", "cpi", "nfp"]."""
```

Returns a frozenset of Python `date` objects. Zero external dependencies.

### How It Wires Into a Strategy

In `generate_signals()`, before generating entry signals:

```python
blackout = load_blackout_dates(["fomc", "cpi"])
signal_date = signal_bar.timestamp_ny.date()
if signal_date in blackout:
    return []  # no entry signals on event days
```

Exit signals are preserved — positions can still close on event days, which is usually the right behavior.

The strategy config specifies which events to blackout via a `blackout_events` parameter.

---

## Instrument Generalization (Session 20)

The pipeline is now instrument-agnostic. The following work end-to-end for any CME quarterly futures contract:

### Three Hardcoded ZN References — Fixed

1. `continuous.py` output paths used literal `"ZN"` — now use the `symbol` parameter
2. `validate.py` RTH window was hardcoded to ZN's 08:20–15:00 ET — now read from `InstrumentRegistry` per symbol
3. `continuous.py` had `last_trading_day_zn()` — renamed to `last_trading_day_quarterly_cme()` for clarity

### RTH Windows Per Instrument

`configs/instruments.yaml` defines RTH hours for each contract. The validate and feature-builder modules read from it:

```yaml
ZN:
  rth_open_et: "08:20"
  rth_close_et: "15:00"
6A:
  rth_open_et: "08:00"
  rth_close_et: "17:00"
```

This is the single source of truth. Hardcoding RTH into strategy code is forbidden (see **What NOT to do**).

### How to Run the Pipeline for a New Instrument

Once historical contracts are downloaded to `data/raw/contracts/`:

```bash
uv run trading-research rebuild-clean --symbol 6A
uv run trading-research rebuild-features --symbol 6A
uv run trading-research verify
```

The pipeline infers symbol from the contract root (AD, ZN, etc.) and applies the correct RTH window, settlement time, and tick size from the instrument registry.

---

## Worked example — adding a 13-minute timeframe experiment

Goal: test a non-standard 13-minute bar with the base-v1 indicator set, without touching any other feature file, without re-downloading anything, and without leaving permanent clutter.

### Step 1 — extend CLEAN with a 13m parquet

The resampler already handles arbitrary sub-hour frequencies:

```python
from trading_research.data.resample import resample_and_write

resample_and_write(
    source=Path("data/clean/ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet"),
    output_dir=Path("data/clean/"),
    freqs=["13min"],
    symbol="ZN",
)
```

Output: `data/clean/ZN_backadjusted_13m_2010-01-03_2026-04-10.parquet` plus its manifest.

This is a CLEAN-layer addition. No indicators, no experiments — just another per-timeframe parquet alongside the 5m and 15m siblings. It costs ~30 seconds of resample time.

### Step 2 — create a feature-set tag for the experiment

Copy `configs/featuresets/base-v1.yaml` to `configs/featuresets/experiment-13min.yaml`. The contents are identical except for a `comment:` field noting the experiment purpose. The indicators and HTF projections don't change — that's the point of the experiment, holding the feature set constant while varying the timeframe.

### Step 3 — build the feature file

```python
from trading_research.indicators.features import build_features

build_features(
    price_path=Path("data/clean/ZN_backadjusted_13m_2010-01-03_2026-04-10.parquet"),
    price_1m_path=Path("data/clean/ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet"),
    daily_path=Path("data/clean/ZN_backadjusted_1D_2010-01-03_2026-04-10.parquet"),
    output_dir=Path("data/features/"),
    symbol="ZN",
    feature_set_tag="experiment-13min",
)
```

Output: `data/features/ZN_backadjusted_13m_features_experiment-13min.parquet` plus manifest.

### Step 4 — run a strategy against it

The strategy config points at the feature file by path. Nothing else changes. The base-v1 feature files for 5m and 15m are untouched.

### Step 5 — delete the experiment when done

```
rm data/features/ZN_backadjusted_13m_features_experiment-13min.parquet
rm data/features/ZN_backadjusted_13m_features_experiment-13min.parquet.manifest.json
rm configs/featuresets/experiment-13min.yaml
```

Optionally keep the 13m CLEAN parquet if the timeframe stays interesting. Git history remembers the YAML if you want to revive it.

**What this example demonstrates:**
- Experiments cost one CLEAN addition + one config + one feature build. No copy of 16 years of ZN.
- The base-v1 baseline is never touched. There's no risk of contaminating canonical data.
- Rollback is three file deletions. No version-tracking archaeology.
- Manifests tell future-Ibby (or future-Claude) exactly what each file is and where it came from.

---

## Cold-start checklist

You haven't touched this project in three months. Here's the path back to working order.

### Data and environment (steps 1–7)

1. **Read this file and `docs/architecture/data-layering.md`.** Ten minutes. Reloads the mental model.
2. **Read the latest session work log in `outputs/work-log/`.** Tells you what state the code was in at last stop.
3. **`uv sync`** — reinstalls dependencies from `uv.lock`.
4. **`uv run pytest`** — confirms the code still runs. If anything fails, fix before touching data.
5. **`uv run trading-research verify`** *(available after session 06)* — walks all manifests, reports stale or orphaned files. If pre-session-06, inspect `data/raw/`, `data/clean/`, `data/features/` manually against the directory layout above.
6. **Check `configs/featuresets/`** — lists the active feature sets. Tag names should match parquets in `data/features/`.
7. **Decide what to rebuild.** If CLEAN code changed: `rebuild clean --symbol ZN`. If an indicator changed: `rebuild features --symbol ZN`. If nothing changed: you're done.

If step 5 shows unexpected files or step 7 produces a different result than the manifest recorded — stop and investigate. The manifest is authoritative; a mismatch means the pipeline was bypassed and something manual happened. Don't paper over it.

### Strategy testing (steps 8–10)

8. **Run a backtest:** `uv run trading-research backtest --strategy configs/strategies/<name>.yaml`
   - Output goes to `runs/<strategy-id>/`. Generates trade log, equity curve, and raw metrics.
   - Take 5 minutes to scan the output. Look for: trade count (should be > 10 per year), win rate (> 40% for mean reversion), max consecutive losses (should not exceed 20–30).

9. **Run walk-forward validation:** `uv run trading-research walkforward --strategy configs/strategies/<name>.yaml`
   - Output to the same `runs/<strategy-id>/` directory. Generates per-fold metrics and aggregate statistics.
   - Walk-forward proves the strategy works across multiple non-overlapping time periods. If all 10 folds pass, the strategy is more likely to generalize.

10. **Generate the report:** `uv run trading-research report <strategy-id>`
    - Generates a 24-section HTML report in `runs/<strategy-id>/report.html`.
    - Contains: equity curve, drawdown curve, monthly heatmap, MAE/MFE, PSR/DSR, bootstrap CIs, Monte Carlo, and per-fold breakdown.
    - This is the one document to share with Ibby or to review before decisions.

---

## What NOT to do

- **Do not add indicator columns to CLEAN parquets.** Ever. CLEAN is OHLCV only.
- **Do not rename feature-set tags.** Delete and recreate. Git remembers.
- **Do not edit RAW files.** If vendor data is wrong, document it in `configs/known_outages.yaml` or an equivalent exclusion config; don't mutate the parquet.
- **Do not bypass the rebuild CLI** *(once session 06 lands)* **to hand-edit a CLEAN or FEATURES file.** If the CLI can't express what you need, fix the CLI.
- **Do not commit `data/`.** The data directory is rebuildable from RAW plus code. RAW is the only part that's expensive to lose, and it's backed up separately.

---

## Related documents

### Architecture and design
- `docs/architecture/data-layering.md` — the decision record and reasoning for three-layer model

### Data pipeline modules
- `src/trading_research/data/continuous.py` — back-adjustment and roll stitching; per-symbol output paths
- `src/trading_research/data/validate.py` — CME calendar validation; per-symbol RTH windows from InstrumentRegistry
- `src/trading_research/indicators/features.py` — indicator computation and HTF projection with look-ahead checking

### Strategy and backtest modules
- `src/trading_research/strategies/event_blackout.py` — event-day blackout filter; consumes calendars
- `src/trading_research/backtest/engine.py` — next-bar-open fills, pessimistic stops, position reconciliation
- `src/trading_research/backtest/walkforward.py` — purged walk-forward validator with per-fold metrics

### Statistical rigor
- `src/trading_research/eval/metrics.py` — PSR, DSR, Calmar, Sharpe; bootstrap confidence intervals
- `src/trading_research/eval/reports.py` — 24-section HTML report generation with interactive charts
- `runs/.trials.json` — trials registry; required for honest DSR across multiple strategy variants

### Configuration
- `configs/instruments.yaml` — instrument registry (tick size, session hours, settlement, RTH window per contract)
- `configs/featuresets/base-v1.yaml` — the canonical feature set (ATR, MACD, RSI, VWAP, Bollinger, etc.)
- `configs/calendars/` — FOMC, CPI, NFP dates (2010–2025); manually verified

### Session work logs
- Start with `outputs/work-log/YYYY-MM-DD-HH-MM-summary.md` for the most recent session state
