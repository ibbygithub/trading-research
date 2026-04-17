# /data-quality-check

Run the calendar-aware data quality validator against one or more bar datasets in `data/raw/`.

## Usage

```
/data-quality-check ZN
/data-quality-check ZN 2024-01-01 2024-01-31
/data-quality-check 6A 6C 6N
/data-quality-check --all
```

## What to do when invoked

When the user runs `/data-quality-check`, read the arguments they provided:

1. **`/data-quality-check <SYMBOL> [start] [end]`** — validate the most recently downloaded parquet for that symbol. If `start`/`end` are given, validate that specific file. If not given, find the largest parquet for that symbol in `data/raw/`.

2. **`/data-quality-check <SYM1> <SYM2> ...`** — validate each named symbol in turn.

3. **`/data-quality-check --all`** — find every parquet in `data/raw/` that has a corresponding `.metadata.json` and validate each one.

For each dataset:

1. **Find the parquet.** Look in `data/raw/` for a file matching `{SYMBOL}_1m_{start}_{end}.parquet`. If start/end not given, pick the file with the widest date range (largest row count is a reasonable proxy).

2. **Extract the date range.** Read the dates from the filename or from the `.metadata.json` sidecar.

3. **Run the validator.** Call `validate_bar_dataset(parquet_path, symbol, start_date, end_date)` from `trading_research.data.validate`. This writes a `.quality.json` sidecar next to the parquet.

4. **Print a human-readable summary** of the report:
   - Symbol and date range
   - `PASS` or `FAIL` verdict in bold/caps
   - Row count vs expected count, missing bar breakdown (total / minor / large)
   - Number of sessions present vs expected
   - buy/sell volume coverage %
   - If FAIL: list each failure clearly with the gap location (UTC time) and duration
   - The 3 largest gaps regardless of pass/fail (useful context)
   - Path to the quality.json for full detail

5. **If FAIL, explain what it means** — distinguish between:
   - Zero-activity overnight gaps (not concerning; mention they're in thin trading hours)
   - RTH gaps (potentially concerning; flag explicitly)
   - Missing sessions (serious; always flag)
   - Known events (CME outages, major holidays) if recognizable

## Example output

```
Data Quality Report — ZN 2010-01-01 to 2026-04-11
--------------------------------------------------
Verdict   : FAIL
Rows      : 5,241,450 / 5,767,455 expected (91.1% coverage)
Missing   : 527,174 bars — 439,710 minor (<6-bar) overnight gaps, 87,464 in large gaps
Sessions  : 4,202 / 4,202 present
Buy/sell vol: 100.0% coverage
Duplicates : 0

Failures:
  [1] 960 bars missing from 2024-07-18 05:01 UTC (16 hrs overnight)
      → This is the CME technology outage of July 2024. Real event, not a data error.
  [2] 720 bars missing from 2011-12-26 23:01 UTC (12 hrs overnight)
      → Post-Christmas thin session; likely zero-activity at TradeStation.
  [3] 720 bars missing from 2012-01-02 23:01 UTC (12 hrs overnight)
      → Post-New Year thin session; same pattern.

Top 3 gaps:
  960 bars at 2024-07-18 05:01 UTC (overnight, non-RTH)
  720 bars at 2011-12-26 23:01 UTC (overnight, non-RTH)
  720 bars at 2012-01-02 23:01 UTC (overnight, non-RTH)

Report written: data/raw/ZN_1m_2010-01-01_2026-04-11.quality.json
```

## Implementation

Run the validator directly using the project's Python environment:

```python
uv run python -c "
from pathlib import Path
from datetime import date
from trading_research.data.validate import validate_bar_dataset

report = validate_bar_dataset(
    Path('data/raw/ZN_1m_2010-01-01_2026-04-11.parquet'),
    'ZN',
    date(2010, 1, 1),
    date(2026, 4, 11),
)
# ... print summary
"
```

After running, always show the key numbers and interpret the failures in plain English. The user should be able to decide whether the dataset is fit for use without reading the raw JSON.

## What "fit for use" means

A dataset is fit for backtesting if:
- All expected sessions are present (no missing trading days)
- No duplicate timestamps
- No inverted OHLC
- No RTH gaps > 30 minutes (except for documented exchange outages)
- buy/sell volume coverage > 90% (if order-flow strategies will use it)

Minor overnight gaps (hundreds of single-bar absences) are normal and do not disqualify a dataset. Large overnight gaps (> 2 hours outside RTH) warrant a note but are often thin-market phenomena, not data errors.
