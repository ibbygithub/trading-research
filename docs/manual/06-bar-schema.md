# Chapter 6 — Bar Schema & Calendar Validation

> **Chapter status:** [EXISTS] except §6.5 (schema migration tooling,
> [GAP]). Every section through §6.4 documents code and behaviour
> present at v1.0. §6.5 documents the migration policy the tooling
> must enforce when it is built in session 52.

---

## 6.0 What this chapter covers

The canonical 1-minute bar schema is the contract between the data
pipeline and everything downstream — strategies, indicators, backtests,
the replay app, and the report framework. Every parquet in `data/clean/`
and `data/features/` conforms to this schema; anything that doesn't
is rejected by the validation gate before it can contaminate a backtest.

After reading this chapter you will:

- Know every field in `BAR_SCHEMA` and why it exists
- Understand the two-timestamp design and why both timestamps are stored
  even though one is a deterministic function of the other
- Know what the validation gate checks, which failures abort the
  pipeline, and which are informational
- Be able to read a quality report produced by `validate_bar_dataset`
- Understand the schema evolution policy even though the migration
  tooling does not yet exist

This chapter is roughly 4 pages. It is referenced by Chapter 4 (Data
Pipeline), Chapter 5 (Instrument Registry, §5.5 for calendar names),
Chapter 7 (Indicator Library), and Appendix A.

---

## 6.1 The canonical 1-minute bar schema

`BAR_SCHEMA` is defined in
[`src/trading_research/data/schema.py:53`](../../src/trading_research/data/schema.py).
It is expressed as a `pyarrow.Schema` (authoritative for parquet I/O)
and mirrored as a `pydantic.BaseModel` (for row-level validation in
tests and at system boundaries). Both must be kept in sync by hand;
the schema_version field is the signal to downstream readers that the
contract has changed.

### 6.1.1 Field reference

| Field | Arrow type | Nullable | Unit / Notes |
|-------|-----------|----------|--------------|
| `timestamp_utc` | `timestamp[ns, UTC]` | No | Bar open, UTC, nanosecond precision |
| `timestamp_ny` | `timestamp[ns, America/New_York]` | No | Same instant as `timestamp_utc`, stored in ET |
| `open` | `float64` | No | Price in instrument native units |
| `high` | `float64` | No | Bar high |
| `low` | `float64` | No | Bar low |
| `close` | `float64` | No | Bar close |
| `volume` | `int64` | No | Total contracts traded |
| `buy_volume` | `int64` | Yes | UpVolume from TradeStation order-flow attribution |
| `sell_volume` | `int64` | Yes | DownVolume from TradeStation order-flow attribution |
| `up_ticks` | `int64` | Yes | Tick-level attribution; same provenance as buy/sell volume |
| `down_ticks` | `int64` | Yes | |
| `total_ticks` | `int64` | Yes | |

The schema's `schema_version` metadata field is `"bar-1m.v1"`. Future
schema changes bump this string; old readers that encounter an unknown
version should refuse to load rather than silently misinterpret the
data.

### 6.1.2 Column order

Column order is fixed by `BAR_COLUMN_ORDER` (a tuple of field names
from `BAR_SCHEMA`). The order is enforced at write time. Reading code
that uses named columns (the standard) is immune to this; reading code
that uses positional indexing is a bug.

> *Why enforce column order:* pyarrow and pandas treat column order as
> part of schema identity when comparing schemas. Enforcing a canonical
> order prevents drift between files produced by different code paths,
> which makes schema comparison cheap and reliable.

---

## 6.2 Why two timestamp columns

`timestamp_utc` and `timestamp_ny` represent the same instant. One is
stored in UTC; one is stored in `America/New_York`. Both are
timezone-aware. This is not redundancy — it is a design decision with
a specific purpose.

**`timestamp_utc`** is the column for all time-series computation:
joins, resampling, lookback windows, sorting. UTC never has
discontinuities from daylight saving time transitions; a 1-minute
resample at bar N will always be at bar N+1 sixty seconds later. The
arithmetic is correct by construction.

**`timestamp_ny`** is the column for all display and market-structure
reasoning: "what time did this trade happen?" "is this a morning bar
or an afternoon bar?" "is this bar inside the RTH window?" These
questions are answered in the exchange's local time because market
participants (including the operator) think in exchange time.

The rule: **never derive one from the other at read time.** Converting
at read time requires a known timezone database version, a valid
DST-transition policy, and awareness of historical timezone rule
changes — and it introduces a silent point of failure whenever any of
those assumptions drift. Storing both at write time, where the code
controls the conversion exactly once, is safer and cheaper than
repeating the conversion on every read.

> *In practice:* strategy expressions that need "hour of day" access
> `timestamp_ny`. The backtest engine's EOD-flat logic, the RTH-window
> filter, and the calendar validator all use `timestamp_ny` for
> session reasoning. Join operations, resamplers, and indicator
> computations use `timestamp_utc` exclusively.

---

## 6.3 The validation gate

The validation gate is implemented in
[`src/trading_research/data/validate.py`](../../src/trading_research/data/validate.py).
It is invoked automatically when `uv run trading-research pipeline`
runs stage 2, and manually via `uv run trading-research verify`.

The gate compares the actual bars in a parquet file against the bars
the exchange calendar says should be there. Discrepancies are
classified as **structural failures** (abort the pipeline) or
**informational** (logged but not fatal).

### 6.3.1 Structural failures — pipeline aborts

Any of these causes `report["passed"]` to be `False` and blocks stage 3:

| Check | What it catches |
|-------|----------------|
| Duplicate timestamps | Two or more bars with the same `timestamp_utc` |
| Negative volumes | Data corruption from vendor |
| Inverted OHLC | `high < low`, `high < open`, `high < close`, `low > open`, `low > close` |
| Null required fields | Any null in `timestamp_utc`, `timestamp_ny`, `open`, `high`, `low`, `close`, `volume` |
| Complete sessions missing | An entire trading session absent from the data |
| Large structural gaps | > 5 consecutive missing bars in RTH, or > 60 consecutive missing bars overnight |

RTH and overnight gaps use different thresholds because the market
behaves differently in the two windows. The RTH session is the liquid
window; any gap longer than 5 minutes is suspicious. Overnight,
zero-activity runs of up to 60 minutes are common in thin markets and
are not data errors. Gaps exceeding 60 bars overnight are structural.

### 6.3.2 Informational — logged, not fatal

| Check | What it catches |
|-------|----------------|
| Minor gaps (≤ 5 bars) | Zero-activity minutes; common in the overnight session |
| Overnight minor gaps (6–60 bars) | Thin-market quiet periods |
| Excluded gaps | Systematic, known omissions excluded from the verdict (see below) |
| Buy/sell volume coverage | Percentage of bars with non-null order-flow attribution |

The report includes a `buy_sell_volume_coverage_pct` field. Coverage
below 100% is normal for instruments and date ranges where TradeStation
did not return order-flow data; strategies that use OFI must handle the
null case explicitly (see §7.9).

### 6.3.3 Excluded gaps — known systematic omissions

Two classes of expected missing bars are excluded from the structural
verdict and are documented in the report for transparency:

**CME post-maintenance window.** CME halts Globex daily 16:00–17:00 CT.
After the session reopens at 17:00 CT, TradeStation systematically
omits the first 30 minutes of bars. Gaps of up to 30 bars starting
between 17:00 and 17:30 CT are classified `exclusion_reason:
post_maintenance` and excluded from the large-gap count.

**Juneteenth calendar patch.** Juneteenth (June 19, observed) has been
a CME closure since 2022 but is absent from the `pandas-market-calendars`
CBOT_Bond and CMEGlobex_FX calendars as of library version 5.x. The
validator removes these sessions from the expected set before gap
analysis. Instruments validated with `CBOT_Bond`, `CMEGlobex_FX`, or
`CME` calendars receive this patch automatically. The
`calendar_patches_applied` field in the report records which patches
were applied.

---

## 6.4 Reading a quality report

`validate_bar_dataset` returns a dict and writes a sidecar
`<parquet_stem>.quality.json` alongside the parquet. The full report
structure:

```json
{
  "dataset_path": "data/clean/ZN_backadjusted_5m_2010-01-03_2026-04-10.parquet",
  "symbol": "ZN",
  "timeframe": "1m",
  "date_range": ["2010-01-03", "2026-04-10"],
  "calendar": "CBOT_Bond",
  "calendar_patches_applied": ["juneteenth_2022+"],
  "row_count": 1064432,
  "expected_row_count": 1091203,
  "missing_bars_total": 26771,
  "missing_bars_minor_gaps": 18940,
  "missing_bars_overnight_minor": 7250,
  "missing_bars_excluded_gaps": 581,
  "missing_bars_structural": 0,
  "missing_bars_unexplained": 0,
  "extra_bars_outside_calendar": 12,
  "duplicate_timestamps": 0,
  "negative_volumes": 0,
  "inverted_high_low": 0,
  "null_required_fields": 0,
  "buy_sell_volume_coverage_pct": 94.3,
  "large_gaps": [],
  "excluded_gaps_count": 23,
  "excluded_gaps": [...],
  "overnight_minor_gap_count": 412,
  "minor_gap_count": 1847,
  "missing_sessions": [],
  "session_count_expected": 4089,
  "session_count_present": 4089,
  "failures": [],
  "passed": true,
  "validation_timestamp_utc": "2026-04-13T18:00:00+00:00",
  "calendar_library_version": "pandas-market-calendars==5.0.1"
}
```

### 6.4.1 First things to look at

**`passed`** — True means no structural failures. If False, read
`failures` for the full list of what failed.

**`missing_bars_structural` (= `missing_bars_unexplained`)** — should
be 0 after a clean build. Any non-zero value means there are large gaps
that are not post-maintenance windows or Juneteenth patches. These
require investigation before the data is used in a backtest.

**`missing_bars_total`** — will almost always be non-zero (zero-volume
minutes are common). The interesting question is how it is distributed:
`minor_gaps` + `overnight_minor` + `excluded` should account for
essentially all of it. What remains is `structural`.

**`buy_sell_volume_coverage_pct`** — anything below 80% is worth
noting; strategies that use OFI should treat the data as OFI-unavailable
for date ranges where coverage is low. This is an informational metric,
not a pass/fail criterion.

**`extra_bars_outside_calendar`** — small counts (< 20) are expected;
TradeStation sometimes returns a bar or two outside the calendar
window around session open/close edge conditions. Large counts are
suspicious and may indicate a timezone handling issue in the download.

**`missing_sessions`** — any session listed here means a complete
trading day is absent from the data. This is a structural failure
regardless of the bars-missing count; a missing session is always
worth investigating.

---

## 6.5 Schema evolution [GAP]

> **Status: [GAP]** — the migration tooling described in this section
> does not yet exist. This section is the specification the tooling
> must conform to when built (session 52). In the meantime, the
> standing rule is: **do not change `BAR_SCHEMA` without implementing
> the migration**.

The current schema version is `"bar-1m.v1"` stored in the parquet
metadata. Future changes to `BAR_SCHEMA` — adding a field, changing a
type, making a nullable field non-nullable — must follow this procedure:

1. **Bump `SCHEMA_VERSION`** in `schema.py` to `"bar-1m.v2"` (or
   higher). Never reuse a version string once a parquet has been
   written with it.

2. **Write a migration function** at
   `src/trading_research/data/migrations/bar1m_v1_to_v2.py` that:
   - Reads an old-schema parquet
   - Applies the column additions or type casts
   - Writes a new-schema parquet
   - Updates the manifest sidecar with the new schema_version and a
     migration provenance record
   - Is idempotent (safe to run twice)

3. **Write a roundtrip test** in
   `tests/data/test_migration_bar1m_v1_to_v2.py` that:
   - Generates a synthetic old-schema parquet
   - Runs the migration
   - Asserts every field's type, value, and nullability match the new
     schema
   - Asserts the manifest records the migration correctly

4. **Run the migration on all existing CLEAN files.** The migration
   CLI command (to be built) will be:
   ```
   uv run trading-research migrate --schema bar-1m.v2 [--dry-run]
   ```
   Dry-run mode prints what would change and estimated bytes written,
   without modifying any files.

5. **Rebuild FEATURES** from the migrated CLEAN files, since FEATURES
   is a derived layer and its schema may also change.

The policy for RAW files: RAW is immutable. If a schema change requires
fields that RAW doesn't have (e.g., adding a new order-flow field that
TradeStation now provides), the migration adds the new column to CLEAN
as nullable with values populated from a re-download pass, not by
mutating RAW. CLEAN can be rebuilt from RAW; RAW cannot be rebuilt from
CLEAN.

> *Why this is non-negotiable:* a schema change applied in place to
> 16 years of parquet files with no migration record is a provenance
> break. If a backtest from session 15 referenced CLEAN files that
> later had a column added, the manifest's `code_commit` and
> `built_at` are the only evidence of what schema was in play. The
> migration record makes this explicit. Without it, old backtest
> results are uninterpretable against the new data.

---

## 6.6 Related references

### Code

- [`src/trading_research/data/schema.py`](../../src/trading_research/data/schema.py)
  — `BAR_SCHEMA`, `SCHEMA_VERSION`, `Bar` pydantic model, `TRADE_SCHEMA`.
- [`src/trading_research/data/validate.py`](../../src/trading_research/data/validate.py)
  — `validate_bar_dataset`, gap thresholds, excluded-gap logic.

### Other manual chapters

- **Chapter 4, §4.1.2** — CLEAN layer definition; the load-bearing rule
  (CLEAN never contains indicators).
- **Chapter 5, §5.5** — calendar names per instrument; the
  `pandas-market-calendars` calendars used.
- **Chapter 7** — Indicator Library: every column added to FEATURES on
  top of BAR_SCHEMA.
- **Chapter 49.1** — `verify` CLI reference; how staleness and
  validation results are surfaced in the operator's workflow.
- **Chapter 53 / Appendix A** — `BAR_SCHEMA` in full; `TRADE_SCHEMA`
  in full.

---

*End of Chapter 6. Next: Chapter 7 — Indicator Library.*
