# Chapter 31 — The Sweep Tool

> **Chapter status:** [EXISTS] — the `sweep` CLI and the `run_sweep` /
> `expand_params` functions are implemented in
> [`cli/sweep.py`](../../src/trading_research/cli/sweep.py). Sweep IDs
> are recorded in `runs/.trials.json` via
> [`eval/trials.py`](../../src/trading_research/eval/trials.py). This
> chapter is the operator's reference for when to sweep, how to read the
> result, and what mistakes to avoid.

---

## 31.0 What this chapter covers

The sweep tool runs a strategy backtest at every point on a parameter
grid and records every variant in the trial registry. After reading this
chapter you will:

- Know when a sweep is the right tool and when it is not
- Be able to invoke the `sweep` CLI and read its output
- Understand sweep IDs and how they connect sweep variants in the
  leaderboard
- Recognise a clean gradient from a noisy one and know what each means
- Know the three sweep mistakes that invalidate a result

This chapter is roughly 4 pages. It is referenced by Chapters 32
(Trial Registry), 33 (Multiple-Testing Correction), 34 (Composite
Ranking), and 46 (Pass/Fail Criteria).

---

## 31.1 When to sweep

A sweep is useful for exactly one purpose: **mapping a knob's effect on
performance across a clean gradient**. Specifically:

- **Sensitivity analysis.** You believe an ATR multiplier of 1.5 is
  reasonable but want to see whether the strategy is brittle to small
  changes. Sweeping `entry_atr_mult=1.0,1.25,1.5,1.75,2.0` and
  observing a smooth, monotone Calmar response says the strategy is
  robust in this region. A jagged, non-monotone response says it isn't.

- **Identifying the tradeable region.** Before committing to a
  parameter, sweep a wide grid and find the region where performance
  holds up. Then constrain your final choice to that region's interior —
  not its peak.

- **Comparing two competing design choices.** Sweeping `adx_max=18,22,25`
  tells you whether the entry filter matters and in which direction.

The diagnostic value is the *shape of the gradient*, not the best point.

> *Why this:* If you are picking the best point on a sweep grid and
> calling it your strategy parameter, you are fitting. The deflated
> Sharpe will reflect this; a 9-variant sweep of a single parameter
> costs you roughly 1.5 Sharpe points of headroom at the validation gate.

---

## 31.2 When NOT to sweep

- **After seeing test-set results.** If you have run any backtest on
  the data range you plan to validate on, a sweep on that same range is
  pure leakage. Every variant the sweep runs on test data trains the
  analyst, even if the code never touches that data explicitly. This is
  the "I just looked at it" trap from the data scientist persona.

- **To find the best parameter.** Picking the highest-Calmar point on a
  multi-dimensional grid produces a trial with deflated Sharpe close to
  zero regardless of the raw Sharpe. The trial registry records every
  variant; DSR sees every variant; the deflation is automatic and
  severe.

- **After the validation gate.** Once a strategy has been promoted to
  validation mode, any further parameter tuning restarts the exploration
  cycle. The validation result is invalidated the moment you run another
  sweep on the same data.

- **With too many dimensions.** A 3×3×3 grid is 27 variants. Each adds
  to the deflation denominator. Unless you have strong prior reasons to
  believe a knob matters, do not include it in the sweep.

---

## 31.3 The `sweep` CLI command

```
uv run trading-research sweep \
    configs/strategies/my-strategy.yaml \
    --param entry_atr_mult=1.0,1.5,2.0 \
    --param adx_max=18,22 \
    [--runs-root runs/] \
    [--data-root data/]
```

The `--param` flag accepts `key=v1,v2,...` strings where values are
YAML-parsed (`1.5` → float, `22` → int, `true` → bool). Multiple
`--param` flags are expanded as a cartesian product.

The expansion is performed by
[`expand_params`](../../src/trading_research/cli/sweep.py) in
`cli/sweep.py:56`. The example above produces 6 variants:

```
{entry_atr_mult: 1.0, adx_max: 18}
{entry_atr_mult: 1.0, adx_max: 22}
{entry_atr_mult: 1.5, adx_max: 18}
{entry_atr_mult: 1.5, adx_max: 22}
{entry_atr_mult: 2.0, adx_max: 18}
{entry_atr_mult: 2.0, adx_max: 22}
```

Knob overrides are patched into the strategy config's `knobs:` block
before the YAML strategy is constructed. The base YAML is not modified.

Each variant writes artifacts to
`runs/<strategy_id>/<timestamp>-sw<sweep_id_prefix>/` and appends one
entry to `runs/.trials.json` with `mode="exploration"` and
`parent_sweep_id=<sweep_id>`.

---

## 31.4 Sweep ID tracking

Every sweep run generates a hex UUID (`uuid4().hex[:8]`), e.g.
`a3f7c21b`. This ID is:

- Stored on every trial record as `parent_sweep_id`
- Embedded in the run directory name (`-sw<first 6 hex chars>`)
- Available as a filter on the leaderboard: `--filter parent_sweep_id=a3f7c21b`

The sweep ID lets you reconstruct exactly which variants came from which
sweep run and compare them as a group. Without the ID, a leaderboard
entry is just a number with no context about whether it was explored
alone or as one of 27 variants.

> *Why this:* DSR is computed per trial group, and the group boundary
> matters. A single variant has DSR ≈ raw Sharpe. The same variant as
> one of 27 has DSR that is substantially lower. The sweep ID is the
> evidence the registry uses to count the group correctly.

---

## 31.5 Reading a sweep gradient

After a sweep, view results with:

```
uv run trading-research leaderboard \
    --filter parent_sweep_id=a3f7c21b \
    --sort calmar
```

**Monotone gradient:** Calmar rises steadily as `entry_atr_mult`
increases from 1.0 to 2.0. This says the signal strengthens with a
wider filter. Your conclusion: pick from the interior of the improving
region (not the peak), then run a walk-forward to see if the improvement
persists out-of-sample.

**Non-monotone gradient:** Calmar peaks at 1.5 and falls on both sides.
This is compatible with genuine non-linearity *or* with overfitting to
the backtest period. A walk-forward on the 1.5 variant will distinguish
the two cases.

**Flat negative gradient:** Calmar is near zero or negative regardless
of parameter value. The signal does not work in this regime. No amount
of parameter tuning will fix this.

The gradient shape is more informative than any individual point. A
strategy with a shallow, wide plateau is robustly parameterised. A
strategy with a sharp spike is fragile.

---

## 31.6 Common sweep mistakes

**Sweeping too many dimensions at once.** An `m×n×p` grid is `m*n*p`
variants. Each costs one DSR unit. A 3×3×3 sweep uses 27 credits and
leaves the best variant with DSR computed against 27 trials. Run one
dimension at a time; understand the gradient before adding the next
dimension.

**Sweeping after the validation gate.** If a strategy has been promoted
to `mode="validation"` and then a sweep is run to "just check one more
thing," the sweep retroactively invalidates the promotion. The trial
registry sees all variants. There is no way to uninvalidate.

**Not recording the rationale.** A sweep ID in the registry is
evidence. A sentence in the work log explaining *why* the sweep was run
and *what the conclusion was* is the context that makes the evidence
usable in future sessions. Without it, session 60 will look at the
registry and see a cluster of exploration trials with no interpretation.

---

## Related references

- Code: [`cli/sweep.py`](../../src/trading_research/cli/sweep.py) —
  `expand_params`, `run_sweep`, `_real_runner`
- Code: [`eval/trials.py`](../../src/trading_research/eval/trials.py) —
  `record_trial`, `compute_dsr`
- Chapter 32 — Trial Registry & Leaderboard
- Chapter 33 — Multiple-Testing Correction
- Chapter 23 — Deflated Sharpe (DSR mechanics)

---

*Chapter 31 of the Trading Research Platform Operator's Manual*
