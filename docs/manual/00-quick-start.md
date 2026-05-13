# Quick-Start Guide

> **Status:** [EXISTS] — describes the platform's normal-operation
> workflow at v1.0. For a clean-clone cold-start (no data on disk,
> no environment built), see Chapter 54 instead.

This is the entry point for a returning session. Data is already on
disk; the environment is already built. You sit down, you want a
backtest result and a report, and you don't want to re-read 200 pages
of the manual to get there.

The pattern is: **verify → inventory → backtest → walkforward →
report.** Five commands, in that order, takes you from "where am I"
to "I have an HTML report I can open in a browser." Worked end to end
in this guide with real terminal output.

---

## A typical session, end to end

### 1. Confirm everything is fresh

The first command of every session. `verify` walks every manifest in
`data/` and reports anything stale or missing.

```
$ uv run trading-research verify
Walking manifests under C:\git\work\Trading-research\data...

  RAW    : 354 files, 354 manifests, 0 stale
  CLEAN  :  63 files,  63 manifests, 0 stale
  FEAT   :  33 files,  33 manifests, 0 stale

All 450 manifests fresh. ✓
$ echo $?
0
```

Exit code 0 means proceed. Exit code 1 means at least one file is
stale; the report names the offending files. Stale almost always
means one of two things: a feature-set YAML was edited without a tag
bump (Chapter 8.4), or a code change in `src/trading_research/data/`
or `src/trading_research/indicators/` invalidated something
downstream. The fix is `rebuild clean` or `rebuild features` for the
affected symbol — not editing the manifest.

> *If verify returns 1:* read what it printed, run the indicated
> rebuild, run verify again. Do not bypass it. Stale data in a
> backtest produces results that look real and are not.

### 2. See what's actually on disk

`inventory` is the snapshot of the data store. Run it any time you
have a "wait, do I have feature parquets for that timeframe?" moment.

```
$ uv run trading-research inventory
Layer      Symbol               TF     Adjust       Rows      Range                       Size  Manifest    Stale
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
RAW        TYH10                1m     raw        67,392      2010-03-01 → 2010-06-01    8.2 MB  ok          –
RAW        TYM10                1m     raw        69,120      2010-06-01 → 2010-09-01    8.4 MB  ok          –
...
RAW        ECH26                1m     raw        87,840      2025-12-15 → 2026-03-15   10.6 MB  ok          –
CLEAN      ZN                   1m     backadj  4,673,993     2010-01-03 → 2026-04-10  225.3 MB  ok          –
CLEAN      ZN                   5m     backadj  1,064,432     2010-01-03 → 2026-04-10   78.1 MB  ok          –
CLEAN      ZN                   15m    backadj    354,810     2010-01-03 → 2026-04-10   28.7 MB  ok          –
CLEAN      ZN                   60m    backadj     88,704     2010-01-03 → 2026-04-10    9.1 MB  ok          –
CLEAN      ZN                   1D     backadj      3,996     2010-01-03 → 2026-04-10  198.0 KB  ok          –
CLEAN      6A                   5m     backadj  1,061,224     2010-01-03 → 2026-05-01   76.4 MB  ok          –
...
FEAT       ZN     base-v1       5m     backadj  1,064,432     2010-01-03 → 2026-04-10  148.6 MB  ok          –
FEAT       ZN     base-v1       15m    backadj    354,810     2010-01-03 → 2026-04-10   54.9 MB  ok          –
FEAT       6A     base-v1       60m    backadj     88,576     2010-01-03 → 2026-05-01   18.7 MB  ok          –
...
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
RAW: 354 files, 737 MB | CLEAN: 63 files, 1.3 GB | FEAT: 33 files, 1.7 GB
```

The columns to read: **Symbol**, **TF**, **Adjust**, **Range**. If
the strategy you want to run says `symbol: ZN, timeframe: 15m`, you
need a row that says `FEAT  ZN  base-v1  15m  backadj`. If that row
is missing, the strategy will fail with "feature parquet not found"
and you'll need to rebuild features for that combination (see
Chapter 4 §4.7.3).

### 3. Pick a strategy

Strategies live in `configs/strategies/`. The committed examples are
the platform's worked strategies — read the YAML before running it
to understand what it's doing.

```
$ ls configs/strategies/
6a-bb-reversion-yaml-v1.yaml
6a-monthly-vwap-fade-yaml-v1.yaml
6a-monthly-vwap-fade-yaml-v2b.yaml
6a-vwap-reversion-adx-yaml-v1.yaml
6c-donchian-breakout-yaml-v1.yaml
zn-macd-momentum-yaml-v1.yaml
zn-macd-zero-cross-240m-yaml-v1.yaml
example-v1.yaml
```

Read the one you intend to run:

```
$ cat configs/strategies/zn-macd-momentum-yaml-v1.yaml
strategy_id: zn-macd-momentum-yaml-v1
symbol: ZN
timeframe: 15m
description: >
  ZN momentum continuation: enter on MACD histogram zero cross
  with the trend, exit on opposite cross or ATR-scaled stop.
feature_set: base-v1

knobs:
  stop_atr_mult: 2.0
  target_atr_mult: 3.0

entry:
  long:
    all:
      - "macd_hist > 0"
      - "shift(macd_hist, 1) <= 0"
      - "close > daily_ema_50"
  short:
    all:
      - "macd_hist < 0"
      - "shift(macd_hist, 1) >= 0"
      - "close < daily_ema_50"

exits:
  stop:
    long:  "close - stop_atr_mult * atr_14"
    short: "close + stop_atr_mult * atr_14"
  target:
    long:  "close + target_atr_mult * atr_14"
    short: "close - target_atr_mult * atr_14"

backtest:
  fill_model: next_bar_open
  eod_flat: true
  max_holding_bars: 26
  quantity: 1
```

The YAML grammar is documented in Chapter 10. The expression syntax
in `entry`/`exits` is documented in Chapter 11.

### 4. Run the backtest

```
$ uv run trading-research backtest --strategy configs/strategies/zn-macd-momentum-yaml-v1.yaml
Loading FEATURES parquet... ZN/15m/base-v1 (354,810 bars)
Generating signals...    487 long, 462 short
Simulating fills (next_bar_open)...
Applying EOD flat...
Computing trade log... 949 trades
Bootstrapping confidence intervals (B=1000)...

Strategy:        zn-macd-momentum-yaml-v1
Symbol:          ZN  (15m, backadjusted, base-v1)
Date range:      2010-01-04 → 2026-04-10  (16.3 years)

──── Headline ────────────────────────────────────────────────
  Trades:                  949        (1.13/week)
  Win rate:               48.7%       95% CI [45.5%, 51.9%]
  Profit factor:           1.04       95% CI [0.91, 1.18]
  Expectancy:           $   12.74     95% CI [-$ 4.81, $ 30.29]
  Sharpe (raw):            0.31       95% CI [-0.18,  0.79]
  Sortino:                 0.44       95% CI [-0.21,  1.07]
  Calmar:                  0.08       95% CI [-0.05,  0.21]   ← headline
  Max drawdown:        -$8,142        depth -7.4%, dur 487 days
  Max consec losses:        9
  Avg MAE:              -0.012 pts    Avg MFE:  0.018 pts

──── Behavioural ──────────────────────────────────────────────
  Drawdown duration:    487 trading days
  Trades / week:           1.13
  Holding period:         11.4 bars   median 9.0

Trade log:        runs/zn-macd-momentum-yaml-v1/2026-05-06-14-22-37/trades.parquet
Equity curve:     runs/zn-macd-momentum-yaml-v1/2026-05-06-14-22-37/equity_curve.parquet
Summary:          runs/zn-macd-momentum-yaml-v1/2026-05-06-14-22-37/summary.json
```

The CI bracketed against each metric is the bootstrap 95% confidence
interval. **A CI that includes zero is the kill criterion.** Here
Calmar's CI is [-0.05, 0.21] — that includes zero. The strategy is
indistinguishable from no-edge at 95% confidence. The data scientist
persona will say this loudly. Read Chapter 21 (Bootstrap CIs) and
Chapter 19 (Headline Metrics) before reasoning about whether a
strategy is real.

### 5. Walk-forward (5 folds)

Single-backtest results are the weakest validation. Walk-forward —
fit on a window, evaluate on the next window, slide forward — is the
minimum bar before any strategy claim.

```
$ uv run trading-research walkforward \
      --strategy configs/strategies/zn-macd-momentum-yaml-v1.yaml \
      --n-folds 5
Walk-forward, 5 folds, purge=5 days, embargo=2 days

Fold  Train range                Test range                 Trades  Calmar  Sharpe
─────────────────────────────────────────────────────────────────────────────────────
1     2010-01-04 → 2013-04-10    2013-04-15 → 2016-07-22    187     0.14    0.51
2     2013-04-15 → 2016-07-22    2016-07-26 → 2019-10-30    164    -0.03   -0.09
3     2016-07-26 → 2019-10-30    2019-11-04 → 2023-02-08    198     0.21    0.62
4     2019-11-04 → 2023-02-08    2023-02-13 → 2026-04-10    151     0.04    0.12
5     2010-01-04 → 2026-04-10    aggregate                  700     0.07    0.28

──── Aggregate verdict ───────────────────────────────────────
  Folds positive:        2 of 4         (gate: > 50%)        ✗
  Calmar (aggregate):    0.07           (gate: > 0.10)       ✗
  Fold variance:         0.092          (gate: < 0.15)       ✓
  DSR (post-deflation):  0.18           (gate: > 0.50)       ✗

Walk-forward parquet: runs/zn-macd-momentum-yaml-v1/2026-05-06-14-25-12/walkforward.parquet
```

Two of four folds positive is a coin flip; aggregate Calmar 0.07 is
below the gate threshold of 0.10; the deflated Sharpe of 0.18 is
statistically indistinguishable from zero. **This strategy does not
pass the validation gate.** That is the correct answer. Knowing
that quickly is what the platform exists for.

### 6. Render the report

Even a non-passing strategy gets a report — the report is where the
diagnostics live: equity curve, drawdown shape, monthly heatmap, MAE
vs MFE scatter. You read the report to understand *why* a strategy
is what it is, not to relitigate whether it's promotable.

```
$ uv run trading-research report zn-macd-momentum-yaml-v1
Loading latest run: 2026-05-06-14-25-12
Loading trades.parquet (949 rows)...
Loading walkforward.parquet (5 folds)...
Computing rolling metrics...
Rendering equity curve, drawdown, monthly heatmap, fold table, MAE/MFE...
Pipeline integrity audit: all checks pass.

Report written to: runs/zn-macd-momentum-yaml-v1/2026-05-06-14-25-12/report.html
File size: 1.4 MB (self-contained, no external assets)
```

Open it:

```
$ start runs/zn-macd-momentum-yaml-v1/2026-05-06-14-25-12/report.html
```

(`start` on Windows; `open` on macOS; `xdg-open` on Linux.)

The report is self-contained — every chart embedded, no live links.
You can email it, archive it, pass it through a code review.

---

## When something goes wrong

| Symptom | First place to look |
|---------|---------------------|
| `verify` returns 1 | The file list it printed; usually a feature-set YAML was edited without a tag bump (Chapter 8.4) |
| Backtest aborts: "feature parquet not found" | `inventory` will tell you whether the (symbol, timeframe, tag) combination exists. If not, `rebuild features --symbol <S> --set <tag>` |
| Strategy YAML expression error | The error names the offending expression and the bar number; see Chapter 11 for syntax rules. Common: `>` vs `<` flipped, or a column name typo (compare to inventory's column list) |
| Bootstrap CI is wider than the metric itself | Trade count is too small for honest inference. See Chapter 21.4. Below ~50 trades, the CI is uninformative regardless of point estimate |
| Walk-forward fold has zero trades | The strategy's regime filter is too restrictive for the test window. Loosen the filter or pick wider folds |
| Report says "stale data warning" | A source parquet's `built_at` is newer than the trade log's; rebuild and rerun the backtest, don't paper over it |

The full troubleshooting chapter is Chapter 55. The behavioural-
metric section in Chapter 20 is what to read when a strategy looks
profitable but you can't actually run it.

---

## Five-command quick reference

| Goal | Command |
|------|---------|
| Confirm everything is fresh | `uv run trading-research verify` |
| See what's on disk | `uv run trading-research inventory` |
| Run a backtest | `uv run trading-research backtest --strategy <path>` |
| Walk-forward (5 folds) | `uv run trading-research walkforward --strategy <path> --n-folds 5` |
| Render the report | `uv run trading-research report <strategy_id>` |

The full CLI reference is Chapter 49. The configuration reference is
Chapter 50.

---

## What this guide does not cover

- **Cold-start from a clean clone** (no data, no `.venv`) — see
  Chapter 54.
- **Adding a new instrument** — see Chapter 5 §5.5 and Chapter 4 §4.11
  for the full GC worked example.
- **Authoring a strategy from scratch** — Part III, Chapters 9–13.
- **Reading a Trader's Desk report deeply** — Chapter 17.
- **Promoting a strategy through the validation gate to paper** —
  Part IX, Chapters 45–48.
- **Disk cleanup** — Chapter 56.5 for the `clean` subcommand group.
- **The replay app** (interactive trade-by-trade forensics) —
  Chapter 18.

If your task is none of the above, the [Table of Contents](TABLE-OF-CONTENTS.md)
is the next stop.

---

*See also: [`README.md`](README.md) for the manual project,
[`04-data-pipeline.md`](04-data-pipeline.md) for the data architecture,
[`05-instrument-registry.md`](05-instrument-registry.md) for the
contract registry.*
