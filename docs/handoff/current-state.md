# Current State
**Last updated:** Session 18 (2026-04-18)
**Updated by:** Claude Code (Sonnet)

---

## Active Branch

`develop` — all sessions 15–18 merged here.
Last commit: `33141e1 test(session-18): indicator census, fix 13 test failures, add P/R/F1 to meta-labeling`

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
| **18** | **Indicator census, DST tests, P/R/F1, fixed 13 failing tests** |

---

## What Is Currently Working

- `uv run trading-research verify` — validates CLEAN/FEATURES parquet inventory
- `uv run trading-research rebuild-clean ZN` — rebuilds 1m/5m/15m/60m/240m/1D
- `uv run trading-research rebuild-features ZN` — recomputes all indicators
- `uv run trading-research backtest` — runs ZN MACD pullback strategy
- `uv run trading-research walkforward` — purged walk-forward with real gap/embargo
- `uv run trading-research report <strategy>` — 24-section HTML report
- `uv run trading-research replay --symbol ZN` — opens 4-pane Dash cockpit
- `uv run pytest` → **353 passed, 1 skipped, 0 failed**

---

## Data State

| Dataset | Status |
|---|---|
| ZN 1m RAW (2010-2026) | Present: `data/raw/ZN_1m_2010-01-01_2026-04-11.parquet` |
| ZN CLEAN (1m, 5m, 15m, 60m, 240m, 1D) | Present: all manifests committed |
| ZN FEATURES (5m, 15m) | Present: manifests committed |
| 6A/6C/6N RAW samples (Jan 2024) | Present: sample manifests only; full pull blocked on OI-010/011/012 |
| FOMC calendar | Present: `configs/calendars/fomc_dates.yaml` (2010–2025, complete) |

---

## Known Issues

See `docs/handoff/open-issues.md` for the full list.

Critical blocking next work:
- OI-013: SHAP JIT crash on Windows — test skipped, not blocking strategy work

---

## Environment

- Python 3.12, managed by `uv`
- `uv sync` restores the environment from `uv.lock`
- `scipy` added properly (in pyproject.toml since session 17)
- Test suite: 353 passed, 1 skipped (test_shap — OI-013), 0 failed

---

## Repository

- GitHub: `https://github.com/ibbygithub/trading-research`
- Working branch: `develop`
- `main` receives only human-approved merges after passing test suite
