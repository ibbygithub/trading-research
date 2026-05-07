# Chapter 16 — Running a Single Backtest

> **Chapter status:** [EXISTS] — documents the `backtest` CLI command
> and its output artefacts. Common-error consolidation is [PARTIAL] —
> the messages are good; this chapter provides the consolidated reference.

---

## 16.0 What this chapter covers

Running a single backtest is the primary daily operation on the platform.
This chapter covers the `backtest` CLI command in full: its options, the
output artefacts it produces, how to read the summary table printed to
the terminal, and the trial-registry side-effect that every `backtest`
run triggers automatically. After reading this chapter you will know
exactly what happened to the data, which files were written, and what
every line in the terminal output means.

---

## 16.1 The `backtest` CLI command

```
uv run trading-research backtest --strategy <path-to-yaml> [OPTIONS]
```

### 16.1.1 Full option reference

| Option | Type | Default | Purpose |
|--------|------|---------|---------|
| `--strategy` | Path | required | Path to a strategy YAML config file |
| `--from` | YYYY-MM-DD | full history | Restrict backtest to this start date |
| `--to` | YYYY-MM-DD | full history | Restrict backtest to this end date |
| `--out` | Path | `runs/` | Override the output root directory |

### 16.1.2 What `--strategy` accepts

The `--strategy` option accepts any strategy YAML config in
`configs/strategies/`. The backtest CLI auto-detects which of three
dispatch paths the config uses:

**YAML template (preferred):** config has an `entry:` block. No Python
module is required.

```yaml
# configs/strategies/zn-macd-pullback-v1.yaml
strategy_id: zn-macd-pullback-v1
symbol: ZN
timeframe: 15m
entry:
  long:
    all:
      - "macd_hist > 0"
      - "close < bb_lower"
```

**Registered template:** config has a `template:` key pointing to a
`StrategyTemplate` name in the registry.

**Python module (legacy):** config has a `signal_module:` key pointing
to an importable module with a `generate_signals` function.

Exactly one of these three keys must be present; the command exits with
code 2 if none or more than one is found.

### 16.1.3 Date filters

`--from` and `--to` filter the FEATURES parquet before signals are
generated. They restrict both the bar data and the signal generation to
the specified window. This is correct: signal generation should not see
data outside the window.

```
uv run trading-research backtest \
    --strategy configs/strategies/zn-macd-pullback-v1.yaml \
    --from 2022-01-01 \
    --to 2024-12-31
```

Omitting both filters uses the full date range of the FEATURES parquet.
This is the standard configuration for an in-sample backtest before
walk-forward validation.

### 16.1.4 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Completed successfully |
| 1 | Runtime error (signal generation failed, engine error) |
| 2 | Configuration error (strategy file not found, unknown symbol, ambiguous dispatch key) |

---

## 16.2 Output artefacts

Every `backtest` run creates a timestamped directory:

```
runs/<strategy_id>/<YYYY-MM-DD-HH-MM>/
├── trades.parquet
├── equity_curve.parquet
└── summary.json
```

The timestamp is UTC at the moment the run completes.

### 16.2.1 `trades.parquet`

The complete trade log, one row per completed trade, conforming to
`TRADE_SCHEMA` (Chapter 15). Written with PyArrow, schema version
`trade.v1` embedded in parquet metadata.

Load it:

```python
import pandas as pd
trades = pd.read_parquet("runs/zn-macd-v1/2026-05-01-14-30/trades.parquet")
```

A strategy with no trades produces an empty parquet with the correct
schema — it is not absent.

### 16.2.2 `equity_curve.parquet`

A two-column parquet: `exit_ts` (UTC timestamp) and `equity_usd`
(cumulative `net_pnl_usd` across all completed trades, sorted by
`exit_ts`).

```python
eq = pd.read_parquet("runs/zn-macd-v1/2026-05-01-14-30/equity_curve.parquet")
eq["exit_ts"] = pd.to_datetime(eq["exit_ts"], utc=True)
eq = eq.set_index("exit_ts")
eq["equity_usd"].plot()
```

The equity curve starts at zero on the first trade's exit and cumulates
from there. It does not represent an account value — it represents the
strategy's net P&L. Adding an initial capital value is the operator's
responsibility during analysis.

### 16.2.3 `summary.json`

A JSON file containing:

1. The flat performance metrics computed by `compute_summary()`.
2. A `confidence_intervals` key containing bootstrap CIs (n=1000, seed=42).

```json
{
  "total_trades": 247,
  "win_rate": 0.623,
  "avg_win_usd": 312.50,
  "avg_loss_usd": -187.25,
  "profit_factor": 1.81,
  "expectancy_usd": 123.40,
  "trades_per_week": 3.2,
  "max_consec_losses": 6,
  "sharpe": 1.34,
  "sortino": 1.89,
  "calmar": 2.11,
  "max_drawdown_usd": -4875.00,
  "max_drawdown_pct": -0.195,
  "drawdown_duration_days": 142,
  "avg_mae_points": -0.218750,
  "avg_mfe_points": 0.390625,
  "confidence_intervals": {
    "sharpe": [0.81, 1.87],
    "calmar": [1.23, 2.98],
    "win_rate": [0.561, 0.682],
    "expectancy_usd": [78.50, 171.20],
    "profit_factor": [1.42, 2.24],
    "sortino": [1.21, 2.61]
  }
}
```

The CI values are `[p5, p95]` — the 5th and 95th percentiles of the
bootstrapped distribution. A CI that includes zero or goes negative
(for Calmar or Sharpe) means the strategy's edge is statistically
indistinguishable from zero at a 90% confidence level.

---

## 16.3 Reading the summary table

The `backtest` command prints a formatted summary table to the terminal
after the run completes. The table is produced by
`format_with_ci()` in `src/trading_research/eval/bootstrap.py`.

A representative table looks like:

```
==================================================
  Backtest Performance Summary
==================================================
  Total trades                       247
  Win rate                         62.3%
  Avg win (USD)                    312.50
  Avg loss (USD)                  -187.25
  Profit factor                      1.81
  Expectancy (USD)                 123.40
  Trades / week                      3.20
  Max consec. losses                    6
  Sharpe (ann.)           1.34  [0.81, 1.87]
  Sortino (ann.)          1.89  [1.21, 2.61]
  Calmar  [headline]      2.11  [1.23, 2.98]
  Max drawdown (USD)           -4875.00
  Max drawdown (%)              -19.5%
  Drawdown duration (d)            142
  Avg MAE (pts)                 -0.2188
  Avg MFE (pts)                  0.3906
==================================================
```

### 16.3.1 Reading the CI columns

The three metrics with CI brackets (Sharpe, Sortino, Calmar) show
`point_estimate  [p5, p95]`. Focus on:

- **Whether the p5 is positive.** A Calmar CI of [1.23, 2.98] means
  there is a 95% chance the true Calmar is above 1.23. A CI of
  [-0.1, 2.31] includes zero — you cannot distinguish this strategy
  from a coin flip at 90% confidence.

- **The width of the CI.** Wide CIs (Sharpe 0.3 to 2.7) indicate
  a small trade sample. Narrow CIs (Sharpe 1.1 to 1.6) indicate
  a large, consistent sample. CIs narrow proportionally to the
  square root of trade count — doubling the number of trades halves
  the standard error.

- **Consistency between Sharpe and Sortino.** If Sortino is much
  higher than Sharpe, the strategy has asymmetric returns — the
  winners are large and the losers are small. This is healthy for
  mean-reversion. If Sortino ≈ Sharpe, the return distribution is
  roughly symmetric — not typical for a stop-gated strategy.

### 16.3.2 Behavioural flags

The platform applies automatic flags after printing the table (visible
in the structured log, not in the terminal table):

- `trades_per_week > 40`: strategy fires too often; likely responding
  to noise.
- `max_consec_losses >= 10`: long losing streaks indicate regime
  sensitivity or a fragile entry condition.

These flags are informational. They do not abort the run.

---

## 16.4 The trial registry side-effect

Every `backtest` run automatically records a trial in
`runs/.trials.json`. This happens regardless of whether the strategy
passed any performance threshold. The trial record is the foundation
of the leaderboard and the deflated Sharpe computation.

### 16.4.1 What is recorded

```json
{
  "trial_id": "abc12345",
  "strategy_id": "zn-macd-pullback-v1",
  "config_path": "configs/strategies/zn-macd-pullback-v1.yaml",
  "timestamp": "2026-05-01T14:30:22Z",
  "mode": "exploration",
  "sharpe": 1.34,
  "calmar": 2.11,
  "win_rate": 0.623,
  "total_trades": 247,
  "max_drawdown_usd": -4875.0,
  "instrument": "ZN",
  "timeframe": "15m",
  "parent_sweep_id": null,
  "trial_group": null
}
```

The `mode` field defaults to `"exploration"`. The `"validation"` mode
is set only when the strategy is being evaluated at the gate (see
Chapter 45). This distinction matters: the deflated Sharpe computation
counts the number of `"exploration"` trials within a `trial_group` to
determine how many variants were tested before the current one.

### 16.4.2 How to read the registry

```
uv run trading-research leaderboard
```

This prints a ranked table of all trials sorted by Calmar (descending
by default). Filter by any field:

```
uv run trading-research leaderboard --filter instrument=ZN --filter mode=exploration
```

The leaderboard is the operator's primary tool for comparing strategies.
It reads `runs/.trials.json` directly — no separate index is required.

### 16.4.3 The `.trials.json` file is append-only

Records are appended; nothing is automatically removed. Over many
sessions, the file grows. Pruning exploration-mode trials older than
N days is the job of `clean trials --keep-mode validation` (Chapter
56.5). The `"validation"` mode records are kept indefinitely.

---

## 16.5 Common errors and resolutions

| Error | Cause | Resolution |
|-------|-------|------------|
| `ERROR: strategy file not found` | Path typo or missing file | Verify the path with `ls configs/strategies/` |
| `ERROR: unknown symbol` | Symbol not in `instruments.yaml` | Add the symbol to `configs/instruments.yaml` (Chapter 5.4) |
| `ERROR: feature parquet not found` | FEATURES not built for this symbol/timeframe/tag | Run `rebuild features --symbol <S> --set <tag>` |
| `ERROR: no bars in the specified date range` | `--from`/`--to` window has no data | Widen the window or check the FEATURES date range with `inventory` |
| `ERROR: invalid YAML template config` | Expression syntax error in `entry:` block | See Chapter 11.7 for common evaluator errors |
| `ERROR: config must have one of 'entry', 'template', or 'signal_module'` | Config file missing all dispatch keys | Add one of the three dispatch keys to the YAML |
| `ERROR: config may have only one` | Two or more dispatch keys present | Remove all but one |

Exit code 2 always means a configuration error that prevents the run
from starting. Exit code 1 means the run started but failed during
execution. Exit code 0 always means a complete run — even if the
strategy produced zero trades.

---

## 16.6 Related references

### Code modules

- [`src/trading_research/cli/main.py:405`](../../src/trading_research/cli/main.py)
  — the `backtest` command implementation.

- [`src/trading_research/eval/summary.py`](../../src/trading_research/eval/summary.py)
  — `compute_summary()`: metric calculation.

- [`src/trading_research/eval/bootstrap.py`](../../src/trading_research/eval/bootstrap.py)
  — `bootstrap_summary()`, `format_with_ci()`: CI computation and
  terminal formatting.

- [`src/trading_research/eval/trials.py`](../../src/trading_research/eval/trials.py)
  — `record_trial()`: the trial-registry side-effect.

### Other chapters

- **Chapter 14** — The Backtest Engine: how the engine interprets the
  strategy config and produces the trade log.
- **Chapter 15** — Trade Schema & Forensics: the `trades.parquet`
  schema and how to interpret each field.
- **Chapter 17** — The Trader's Desk Report: the `report` CLI command
  that turns run outputs into an HTML report.
- **Chapter 22** — Walk-Forward Validation: running the engine
  repeatedly on folded data with `walkforward`.
- **Chapter 32** — Trial Registry & Leaderboard: the leaderboard CLI
  and the trial JSON format in detail.

---

*End of Chapter 16. Next: Chapter 17 — The Trader's Desk Report.*
