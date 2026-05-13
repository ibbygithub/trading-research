# Chapter 32 — Trial Registry & Leaderboard

> **Chapter status:** [EXISTS] — the trial registry is implemented in
> [`eval/trials.py`](../../src/trading_research/eval/trials.py); the
> leaderboard is in
> [`eval/leaderboard.py`](../../src/trading_research/eval/leaderboard.py);
> CI columns (§32.4) are surfaced in both text and HTML output; and
> the `migrate-trials` CLI (§32.5) is bound to a subcommand. Full
> command reference at
> [Chapter 49.22](49-cli-command-reference.md).

---

## 32.0 What this chapter covers

Every backtest and sweep variant writes a record to `runs/.trials.json`.
The leaderboard is the read-side of that registry. After reading this
chapter you will:

- Know every field in a trial record and what it is for
- Understand `mode` tagging and why it changes what DSR means
- Be able to invoke the `leaderboard` CLI with filters and sorts
- Read the CI columns and know when they are populated
- Know what `migrate-trials` does and when to run it

This chapter is roughly 4 pages. It is referenced by Chapters 23
(Deflated Sharpe), 31 (Sweep Tool), 46 (Pass/Fail Criteria).

---

## 32.1 The trial JSON format

`runs/.trials.json` is an append-only JSON file with the structure:

```json
{
  "trials": [
    {
      "timestamp":        "2026-05-01T10:42:00+00:00",
      "strategy_id":      "6a-vwap-fade-v2b",
      "config_hash":      "md5 of the strategy YAML at record time",
      "sharpe":           1.34,
      "trial_group":      "6a-vwap-fade-v2b",
      "code_version":     "13cb802",
      "featureset_hash":  null,
      "cohort_label":     "13cb802",
      "mode":             "validation",
      "parent_sweep_id":  null,
      "calmar":           2.1,
      "max_drawdown_usd": -4200.0,
      "win_rate":         0.58,
      "total_trades":     312,
      "instrument":       "6A",
      "timeframe":        "5m",
      "sharpe_ci_lo":     0.82,
      "sharpe_ci_hi":     1.91,
      "calmar_ci_lo":     1.1,
      "calmar_ci_hi":     3.4,
      "n_obs":            null,
      "skewness":         null,
      "kurtosis_pearson": null
    },
    ...
  ]
}
```

Key fields and their semantics:

| Field | Type | Purpose |
|---|---|---|
| `timestamp` | ISO-8601 UTC | When the trial was recorded |
| `strategy_id` | string | Strategy name from the YAML |
| `config_hash` | MD5 | Config YAML at record time — detects if config changed |
| `sharpe` | float | Raw annualised Sharpe |
| `trial_group` | string | Cohort for DSR; defaults to `strategy_id` |
| `code_version` | git SHA | Engine version at backtest time |
| `cohort_label` | string | Defaults to `code_version`; used to fence DSR |
| `mode` | string | `"exploration"` or `"validation"` |
| `parent_sweep_id` | hex | Links to the sweep that produced this trial |
| `calmar`, `win_rate`, `total_trades`, … | numeric | Cached metrics for leaderboard display |
| `sharpe_ci_lo/hi`, `calmar_ci_lo/hi` | float | Bootstrap CI bounds (90%), when available |
| `n_obs`, `skewness`, `kurtosis_pearson` | float | Per-trial moments for accurate DSR |

Records are written by `record_trial`
([`eval/trials.py:174`](../../src/trading_research/eval/trials.py))
and are never edited or deleted by normal platform operation. The file
grows by one entry per backtest and per sweep variant.

---

## 32.2 Mode tagging

Every trial has a `mode` field: `"exploration"` or `"validation"`.

**Exploration mode** (`mode="exploration"`)
- Set automatically on all variants produced by the `sweep` command
- Signals that the operator is still searching the parameter space
- DSR counts all exploration trials in the same `trial_group` against
  each other — higher trial count means steeper deflation

**Validation mode** (`mode="validation"`)
- The default for single backtests run with the `backtest` command
- Signals that the operator has committed to a configuration and is
  testing it honestly
- DSR for a validation trial is computed against the full trial group;
  if a large exploration sweep preceded it, the deflation is steep
- Validation-mode trials are never pruned by `clean trials`

The mode field is the cleanest expression of researcher intent in the
registry. An exploration trial is "I am looking for something." A
validation trial is "I believe this is the thing; I am testing it."

> *Why this:* DSR without mode tagging treats every backtest as
> equivalent. A single "sanity check" run has DSR ≈ raw Sharpe. A run
> that follows 30 exploration variants has DSR that is substantially
> lower. Mode tagging makes this distinction explicit in the data.

---

## 32.3 The `leaderboard` CLI command

```
uv run trading-research leaderboard \
    [--filter key=value [--filter key=value ...]] \
    [--sort calmar] \
    [--html outputs/leaderboard.html]
```

Available filter keys: `mode`, `instrument`, `timeframe`,
`strategy_id`, `trial_group`, `code_version`, `parent_sweep_id`.

Available sort keys: `calmar`, `sharpe`, `win_rate`, `total_trades`,
`max_drawdown_usd` (and any other numeric trial field).

Example — show all exploration trials on 6A sorted by Calmar:

```
uv run trading-research leaderboard \
    --filter mode=exploration \
    --filter instrument=6A \
    --sort calmar
```

The text output is a fixed-width table; `--html` writes a dark-themed
HTML table to the specified path.

The columns displayed (in order) are: Timestamp, Strategy, Instrument,
Timeframe, Calmar, **Calmar CI**, Sharpe, **Sharpe CI**, Max DD (USD),
Win Rate, Trades, Mode, Sweep ID. The CI columns are populated only for
trials that were recorded with CI bounds (backtests run since session 46
with a trade count large enough for reliable bootstrap).

---

## 32.4 Leaderboard CI surfacing

When a trial was recorded with bootstrap CI bounds
(`sharpe_ci_lo`/`hi`, `calmar_ci_lo`/`hi`), the leaderboard renders
them as `[lo, hi]` formatted to two decimal places. When the bounds are
absent (pre-session-46 trials, or trials from sweeps run without CI
computation), the cell shows `N/A`.

The CI columns are implemented in
[`eval/leaderboard.py:62`](../../src/trading_research/eval/leaderboard.py):

```python
if field == "calmar_ci":
    lo = getattr(trial, "calmar_ci_lo", None)
    hi = getattr(trial, "calmar_ci_hi", None)
    return _format_ci_range(lo, hi)
```

Reading the CI columns: a Calmar of 2.1 with CI `[1.1, 3.4]` is a
meaningful estimate with a positive lower bound. A Calmar of 2.1 with CI
`[-0.3, 4.5]` has a lower bound that includes zero — the CI-includes-zero
flag fires in the Trader's Desk Report headline, and this trial should not
be promoted to the validation gate without substantially more data.

This section closes the [PARTIAL] marker from §32.4 of the TOC. The CI
columns are fully surfaced in both text and HTML leaderboard output.

---

## 32.5 Migrating older trials

The platform's schema has evolved across sessions. Pre-session-35 trials
may be missing `mode`, `parent_sweep_id`, and other fields; pre-session-33
trials may be missing `code_version` and `cohort_label`.

The `migrate_trials` function in
[`eval/trials.py:267`](../../src/trading_research/eval/trials.py)
normalises any registry to the current schema:

- Converts flat-list format to `{"trials": [...]}` dict format
- Tags entries missing `code_version` as `"pre-hardening"`
- Tags entries missing `mode` as `"validation"` (conservative default)
- Sets `featureset_hash` to None on entries that lack it

The function is idempotent: running it twice produces the same output.

The CLI binding is `uv run trading-research migrate-trials`. Dry-run
is the default; pass `--apply` to write. A `.json.backup` sidecar is
written before the new file unless `--no-backup` is given. The full
command reference is in
[Chapter 49.22](49-cli-command-reference.md).

```
uv run trading-research migrate-trials              # dry-run
uv run trading-research migrate-trials --apply      # write + backup
```

The migration is idempotent — running it twice on a fully migrated
registry is a no-op.

---

## Related references

- Code: [`eval/trials.py`](../../src/trading_research/eval/trials.py) —
  `record_trial`, `load_trials`, `migrate_trials`, `compute_dsr`
- Code: [`eval/leaderboard.py`](../../src/trading_research/eval/leaderboard.py) —
  `build_leaderboard`, `generate_html`
- Chapter 23 — Deflated Sharpe
- Chapter 31 — The Sweep Tool
- Chapter 49 — CLI Command Reference (§49.14 `leaderboard`)

---

*Chapter 32 of the Trading Research Platform Operator's Manual*
