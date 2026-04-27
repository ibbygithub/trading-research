# Trading Research Platform — Complete Status
**Date:** 2026-04-19 (end of Session 19)
**Author:** Claude Code (Sonnet), reviewed by Ibby

This is the single document that answers "where are we?" for anyone picking up this
project. It supersedes the individual session handoff docs for the purpose of
an overall status picture.

---

## What the platform is supposed to be

A personal quant trading desk:
- Pull historical bars from TradeStation for CME futures instruments
- Validate, clean, and store as parquet (three-layer model: RAW → CLEAN → FEATURES)
- Design and backtest strategies with honest statistics (no same-bar fills, pessimistic TP/SL, real commissions)
- Forensically review trades in an interactive cockpit
- Walk-forward validate with proper purge/embargo gaps
- Eventually paper-trade and go live

The platform is instrument-agnostic by design. ZN (10-year Treasury futures) is the
first instrument. 6A (Aussie dollar futures) is the second. The platform is not
complete until it handles both without hardcoded workarounds.

---

## What is built and working

### Foundation — Data Pipeline (Sessions 02–05) ✓

- RAW layer: ZN 14-year history (2010–2026) ingested, stored as parquet with manifests
  per contract and as a bulk continuous file
- CLEAN layer: ZN back-adjusted and unadjusted at 1m, 5m, 15m, 60m, 240m, 1D
- FEATURES layer: ZN 5m and 15m with full indicator set (ATR, MACD, RSI, VWAP,
  Bollinger, Donchian, ADX, OFI, EMA/SMA, HTF daily bias)
- Back-adjustment via Panama method; roll log tracked and committed
- Calendar-based gap validation using `pandas-market-calendars` (CME awareness)
- Manifest system: every parquet has a sibling `.manifest.json` tracking provenance,
  row count, date range, build time, source code commit, and staleness

**Documentation:** [docs/pipeline.md](pipeline.md) — three-layer model, naming
conventions, manifest schema, cold-start checklist, worked examples.
⚠️ Needs updating to cover sessions 11–19 additions (statistical rigor, walk-forward,
event calendars). The core data architecture sections are accurate.

### CLI Automation (Session 06) ✓

```
uv run trading-research verify                       # manifest + staleness check
uv run trading-research rebuild-clean --symbol ZN    # RAW → CLEAN
uv run trading-research rebuild-features --symbol ZN # CLEAN → FEATURES
uv run trading-research backtest --strategy <yaml>   # full backtest run
uv run trading-research walkforward --strategy <yaml># purged walk-forward
uv run trading-research report <strategy>            # 24-section HTML report
uv run trading-research replay --symbol ZN           # 4-pane Dash cockpit
```

### Visual Forensics — Replay Cockpit (Session 07) ✓

4-pane Dash app: 5m / 15m / 60m / 1D with synced crosshairs, OFI subplot,
VWAP + Bollinger overlays. Trade markers from backtest trade log overlay all panes.

### Backtest Engine (Sessions 08–09) ✓

- Fill model: next-bar-open (default, configurable per strategy)
- TP/SL ambiguous bars: pessimistic (stop assumed to hit before target)
- EOD flat: closes all positions at 15:00 ET (20:00 UTC) when enabled
- Slippage and commission: pessimistic relative to TradeStation retail rates
- Trade log: captures trigger bar, entry bar, exit bar, MAE, MFE, all separable
- Portfolio manager: multi-strategy position tracking, combined margin

### Reporting Suite (Sessions 10–13) ✓

24-section HTML report including:
- Equity curve, drawdown curve, monthly returns heatmap
- Trade distribution, MAE/MFE scatter, holding period histogram
- Walk-forward per-fold breakdown
- Bootstrap confidence intervals on all key metrics
- Deflated Sharpe Ratio (DSR), Probabilistic Sharpe Ratio (PSR)
- Monte Carlo simulation, regime breakdown
- Trials registry for honest deflated Sharpe across strategy variants

### Statistical Rigor (Sessions 11–18) ✓

- Kurtosis convention fixed (Pearson, not Fisher) in PSR/DSR — was load-bearing bug
- Walk-forward purge/embargo wired correctly (was missing in early implementation)
- FOMC calendar: 2010–2025 complete including emergency inter-meeting actions
- Indicator look-ahead audit: all indicators clean under next-bar-open fill
- Meta-labeling: Precision/Recall/F1 metrics added
- DST handling verified

### Event-Day Blackout Filter (Session 19) ✓

- `configs/calendars/fomc_dates.yaml` — complete 2010–2025
- `configs/calendars/cpi_dates.yaml` — 2010–2025
- `configs/calendars/nfp_dates.yaml` — 2010–2025
- `src/trading_research/strategies/event_blackout.py` — testable module,
  `load_blackout_dates(["fomc","cpi","nfp"])` → `frozenset[date]`
- Wired into `generate_signals()` in `zn_macd_pullback.py`: entry signals
  suppressed on event days, exit signals preserved
- 19 tests covering the filter in isolation and integrated with the strategy

### Test Suite ✓

374 tests pass, 1 skipped (OI-013: SHAP/numba JIT crash on Windows, not a
code bug). 0 failures.

---

## What is NOT working or NOT validated

### OI-011: Hardcoded "ZN" in continuous.py output paths — BLOCKING 6A

**File:** `src/trading_research/data/continuous.py`
Three output path strings contain literal `"ZN"`. A call with `symbol="6A"`
silently writes ZN-named files. The data is correct; the filename is wrong.
The manifest picks up the wrong symbol name and verify will report inconsistencies.

**Fix:** Replace `"ZN"` with `symbol` in three path assignments.

### OI-010: RTH window hardcoded for ZN in validate.py — BLOCKING 6A

**File:** `src/trading_research/data/validate.py`
`_RTH_OPEN_ET = 08:20` and `_RTH_CLOSE_ET = 15:00` are ZN RTH hours.
6A (AUD futures) RTH is 08:00–17:00 ET. Running validate on 6A would
silently misclassify 2 hours of valid 6A trading as overnight gaps.

**Fix:** Read RTH window from `InstrumentRegistry` using the `symbol` argument
already passed to `validate_bar_dataset()`. The registry entry for 6A already
has the correct RTH definition in `configs/instruments.yaml`.

### OI-012: last_trading_day_zn() in continuous.py — MISLEADING, NOT BLOCKING

Function name implies ZN-specificity but the logic is the generic quarterly
CME rule (third Friday of expiry month). Works for 6A but creates confusion.

**Fix:** Rename to `last_trading_day_quarterly_cme()` and update callers.

### OI-013: SHAP/numba JIT crash on Windows — NOT BLOCKING STRATEGY WORK

`test_shap.py` is skipped. SHAP import causes a Windows access violation
in numba/llvmlite JIT compilation. Not related to any code in this project.
Fix: pin compatible numba + llvmlite versions.

### zn-macd-pullback-v1 — STRATEGY DOES NOT WORK (expected at this stage)

First backtest run (Session 19) produced: 3.9% win rate, Calmar -0.04,
Sharpe -21.3. Walk-forward: 10/10 folds fail, consistent across all
time periods 2010–2024.

**This is not a platform bug.** The plumbing is correct. The strategy
hypothesis is wrong. Two structural problems in the strategy design:

1. No RTH session filter — 75.5% of entries are overnight (globex session).
   The features parquet covers 24h; the strategy fires on every bar.
   These generate immediate EOD-flat losses (commission only).

2. MACD zero-cross exit is a momentum event, not a price event. Price can
   be below the long entry when the histogram crosses zero. The strategy
   enters on "uncertain momentum" (histogram fading toward zero) and exits
   when momentum finally confirms — but at whatever price that happens to be.
   RTH-only win rate: 11.2%. Breakeven requires 62.6%.

**The strategy needs a redesign, not parameter tuning.** See next-actions.

### Blackout filter edge case — MINOR, NOT BLOCKING

6 of 10,631 trades appeared on event-day mornings (midnight ET, before 6am).
Root cause: the filter checks the signal bar's ET date. For an overnight entry
where the signal fires at 11pm ET on the eve of an event, the signal date is
"day before" but the entry lands in the early morning of the event day.
Fix: check the entry bar date (T+1) instead of the signal bar date (T).
Low priority given strategy redesign is pending.

### docs/pipeline.md — ACCURATE BUT INCOMPLETE

The data architecture sections (three-layer model, manifest schema, naming,
cold-start checklist) are accurate and complete. The document does not yet
cover the statistical rigor layer (PSR/DSR, bootstrap CI, walk-forward engine,
trials registry, event-day blackout system) added in sessions 11–19.

---

## What should be built next

### Session 20 — 6A Pipeline Generalization + End-to-End Test

**Goal:** Prove the platform is instrument-agnostic. Fix the three ZN-specific
bugs in the data layer, then run 6A through the full pipeline (download → CLEAN
→ FEATURES) with zero intervention.

**Estimated time:** 4 hours.

**Scope:** Only `continuous.py` and `validate.py`. Do not touch strategy or
backtest code. Do not expand to other instruments until 6A is clean.

Steps:
1. Fix OI-011: Replace hardcoded `"ZN"` with `symbol` in continuous.py
2. Fix OI-010: Read RTH window from `InstrumentRegistry` in validate.py
3. Fix OI-012: Rename `last_trading_day_zn()` → `last_trading_day_quarterly_cme()`
4. Add/update tests for the fixed functions
5. Run `uv run trading-research rebuild-clean --symbol 6A`
6. Run `uv run trading-research rebuild-features --symbol 6A`
7. Run `uv run trading-research verify` — must pass clean for both ZN and 6A
8. Confirm test suite still passes

**Success criteria:**
- verify reports clean for ZN and 6A
- 6A CLEAN parquet named `6A_backadjusted_*`, not `ZN_*`
- 6A gap validation uses 08:00–17:00 ET RTH window
- Test suite still passes
- No hardcoded `"ZN"` remaining in continuous.py or validate.py

### Session 21 — docs/pipeline.md Refresh

Update the pipeline doc to reflect everything built in sessions 11–19:
- Statistical rigor layer: PSR/DSR, bootstrap CI, trials registry
- Walk-forward engine: purge/embargo, per-fold reporting
- Event-day blackout system: calendars, filter module
- Cold-start checklist: add the backtest and walkforward commands

### Session 22 — Strategy v2 Design + Implementation

**Before writing any code:** design conversation on the v2 hypothesis.

Ibby's current thinking:
- Remove EOD flat requirement (allow overnight holds when the trade warrants it)
- Use VWAP 2nd standard deviation as the entry trigger (price must reach a
  structural mean-reversion level, not just any MACD condition)
- Use MACD (or a different momentum indicator) as confirmation at that level, not as the entry signal itself

The data-scientist's prerequisite for any v2 implementation:
- RTH session filter must be in the strategy (no overnight signals unless explicitly designed for overnight)
- The exit must be price-based, not indicator-based
- State the hypothesis precisely before coding it:
  "When ZN reaches VWAP ± 2σ within RTH, and [momentum condition], enter with [stop] and [target]"

---

## The pipeline, one paragraph

The platform pulls historical 1-minute bars from TradeStation, validates them
against a CME trading calendar, stores them as immutable RAW parquets, resamples
to 5m/15m/60m/240m/1D CLEAN parquets (OHLCV only, no indicators), then computes
a versioned feature set (indicators + HTF projections) into FEATURES parquets.
A CLI runs the full chain. A backtest engine runs strategies against FEATURES
with next-bar-open fills, pessimistic stops, real commissions, and a purged
walk-forward validator that computes DSR and Calmar with bootstrap confidence
intervals. A Dash replay cockpit overlays trade markers on MTF charts for
forensic review. All of this is tested (374 tests) and works end-to-end for ZN.
It has never been run on a second instrument. That is Session 20.
