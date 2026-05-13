# Chapter 30 — Event Studies & Blackout Filtering

> **Chapter status:** [EXISTS] — blackout calendars in
> [`configs/calendars/`](../../configs/calendars/), filter logic in
> [`strategies/event_blackout.py`](../../src/trading_research/strategies/event_blackout.py),
> event-study analysis in
> [`eval/event_study.py`](../../src/trading_research/eval/event_study.py).
> Event-conditioned performance surfaces in the `fomc_regime` regime
> breakdown (Chapter 27).

---

## 30.0 What this chapter covers

High-impact economic releases — FOMC statements, CPI, NFP — change
the microstructure of every futures market the platform trades. Mean
reversion fails systematically on these dates; trend strategies
behave unpredictably. The blackout system is the way strategies opt
out of those dates, and the event-study analyser is how the operator
verifies the opt-out is helping rather than hurting. After reading
this chapter you will:

- Know which calendars ship with the platform and how they are
  maintained
- Be able to wire blackout into a strategy
- Know how to read event-conditioned performance

This chapter is roughly 2 pages. It is referenced by Chapters 9, 12,
17, 27.

---

## 30.1 The blackout calendars

[`configs/calendars/`](../../configs/calendars/) holds three
hand-maintained YAML files:

| File | Calendar | Source |
|---|---|---|
| `fomc_dates.yaml` | FOMC policy statement release dates | Federal Reserve historical calendar |
| `cpi_dates.yaml` | BLS CPI-U release dates | U.S. Bureau of Labor Statistics |
| `nfp_dates.yaml` | BLS Nonfarm Payrolls release dates | U.S. Bureau of Labor Statistics |

Each YAML is a flat list of dates under a single top-level key
(`fomc_dates`, `cpi_dates`, `nfp_dates`). The lists run from 2010-01-01
through the most recent release at the time of the last update; the
header comments in each file record the coverage window and the
source.

> *Why hand-maintained rather than scraped:* the three release
> calendars are stable enough that a manual quarterly update is
> cheaper than building a scraper for three different
> government-and-Fed websites. Inter-meeting actions (e.g. the
> March 2020 emergency Fed actions) are included because they cause
> the same microstructure impact as scheduled meetings even though
> they don't appear in the regular calendar.

### 30.1.1 How to update a calendar

1. Find the official release date list (Fed website for FOMC, BLS
   schedule for CPI/NFP).
2. Append the new dates to the relevant YAML in `YYYY-MM-DD` format.
3. Bump the coverage comment in the header.
4. Run `uv run pytest tests/strategies/test_event_blackout.py` —
   the test loads every calendar and verifies the YAML parses.
5. Commit with a one-line message naming which calendar was updated
   and the new coverage end date.

The update is a maintenance task, not a code change. The blackout
filter does not need to be modified.

---

## 30.2 Wiring blackout into a strategy

[`load_blackout_dates`](../../src/trading_research/strategies/event_blackout.py:29)
loads one or more named calendars and returns a `frozenset[date]`.
[`is_blackout`](../../src/trading_research/strategies/event_blackout.py:71)
checks whether a given trade date is in the set.

The typical wiring is via the strategy template — a Python template
loads the calendars at construction and checks the date at signal
time. A YAML-only strategy can declare a regime filter that consumes
the `fomc_regime` column (or `cpi_regime`, etc.) that the strategy
template attaches per bar.

The semantic decision the strategy must make:

- **Block entries on event days.** The most common pattern. Existing
  positions are left to play out; no new positions are opened on
  event dates.
- **Block both entries and exits.** Rare; only when the strategy
  is explicitly trading the post-event reaction. In this case the
  filter usually flips: blackout = "do nothing", non-blackout =
  "allowed to trade."
- **Block entries on event days *and* the day after.** When the
  operator believes the microstructure stays disrupted for one
  additional session. The standard `window_days=1` event-study
  parameter is calibrated for this.

The flag is per-date, not per-bar; strategies that need finer
control (e.g. block the 30 minutes either side of the release)
implement that logic in the template rather than in the calendar
filter.

---

## 30.3 The event_study analyser

[`event_study`](../../src/trading_research/eval/event_study.py:10)
takes a trade log, a list of event dates, and a window in days, and
splits the trades into *in-window* (within `window_days` of any
event) and *out-of-window* trades:

| Field | Meaning |
|---|---|
| `in_window_trades`, `out_window_trades` | Counts of trades in each bucket |
| `in_window_pnl`, `out_window_pnl` | Total P&L in each bucket |
| `in_window_win_rate`, `out_window_win_rate` | Win rate in each bucket |
| `curve_x`, `curve_y` | Cumulative average P&L curve centred on event date |

The curve is the most useful single output. The x-axis runs from
`-window_days` to `+window_days`; the y-axis is the cumulative
average per-event P&L. A strategy whose blackout helps will show a
flat or rising curve; a strategy whose blackout is unnecessary will
show no systematic shape.

> *Why this is informational rather than gating:* an FOMC blackout
> that hurts mean-reversion strategies is rare but not impossible. A
> strategy whose edge is "fade the post-FOMC reversal" should *not*
> blackout FOMC days. The event study is how the operator verifies
> the filter is doing what he thinks it's doing. The mentor's
> question: "show me the proof your blackout helped."

### 30.3.1 Reading the in/out comparison

The four-number summary tells the bulk of the story:

- **In-window count vs out-window count.** Ratio should track the
  expected exposure. If FOMC blackout excludes ~8 dates per year and
  the strategy fires ~20 trades per week, in-window trades should
  be roughly 8/(52·20) ≈ 0.8% of total — close to zero.
- **In-window total P&L.** Strongly negative means the blackout is
  saving the strategy; close to zero means it has no measurable
  effect; positive means the strategy was making money on event days
  and the blackout is costing it.
- **Win rate differential.** Lower win rate in-window than
  out-of-window confirms the blackout's value; higher win rate
  in-window suggests the strategy thrives on event volatility and
  the blackout is the wrong choice.

If the operator suspects the blackout is hurting more than helping,
the right action is to remove it and re-run the gate. The event
study makes that decision data-driven rather than intuition-driven.

---

## 30.4 Related references

### Code modules and config

- [`src/trading_research/strategies/event_blackout.py`](../../src/trading_research/strategies/event_blackout.py)
  — `load_blackout_dates`, `is_blackout`.
- [`src/trading_research/eval/event_study.py`](../../src/trading_research/eval/event_study.py)
  — `event_study` (in/out comparison + curve).
- [`configs/calendars/fomc_dates.yaml`](../../configs/calendars/fomc_dates.yaml),
  [`cpi_dates.yaml`](../../configs/calendars/cpi_dates.yaml),
  [`nfp_dates.yaml`](../../configs/calendars/nfp_dates.yaml) —
  the three hand-maintained event calendars.

### Other manual chapters

- **Chapter 9** — Strategy Design Principles: when to consider an
  event blackout.
- **Chapter 12** — Composable Regime Filters: how `fomc_regime` and
  friends are consumed in YAML.
- **Chapter 17** — Trader's Desk Report: §14 Market Context surfaces
  the event-conditioned breakdown.
- **Chapter 27** — Regime Metrics & Classification: the
  `fomc_regime` regime split.

---

*End of Chapter 30. Next: Chapter 31 — The Sweep Tool.*

*This is the final chapter of Part V — Validation and Statistical Rigor.
Next part: Part VI — Parameter Exploration.*
