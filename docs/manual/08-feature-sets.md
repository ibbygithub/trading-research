# Chapter 8 — Feature Sets

> **Chapter status:** [EXISTS] for §8.1–8.5. §8.6 is [PARTIAL] —
> the feature inventory is surfaced by the `inventory` CLI but is not
> yet integrated into the `status` output (forward reference to
> Chapter 49.16 [GAP]).

---

## 8.0 What this chapter covers

A feature set is the configuration contract between the indicator
library and a strategy. It specifies exactly which indicators to
compute, at which timeframes to build the FEATURES parquet, and which
higher-timeframe columns to project. The feature-set tag is the
audit-trail key that connects a strategy YAML to a specific version of
the indicator stack.

After reading this chapter you will:

- Understand what a feature set is and what the tag guarantees
- Be able to read the base-v1 and base-v2 YAML specifications line
  by line
- Know the fork-and-bump-tag discipline and why tags are immutable
- Know how to delete an experiment feature set safely
- Know how to audit which feature parquets exist for which instruments
  and date ranges

This chapter is roughly 5 pages. It is referenced by Chapter 7
(Indicator Library, §7.12 adding indicators), Chapter 9 (Strategy
Design Principles), Chapter 10 (YAML Strategy Authoring), and Chapter
49.6 (inventory CLI).

---

## 8.1 What a feature set is

A feature set is a versioned, tagged YAML file at
`configs/featuresets/<tag>.yaml`. It declares:

1. **Which indicators** to compute on the bar's native timeframe
   (ATR, RSI, Bollinger, MACD, SMA, Donchian, ADX, OFI, EMA, CCI, etc.)
   with their parameters.
2. **Which VWAP variants** to compute on the 1-minute base frame and
   sample at each bucket close (session, weekly, monthly).
3. **Which HTF columns** to project forward from the daily bar, with
   look-ahead prevention via shift(1).
4. **Which target timeframes** to build FEATURES parquets for (5m, 15m,
   60m, 240m).

The `tag` field in the YAML is the contract between the configuration
and the FEATURES filename. A FEATURES file named
`ZN_backadjusted_5m_features_base-v1_*.parquet` was built against the
`base-v1` tag and contains exactly the indicators specified in
`configs/featuresets/base-v1.yaml` at the time of the build.

### 8.1.1 Why the tag is immutable

Once a FEATURES parquet has been built against a tag, the tag is
**immutable**. The tag is recorded in the parquet's manifest
(`feature_set_tag` field) along with the indicator list and parameters
that were actually applied. If the YAML changes but the tag does not,
the manifest's recorded indicator list will diverge from the YAML's
current content — a silent inconsistency that causes wrong backtest
results with no error message.

The platform detects this: `uv run trading-research verify` compares
the manifest's `parameters` against the current content of
`configs/featuresets/<tag>.yaml` and flags any mismatch. But the
detection is a safety net, not a procedure. The correct procedure is:
when you want to change what a feature set contains, create a new tag.

> *Why not just rebuild under the same tag?* Because the old parquets
> still exist with the old manifest, and any trial in `.trials.json`
> that referenced the old tag now refers to a parquet built with
> different indicators than the strategy was designed against. The
> divergence is silent and retroactive. A new tag prevents this: old
> trials and old parquets remain coherent; new work starts clean.

### 8.1.2 A feature set is not a strategy

A feature set defines the *data available* to a strategy. It does not
define what signal the strategy uses, what timeframe it trades, or what
its risk parameters are. Two strategies with identical entry logic but
different feature sets are different experiments and must run against
different FEATURES parquets.

---

## 8.2 The base-v1 specification

[`configs/featuresets/base-v1.yaml`](../../configs/featuresets/base-v1.yaml)
is the canonical baseline for all single-instrument intraday work on
the platform. Full annotation:

```yaml
tag: base-v1
description: >
  Baseline feature set for ZN intraday mean-reversion work. Includes
  trend/momentum/volatility/order-flow indicators on the bar's own
  timeframe, session/weekly/monthly VWAP sampled from 1m, and
  higher-timeframe bias columns projected from the daily bar.

# -----------------------------------------------------------------------
# Indicators computed on the bar's own timeframe
# -----------------------------------------------------------------------
indicators:
  - name: atr
    period: 14             # Wilder ATR; column: atr_14

  - name: rsi
    period: 14             # Wilder RSI; column: rsi_14

  - name: bollinger
    period: 20
    num_std: 2.0           # columns: bb_mid, bb_upper, bb_lower, bb_pct_b, bb_width

  - name: macd
    fast: 12
    slow: 26
    signal: 9              # columns: macd, macd_signal, macd_hist,
                           #   macd_hist_above_zero, macd_hist_slope,
                           #   macd_hist_bars_since_zero_cross, macd_hist_decline_streak
    derived:
      - hist_above_zero
      - hist_slope
      - bars_since_zero_cross
      - hist_decline_streak

  - name: sma
    period: 200            # column: sma_200

  - name: donchian
    period: 20             # columns: donchian_upper, donchian_lower, donchian_mid

  - name: adx
    period: 14             # column: adx_14

  - name: ofi
    period: 14             # column: ofi_14 (nullable where order-flow absent)

# -----------------------------------------------------------------------
# VWAP flavors — computed on 1m and sampled at the bar close
# -----------------------------------------------------------------------
vwap:
  - name: vwap_session     # columns: vwap_session, vwap_session_std_1_0/1_5/2_0/3_0
  - name: vwap_weekly      # columns: vwap_weekly,  vwap_weekly_std_1_0/1_5/2_0/3_0
  - name: vwap_monthly     # columns: vwap_monthly, vwap_monthly_std_1_0/1_5/2_0/3_0

# -----------------------------------------------------------------------
# Higher-timeframe bias projections (shift(1) applied — no look-ahead)
# -----------------------------------------------------------------------
htf_projections:
  - source_tf: 1D
    columns:
      - name: daily_ema_20     # EMA(20) on daily close, prior session
        indicator: ema
        period: 20
      - name: daily_ema_50     # EMA(50) on daily close, prior session
        indicator: ema
        period: 50
      - name: daily_ema_200    # EMA(200) on daily close, prior session
        indicator: ema
        period: 200
      - name: daily_sma_200    # SMA(200) on daily close, prior session
        indicator: sma
        period: 200
      - name: daily_atr_14     # ATR(14) on daily bars, prior session
        indicator: atr
        period: 14
      - name: daily_adx_14     # ADX(14) on daily bars, prior session
        indicator: adx
        period: 14
      - name: daily_macd_hist  # MACD(12,26,9) histogram on daily bars, prior session
        indicator: macd_hist
        fast: 12
        slow: 26
        signal: 9

# -----------------------------------------------------------------------
# Timeframes this feature set is built for
# -----------------------------------------------------------------------
target_timeframes:
  - 5m
  - 15m
  - 60m
  - 240m
```

The result of building base-v1 for one instrument is four FEATURES
parquets (5m, 15m, 60m, 240m), each containing the 8 native-TF
indicator families (yielding ~25 columns), the 15 VWAP columns (3
flavors × 5 columns each), and the 7 daily HTF columns — approximately
47 feature columns per bar, plus the 12 BAR_SCHEMA columns from the
underlying CLEAN.

---

## 8.3 The base-v2 specification

[`configs/featuresets/base-v2.yaml`](../../configs/featuresets/base-v2.yaml)
is a strict superset of base-v1, adding three indicators:

```yaml
tag: base-v2
description: >
  Session-37 feature set. Extends base-v1 with fast EMA (9-period) for
  momentum-crossover signals, CCI-14 as an oscillator complementary to
  RSI, and EMA-20 at the bar's native timeframe. All base-v1 columns
  are included — this is a strict superset.

extends: base-v1        # inherits all base-v1 content

indicators:
  - name: ema
    period: 9           # column: ema_9 — fast EMA for momentum crossover

  - name: ema
    period: 20          # column: ema_20 — native-TF EMA-20

  - name: cci
    period: 14          # column: cci_14 — CCI oscillator
```

**Why these additions:**

- `ema_9` / `ema_20`: the 9×20 EMA crossover is a momentum signal
  complementary to the MACD line. Naming them separately allows
  expressions like `ema_9 > ema_20` (bullish cross) without requiring
  a custom indicator.
- `cci_14`: the Commodity Channel Index is an oscillator bounded around
  ±100. It is less common than RSI but has different distributional
  properties (it is not bounded) that can be useful when RSI is
  consistently stuck at extremes in trending conditions.

Strategies on base-v1 continue to run against base-v1 parquets
unchanged. Strategies that want `ema_9`, `ema_20`, or `cci_14` must
set `feature_set: base-v2` in their YAML.

---

## 8.4 Forking a feature set

The procedure when you want to experiment with new indicators without
touching a canonical tag:

```bash
# 1. Copy the nearest ancestor
cp configs/featuresets/base-v2.yaml configs/featuresets/experiment-cci.yaml

# 2. Edit the copy: change the tag, update description, add indicators
#    tag: experiment-cci
#    extends: base-v2
#    indicators:
#      - name: cci
#        period: 20    # try wider CCI

# 3. Build the experiment feature set
uv run trading-research rebuild features --symbol ZN --set experiment-cci

# 4. Run strategies against it
#    In strategy YAML: feature_set: experiment-cci

# 5. Delete the experiment when done
del configs\featuresets\experiment-cci.yaml
del data\features\ZN_backadjusted_*_features_experiment-cci_*.parquet
del data\features\ZN_backadjusted_*_features_experiment-cci_*.parquet.manifest.json
```

Git history of `configs/featuresets/` is the audit log: if you want
to recover a deleted experiment tag, `git log --all -- configs/featuresets/experiment-cci.yaml`
shows it. This is intentional — the config is small and meaningful;
the parquet is large and rebuildable.

**What "delete when done" means.** An experiment tag should not persist
indefinitely in the repository. Each experiment tag accumulates FEATURES
parquets (four timeframes × four instruments = 16+ parquets at ~25 MB
each). After an experiment is complete — whether the indicator made it
into a permanent tag or was discarded — delete the experiment YAML and
the experiment FEATURES parquets. The cleanup CLI commands
(Chapter 56.5) have a `clean features --tag <tag>` subcommand for this.

---

## 8.5 Feature set audit trail

The `git log` of `configs/featuresets/` is the complete history of
what feature sets have existed and when. Tags are immutable but
deletable; a deleted tag's last state is recoverable from git.

The parquet manifests are the per-file audit trail. Each FEATURES
manifest records:

```json
{
  "feature_set_tag": "base-v1",
  "feature_set_config": "configs/featuresets/base-v1.yaml",
  "indicators": [
    {"name": "atr", "period": 14},
    {"name": "rsi", "period": 14},
    ...
  ],
  "htf_projections": [
    {"source_tf": "1D", "columns": ["daily_ema_20", "daily_ema_50", ...]}
  ]
}
```

This means every backtest's trial record (in `runs/.trials.json`)
references a strategy YAML that names a feature_set tag, and that tag's
parquet has a manifest that records the exact indicators that were
applied. The chain from backtest result → feature set → indicator
parameters is unambiguous and auditable without running any code.

The `verify` command checks that the manifest's recorded `parameters`
match the YAML on disk. A mismatch (the YAML was edited without bumping
the tag and without rebuilding) produces a staleness warning and sets
the file's status to stale.

---

## 8.6 The available feature inventory [PARTIAL]

The `inventory` CLI command shows what FEATURES files exist on disk,
for which instruments and timeframes, and with what date ranges:

```
uv run trading-research inventory
```

Example output (abbreviated):

```
Layer      Symbol  Timeframe  Adj         Tag      Start       End         Rows       Size
--------   ------  ---------  ----------  -------  ----------  ----------  ---------  ------
features   ZN      5m         backadjust  base-v1  2010-01-03  2026-04-10  1,064,432  28 MB
features   ZN      15m        backadjust  base-v1  2010-01-03  2026-04-10  354,811    10 MB
features   ZN      60m        backadjust  base-v1  2010-01-03  2026-04-10  88,703     3 MB
features   ZN      240m       backadjust  base-v1  2010-01-03  2026-04-10  22,176     1 MB
features   6A      5m         backadjust  base-v1  2010-01-03  2026-05-01  1,091,284  30 MB
...
```

This output tells the operator which feature parquets exist, whether
they are stale, and what date ranges they cover — answering "can I run
a strategy for this symbol/timeframe combination?" without opening
any files.

**[PARTIAL status note]:** The inventory output is correct and complete
as a CLI command. It is not yet integrated into the `status` CLI output
(Chapter 49.16, **[GAP]**), which should show a feature-freshness
summary as part of the platform status dashboard. Until `status` is
built, `inventory` is the canonical way to audit what feature parquets
are available.

---

## 8.7 Related references

### Configuration

- [`configs/featuresets/base-v1.yaml`](../../configs/featuresets/base-v1.yaml)
  — the baseline; reference when authoring strategies.
- [`configs/featuresets/base-v2.yaml`](../../configs/featuresets/base-v2.yaml)
  — the v2 superset; use when `ema_9`, `ema_20`, or `cci_14` are needed.

### Code

- [`src/trading_research/indicators/features.py`](../../src/trading_research/indicators/features.py)
  — the feature builder; reads the feature-set YAML and drives all
  indicator computation.
- [`src/trading_research/data/manifest.py`](../../src/trading_research/data/manifest.py)
  — `build_features_manifest` and `write_manifest`; how the audit trail
  is written into each parquet sidecar.

### Other manual chapters

- **Chapter 4, §4.9** — worked example: adding a 13-minute timeframe
  experiment using a custom feature-set tag.
- **Chapter 7** — Indicator Library: the full reference for every
  indicator that can appear in a feature-set YAML.
- **Chapter 10, §10.1** — `feature_set` key in a strategy YAML: how
  the strategy references the feature set.
- **Chapter 49.6** — `inventory` CLI full reference.
- **Chapter 49.16** — `status` CLI [GAP]: where the feature freshness
  table will appear once that command is built.
- **Chapter 56.5** — Storage Management: `clean features --tag` for
  retiring experiment tags.

---

*End of Chapter 8. End of Part II — Data Foundation.*
*Next: Part III — Strategy Authoring, Chapter 9.*
