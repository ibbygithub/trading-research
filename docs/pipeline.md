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
│   │   └── ... (66 quarterly TY contracts)
│   └── ZN_1m_2010-01-01_2026-04-11.parquet         # original full pull
│   └── ZN_1m_2010-01-01_2026-04-11.parquet.manifest.json
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
│   └── ZN_roll_log_2010-01-01_2026-04-11.json
│
└── features/                                 # session 05 creates this
    ├── ZN_backadjusted_5m_features_base-v1.parquet
    ├── ZN_backadjusted_5m_features_base-v1.parquet.manifest.json
    ├── ZN_backadjusted_15m_features_base-v1.parquet
    └── ZN_backadjusted_15m_features_base-v1.parquet.manifest.json
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

1. **Read this file and `docs/architecture/data-layering.md`.** Ten minutes. Reloads the mental model.
2. **Read the latest session work log in `outputs/work-log/`.** Tells you what state the code was in at last stop.
3. **`uv sync`** — reinstalls dependencies from `uv.lock`.
4. **`uv run pytest`** — confirms the code still runs. If anything fails, fix before touching data.
5. **`uv run trading-research verify`** *(available after session 06)* — walks all manifests, reports stale or orphaned files. If pre-session-06, inspect `data/raw/`, `data/clean/`, `data/features/` manually against the directory layout above.
6. **Check `configs/featuresets/`** — lists the active feature sets. Tag names should match parquets in `data/features/`.
7. **Decide what to rebuild.** If CLEAN code changed: `rebuild clean`. If an indicator changed: `rebuild features --set base-v1`. If nothing changed: you're done.
8. **Read `docs/session-plans/` for the most recent plan.** Confirms what the next intended step is.

If step 5 shows unexpected files or step 7 produces a different result than the manifest recorded — stop and investigate. The manifest is authoritative; a mismatch means the pipeline was bypassed and something manual happened. Don't paper over it.

---

## What NOT to do

- **Do not add indicator columns to CLEAN parquets.** Ever. CLEAN is OHLCV only.
- **Do not rename feature-set tags.** Delete and recreate. Git remembers.
- **Do not edit RAW files.** If vendor data is wrong, document it in `configs/known_outages.yaml` or an equivalent exclusion config; don't mutate the parquet.
- **Do not bypass the rebuild CLI** *(once session 06 lands)* **to hand-edit a CLEAN or FEATURES file.** If the CLI can't express what you need, fix the CLI.
- **Do not commit `data/`.** The data directory is rebuildable from RAW plus code. RAW is the only part that's expensive to lose, and it's backed up separately.

---

## Related documents

- `docs/architecture/data-layering.md` — the decision record and reasoning.
- `docs/session-plans/session-05-plan.md` — the indicator layer work that adopts these conventions.
- `docs/session-plans/session-06-plan.md` — the CLI automation that enforces them.
- `configs/featuresets/base-v1.yaml` — the first canonical feature set.
