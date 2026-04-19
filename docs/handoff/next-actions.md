# Next Actions
**Last updated:** Session 18 (2026-04-18)

The rigor gate is closed. Sessions 15–18 resolved all load-bearing statistical
bugs and cleared the indicator look-ahead audit. The codebase is ready for the
first real strategy run on live ZN data.

---

## Immediate Next: Event-Day Blackout Filter + First Strategy Run

### Step 1 — Event-day blackout filter

**What:** Gate strategy entries on FOMC, CPI, and NFP release days.
The FOMC calendar is already fully populated in `configs/calendars/fomc_dates.yaml`.
CPI and NFP calendars need to be added alongside it.

**Where:** Strategy entry logic in `src/trading_research/strategies/zn_macd_pullback.py`
(or equivalent config gate). The blackout filter loads the calendar and skips any
`entry_bar` whose `trade_date` matches a release date.

**Why now:** Not doing this before a live-capital run violates the quant-mentor's
hard rule: "event-day microstructure is structurally different — wider spreads,
non-mean-reverting, fat-tail gap risk." Including those days inflates apparent edge.

**Scope:** ~2-3 hours. FOMC calendar wired; CPI/NFP need date files (public FRED data).

### Step 2 — First real backtest run

```
uv run trading-research backtest
uv run trading-research report zn-macd-pullback-v1
```

Open the HTML report. Check:
- Trade count (≥30 for any meaningful Sharpe estimate)
- Calmar ≥ 2.0 before looking at Sharpe
- DSR — trust this number, not raw Sharpe
- Max consecutive losses and longest drawdown in trading days
- Event-day trades: should be zero after blackout filter lands

### Step 3 — Walk-forward validation

```
uv run trading-research walkforward
```

Per-fold equity curves and out-of-sample DSR. If fold-by-fold Calmar
degrades sharply toward recent history, that is a regime signal, not noise.

---

## Backlog (Unblocked by Steps 1–3 Outcome)

In priority order:

1. **6A pipeline generalization** (OI-010, OI-011, OI-012) — ~4 hours.
   Fix hardcoded ZN paths in `continuous.py` and RTH window in `validate.py`.
   Then run 6A historical download.

2. **OI-013: SHAP JIT crash on Windows** — pin compatible numba + llvmlite.
   Run `uv run python -c "import shap"` to validate, then remove skip from
   `tests/test_shap.py`.

3. **OI-009: unadjusted ZN roll consumption audit** — verify all load paths
   in strategy and indicator code consume back-adjusted parquets. Add a test.

---

## Low-Priority Cleanup

- OI-003: `git rm --cached .claude/settings.local.json` then commit
- OI-004: `rm -rf "C:Trading-researchconfigsstrategies/"` and the other mangled dir
- OI-005: Move `prep_migration_samples.py` to `Legacy/` or delete
- OI-002: Retire `outputs/planning/planning-state.md` (stale since sessions 06–07)
