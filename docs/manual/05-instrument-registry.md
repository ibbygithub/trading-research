# Chapter 5 — Instrument Registry

> **Chapter status:** [EXISTS] — every section in this chapter documents
> the platform as it operates at v1.0. The registry is a single typed
> file consumed by a single typed loader.

---

## 5.0 What this chapter covers

Every contract the platform touches — every tick size, every contract
multiplier, every session window, every commission, every calendar — is
defined in **one** file: [`configs/instruments_core.yaml`](../../configs/instruments_core.yaml).
The platform's rule on this is uncompromising: **hard-coding any of
these values in strategy, indicator, backtest, sizing, or evaluation
code is forbidden.** This chapter is the reason why, and the reference
for what the registry contains.

After reading this chapter you will:

- Understand the `Instrument` contract — every field, its type, and
  what depends on it
- Know the five registered instruments and their full specifications
- Understand the CME-vs-TradeStation symbol mapping and how to verify
  a new mapping before committing it
- Know what calendar each instrument validates against and what that
  calendar does and does not catch
- Be able to add a new instrument from scratch in five steps
- Understand the contract-economics pitfall around tick math and why
  the registry uses `Decimal` everywhere

This chapter is roughly 6 pages. It is referenced by Chapter 4 (Data
Pipeline), Chapter 6 (Bar Schema), Chapter 14 (Backtest Engine),
Chapter 36 (Position Sizing), Chapter 50 (Configuration Reference), and
the cold-start procedure in Chapter 54.

---

## 5.1 The Instrument contract

The registry holds a typed [`Instrument`](../../src/trading_research/core/instruments.py)
record per symbol. Every field is required (with two explicit
exceptions noted below); the model is `frozen=True` after load, so no
code in the platform can mutate an instrument once the registry has
returned it. If a fact about a contract changes, the YAML changes and
git records the diff.

### 5.1.1 Field groups

The fields fall into five groups by purpose. Strategy code touches
them through the registry, never by name.

| Group | Fields | What depends on them |
|-------|--------|----------------------|
| **Identity** | `symbol`, `tradestation_symbol`, `name`, `exchange`, `asset_class` | The data downloader; the inventory CLI; trade-log column labels |
| **Economics** | `tick_size`, `tick_value_usd`, `contract_multiplier`, `is_micro` | Sizing; P&L; slippage and commission expressed in ticks |
| **Costs** | `commission_per_side_usd`, `intraday_initial_margin_usd`, `overnight_initial_margin_usd` | Backtest cost model; capital allocation; margin-aware position sizing |
| **Schedule** | `session_open_et`, `session_close_et`, `rth_open_et`, `rth_close_et`, `timezone` | EOD-flat in the backtest engine; RTH filters in feature builders; replay-app session shading |
| **Calendar & roll** | `calendar_name`, `roll_method` | Calendar validation in the data pipeline; back-adjuster construction of continuous contracts |

Two optional fields exist:

- `overnight_initial_margin_usd` may be `null` for instruments where
  the broker does not publish an overnight rate the platform cares
  about today.
- `tradeable_ou_bounds_bars` is per-timeframe Ornstein-Uhlenbeck half-
  life bounds used by the stationarity suite (Chapter 24). Instruments
  without explicit bounds fall back to the platform's general defaults.

### 5.1.2 Why every value is `Decimal`

Tick sizes, tick values, contract multipliers, commissions, and margin
figures are all `Decimal` at the model layer, deserialised from
quoted strings in the YAML. This is not a stylistic choice; it is a
correctness requirement.

Consider ZN: tick size 1/64 = 0.015625, tick value $15.625. A 1,000-
trade backtest with one tick of slippage per side accumulates 2,000
slippage charges. In `float`, repeated `0.015625 * 15.625` arithmetic
accumulates representational error that drifts P&L by cents over the
backtest. In `Decimal`, the arithmetic is exact.

The error is small per trade and large in aggregate. It can change
which side of the validation gate a marginal strategy lands on. The
registry forces `Decimal` so no consumer can downcast accidentally.

> *Why this matters operationally:* if you write a new sizing or
> P&L helper, accept and return `Decimal`. Casting to `float` for a
> calculation and back is a bug, even if it looks innocent. The
> backtest engine and the eval modules do this consistently; new
> code must match.

### 5.1.3 What the registry refuses to hold

The `Instrument` record is *contract metadata only*. It does not hold:

- Indicator parameters or feature-set configuration (those live in
  `configs/featuresets/`, see Chapter 8)
- Strategy parameters (those live in `configs/strategies/<name>.yaml`,
  see Chapter 10)
- Backtest fill-model defaults beyond `commission_per_side_usd`
- Order-routing or broker-specific configuration

The split is deliberate: the registry is the kind of fact that is true
about a contract regardless of what you do with it. Anything that
varies by experiment, strategy, or session belongs elsewhere.

---

## 5.2 Currently registered instruments

Five instruments are registered today: ZN (the project's bond anchor)
and four CME FX contracts (6E, 6A, 6C, 6N). The platform is
instrument-agnostic by design — adding a sixth is a configuration
change, not a code change (§5.5).

### 5.2.1 Reference table

| Symbol | TS Root | Name | Class | Tick Size | Tick $ | RTH (ET) | Calendar |
|--------|---------|------|-------|-----------|--------|----------|----------|
| **ZN** | TY | 10-Year Treasury Note | rates | 0.015625 | $15.625 | 08:20 – 15:00 | `CBOT_Bond` |
| **6E** | EC | Euro FX | fx | 0.00005 | $6.25 | 08:00 – 17:00 | `CMEGlobex_FX` |
| **6A** | AD | Australian Dollar | fx | 0.0001 | $10.00 | 08:00 – 17:00 | `CMEGlobex_FX` |
| **6C** | CD | Canadian Dollar | fx | 0.0001 | $10.00 | 08:00 – 17:00 | `CMEGlobex_FX` |
| **6N** | NE1 | New Zealand Dollar | fx | 0.0001 | $10.00 | 08:00 – 17:00 | `CMEGlobex_FX` |

Globex hours for all five: 18:00 ET (prior day) to 17:00 ET, with a
one-hour daily maintenance halt 17:00 – 18:00 ET. Default commission is
$1.75 per side.

### 5.2.2 Per-instrument notes

**ZN — 10-Year Treasury Note.** The project's bond anchor. Tick size
of 1/64 of a point ($15.625) is unusual relative to FX and is a common
source of bugs in code that assumes a "round" tick. Treat the
`tick_size: Decimal` literally — never cast to float for sizing math.
RTH is 08:20 – 15:00, the historical CBOT bond-pit window, which
`CBOT_Bond` honors along with US-Treasury-specific market closures
that the FX calendar does not.

**6E — Euro FX.** Largest of the FX contracts by notional ($125,000
EUR per contract). Active US session begins at 08:00 ET (the
London/New York overlap), not the bond-pit 08:20. The intraday
initial margin and tick value are large enough that 6E is the FX
contract where slippage assumptions matter most.

**6A — Australian Dollar.** Commodity currency. Correlated with iron
ore prices and broader risk sentiment more than with AUD-specific
fundamentals. Notional of 100,000 AUD per contract; tick value $10.

**6C — Canadian Dollar.** Commodity currency. Closely tracks WTI
crude and broader risk-on/off; less sensitive to Canadian-specific
data than many traders assume.

**6N — New Zealand Dollar.** Less liquid than 6A and 6C. Pairs
naturally with 6A and 6C for commodity-FX spread trades when the
platform supports pairs strategies (Chapter 39).

### 5.2.3 Why GC is not registered

Standard CME gold (GC, 100 troy oz) is deliberately excluded from the
registry. The reason is capital, not technical: recent CME margin
increases pushed standard GC initial margin to a level that
substantially constrains a typical retail account. The realistic
vehicle for an account of this size is **micro gold (MGC, 10 troy
oz)** at one-tenth the notional. Both contracts share an identical
spec shape and slot directly into the registry as `GC` or `MGC`. The
full procedure for adding gold from cold is the worked example in
[Chapter 4 §4.11](04-data-pipeline.md#411-worked-example--adding-gold-gc-from-cold).

---

## 5.3 The TradeStation symbol mapping

The CME publishes one set of root symbols. TradeStation's API exposes
a different set. The mapping is irregular enough that hard-coding
either form would produce subtle download bugs, and is centralised in
the registry.

### 5.3.1 The mapping

| CME root | TS root | TS continuous | Why the difference |
|----------|---------|---------------|--------------------|
| ZN | TY | `@TY` | TY is TradeStation's historical name for 10-Year T-Note |
| 6E | EC | `@EC` | TradeStation predates the CME's "6E" rebranding |
| 6A | AD | `@AD` | Same — TS uses the original AUD/USD root |
| 6C | CD | `@CD` | Same — TS uses the original CAD/USD root |
| 6N | NE1 | `@NE1` | `NE` collides with a US equity symbol; TS appends `1` to disambiguate |

Individual contracts follow `{ts_root}{month_code}{year_code}`:
`TYM26` is June 2026 ZN, `ECH24` is March 2024 6E, `NE1Z25` is
December 2025 6N. Quarterly month codes are H (Mar), M (Jun), U
(Sep), Z (Dec).

### 5.3.2 Where the mapping lives in code

The mapping is the `tradestation_symbol` field on the `Instrument`
record. Every code path that talks to TradeStation reads it from
there:

- [`src/trading_research/data/tradestation/`](../../src/trading_research/data/tradestation/)
  — the historical bar downloader; resolves contracts via the
  per-instrument TS root.
- [`src/trading_research/data/contracts.py`](../../src/trading_research/data/contracts.py)
  — quarterly contract enumeration; emits `TYH10`-style names by
  combining the TS root with month/year codes.
- The streaming-bar client (when wired up) — same lookup.

Strategy code never sees a TS symbol. Strategy code refers to
instruments by their CME root (`ZN`, `6E`, ...) and the registry
performs the translation when it matters.

### 5.3.3 Verifying a new mapping before commit

Before committing a new instrument's `tradestation_symbol`, verify
that TradeStation accepts it. The data downloader exposes a symbol
probe that issues a small bar request and reports the response:

```
uv run python -m trading_research.data.tradestation.probe --symbol @TY --bars 5
```

A 200 response with five bars is a verified mapping. A 404 means the
symbol does not exist on TradeStation; do not commit the mapping.
The `6N → NE1` mapping was discovered exactly this way: `@NE`
returned a stock and `@NE1` returned the futures contract.

> *Why a one-shot probe rather than CI automation:* the probe hits
> TradeStation's live API and consumes a request quota slot. A human
> one-shot before commit is cheaper than running the probe on every
> CI build, and the mapping changes rarely enough that automation
> would be running for nothing 99% of the time.

---

## 5.4 Calendar awareness

Every instrument declares a [`pandas-market-calendars`](https://pandas-market-calendars.readthedocs.io/)
calendar. The calendar is consumed by the validator
([`src/trading_research/data/validate.py`](../../src/trading_research/data/validate.py))
to determine which timestamps should exist and which gaps are
expected.

| Calendar | Used by | Open (ET) | Close (ET) | Daily halt | Honors |
|----------|---------|-----------|------------|------------|--------|
| `CBOT_Bond` | ZN | 18:00 (prior day) | 17:00 | 17:00 – 18:00 | US bank holidays + Treasury-auction early closes |
| `CMEGlobex_FX` | 6E, 6A, 6C, 6N | 18:00 (prior day) | 17:00 | 17:00 – 18:00 | US bank holidays |
| `CMEGlobex_Metals` | future GC/MGC | 18:00 (prior day) | 17:00 | 17:00 – 18:00 | US bank holidays + COMEX-specific closes |

The two currently-used calendars have identical session windows
(23:00 UTC open, 22:00 UTC close, 1-hour break) but differ on holiday
handling — `CBOT_Bond` honors US-Treasury-specific market closures
(early closes around bond auctions and certain federal holidays) that
`CMEGlobex_FX` does not.

### 5.4.1 What the calendar validates

For a given (symbol, timeframe) the validator constructs the expected
list of bar timestamps from the calendar and compares it to the
parquet's actual timestamps. The four checks:

1. **Missing bars** — the calendar says a bar should exist; the
   parquet has none. Reported as informational for back-adjusted
   continuous contracts (roll seams produce expected gaps); reported
   as an error for unadjusted single-contract data.
2. **Unexpected bars** — the parquet has a bar at a time the
   calendar considers closed (a holiday, the maintenance halt).
   Always an error.
3. **Duplicate timestamps** — the parquet has multiple bars at the
   same time. Always an error; the resampler must produce one row
   per bucket.
4. **Trade-date misalignment** — a bar's `trade_date` field does
   not match the calendar's session assignment for that timestamp.
   Always an error.

### 5.4.2 What the calendar does not validate

- **Volume sanity** — the calendar knows when bars exist but not
  whether their volumes are plausible. Volume diagnostics are in the
  data-quality report (Chapter 6.3), not the calendar check.
- **Buy/sell-volume coverage** — calendar-blind. TradeStation's
  order-flow attribution is partial for older contracts; the
  validator warns rather than fails.
- **Roll continuity** — the calendar treats the back-adjusted
  continuous-contract series as a single instrument; whether the
  roll was stitched correctly is the back-adjuster's responsibility.

> *Why two separate concerns:* calendars handle "should this bar
> exist," validators handle "is this bar plausible." Conflating them
> would produce error messages where the operator can't tell whether
> the calendar is wrong or the data is wrong. The split is
> deliberate.

---

## 5.5 Adding a new instrument

The procedure is five steps. Most of the time is data acquisition;
the registry edit itself is minutes. The complete worked example
(adding GC) is [Chapter 4 §4.11](04-data-pipeline.md#411-worked-example--adding-gold-gc-from-cold).

1. **Verify the TradeStation root** with the probe (§5.3.3). Do not
   proceed if the probe fails.
2. **Add the entry to [`configs/instruments_core.yaml`](../../configs/instruments_core.yaml).**
   Cite the CME contract specification page for tick size, tick
   value, contract multiplier, and session hours. Cite the broker's
   published rate sheet for `commission_per_side_usd`. Use quoted-
   string literals for every numeric field — these are deserialised
   to `Decimal` and the typed loader rejects bare floats.
3. **Verify the registry parses the new entry:**
   ```
   uv run python -c "from trading_research.core.instruments import InstrumentRegistry; print(InstrumentRegistry().get('<SYM>'))"
   ```
   A printed `Instrument` record means the YAML is valid. A
   `ValidationError` names the offending field.
4. **Download the RAW contracts:**
   ```
   uv run python -m trading_research.data.tradestation \
       --symbol <SYM> --start <YYYY-MM-DD> --end <YYYY-MM-DD>
   ```
   Expected duration: 30–90 minutes for 16 years of quarterly
   contracts, depending on TradeStation rate limits. The downloader
   is resumable.
5. **Build CLEAN and FEATURES:**
   ```
   uv run trading-research pipeline --symbol <SYM> --set base-v1
   ```
   This invokes `rebuild clean`, validation, and `rebuild features`
   in order. See Chapter 4 §4.7 for per-stage commands if you need
   to debug a single stage.

### 5.5.1 What can fail and where

| Stage | Failure mode | Where to look |
|-------|--------------|---------------|
| Probe | 404 or wrong asset class | The TS root may differ from CME's; common alternatives include `NE` → `NE1` (FX) or appending a digit |
| YAML load | Pydantic `ValidationError` | The error names the field; numeric fields must be quoted strings (they're `Decimal`); `is_micro` is `bool` |
| Download | TradeStation rate limit | The downloader is resumable; rerun and it picks up from the last successful contract |
| `rebuild clean` | Calendar mismatch | The `calendar_name` must exist in `pandas-market-calendars`; see §5.4 for the supported list |
| Validation | Inverted high/low or duplicate timestamps | Bug in vendor data; see Chapter 6.3 — investigate before forcing through |
| `rebuild features` | Missing CLEAN files | The pipeline aborted before reaching features; resolve the validation failure first |

---

## 5.6 The contract-economics pitfall

This section is a short reference for the kind of arithmetic mistake
that the registry is designed to prevent. The intent is to make
explicit what is otherwise easy to forget.

### 5.6.1 Tick math

A position of *N* contracts moving *M* ticks in your favour is worth
**N × M × tick_value_usd**. For ZN at 1 contract and 8 ticks favourable,
that is 1 × 8 × $15.625 = **$125.00**. Notice that tick_value already
encodes the contract multiplier — you do not multiply by tick_size or
contract_multiplier again.

The bug pattern: a developer writes `pnl = ticks * 0.015625 *
contract_multiplier` (i.e., tick_size × multiplier), gets $15.625 by
luck on ZN, and then breaks silently when applied to 6A where the
correct formula gives a different number. The registry's
`tick_value_usd` field is the pre-computed correct value; use it
directly.

### 5.6.2 Slippage in ticks vs dollars

The platform's backtest cost model expresses slippage in **ticks per
side**, deliberately. One tick of ZN slippage is $15.625; one tick of
6A slippage is $10.00. Expressing slippage in dollars would force the
strategy author to look up tick values; expressing it in ticks lets a
strategy say "I expect 1 tick of slippage per side" and have the
correct dollar amount applied automatically by the registry.

### 5.6.3 Commission per side vs round-trip

`commission_per_side_usd` is one side. A round-trip costs *2 ×
commission_per_side_usd*. Strategy code that compares P&L against
"commission" should be explicit about which it means; the trade log
records both `entry_commission` and `exit_commission` separately for
this reason (Chapter 15).

---

## 5.7 Related references

### Code modules

- [`src/trading_research/core/instruments.py`](../../src/trading_research/core/instruments.py)
  — the typed `Instrument` model and `InstrumentRegistry`. Single
  source of truth for the registry.
- [`src/trading_research/data/contracts.py`](../../src/trading_research/data/contracts.py)
  — quarterly contract enumeration for the downloader.
- [`src/trading_research/data/validate.py`](../../src/trading_research/data/validate.py)
  — calendar-aware quality validation.
- [`src/trading_research/data/tradestation/`](../../src/trading_research/data/tradestation/)
  — the historical bar downloader; consumes `tradestation_symbol`.

### Configuration

- [`configs/instruments_core.yaml`](../../configs/instruments_core.yaml)
  — the registry file. Edit to add or modify an instrument.

### Other manual chapters

- **Chapter 4 §4.5** — The CME trade-date convention; consumes
  per-instrument session hours from this registry.
- **Chapter 4 §4.11** — Adding gold from cold; full worked example
  including the contract-spec block.
- **Chapter 6** — Bar Schema; the calendar validation gate uses the
  registry's `calendar_name`.
- **Chapter 14** — Backtest Engine; consumes `commission_per_side_usd`
  and the RTH window for EOD-flat behaviour.
- **Chapter 36** — Position Sizing; consumes `tick_value_usd` and
  `contract_multiplier` for every sizing calculation.
- **Chapter 50.1** — Configuration Reference for
  `configs/instruments_core.yaml`.

---

*End of Chapter 5. Next: Chapter 6 — Bar Schema & Calendar Validation.*
