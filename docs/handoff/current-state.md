# Current State
**Last updated:** Session 14 (2026-04-17)  
**Updated by:** Claude Code (Sonnet)

---

## Active Session

**Session 14 — Repo Census, Pipeline Audit, Governance Bootstrap**  
Branch: `session/14-repo-census`  
Status: PR open, awaiting Ibby review and merge to `develop`

---

## Canonical Session Count

| Sessions | Status |
|---|---|
| 02–05 | Foundation: data pipeline, RAW/CLEAN/FEATURES for ZN (154+ tests) |
| 06 | CLI automation: verify, rebuild, features, inventory |
| 07 | Visual cockpit: Dash 4-pane MTF replay app |
| 08–09 | Backtest engine + portfolio risk |
| 10–13 | Reporting suite: v1 Trader's Desk, v2 Risk Officer, v3 Regime & ML, v4 Portfolio |
| **14** | **Repo census, pipeline audit, governance bootstrap — IN PROGRESS** |

---

## Next Approved Session

**Session 15 — Indicator Census**  
Plan: to be written (draft from session-14 planning: indicator file enumeration, look-ahead audit, HTF aggregation validation, unadjusted ZN roll consumption audit)

---

## What Is Currently Working

- `uv run trading-research verify` — validates CLEAN/FEATURES parquet inventory
- `uv run trading-research rebuild-clean ZN` — rebuilds 1m/5m/15m/60m/240m/1D from contract cache
- `uv run trading-research rebuild-features ZN` — recomputes all indicators
- `uv run trading-research backtest` — runs ZN MACD pullback strategy
- `uv run trading-research walkforward` — purged k-fold walk-forward validation
- `uv run trading-research report <strategy>` — 24-section HTML report (v2)
- `uv run trading-research replay --symbol ZN` — opens 4-pane Dash cockpit

---

## Data State

| Dataset | Status |
|---|---|
| ZN 1m RAW (2010-2026) | Present: `data/raw/ZN_1m_2010-01-01_2026-04-11.parquet` |
| ZN CLEAN (1m, 5m, 15m, 60m, 240m, 1D) | Present: all manifests committed |
| ZN FEATURES (5m, 15m) | Present: manifests committed |
| 6A/6C/6N RAW samples (Jan 2024) | Present: sample manifests only; full pull not done |
| Per-contract cache (TY series) | Present in `data/raw/contracts/` (not tracked) |

---

## Known Issues

See `docs/handoff/open-issues.md` for the full list.

Critical: none blocking session 15.

---

## Environment

- Python 3.12, managed by `uv`
- `uv sync` restores the environment from `uv.lock`
- `scipy` added to venv via pip during session 11 (uv lock conflict); needs `uv add scipy` from a clean terminal — tracked in open issues
- All 384+ tests passing as of session 11

---

## Repository

- GitHub: `https://github.com/ibbygithub/trading-research`
- Default branch on remote: not yet set (first push happens at end of session 14)
- Local: `main` is the initial commit root; `develop` and `session/14-repo-census` exist
