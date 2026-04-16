# Session 04 Plan — Data Promotion, Back-Adjustment, and Resampling

**Author:** Claude (Sonnet 4.6), drafted at end of session 03 review (2026-04-13)
**Goal:** Get validated, clean data into `data/clean/` and build the first higher-timeframe
views. By the end of this session, the indicator and strategy layers have a solid,
trustworthy data foundation to build on.

---

## Assumed inputs from session 03

- `data/raw/ZN_1m_2010-01-01_2026-04-11.parquet` — 5.24M rows, all 4,202 sessions present,
  100% buy/sell volume coverage.
- `data/raw/ZN_1m_2010-01-01_2026-04-11.quality.json` — currently `passed: false`.
- `data/raw/` also has 1-month smoke pulls for 6A, 6C, 6N with quality reports.
- `validate.py` is working but has two known issues (see Step 1).
- `data/clean/` is empty — nothing has been promoted yet.

---

## Why `data/clean/` is still empty

The `passed: false` verdict on ZN is driven by three fixable issues discovered in the
session 03 post-mortem:

1. **Validator reporting bug** — `failures` only records the top-3 largest gaps. There are
   actually 7,500 large-gap events. The verdict is correct but the failure messages are
   misleading.

2. **Post-maintenance systematic gaps** — Every trading night, ~30 bars are missing starting
   at 22:01 UTC (winter) or 23:01 UTC (summer). This is CME's daily 4–5 PM ET maintenance
   halt; TradeStation does not return data for the first ~30 minutes after the session
   reopens. 449 occurrences of this exact pattern. The calendar model claims these bars
   should exist — the calendar model is wrong, not the data.

3. **Juneteenth not in CBOT_Bond calendar** — June 19 is a CME closure since 2021. The
   `pandas-market-calendars` CBOT_Bond calendar does not include it, producing ~240-bar
   false-failure gaps in 2022, 2023, 2024, and 2025.

There is also an unresolved issue:

4. **September 2023 RTH gap cluster** — Six consecutive trading days (Sept 14–20, 2023) have
   substantial RTH gaps (96–345 bars each). Working hypothesis: `@ZN` continuous contract
   roll artifact. Must be confirmed before ZN data is trusted for backtests.

---

## Goals for session 04 (in priority order)

### 1. Fix the validator

**What:** Two targeted changes to `src/trading_research/data/validate.py`:

- Report ALL large gaps in `failures`, not just top-3. Current code
  (`top = sorted(large_gaps, ...)[:3]`) is the bug.
- Add a `known_gap_windows` parameter — a list of `(utc_time_of_day_start, duration_minutes)`
  tuples that are excluded from the large-gap verdict. The post-maintenance window
  (`time=22:00 UTC, duration=30`) goes here. These are documented as structural data
  limitations, not errors.

**Also:** Add Juneteenth (June 19, observed) to the calendar exclusion logic. The cleanest
approach is a per-calendar override dict in `validate.py` that subtracts known-missing
holidays from the expected set before gap analysis.

**Test additions:** Update `tests/test_validate.py` to cover:
- All failures appear in the `failures` list (not just top-3).
- Known-gap windows are excluded from the verdict.
- Juneteenth exclusion for CBOT_Bond calendar years 2022+.

**Checkpoint A:** Tests green. Re-run validation on the full ZN parquet. Inspect the new
report — expect `passed: true` or a small number of genuine failures. Review with Ibby.

### 2. Diagnose the September 2023 RTH gap cluster

**What:** Compare `@ZN` continuous contract data against raw front-contract bars for
the period September 8–22, 2023 (covering the ZNU23 → ZNZ23 roll window).

Pull ZNU23 (Sep 2023 contract, symbol `TYU23` in TradeStation) and ZNZ23 (`TYZ23`) for
that period directly — not as a continuous series. Compare bar-by-bar against the
`@ZN` data we already have.

**Expected outcome A:** `@ZN` has gaps that the raw contracts do not → confirmed roll
artifact. This makes the multi-contract back-adjustment (Step 3) higher priority.

**Expected outcome B:** Both have the same gaps → CME-side event or TS-side data loss
for that week. Document as a known outage in a `data/raw/known_outages.yaml` file.

**Checkpoint B:** Ibby reviews the comparison. We decide: is ZN 2023 data trustworthy
for backtests that include September 2023? If not, we document the affected date range
as excluded in the instrument spec.

### 3. Multi-contract back-adjusted ZN construction

This was deferred from session 03. It is now higher priority because Step 2 may reveal
that `@ZN` continuous data is unreliable around rolls.

**What gets built:**

- `src/trading_research/data/continuous.py` — `build_back_adjusted_continuous()`:
  - Downloads each quarterly contract individually (ZNH, ZNM, ZNU, ZNZ), using TS
    symbols `TYH`, `TYM`, `TYU`, `TYZ` with explicit expiry year suffixes.
  - Roll date: first business day of the expiration month (ZN expires on the last business
    day of the delivery month; front-month liquidity migrates ~3–5 days earlier).
    Document this choice and flag it for Ibby's review — he may have better intel on
    where ZN liquidity actually moves.
  - Back-adjustment method: **additive** (add a constant to all prior prices at each roll
    to eliminate the price gap). Not ratio-adjusted. Rationale: ZN is a rate product with
    a narrow price range; additive adjustment preserves tick-size relationships correctly.
  - Roll gap calculation: `front_close_at_roll - back_open_at_roll`. Record each roll date
    and adjustment delta in the parquet metadata.
  - Outputs:
    - `data/clean/ZN_1m_backadjusted_<start>_<end>.parquet` — the primary series for
      backtesting (adjusted prices).
    - `data/clean/ZN_1m_unadjusted_<start>_<end>.parquet` — raw per-contract prices
      stitched end-to-end without adjustment (for order-flow analysis where absolute
      price matters).
  - Runs the validator against both outputs before writing.

**Open questions to resolve in this step:**
- Where does ZN front-month liquidity actually migrate? Check Ibby's experience vs. the
  "first business day of expiration month" default.
- At the roll, do we use the outgoing contract's **settlement price** or its **last
  traded close**? Settlement is cleaner and TradeStation's end-of-day bar should have it.

**Checkpoint C:** Ibby reviews a sample roll transition (e.g., ZNH23 → ZNM23, March 2023).
Show: raw front prices, raw back prices, computed adjustment delta, resulting continuous
series. Data scientist checks for price discontinuities in the adjusted series.

### 4. Promote raw → clean for ZN and FX smoke files

Once the validator passes (Steps 1–3 resolved), promote:
- `data/raw/ZN_1m_2010-01-01_2026-04-11.parquet` → `data/clean/`
- The back-adjusted and unadjusted continuous files from Step 3 are written directly
  to `data/clean/`.
- The FX smoke pulls (6A, 6C, 6N 1-month files) are informational only — do not
  promote them until full-history pulls are done.

### 5. Resample 1m → higher timeframes

**What gets built:**

- `src/trading_research/data/resample.py` — `resample_bars(df_1m, timeframe) -> DataFrame`:
  - Supported timeframes: `"3m"`, `"5m"`, `"15m"`, `"30m"`, `"1h"`.
  - Resampling is always from 1-minute base — never from a different resampled set.
  - OHLC aggregation: first open, max high, min low, last close, sum volume/buy_volume/
    sell_volume/up_ticks/down_ticks/total_ticks. Nullable fields remain nullable if any
    bar in the window is null.
  - Respects session boundaries: a resampled bar does not cross the daily maintenance halt.
    A 5-minute bar at 15:58 ET closes at 15:58, not at 16:03.
  - Writes to `data/features/<symbol>_<timeframe>_<start>_<end>.parquet` with a
    corresponding quality report.
  - Unit tests: verify OHLC aggregation correctness, session boundary respect,
    timestamp alignment.

**Checkpoint D:** Resample ZN 1m → 5m and 15m. Ibby spot-checks a known date and confirms
a resampled bar matches manual aggregation.

---

## Explicitly out of scope for session 04

- Indicators. Session 05.
- Any strategy code.
- 6A/6C/6N full history pulls. Not until roll convention is understood for FX contracts.
- Streaming data.
- Anything in `risk`, `backtest`, `eval`, `replay`, `live`.

---

## Open questions to resolve early in session 04

1. **ZN roll timing**: Does Ibby have a view on when front-month ZN liquidity migrates?
   The default (first business day of expiration month) may be 1–3 days late relative
   to actual liquidity migration.

2. **September 2023 data**: No pre-decision required. The Step 2 diagnosis determines
   root cause; the back-adjusted series built in Step 3 is the fix regardless of outcome.
   - Roll artifact confirmed → back-adjusted series replaces @ZN; issue disappears.
   - Real CME/TS outage → document in `known_outages.yaml`, add to validator exclusion
     list, accept it. A real outage means the market was unavailable; excluding it is
     honest, not a flaw.
   Either way, proceed directly to Step 3. Do not defer backtesting pending this answer.

3. **Additive vs. ratio back-adjustment**: The plan defaults to additive. The data scientist
   will check whether any strategy we're planning requires ratio adjustment (ratio matters
   more for percentage-return strategies; additive is correct for fixed-tick-value
   instruments like ZN).

---

## Risk register for session 04

1. **Individual contract availability**: TradeStation may not have clean 1-minute data for
   all ZN quarterly contracts back to 2010. Expect gaps in older contracts (pre-2013).
   Design the continuous constructor to handle partial-history contracts gracefully.

2. **Adjustment magnitude surprises**: Some ZN rolls produce 20–30 tick adjustments.
   Back-adjusted prices for 2010 may be negative or implausibly low. This is mathematically
   correct but visually confusing. Document it prominently in the parquet metadata.

3. **Juneteenth calendar patch scope**: The `pandas-market-calendars` library may not have
   Juneteenth in other calendars (CMEGlobex_FX for 6A/6C/6N). Apply the same fix
   consistently across all calendars used by this project.

4. **Session boundary resampling edge cases**: The CME maintenance halt is 60 minutes
   exactly (16:00–17:00 ET). A resampled bar that straddles this boundary should be
   truncated, not silently merged. Edge case must have an explicit unit test.

---

## Personas at the end of session 04

- **Quant mentor:** "We finally have data we can trust. The back-adjusted series is the
  foundation every ZN backtest will stand on — getting it right now saves us from
  discovering roll artifacts after we've already committed to a strategy. Don't rush it."

- **Data scientist:** "The September 2023 cluster needs a verdict before I sign off on
  any ZN backtest that includes that period. Everything else in session 04 is plumbing —
  good, necessary plumbing, but the roll artifact question is the one with teeth."
