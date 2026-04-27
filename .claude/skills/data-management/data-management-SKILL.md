---
name: data-management
description: Use when working with bar data, trade logs, instrument specifications, trading calendars, or any data that flows through the trading-research pipeline. This skill defines the canonical schemas and contracts that every other skill depends on. Invoke when downloading, validating, storing, resampling, or reading market data; when defining or reading instrument specs; when writing or reading trade logs; when handling timezones, sessions, or holiday gaps; or when designing any data structure that will be consumed by another part of the system.
---

# Data Management

This skill owns the ground-truth contracts for all data in the trading-research project. Every other skill depends on these decisions. Get them right and downstream code is straightforward; get them wrong and you'll fight subtle bugs for months.

The principle: **data integrity is non-negotiable, and the schema is the contract.** A backtest on dirty data is worse than no backtest because it produces false confidence. A trade log without trigger-bar snapshots cannot be forensically replayed. An instrument spec hard-coded in strategy code becomes a maintenance nightmare the first time you trade a second instrument. Get these right once, then never think about them again.

## What this skill covers

- The canonical bar schema (OHLCV with order flow)
- The contract registry (instrument specifications in YAML)
- Trading calendar validation and gap handling
- Timezone discipline
- Resampling 1-minute bars to higher timeframes
- The trade log schema for backtest outputs
- Data quality reports
- File layout and naming conventions for raw, clean, and feature data

## What this skill does NOT cover

- Actually downloading data from TradeStation (see `historical-bars` and `streaming-bars`)
- Computing indicators on bars (see `indicators`)
- Running backtests against bar data (see `backtesting`)
- Visualizing bar data (see `charting`)

## The canonical bar schema

Every bar in the project, regardless of source or timeframe, conforms to this schema. This is enforced at write time and assumed at read time.

```python
# src/trading_research/data/schema.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Polars/pandas dtype mapping for the parquet schema
BAR_SCHEMA = {
    "timestamp_utc": "datetime64[ns, UTC]",      # bar OPEN time, tz-aware UTC
    "timestamp_ny": "datetime64[ns, America/New_York]",  # same instant, NY tz
    "symbol": "string",                          # canonical symbol e.g. "ZN", "6A"
    "timeframe": "string",                       # "1m", "3m", "5m", "15m", "1h", "1d"
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "int64",                           # total volume (always present)
    "buy_volume": "Int64",                       # nullable: volume at ask
    "sell_volume": "Int64",                      # nullable: volume at bid
    "tick_count": "Int64",                       # nullable: number of trades in bar
    "session_id": "string",                      # e.g. "2024-03-15-RTH" or "2024-03-15-GLOBEX"
    "is_session_open": "bool",                   # first bar of a session
    "is_session_close": "bool",                  # last bar of a session
    "data_source": "string",                     # e.g. "tradestation_v3"
    "ingestion_timestamp_utc": "datetime64[ns, UTC]",  # when this row was written
}
```

**Field rules and rationale:**

- **`timestamp_utc` is the bar's OPEN time, not its close.** This is a deliberate choice because it makes "what was known at time T" queries unambiguous. The bar at `timestamp_utc=09:30` covers the interval `[09:30, 09:31)`. When a strategy makes a decision "at" 09:30, it can only see bars whose `timestamp_utc < 09:30` because the 09:30 bar hasn't closed yet. Storing close times leads to off-by-one bugs that are hard to find.

- **Both UTC and NY timestamps are stored.** Yes, it's redundant. Yes, it costs disk space. The tradeoff is that every reader downstream gets the timezone they want without having to convert, and timezone conversion bugs are eliminated as a class. Disk is cheap; debugging timezone bugs at 2 AM is expensive.

- **`buy_volume` and `sell_volume` are nullable.** TradeStation provides these for most CME futures most of the time, but not always. Strategies that depend on them must check for null and either skip the bar or fall back to a defined behavior. A strategy that silently treats null buy_volume as zero is a bug.

- **`session_id` and `is_session_open`/`is_session_close` flags exist** because resampling and indicator computation both need to respect session boundaries. A 15-minute bar must not span the daily settlement gap; an EMA must be reset (or at least flagged) at session opens for some strategies. These flags make session-aware logic possible without re-computing session membership on every read.

- **`data_source` and `ingestion_timestamp_utc` are provenance.** Six months from now you'll re-pull data with a new TradeStation API version, and you need to know which trade logs were generated against which data version. Provenance fields make this traceable. Never omit them.

**Naming convention for symbols:** use the canonical CME root symbol without month/year codes. `ZN` not `ZNH25`. Continuous contract construction (handling rolls) is a separate concern handled in the `historical-bars` skill, and the result of that construction is a continuous series stored under the root symbol.

## The contract registry

Instrument specifications live in `configs/instruments.yaml`, never in code. Strategies reference instruments by symbol and look up specs at runtime.

```yaml
# configs/instruments.yaml
ZN:
  description: "10-Year US Treasury Note futures"
  exchange: CBOT
  asset_class: bonds
  tick_size: 0.015625        # 1/64 of a point
  tick_value_usd: 15.625
  contract_size: 100000
  currency: USD
  sessions:
    globex:
      open_ny: "18:00"
      close_ny: "17:00"      # next day
      days: [Sun, Mon, Tue, Wed, Thu]
  settlement_time_ny: "15:00"
  daily_break_start_ny: "17:00"
  daily_break_end_ny: "18:00"
  micro_symbol: null         # no micro version
  typical_initial_margin_usd: 1800   # approximate, verify with broker
  typical_maintenance_margin_usd: 1600
  notes: |
    Liquid throughout US session, thinner overnight.
    Sensitive to FOMC, NFP, CPI releases.
    Mean-reverts well in calm rate environments; trends hard during
    Fed policy shifts.

6A:
  description: "Australian Dollar futures"
  exchange: CME
  asset_class: fx
  tick_size: 0.0001
  tick_value_usd: 10.00
  contract_size: 100000      # AUD
  currency: USD
  sessions:
    globex:
      open_ny: "18:00"
      close_ny: "17:00"
      days: [Sun, Mon, Tue, Wed, Thu]
  settlement_time_ny: "15:00"
  daily_break_start_ny: "17:00"
  daily_break_end_ny: "18:00"
  micro_symbol: M6A
  typical_initial_margin_usd: 1500
  typical_maintenance_margin_usd: 1350
  notes: |
    Commodity currency, correlated with iron ore and risk sentiment.
    Active during Asian and European sessions.
    Pairs naturally with 6C (CAD) and 6N (NZD).
```

**Rules for the contract registry:**

- Every instrument the project trades must have an entry. No exceptions.
- Hard-coding `tick_size = 0.1` or `usd_per_tick = 10` in strategy code is forbidden. Strategies receive an `Instrument` object loaded from this YAML.
- The `notes` field is for human-readable context that the mentor persona may reference. Keep it factual and current.
- When CME changes margin requirements (which happens), update the YAML. Margin numbers that are six months stale will lie to you about pair capital efficiency.
- Add new instruments by editing the YAML, not by writing Python.

A loader lives at `src/trading_research/data/instruments.py`:

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import yaml

@dataclass(frozen=True)
class SessionSpec:
    open_ny: str
    close_ny: str
    days: list[str]

@dataclass(frozen=True)
class Instrument:
    symbol: str
    description: str
    exchange: str
    asset_class: str
    tick_size: float
    tick_value_usd: float
    contract_size: int
    currency: str
    sessions: dict[str, SessionSpec]
    settlement_time_ny: str
    daily_break_start_ny: Optional[str]
    daily_break_end_ny: Optional[str]
    micro_symbol: Optional[str]
    typical_initial_margin_usd: float
    typical_maintenance_margin_usd: float
    notes: str

def load_instruments(path: Path = Path("configs/instruments.yaml")) -> dict[str, Instrument]:
    """Load all instruments from the registry. Cache the result; the file rarely changes."""
    raw = yaml.safe_load(path.read_text())
    result = {}
    for symbol, spec in raw.items():
        sessions = {
            name: SessionSpec(**s) for name, s in spec.pop("sessions").items()
        }
        result[symbol] = Instrument(symbol=symbol, sessions=sessions, **spec)
    return result
```

## Trading calendar validation

CME futures trade nearly 24 hours but not quite. Every bar dataset must be validated against an exchange-aware calendar before being used. The standard library is `pandas-market-calendars`, which knows CME Globex sessions, holiday closures, half-days, and historical session changes going back to 2010 and earlier.

**The validation contract:** for any cleaned bar dataset, a `data_quality_report.json` exists alongside the parquet file with the same base name. The report includes:

```json
{
  "dataset_path": "data/clean/ZN_1m_2020-01-01_2024-12-31.parquet",
  "symbol": "ZN",
  "timeframe": "1m",
  "date_range": ["2020-01-01", "2024-12-31"],
  "row_count": 1834521,
  "expected_row_count": 1834892,
  "missing_bars": 371,
  "missing_bars_explained_by_calendar": 371,
  "missing_bars_unexplained": 0,
  "duplicate_timestamps": 0,
  "negative_volumes": 0,
  "inverted_high_low": 0,
  "null_required_fields": 0,
  "buy_sell_volume_coverage_pct": 98.4,
  "session_coverage": {
    "globex_full_days": 1240,
    "globex_half_days": 18,
    "missing_full_days": 0,
    "missing_half_days": 0
  },
  "validation_timestamp_utc": "2025-01-15T14:32:10Z",
  "calendar_library_version": "pandas-market-calendars==4.4.0",
  "passed": true
}
```

**Validation rules:**

1. **No unexplained gaps.** Every missing bar must correspond to a known calendar event (holiday, half-day, daily break, weekend). Unexplained gaps fail the report.
2. **No duplicates.** Duplicate timestamps within a symbol+timeframe are a bug — usually a re-download that wasn't deduplicated properly.
3. **No negative volumes.** Volume of zero is acceptable (illiquid bars happen). Negative volume is a bug.
4. **No inverted high/low.** `high >= low` always; `high >= open` and `high >= close`; `low <= open` and `low <= close`. Inversions indicate bad data.
5. **No nulls in required fields.** `timestamp_utc`, `symbol`, `timeframe`, OHLC, and `volume` are required. `buy_volume`, `sell_volume`, and `tick_count` may be null.
6. **Buy/sell volume coverage is reported but not enforced.** A dataset with 0% order flow coverage still passes; downstream code that depends on order flow handles the absence.

**When validation fails:** the report is written with `passed: false` and a list of failures. The dataset is NOT moved from `data/raw/` to `data/clean/`. It stays in raw with the failed report next to it. The user is informed of what failed and asked how to proceed (re-download, accept the gaps, manual fix). Validation failures are never silently ignored.

**Implementation skeleton:**

```python
# src/trading_research/data/validate.py
import pandas_market_calendars as mcal
import polars as pl
from pathlib import Path
from datetime import datetime, timezone
import json

def validate_bar_dataset(
    parquet_path: Path,
    symbol: str,
    timeframe: str,
    exchange: str = "CMEGlobex",
) -> dict:
    """Validate a bar dataset against the exchange calendar.
    Returns a dict matching the data_quality_report.json schema.
    Writes the report next to the parquet file."""

    df = pl.read_parquet(parquet_path)
    cal = mcal.get_calendar(exchange)

    # ... (full implementation generated by the agent at build time;
    #      this skill defines the contract, not the entire implementation)
```

## Timezone discipline

- All stored timestamps are tz-aware. Naive datetimes are a bug and will be rejected at write time.
- Storage is UTC. Display is America/New_York. The dual-column schema (`timestamp_utc` and `timestamp_ny`) makes both available without conversion.
- Daylight saving transitions: NY observes DST, CME's Globex session times are anchored to NY local time so they shift in clock terms when DST changes. The calendar library handles this; do not handle it manually.
- When parsing timestamps from TradeStation responses, force `utc=True` in `pd.to_datetime` to avoid the silent-naive trap. Then convert to NY for the dual-column write.

## Resampling 1-minute bars to higher timeframes

1-minute bars are the canonical base. 3m, 5m, 15m, 1h, 1d are *always* resampled from 1m, never downloaded separately. This guarantees consistency across timeframes and makes the data integrity story trivial: validate the 1m base once, and every higher timeframe inherits the validation.

**The session-aware resampling rule:** higher-timeframe bars must not span session boundaries. A 15-minute bar that contains 1-minute bars from both before and after the daily break is invalid. The resampler must group by `(session_id, time_bucket)`, not just by time bucket.

```python
# src/trading_research/data/resample.py
import polars as pl

VALID_TIMEFRAMES = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "1d": "1d",
}

def resample_bars(
    df_1m: pl.DataFrame,
    target_timeframe: str,
    instrument_symbol: str,
) -> pl.DataFrame:
    """Resample 1-minute bars to a target timeframe.

    Critical: the resampling MUST respect session boundaries. A bar that
    would span a session break is split or dropped, never merged.

    The session_id of each output bar is the session_id of its first
    constituent 1m bar. is_session_open and is_session_close flags are
    recomputed based on the resampled data.
    """
    if target_timeframe not in VALID_TIMEFRAMES:
        raise ValueError(f"Unknown timeframe: {target_timeframe}")
    if target_timeframe == "1m":
        return df_1m

    # Group by session and time bucket within the session
    # ... (implementation by agent at build time)
```

**Resampling output is computed on demand and cached.** When a strategy asks for 5-minute bars on ZN, the system checks `data/features/ZN_5m_*.parquet` first; if absent or stale, it resamples from `data/clean/ZN_1m_*.parquet` and writes the result. Cache invalidation: if the 1m source file's modification time is newer than the 5m cache, the cache is stale.

## The trade log schema

Backtests write trade logs to `runs/<run_id>/trades.parquet` conforming to this schema. The replay app and the evaluation skill both read from it. The schema is verbose by design — verbose-on-disk costs nothing, verbose-in-the-debugger saves weeks.

```python
# src/trading_research/data/trade_schema.py
TRADE_LOG_SCHEMA = {
    # Identity
    "trade_id": "string",
    "strategy_id": "string",
    "strategy_version": "string",
    "run_id": "string",
    "symbol": "string",

    # Side and size
    "side": "string",                            # "long" or "short"
    "size": "float64",                           # contracts (may be fractional for sim)

    # Trigger bar (the bar whose close caused the decision)
    "trigger_bar_time_utc": "datetime64[ns, UTC]",
    "trigger_bar_time_ny": "datetime64[ns, America/New_York]",
    "trigger_bar_open": "float64",
    "trigger_bar_high": "float64",
    "trigger_bar_low": "float64",
    "trigger_bar_close": "float64",
    "trigger_bar_volume": "int64",
    "trigger_bar_buy_volume": "Int64",
    "trigger_bar_sell_volume": "Int64",
    "trigger_indicators_json": "string",         # as-of values, json-encoded

    # Entry bar (the bar where the fill happened)
    "entry_bar_time_utc": "datetime64[ns, UTC]",
    "entry_bar_time_ny": "datetime64[ns, America/New_York]",
    "entry_bar_open": "float64",
    "entry_bar_high": "float64",
    "entry_bar_low": "float64",
    "entry_bar_close": "float64",
    "entry_bar_volume": "int64",
    "entry_bar_buy_volume": "Int64",
    "entry_bar_sell_volume": "Int64",
    "entry_fill_price": "float64",
    "entry_fill_assumption": "string",           # "next_bar_open", "trigger_bar_close", etc.
    "entry_slippage_ticks": "float64",

    # Exit trigger bar (the bar whose close caused the exit decision)
    "exit_trigger_bar_time_utc": "datetime64[ns, UTC]",
    "exit_trigger_bar_time_ny": "datetime64[ns, America/New_York]",
    "exit_trigger_bar_open": "float64",
    "exit_trigger_bar_high": "float64",
    "exit_trigger_bar_low": "float64",
    "exit_trigger_bar_close": "float64",
    "exit_trigger_bar_volume": "int64",
    "exit_trigger_bar_buy_volume": "Int64",
    "exit_trigger_bar_sell_volume": "Int64",
    "exit_indicators_json": "string",

    # Exit bar (the bar where the exit fill happened)
    "exit_bar_time_utc": "datetime64[ns, UTC]",
    "exit_bar_time_ny": "datetime64[ns, America/New_York]",
    "exit_bar_open": "float64",
    "exit_bar_high": "float64",
    "exit_bar_low": "float64",
    "exit_bar_close": "float64",
    "exit_bar_volume": "int64",
    "exit_bar_buy_volume": "Int64",
    "exit_bar_sell_volume": "Int64",
    "exit_fill_price": "float64",
    "exit_reason": "string",                     # "tp", "sl", "tp_sl_ambiguous", "timeout", "signal", "manual", "eod_flat"
    "exit_resolution_method": "string",          # "unambiguous", "pessimistic", "delta_inferred", "tick_verified"
    "exit_slippage_ticks": "float64",

    # P&L
    "pnl_ticks": "float64",
    "pnl_usd_gross": "float64",
    "commission_usd": "float64",
    "pnl_usd_net": "float64",

    # Re-entry tracking (for planned scale-in patterns)
    "is_reentry": "bool",                        # True if this is a planned add-on to a prior trade
    "parent_trade_id": "string",                 # the original trade if is_reentry, else null
    "combined_target_price": "float64",          # the combined target if part of a re-entry sequence
    "combined_risk_usd": "float64",              # the combined risk if part of a re-entry sequence

    # Provenance
    "data_source": "string",                     # which data version this trade was generated against
    "notes": "string",                           # free-form, optional
}
```

**Why both trigger bar and entry bar are stored separately:** the trigger bar is what the strategy *saw* when it made the decision. The entry bar is where the *fill* actually happened (typically the next bar's open). These are almost never the same bar, and confusing them is one of the most common backtesting bugs. The replay app shows both bars marked distinctly so the human can visually verify "yes, the indicators at the trigger bar justified this trade, and the fill happened at the entry bar's open as expected."

**Why `trigger_indicators_json` is JSON-encoded rather than columnar:** different strategies use different indicator sets. A schema with one column per indicator would require schema migrations every time a new indicator is added. JSON in a single column is the right tradeoff: slightly worse for analytics, dramatically better for evolution.

**Why re-entry fields exist:** the re-entry rules in `CLAUDE.md` require that planned re-entries declare their combined risk and combined target before the second entry is placed. The trade log captures this so the evaluation skill can verify that re-entries actually behaved as planned, and so the replay app can group related trades visually.

## File layout for data

```
data/
├── raw/
│   ├── ZN_1m_2020-01-01_2024-12-31.parquet         # exact TradeStation download, untouched
│   ├── ZN_1m_2020-01-01_2024-12-31.metadata.json   # download params, API version, timestamp
│   └── ZN_1m_2020-01-01_2024-12-31.quality.json    # validation report (passed: false initially)
├── clean/
│   ├── ZN_1m_2020-01-01_2024-12-31.parquet         # validated, schema-conformant
│   └── ZN_1m_2020-01-01_2024-12-31.quality.json    # validation report (passed: true)
└── features/
    ├── ZN_5m_2020-01-01_2024-12-31.parquet         # resampled from 1m clean
    ├── ZN_15m_2020-01-01_2024-12-31.parquet
    └── ZN_1m_2020-01-01_2024-12-31_indicators.parquet  # 1m + indicator columns
```

**Naming convention:** `{symbol}_{timeframe}_{start_date}_{end_date}.parquet`. Dates in ISO format. No spaces, no special characters. The metadata and quality JSON files share the parquet's base name with their respective extensions.

**Why three layers (raw, clean, features) and not one:**

- **Raw is the ground truth.** Untouched downloads. If anything goes wrong downstream, you can always re-derive everything from raw. Never edited.
- **Clean is the validated, schema-conformant version.** This is what strategies and backtests read. Clean files have `passed: true` quality reports.
- **Features is computed-on-demand cache.** Resampled timeframes and indicator-augmented bars live here. Always re-derivable from clean.

The separation also makes the agent's job clearer at each stage: `historical-bars` writes to raw, `data-management` validates raw → clean, `indicators` writes from clean → features.

## Standing rules this skill enforces

1. **No naive datetimes anywhere in the project.** All timestamps are tz-aware. Code that produces a naive datetime is a bug.
2. **No hard-coded instrument specs.** Tick sizes, contract values, session hours come from `instruments.yaml`.
3. **No backtests on unvalidated data.** A strategy that tries to read from `data/raw/` instead of `data/clean/` is a bug. Reads from `data/clean/` will check for the quality report and refuse if it's missing or `passed: false`.
4. **No higher-timeframe downloads.** 3m, 5m, 15m, 1h, 1d come from resampling 1m, period.
5. **No silent gap-filling.** Missing data is either explained by the calendar (silently OK) or unexplained (loud error). Never interpolated, never forward-filled, never zero-padded without explicit user consent.
6. **Provenance is mandatory.** Every parquet has its `data_source` column populated. Every trade log knows which data version it was generated against.

## When to invoke this skill

Load this skill when the task involves:

- Defining or modifying the bar schema, trade log schema, or instrument registry
- Writing or reading parquet files in `data/raw/`, `data/clean/`, or `data/features/`
- Validating data quality against the trading calendar
- Resampling 1-minute bars to higher timeframes
- Handling timezones, sessions, or holidays in any data context
- Any task where another skill's correctness depends on knowing the schema

If the task is "implement an indicator," you don't need this skill loaded — `indicators` knows the schema by reference. If the task is "design a new field for the trade log," you do need this skill loaded, because changing the schema affects every downstream consumer.

## Open questions for build time

These are decisions that should be made when implementing the skill, not now:

1. **Polars or pandas as the primary dataframe library?** Polars is faster and has better parquet support; pandas has more ecosystem. Recommend Polars for the data layer with pandas adapters where ecosystem libraries (e.g. `pandas-market-calendars`) require it.
2. **Continuous contract construction for futures rolls.** Back-adjustment, ratio-adjustment, or unadjusted with explicit roll markers? Each has tradeoffs. Recommend back-adjustment as the default with the unadjusted series also available, and document the choice in `data_source`.
3. **Where to store the ingestion_timestamp.** Per-row (cheap, accurate) or per-file metadata (smaller, less granular). Recommend per-row for clean and features, per-file for raw.
