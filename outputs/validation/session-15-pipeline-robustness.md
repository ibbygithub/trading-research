# Pipeline Robustness Audit — Session 15
**Date:** 2026-04-17  
**Tree:** `main@de03c04` (canonical Line A)  
**Scope:** RAW→CLEAN path only. Does the pipeline generalize to 6A (Australian Dollar futures, TS symbol: AD)?

---

## State Classification Legend

- **State A** — General: works for any CME instrument with appropriate config in `configs/instruments.yaml`. No code changes required.
- **State B** — ZN-first but adaptable: code is functionally general but has ZN-specific assumptions that may produce incorrect results for other instruments without targeted fixes.
- **State C** — ZN-specific: cannot work for 6A without code changes. Blocks the 6A full pipeline.

---

## Per-Step Audit

### 1. Download
**State: A**  
**Code path:** `src/trading_research/data/tradestation/download.py:download_historical_bars()`  
**Evidence:** `download.py:136 _resolve_symbol(root_symbol)` → `default_registry().get(root_symbol)` → returns `spec.continuous_symbol` (e.g. `"@AD"` for 6A). Output filename: `f"{symbol}_1m_{start}.{end}.parquet"` — symbol is a parameter, not hardcoded. The instrument registry at `configs/instruments.yaml` already has 6A (symbol: `"6A"`, ts_symbol: `"AD"`) confirmed by Session 03 smoke pull.  
**6A verdict:** Works today. The direct download path (`continuous_method="tradestation_continuous"`) resolves to `@AD` and writes `6A_1m_{date}.parquet`. Session 03 confirmed this with a smoke pull of `6A_1m_2024-01-01_2024-01-31.parquet`.

---

### 2. Calendar Validation
**State: A**  
**Code path:** `src/trading_research/data/validate.py:validate_bars()`  
**Evidence:** `validate.py:115 _get_calendar_name(symbol)` → `default_registry().get(symbol).data.calendar`. Calendar is looked up from `instruments.yaml`, not hardcoded. 6A is already configured with `CMEGlobex_FX` calendar in the instrument registry (confirmed Session 03). The `_JUNETEENTH_CALENDARS` set includes `CMEGlobex_FX`.  
**6A verdict:** Works today. 6A already has a `CMEGlobex_FX` entry.

---

### 3. Gap Detection
**State: B**  
**Code path:** `src/trading_research/data/validate.py`, module-level constants `_RTH_OPEN_ET` and `_RTH_CLOSE_ET`  
**Evidence:**
```python
# validate.py:90–92
_RTH_OPEN_ET = pd.Timedelta(hours=8, minutes=20)   # 08:20 ET
_RTH_CLOSE_ET = pd.Timedelta(hours=15, minutes=0)  # 15:00 ET
```
These are module-level constants, not instrument-aware. For ZN (Treasury bonds), RTH is 08:20–15:00 ET — the floor-trading window. For CME FX futures (6A/6C/6N), the effective liquid hours are approximately the same (FX pit hours are 08:20–15:00 ET for CME Chicago), so the constants happen to be correct for 6A too.  
**However:** The `_CME_MAINTENANCE_REOPEN_CT` logic that excludes post-maintenance gaps is also instrument-agnostic and applies correctly to all CME Globex instruments (same 17:00–17:30 CT window).  
**Risk:** If a future instrument has a different RTH definition (e.g., equity futures with 09:30–16:00 ET), the gap classifier would produce wrong RTH/overnight labels. The constants should eventually become instrument-aware (looked up from `instruments.yaml`). Not a blocker for 6A.  
**6A verdict:** Functionally correct for 6A today. Structural technical debt — gap thresholds are global constants, not per-instrument.

---

### 4. Roll Handling
**State: C**  
**Code path:** `src/trading_research/data/continuous.py:build_back_adjusted_continuous()`  
**Evidence (specific violations):**

**Violation 1 — ZN roll convention hardcoded:**
```python
# continuous.py:103–113
def last_trading_day_zn(expiry_year: int, expiry_month: int) -> date:
    """ZN last trading day: 7 business days before last biz day of delivery month."""
    last_biz = _last_biz_day_of_month(expiry_year, expiry_month)
    return _subtract_biz_days(last_biz, 7)
```
ZN/TY rolls on the last business day minus 7 business days of the delivery month. CME FX futures (6A/6C/6N) roll on IMM dates — the third Wednesday of the quarterly month. Completely different convention.

**Violation 2 — ZN hardcoded output paths:**
```python
# continuous.py:542–544
adj_path = output_dir / f"ZN_1m_backadjusted_{date_tag}.parquet"
unadj_path = output_dir / f"ZN_1m_unadjusted_{date_tag}.parquet"
roll_log_path = output_dir / f"ZN_roll_log_{date_tag}.json"
```
The `symbol` parameter exists but is not used in the output paths. Calling `build_back_adjusted_continuous("6A", ...)` would write files named `ZN_1m_backadjusted_...` — wrong and confusing.

**Violation 3 — Quarterly TY contract naming assumed:**
The `contract_sequence()` function uses `ts_root` (e.g. `"TY"` for ZN) to construct quarterly contract symbols (`TYU23`, `TYZ23`, etc.). This works for Treasury futures. FX futures use different root symbols (`AD`, `CD`, `NE`) and CME FX uses IMM months (H, M, U, Z) on a different roll schedule.

**6A verdict:** Blocked. The `build_back_adjusted_continuous` function cannot be used for 6A without:
1. Implementing an `last_trading_day_fx()` function using IMM date convention.
2. Parameterizing the output paths to use `symbol` instead of hardcoded `"ZN"`.
3. Verifying the quarterly contract naming works with AD/CD/NE roots.

**Note on 6A data strategy:** For 6A, the direct TradeStation continuous contract download (`@AD`) via `download_historical_bars()` (State A) is the simpler path. The `build_back_adjusted_continuous` function exists specifically because TradeStation's `@TY` continuous contract had roll-timing problems (September 2023 diagnostic). Whether `@AD` has similar issues is unknown. Start with the direct download; add per-contract stitching only if a roll artifact is confirmed.

---

### 5. Session Alignment / Daily Bar
**State: B**  
**Code path:** `src/trading_research/data/resample.py:resample_daily()`  
**Evidence:**
```python
# resample.py:198–228 (simplified)
# A ZN "daily bar" is a session, not a calendar day.
# Session runs from 18:00 ET (prev calendar day) to 17:00 ET.
# Implementation: shift timestamp_ny by +6h so 18:00 ET → midnight.
df["trade_date"] = (df["timestamp_ny"] + pd.Timedelta(hours=6)).dt.date
```
This comment says "ZN" but the CME FX (6A/6C/6N) session hours are **identical** to ZN/TY: Sunday–Friday 17:00 CT (18:00 ET) open, 16:00 CT (17:00 ET) close, with the same 1-hour maintenance halt 16:00–17:00 CT. The +6h offset works for 6A too.  
The zero-volume bucket drop for maintenance-halt detection is also instrument-agnostic.  
**6A verdict:** Works today. Comments say "ZN" but the logic is correct for all CME Globex instruments with the same session hours.

---

### 6. Timezone Normalization
**State: A**  
**Code path:** `src/trading_research/data/schema.py:BAR_SCHEMA`, `data/tradestation/normalize.py`  
**Evidence:** The `BAR_SCHEMA` defines `timestamp_utc` (UTC tz-aware) and `timestamp_ny` (America/New_York tz-aware) as first-class columns. `normalize.py` converts TradeStation's response timestamps into these two columns for all instruments. No instrument-specific timezone handling.  
**6A verdict:** Works today.

---

### 7. Schema Enforcement
**State: A**  
**Code path:** `src/trading_research/data/schema.py:BAR_SCHEMA`, `data/tradestation/normalize.py:normalize_bars()`  
**Evidence:** `BAR_SCHEMA` (PyArrow schema) includes `timestamp_utc`, `timestamp_ny`, `open`, `high`, `low`, `close`, `volume`, `buy_volume`, `sell_volume` as the canonical columns. Schema is instrument-agnostic. `normalize.py` enforces it via `pa.Table.cast()`.  
**6A verdict:** Works today.

---

### 8. Quality Report Generation
**State: A**  
**Code path:** `src/trading_research/data/validate.py:validate_bars()` — writes `{parquet_path.stem}.quality.json`  
**Evidence:** Output path is `parquet_path.stem + ".quality.json"` — fully instrument-agnostic. Report structure is JSON with row counts, gap summaries, and pass/fail verdict.  
**6A verdict:** Works today.

---

## Per-Step State Summary

| Step | State | Code Path | 6A Blocker? |
|---|---|---|---|
| Download | A | `data/tradestation/download.py:download_historical_bars` | No |
| Calendar Validation | A | `data/validate.py:validate_bars` + `_get_calendar_name` | No |
| Gap Detection | B | `validate.py` module constants `_RTH_OPEN_ET/_CLOSE_ET` | No (correct values for 6A) |
| Roll Handling | C | `data/continuous.py:build_back_adjusted_continuous` | **Yes** |
| Session Alignment | B | `data/resample.py:resample_daily` | No (same CME hours) |
| Timezone Normalization | A | `data/schema.py`, `data/tradestation/normalize.py` | No |
| Schema Enforcement | A | `data/schema.py:BAR_SCHEMA` | No |
| Quality Report | A | `data/validate.py` → `.quality.json` | No |

---

## Aggregate Verdict: State B (with one C blocker)

**The pipeline as a whole is State B.** The direct download path (Sessions 03 method: `download_historical_bars` + `validate_bars`) is **State A** for 6A and would work today.

The single State C blocker is `continuous.py:build_back_adjusted_continuous` — the ZN-specific roll convention and hardcoded output paths. This function is not in the critical path for a 6A direct download. It only becomes relevant if we decide 6A needs per-contract back-adjusted stitching (which would require confirming that `@AD` has roll artifacts similar to `@TY`).

---

## Effort Estimate

| Task | Effort | Notes |
|---|---|---|
| 6A direct download + validate (Session 03 method) | Ready now | State A path, no code changes |
| 6A resample to higher TFs | 30 min | `resample_bars` is State A; just point at 6A parquet |
| 6A features (base-v1 featureset) | 1–2 hours | `build_features` is State A; needs 6A in feature-set config |
| 6A full continuous stitching | 1 session | State C; needs IMM roll function, output path fix |

**Recommendation:** Execute 6A data pull using the direct download path now. Defer per-contract stitching until there is evidence that `@AD` has roll artifacts.

---

## Named Edge Cases That Would Break on 6A

1. **`continuous.py:542–544`** — Hardcoded `"ZN"` output paths. Any call to `build_back_adjusted_continuous` for a non-ZN symbol would produce files with wrong names.

2. **`continuous.py:last_trading_day_zn()`** — ZN/TY roll convention (7 biz days). CME FX uses IMM dates (3rd Wednesday of March/June/September/December). Wrong roll dates would stitch contracts at the wrong point, corrupting the continuous series.

3. **`validate.py:_RTH_OPEN_ET = 08:20 ET`** — Correct for 6A today, but it's a global constant. If equity futures are ever added (09:30 ET RTH), this would misclassify gaps. Technical debt, not a current blocker.

4. **`resample_daily()` comment says "ZN"** — Not a code bug, but misleading. Any future engineer reading the comment might assume the +6h offset is ZN-specific and "fix" it for other instruments, breaking what already works.

---

## Reference to Evidence Files

Raw grep outputs that informed this audit are in `outputs/validation/session-15-evidence/`:
- `pipeline-zn-refs.txt` — all ZN/TY references in `src/trading_research/data/`
- `pipeline-session-refs.txt` — all session-hours references in `src/trading_research/data/`
- `dir-counts.txt` — directory and file inventory
- `src-tree.txt` — full Python file list under `src/`
- `pytest-baseline.txt` — full pytest output (57K lines, includes tracebacks)
