# Quick-Start Guide

> **Status:** Draft v0.1 — stub. The final version is a v1.0 deliverable
> verified end-to-end on a clean clone (see Chapter 54). This stub
> establishes the format and content target.

This is the one-page entry point. If you have not touched the platform
in a while or are sitting down to it for the first time, this page gets
you to a working backtest in under thirty minutes assuming the data is
already on disk.

If the data is *not* on disk (cold-start from clean clone), see
Chapter 54 instead.

---

## Five commands you will use most

| Goal | Command |
|------|---------|
| Confirm everything is fresh | `uv run trading-research verify` |
| See what's on disk | `uv run trading-research inventory` |
| Run a backtest | `uv run trading-research backtest --strategy configs/strategies/<name>.yaml` |
| Walk-forward (5 folds) | `uv run trading-research walkforward --strategy configs/strategies/<name>.yaml --n-folds 5` |
| Render the report | `uv run trading-research report <strategy_id>` |

The full CLI reference is Chapter 49. The configuration reference is
Chapter 50.

---

## The 30-minute first run

1. **Verify environment** — `uv sync && uv run pytest -x -q`. Both must
   succeed before doing anything else.
2. **Verify data** — `uv run trading-research verify`. Exit code 0 means
   you can proceed; exit code 1 means at least one file is stale, see
   §4.4.3 for what that means.
3. **List what's there** — `uv run trading-research inventory`. Confirm
   you have feature parquets for the instrument and timeframe you want
   to backtest.
4. **Pick or write a strategy YAML** — see existing examples in
   `configs/strategies/`. The grammar is in Chapter 10.
5. **Backtest** — `uv run trading-research backtest --strategy <path>`.
   Output goes to `runs/<strategy_id>/<timestamp>/`. The summary table
   prints to terminal with bootstrap CIs.
6. **Render the report** — `uv run trading-research report <strategy_id>`.
   Open `runs/<strategy_id>/<timestamp>/report.html` in any browser.

---

## When things go wrong

| Symptom | First place to look |
|---------|---------------------|
| `verify` returns 1 | The file list it printed; usually a feature-set tag was edited without a tag bump (Chapter 8.4) |
| Backtest can't find features | Is the feature parquet built for the strategy's timeframe? `inventory` will tell you |
| Strategy YAML errors | The error mentions the bad expression; see Chapter 11 for syntax rules |
| Reports look stale | `verify` again; the HTML is built from `summary.json` which must match the trade log |

The full troubleshooting reference is Chapter 55.

---

## What this guide does not cover

- Adding a new instrument from cold (see §4.11 — the GC worked example,
  or Chapter 56.1)
- Authoring a strategy from scratch (Part III, Chapters 9–13)
- Reading a Trader's Desk report deeply (Chapter 17)
- Validating a strategy for promotion to paper (Part IX, Chapters 45–48)
- Cleaning up disk space (Chapter 56.5)

If your task isn't on this page or in the references above, the Table of
Contents is the next stop.

---

*See also: `README.md` for the manual project, `TABLE-OF-CONTENTS.md`
for the chapter map, `04-data-pipeline.md` for the worked example
chapter at quality bar.*
