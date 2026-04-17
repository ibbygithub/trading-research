# Session 14 — Pipeline Robustness Audit
**Date:** 2026-04-17  
**Branch:** session/14-repo-census  
**Auditor:** Claude Code (Sonnet) — read-only; no code changes made

---

## Aggregate Verdict: **State B**

The pipeline is architecturally generalized — all key data paths read instrument specs (tick size, session hours, calendar name, TS symbol) from `configs/instruments.yaml` via `InstrumentRegistry`. No strategy code hard-codes instrument values.

Three specific issues would produce **incorrect behavior (not crashes)** when adding 6A:
1. RTH session window is hardcoded for ZN in `validate.py`
2. Output parquet filenames are hardcoded `"ZN_..."` in `continuous.py`
3. Function `last_trading_day_zn()` is ZN-named but its logic is reusable

These are targeted fixes, not a pipeline rewrite. **Estimated remediation: 2–4 hour fix session** before running a 6A download.

---

## Per-Step Classification

### Step 1: Download
**State A — fully generalized**

**Evidence:** `src/trading_research/data/tradestation/download.py`

```python
def _resolve_symbol(root_symbol: str) -> tuple[str, InstrumentSpec]:
    spec = default_registry().get(root_symbol)
    return spec.continuous_symbol, spec
```

`download_historical_bars()` accepts `symbol: str` and immediately resolves it against the instrument registry. Output filename: `f"{symbol}_1m_{start_date}_{end_date}.parquet"` — parameterized. Session template: `spec.data.tradestation_session_template` — read from registry.

Caveat: `continuous_method` defaults to `"tradestation_continuous"` (TS's @SYMBOL); the multi-contract back-adjusted path is a separate module (`continuous.py`). For FX instruments, `tradestation_continuous` is appropriate — FX contracts do not have the liquidity-migration problem that motivated the ZN-specific multi-contract approach.

---

### Step 2: Calendar Validation
**State B — half-generalized**

**Evidence:** `src/trading_research/data/validate.py`

The `_get_calendar_name(symbol)` function reads the calendar from the registry:
```python
spec = reg.get(symbol)
if spec.data.calendar:
    return spec.data.calendar
```
`instruments.yaml` has `calendar: CMEGlobex_FX` for 6A/6C/6N and `calendar: CBOT_Bond` for ZN. The Juneteenth patch covers both: `_JUNETEENTH_CALENDARS = {"CBOT_Bond", "CMEGlobex_FX", "CME"}`.

**Issue (B-class):** RTH gap classification uses ZN-specific hardcoded constants at module level:
```python
_RTH_OPEN_ET = pd.Timedelta(hours=8, minutes=20)   # ZN RTH: 08:20 ET
_RTH_CLOSE_ET = pd.Timedelta(hours=15, minutes=0)  # ZN RTH: 15:00 ET
```
FX instruments (6A/6C/6N) have RTH 08:00–17:00 ET per `instruments.yaml`. Gaps between 15:00 and 17:00 ET in FX data would be incorrectly classified as overnight gaps (not RTH), suppressing structural failure flags. This will not crash; it will silently under-report RTH anomalies in FX data.

**Fix:** Pass the instrument spec's RTH window into `validate_bar_dataset()` and use it for RTH classification. Alternatively, look up session hours from the registry inside the validator using the `symbol` argument (already passed in).

---

### Step 3: Gap Detection
**State B — same issue as Step 2**

**Evidence:** `src/trading_research/data/validate.py`, `_consecutive_runs()` + gap loop

The gap detection logic itself is fully generalized — it works on any `pd.DatetimeIndex`. The B-state arises from the RTH window used to classify gaps, as described in Step 2. The `_LARGE_GAP_BARS_RTH` vs `_LARGE_GAP_BARS_OVERNIGHT` threshold selection is correct in structure; only the window boundaries are wrong for non-ZN instruments.

---

### Step 4: Roll Handling
**State B — ZN-specific output paths; reusable logic**

**Evidence:** `src/trading_research/data/continuous.py`

**Issue 1 — hardcoded output filenames:**
```python
adj_path = output_dir / f"ZN_1m_backadjusted_{date_tag}.parquet"
unadj_path = output_dir / f"ZN_1m_unadjusted_{date_tag}.parquet"
roll_log_path = output_dir / f"ZN_roll_log_{date_tag}.json"
```
The string `"ZN"` is hardcoded. A call with `symbol="6A"` would write files named `ZN_1m_backadjusted_...`. This is a State C bug within an otherwise B-state module.

**Issue 2 — function name:**
`last_trading_day_zn()` is ZN-named, but its logic (`7 business days before end of delivery month`) is the CME rule for all quarterly futures on CBOT/CME. The function body has no ZN-specific code. It should be renamed `last_trading_day_quarterly_futures()` or similar, with ZN-specific roll convention documented as a parameter.

**What is generalized:** `contract_sequence()` derives the TradeStation root from `spec.continuous_symbol.lstrip("@")` — for 6A this gives `"AD"`, producing `ADH24`, `ADM24`, etc. The quarterly month codes (H/M/U/Z) are shared across all CME quarterly contracts. The additive back-adjustment logic is instrument-agnostic. The per-contract download and cache path are symbol-parameterized.

**Fix for 6A:** Replace the 3 hardcoded `"ZN"` strings in the output path assignments with the `symbol` variable. Rename `last_trading_day_zn()`. Total code change: ~5 lines.

---

### Step 5: Session Alignment
**State B — tied to calendar validation RTH issue**

**Evidence:** `src/trading_research/data/validate.py`, session gap analysis loop

Session alignment is verified during gap detection: complete sessions are checked against the exchange calendar schedule (`schedule.index`). The calendar is read from the registry (State A). The RTH window used within session-gap classification carries the B-state issue from Steps 2–3. No separate session-alignment module exists; it is part of the validation step.

---

### Step 6: Timezone Normalization
**State A — fully generalized**

**Evidence:** `src/trading_research/data/tradestation/normalize.py`

```python
_NY_TZ = "America/New_York"
# ...
df["timestamp_ny"] = df["timestamp_utc"].dt.tz_convert(_NY_TZ)
```

All timestamps are stored as UTC (authoritative) with a derived NY column. America/New_York is correct for all CME/CBOT futures (ZN, FX). The schema stores `timestamp_ny` as `pa.timestamp("ns", tz="America/New_York")` — enforced at write time via `BAR_SCHEMA`. No instrument-specific path exists.

---

### Step 7: Schema Enforcement
**State A — fully generalized**

**Evidence:** `src/trading_research/data/schema.py`

`BAR_SCHEMA` is a fixed pyarrow schema with 12 columns (timestamp_utc, timestamp_ny, OHLCV, buy_volume, sell_volume, tick counts). Applied via `pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)` at every write point. The schema contains no instrument-specific columns. `TRADE_SCHEMA` is similarly instrument-agnostic.

The pydantic `Bar` model mirrors the schema for row-level validation. Both are tested in `tests/test_schema.py`.

---

### Step 8: Quality Report Generation
**State B — same RTH classification issue; report structure is generalized**

**Evidence:** `src/trading_research/data/validate.py`, `validate_bar_dataset()`

The quality report JSON structure is fully parameterized: `symbol`, `calendar`, `date_range` are all injected from the caller. The report format would produce correct output for 6A in all fields except RTH gap classification (same B-state issue as Steps 2–3). A 6A quality report would pass incorrectly when 15:00–17:00 ET structural RTH gaps exist, because the validator treats those hours as overnight (non-RTH).

---

## ZN-Specific Code That Would Break on 6A

| File | Line/Pattern | Severity | Fix |
|---|---|---|---|
| `data/continuous.py` | `f"ZN_1m_backadjusted_{date_tag}.parquet"` | **Bug** — wrong filename | Replace `"ZN"` with `symbol` variable |
| `data/continuous.py` | `f"ZN_1m_unadjusted_{date_tag}.parquet"` | **Bug** — wrong filename | Replace `"ZN"` with `symbol` variable |
| `data/continuous.py` | `f"ZN_roll_log_{date_tag}.json"` | **Bug** — wrong filename | Replace `"ZN"` with `symbol` variable |
| `data/continuous.py` | `def last_trading_day_zn(...)` | Misleading name (logic is correct) | Rename function |
| `data/validate.py` | `_RTH_OPEN_ET = pd.Timedelta(hours=8, minutes=20)` | **Silent misclassification** for 6A RTH | Read from instrument registry |
| `data/validate.py` | `_RTH_CLOSE_ET = pd.Timedelta(hours=15, minutes=0)` | **Silent misclassification** for 6A RTH | Read from instrument registry |

**No ZN-specific branches exist in:** `normalize.py`, `schema.py`, `instruments.py`, `manifest.py`, `resample.py`, `indicators/features.py`, `pipeline/rebuild.py`, `pipeline/verify.py`.

---

## Estimated Cost of Adding 6A

| Work item | Effort |
|---|---|
| Fix 3 hardcoded "ZN" strings in `continuous.py` | 15 min |
| Rename `last_trading_day_zn()` + update callers | 30 min |
| Fix RTH window in `validate.py` (read from registry) | 1 hour (includes tests) |
| Download 6A historical data (API call) | 30 min operational |
| Run validate + rebuild CLEAN for 6A | 1 hour operational |
| Update tests for generalized functions | 1 hour |
| **Total** | **~4 hours** |

This is a **fix-and-run session**, not an architectural rework. The registry-first design absorbed most of the generalization work during Sessions 02–05.

---

## Three Open Risks from Antigravity Handoff

These are documented here as scheduled for Session 15 (Indicator Census), not this session:

1. **HTF aggregation validation** — higher-timeframe resample correctness has not been audited for bar-boundary alignment or OHLC ordering under edge cases (e.g., a 15m bar where constituent 1m bars span a session boundary).
2. **Indicator look-ahead strictness under next-bar-open fill** — indicators are computed at bar T using data through bar T's close. Under next-bar-open fill semantics, the signal fires at bar T+1 open, which is consistent. However, any indicator that uses bar T+1's open in its own computation (e.g., an open-referenced VWAP) would introduce forward leakage. None found on a surface read; audit required.
3. **Unadjusted ZN roll consumption** — strategy code and indicators should consume the back-adjusted series, not the unadjusted. A strategy that accidentally loads the unadjusted parquet would see price gaps at roll dates. Currently: `rebuild_features()` globs for `{symbol}_1m_backadjusted_*.parquet` explicitly — correct. No unadjusted consumption found in strategy or indicator code on surface read; full audit is Session 15 scope.
