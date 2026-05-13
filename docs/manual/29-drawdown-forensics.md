# Chapter 29 — Drawdown Forensics

> **Chapter status:** [EXISTS] — per-drawdown decomposition in
> [`eval/drawdowns.py`](../../src/trading_research/eval/drawdowns.py),
> portfolio attribution in
> [`eval/portfolio_drawdown.py`](../../src/trading_research/eval/portfolio_drawdown.py),
> Ulcer Index / UPI / Pain Ratio in
> [`eval/stats.py`](../../src/trading_research/eval/stats.py). Surfaces
> in §18 (Extended Risk Metrics), §19 (Drawdown Forensics), and §20
> (Time Underwater) of the Trader's Desk Report.

---

## 29.0 What this chapter covers

A strategy's maximum drawdown is one number. The history of drawdowns
that produced it is many numbers, and the shape of that history is
where the operator's psychological tolerance is actually tested.
After reading this chapter you will:

- Be able to read the per-drawdown catalogue
- Know what the Ulcer Index tells you that max drawdown doesn't
- Understand how portfolio-level drawdowns attribute losses across
  strategies

This chapter is roughly 2 pages. It is referenced by Chapters 17, 19,
20, 41, 42.

---

## 29.1 Per-drawdown decomposition

[`catalog_drawdowns`](../../src/trading_research/eval/drawdowns.py:4)
walks the equity curve and emits one record per drawdown episode
exceeding `threshold_pct` (default 1%):

| Field | Meaning |
|---|---|
| `start_date` | First bar after the most recent peak |
| `trough_date` | Bar at which the drawdown reached its minimum |
| `recovery_date` | First bar to print a new high above the prior peak — `NaT` if not yet recovered |
| `depth_usd` | Peak minus trough, in dollars |
| `depth_pct` | Depth as a fraction of the peak value at the start of the drawdown |

The 1% floor exists to keep the table readable. Every tiny tick-back
in the equity curve is technically a drawdown; threshold-filtering
surfaces the episodes that matter and discards noise.

§19 of the Trader's Desk Report renders this as a sortable table.
Sorting by `depth_pct` descending answers "what is the worst drawdown
this strategy has had?"; sorting by recovery-to-trough duration
answers "what is the longest losing run that ever happened?"

> *Why this beats max drawdown alone:* a strategy with one big
> drawdown and twenty tiny ones tells a different story than a
> strategy with five medium drawdowns of similar depth. The first is
> a strategy that mostly does fine until something specific goes
> wrong; the second is a strategy whose losing runs are systemic.
> The headline `max_drawdown_usd` cannot distinguish.

### 29.1.1 The open-drawdown case

A drawdown that has not recovered by the end of the test window gets
`recovery_date = NaT` and is still counted in the catalogue. Its
duration is measured to the final bar. The platform never silently
hides incomplete drawdowns — surfacing them is essential because the
operator may be looking at a strategy that is currently in a
drawdown and needs to know whether the historical pattern includes
similar episodes.

---

## 29.2 Time underwater

[`time_underwater`](../../src/trading_research/eval/drawdowns.py:31)
returns three numbers:

| Field | Meaning |
|---|---|
| `pct_time_underwater` | Fraction of bars below the running peak |
| `longest_run_days` | Longest peak-to-recovery interval in calendar days |
| `run_lengths` | List of all drawdown run lengths in bars |

`longest_run_days` is the same number reported in the headline as
`drawdown_duration_days`, but the underlying list `run_lengths` is
what §20 of the Trader's Desk Report uses to render the
distribution: how often the strategy is in *some* drawdown, how the
durations are distributed, where the longest run sits relative to
typical.

A strategy with `pct_time_underwater = 0.75` and the longest run at
40 trading days is in drawdown 75% of the time but never for long.
A strategy with `pct_time_underwater = 0.40` and the longest run at
180 trading days is rarely in drawdown but, when it is, stays there
for nearly a year. The two have very different psychological
profiles. The headline cannot distinguish; the time-underwater
distribution does.

---

## 29.3 Ulcer Index and the pain metrics

`max_drawdown_usd` is a point statistic — the single worst episode.
The Ulcer Index is a *path* statistic: the RMS of percentage
drawdowns across all bars
([`eval/stats.py:88`](../../src/trading_research/eval/stats.py)):

```python
peak = equity_series.cummax()
dd_pct = (peak - equity_series) / peak
ulcer_index = sqrt(mean(dd_pct ** 2))
```

A strategy with one big drawdown and otherwise no time below peak has
a low Ulcer Index. A strategy that spends most of its time near peak
with frequent small drawdowns also has a low Ulcer Index. A strategy
that grinds in a long shallow drawdown has a high Ulcer Index even
when its maximum is moderate. The Ulcer Index is the metric Peter
Martin built specifically to capture pain-over-time rather than
pain-at-a-moment.

The platform reports three derived metrics:

- **Ulcer Performance Index (UPI)** — annual return divided by Ulcer
  Index. The Sharpe analogue for path-dependent pain.
- **Recovery Factor** — total net P&L divided by max drawdown. How
  many drawdowns' worth of returns did the strategy produce? Bigger
  is better; 3.0 is solid, 5.0 is strong, 10.0 is exceptional.
- **Pain Ratio** — total net P&L divided by the mean drawdown depth
  (not max). A pain ratio above 5 means the average drawdown is
  small relative to the total return.

These four (Ulcer Index, UPI, Recovery Factor, Pain Ratio) appear in
§18 of the Trader's Desk Report and are the right metrics to consult
when the operator is choosing between two strategies that have
similar Calmar.

---

## 29.4 Portfolio-level drawdowns

[`portfolio_drawdown_attribution`](../../src/trading_research/eval/portfolio_drawdown.py:5)
identifies drawdowns in the combined-portfolio equity curve and
attributes the losses to individual strategies in the portfolio
during the drawdown window. The output is a DataFrame: one row per
portfolio drawdown, with per-strategy contribution columns.

This matters because portfolio drawdowns are typically *not* the
union of strategy drawdowns. When two strategies enter drawdown
simultaneously, the portfolio drawdown can be deeper than either
strategy's solo drawdown — and that *correlated* drawdown is what
destroys diversification's apparent benefit.

The use case: the operator sees a 12% portfolio drawdown in 2023.
The attribution table shows that 9 percentage points came from
Strategy A and 3 percentage points came from Strategy B. The
question becomes: were A and B drawing down on *correlated* signals
(in which case the diversification was illusory) or on *independent*
bad luck (in which case the portfolio is structurally fine and the
event was a coincidence)? Chapter 41 (Correlation Analysis) is the
companion tool.

---

## 29.5 Related references

### Code modules

- [`src/trading_research/eval/drawdowns.py`](../../src/trading_research/eval/drawdowns.py)
  — `catalog_drawdowns`, `time_underwater`.
- [`src/trading_research/eval/portfolio_drawdown.py`](../../src/trading_research/eval/portfolio_drawdown.py)
  — `portfolio_drawdown_attribution`.
- [`src/trading_research/eval/stats.py`](../../src/trading_research/eval/stats.py)
  — `ulcer_index`, `ulcer_performance_index`, `recovery_factor`,
  `pain_ratio`.

### Other manual chapters

- **Chapter 17** — Trader's Desk Report: §18 (Extended Risk Metrics),
  §19 (Drawdown Forensics table), §20 (Time Underwater).
- **Chapter 19** — Headline Metrics: max drawdown and duration.
- **Chapter 20** — Behavioural Metrics: drawdown duration in
  trading days.
- **Chapter 41** — Correlation Analysis: companion for
  portfolio-level diagnosis.
- **Chapter 42** — Portfolio Drawdown: the deeper portfolio chapter.

---

*End of Chapter 29. Next: Chapter 30 — Event Studies & Blackout Filtering.*
