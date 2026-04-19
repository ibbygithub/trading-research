# Current State
**Last updated:** Session 19 (2026-04-19)
**Updated by:** Claude Code (Sonnet)

---

## Active Branch

`develop` — all sessions 15–19 merged here.
Last commit: `33141e1 test(session-18): indicator census, fix 13 test failures, add P/R/F1 to meta-labeling`
Session 19 changes staged but not yet committed (see below).

---

## Canonical Session Count

| Sessions | Status |
|---|---|
| 02–05 | Foundation: data pipeline, RAW/CLEAN/FEATURES for ZN (154+ tests) |
| 06 | CLI automation: verify, rebuild, features, inventory |
| 07 | Visual cockpit: Dash 4-pane MTF replay app |
| 08–09 | Backtest engine + portfolio risk |
| 10–13 | Reporting suite: v1–v4, 24-section HTML report |
| 14–15 | Repo census, pipeline audit, governance bootstrap |
| 16 | Antigravity code review — "Cohesive extension" verdict |
| 17 | Statistical rigor audit — 3 load-bearing bugs fixed (kurtosis, purge, FOMC calendar) |
| 18 | Indicator census, DST tests, P/R/F1, fixed 13 failing tests |
| **19** | **Event-day blackout filter built; first backtest run — strategy v1 FAILED (see diagnosis)** |

---

## What Is Currently Working

- `uv run trading-research verify` — validates CLEAN/FEATURES parquet inventory
- `uv run trading-research rebuild-clean ZN` — rebuilds 1m/5m/15m/60m/240m/1D
- `uv run trading-research rebuild-features ZN` — recomputes all indicators
- `uv run trading-research backtest --strategy <yaml>` — runs ZN MACD pullback strategy
- `uv run trading-research walkforward --strategy <yaml>` — purged walk-forward with real gap/embargo
- `uv run trading-research report <strategy>` — 24-section HTML report
- `uv run trading-research replay --symbol ZN` — opens 4-pane Dash cockpit
- `uv run pytest` → **374 passed, 1 skipped, 0 failed**

---

## Data State

| Dataset | Status |
|---|---|
| ZN 1m RAW (2010-2026) | Present: `data/raw/ZN_1m_2010-01-01_2026-04-11.parquet` |
| ZN CLEAN (1m, 5m, 15m, 60m, 240m, 1D) | Present: all manifests committed |
| ZN FEATURES (5m, 15m) | Present: manifests committed |
| 6A/6C/6N RAW samples (Jan 2024) | Present: sample manifests only; full pull blocked on OI-010/011/012 |
| FOMC calendar | Present: `configs/calendars/fomc_dates.yaml` (2010–2025, complete) |
| CPI calendar | Present: `configs/calendars/cpi_dates.yaml` (2010–2025) — Session 19 |
| NFP calendar | Present: `configs/calendars/nfp_dates.yaml` (2010–2025) — Session 19 |

---

## First Backtest Results (Session 19)

**zn-macd-pullback-v1 — RUN DATE 2026-04-19**

The strategy was run on ZN 5m features (2010–2026) with FOMC/CPI/NFP blackout filter active.

**Result: STRATEGY DOES NOT WORK**

| Metric | Value |
|---|---|
| Total trades | 10,631 |
| Win rate | 3.9% (RTH-only: 11.2%) |
| Calmar | -0.04 |
| Sharpe | -21.32 |
| Expectancy/trade | -$64.38 |
| Trades/week | 12.64 |

Walk-forward (10 folds, 2010–2024): consistent Sharpe -20 to -23, win rate 1–6.3%, no fold showed any edge.

**Diagnosis (full details in Session 19 work log):**
1. 75.5% of entries are overnight — no RTH filter exists in the strategy
2. RTH win rate (11.2%) far below the 62.6% breakeven needed given the win/loss ratio
3. The zero-cross exit is a MACD event, not a price event — price can be below entry when histogram recovers
4. The failure is regime-independent (all 10 walk-forward folds fail equally)

---

## Known Issues

See `docs/handoff/open-issues.md` for the full list.

Critical blocking next work:
- OI-013: SHAP JIT crash on Windows — test skipped, not blocking strategy work
- **OI-014: zn-macd-pullback-v1 strategy redesign required** — v1 has no RTH filter and no price-based exit; the MACD zero-cross exit produces systematic directional mismatch

---

## Environment

- Python 3.12, managed by `uv`
- `uv sync` restores the environment from `uv.lock`
- `scipy` added properly (in pyproject.toml since session 17)
- Test suite: 374 passed, 1 skipped (test_shap — OI-013), 0 failed
