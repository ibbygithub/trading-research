# Chapter 28 — Subperiod Analysis

> **Chapter status:** [EXISTS] — implementation in
> [`eval/subperiod.py`](../../src/trading_research/eval/subperiod.py).
> Output renders in §22 of the Trader's Desk Report (Subperiod
> Stability) as the year-by-year metrics table and Calmar bar chart,
> with the degradation flag highlighted in red.

---

## 28.0 What this chapter covers

A strategy that prints Calmar 2.0 over 2010–2024 might be Calmar 4.0
for the first eight years and Calmar 0.2 for the last six. The
headline does not distinguish. Subperiod analysis is the temporal
split that surfaces this. After reading this chapter you will:

- Know which splits the platform produces by default
- Be able to read the degradation flag and know when to trust it
- Know how subperiod analysis differs from walk-forward

This chapter is roughly 2 pages. It is referenced by Chapters 17, 19,
22.

---

## 28.1 Performance by year, month, day-of-week, hour

[`subperiod_analysis`](../../src/trading_research/eval/subperiod.py:5)
splits the trade log by year by default (`splits='yearly'`). Per year
it slices the equity curve to that year's window, builds a
`BacktestResult` for the slice, and runs `compute_summary` to produce
the same metric dict the headline uses. The output is a DataFrame
with one row per year and columns matching the standard summary
(Calmar, Sharpe, win rate, trades, drawdown, expectancy).

The other supported split granularities — monthly, day-of-week,
hour-of-day — surface in §11 (Heatmaps) of the Trader's Desk Report
rather than in §22. The heatmaps are the right format for sparse
granular splits (each cell has few trades); the year-by-year table is
the right format for the regime question.

> *Why the year split is the headline:* a year is the natural unit
> for assessing regime persistence. Months are too short — small
> samples and noise dominate. Multi-year windows hide regime
> transitions. Yearly granularity catches the "this strategy stopped
> working in 2023" pattern with the right signal-to-noise ratio.

---

## 28.2 The degradation flag

```python
if not res_df.empty and 'calmar' in res_df.columns:
    cals = res_df['calmar'].dropna().values
    if len(cals) >= 3 and cals[-1] < 0 and cals[-2] < 0:
        degradation = True
        msg = "Recent periods show significant performance degradation."
```

([`eval/subperiod.py:28`](../../src/trading_research/eval/subperiod.py))

The rule: the two most recent periods both show negative Calmar and
there are at least three periods of history. That is a strict and
useful rule. It catches the strategy that worked through 2022 and
broke in 2023 and 2024 — exactly the regime-decay pattern the mentor
persona watches for.

The flag is informational, not gating. A strategy with the
degradation flag set can still pass the gate criteria (Chapter 46);
the operator must read the flag, look at the year-by-year Calmar
row, and decide. The flag exists to make sure the decision is
explicit rather than accidental.

### 28.2.1 When the flag fires incorrectly

Two known false positives:

1. **A strategy whose final year has only a handful of trades.** A
   tiny-sample year with negative Calmar can fire the flag even when
   the strategy is structurally fine. Read the trade count per year
   alongside the Calmar.
2. **A strategy whose final two years span an unusual market event.**
   2020 (COVID) and the brief 2023 regional-bank stress are both
   capable of producing negative-Calmar years for otherwise sound
   strategies. The flag is asking a question; it is not the answer.

The opposite case — the flag *not* firing when degradation is real —
happens when the most recent year is positive but the broader
trajectory is decay. Look at the bar chart in §22, not only the
flag.

---

## 28.3 Subperiod vs walk-forward

The two analyses look superficially similar — both split history into
windows and report per-window metrics. They differ in purpose:

| Walk-forward (Chapter 22) | Subperiod (this chapter) |
|---|---|
| Tests *generalisation* — does the strategy work out-of-sample? | Tests *stability* — does the strategy work consistently across time? |
| Per-fold uses train/test split with gap and embargo | Per-period uses the full strategy fit; no in-sample/out-of-sample split |
| Required by the gate (Chapter 46) | Informational; surfaces the degradation flag |
| Many short folds (default 10) | Few long periods (typically 5–15 years) |
| Used during validation | Used post-validation to characterise the strategy |

Both should be passed. Walk-forward catches strategies that don't
generalise; subperiod catches strategies that worked in one regime
and stopped. A strategy passes the gate by surviving walk-forward and
is shipped only after subperiod confirms recent stability.

---

## 28.4 Related references

### Code modules

- [`src/trading_research/eval/subperiod.py`](../../src/trading_research/eval/subperiod.py)
  — `subperiod_analysis` (yearly split, degradation flag).
- [`src/trading_research/eval/summary.py`](../../src/trading_research/eval/summary.py)
  — the per-period summary computation is the same `compute_summary`
  the headline uses.
- [`src/trading_research/eval/report.py`](../../src/trading_research/eval/report.py)
  — §22 rendering (table, Calmar bar chart, degradation flag).

### Other manual chapters

- **Chapter 17** — Trader's Desk Report: §22 (Subperiod Stability),
  §11 (Heatmaps).
- **Chapter 19** — Headline Metrics: the per-period metrics are the
  same ones.
- **Chapter 22** — Walk-Forward Validation: the orthogonal
  out-of-sample test.
- **Chapter 27** — Regime Metrics: complementary non-temporal
  conditioning.

---

*End of Chapter 28. Next: Chapter 29 — Drawdown Forensics.*
