# Chapter 20 — Behavioural Metrics

> **Chapter status:** [EXISTS] — every metric is produced by
> [`compute_summary`](../../src/trading_research/eval/summary.py:29)
> and surfaces in §2 and §10 of the Trader's Desk Report. The trade
> log carries `mae_points` and `mfe_points` per trade
> ([`schema.py:107`](../../src/trading_research/data/schema.py)); the
> aggregates come from the summary.

---

## 20.0 What this chapter covers

Behavioural metrics describe whether a strategy is *runnable* in the
hands of a human, not whether the math works. A profitable strategy
the operator turns off at the worst moment is worth zero. After reading
this chapter you will:

- Know the tradeable bands for trades-per-week by strategy class
- Understand why `max_consec_losses` counts zero-P&L trades as losers
- Know what drawdown duration in *trading days* tells you that
  duration in calendar days does not
- Be able to read MAE and MFE distributions for evidence of stop and
  exit-rule problems

This chapter is roughly 3 pages. It is referenced by Chapters 17, 19,
and 46.

---

## 20.1 Trades per week

[`compute_summary`](../../src/trading_research/eval/summary.py:56)
computes:

```python
span_days = (last_exit - first_entry).days
span_weeks = span_days / 7.0
trades_per_week = total_trades / span_weeks
```

This is calendar-week density. There is no adjustment for holidays or
exchange downtime; for a multi-year backtest the noise cancels out.

The bands the mentor uses to flag a strategy:

| trades/week | Verdict |
|---|---|
| < 1 | Too few trades for statistical confidence on most timeframes; the bootstrap CI on every metric will be uninformatively wide |
| 1 – 10 | Typical zone for swing and intraday mean reversion on a single instrument |
| 10 – 30 | Active intraday work; manageable for a discretionary overseer; HTF density for momentum/scalp hybrids |
| 30 – 60 | High-frequency rule density; check costs and slippage assumptions hard |
| > 60 | Flag for investigation regardless of P&L — likely competing with HFT on the wrong timeframe |

A flag in either tail does not mean the strategy is bad. It means the
strategy is unusual enough that the next questions should be specific
to its rhythm: at the low end, is the sample big enough to trust the
metrics; at the high end, do the cost assumptions still hold.

---

## 20.2 Max consecutive losses

[`_max_consecutive_losses`](../../src/trading_research/eval/summary.py:122)
walks the trade list and counts the longest run of `net_pnl_usd <= 0`.
The `<=` is deliberate: a zero-P&L trade (entry stop with no fill, or
a wash) counts as a loss for streak purposes. The reasoning is
psychological — a zero-P&L trade does not feel like a win to the
operator, and any streak metric that pretends otherwise is rosier than
the lived experience.

The bands:

| max_consec_losses | Verdict |
|---|---|
| < 5 | Comfortable; few traders abandon a strategy on 4 in a row |
| 5 – 9 | Tolerable for an experienced operator who has seen the equity curve and trusts the gate |
| 10 – 15 | Flag — at this depth the operator should pre-commit in writing to riding it out |
| > 15 | Unrunnable for most operators regardless of P&L; will be turned off at exactly the worst moment |

This metric is the headline-level form of the more granular
"drawdown duration" measurements (§20.3, Chapter 29). It is the easier
number for an operator to internalise: "the worst losing streak this
strategy will hand me is X trades."

---

## 20.3 Drawdown duration in trading days

[`drawdown_duration_days`](../../src/trading_research/eval/summary.py:99)
is computed in calendar days. Trading-day duration is the same series
filtered through `pandas-market-calendars` and surfaces in §20 (Time
Underwater) of the Trader's Desk Report.

The difference matters. A 60-calendar-day drawdown is roughly 42
trading days — but a 60-calendar-day drawdown that straddles two
holiday-heavy periods (Thanksgiving + Christmas) might be only 35
trading days. The trading-day number is the right one when comparing
recovery speeds across strategies that ran in different parts of the
calendar.

The "recovery clock" idea — how long does the operator have to wait
before equity prints a new high — is what makes this metric brutal in
practice. A six-month drawdown destroys conviction even when the
strategy is fundamentally working; the gate criterion (Chapter 46)
explicitly bounds drawdown duration for this reason.

> *Edge case the summary handles:* a drawdown that never recovers
> before the end of the test window is measured to the final bar. The
> reported duration is a lower bound in this case — the recovery
> simply has not happened yet. The §19 Drawdown Forensics section
> (Chapter 29) marks the recovery date as `NaT` for any open
> drawdown.

---

## 20.4 MAE and MFE distributions

Maximum Adverse Excursion (MAE) and Maximum Favourable Excursion (MFE)
are tracked per trade by the backtest engine and stored in the trade
log as `mae_points` and `mfe_points` (Chapter 15). The summary reports
the averages — `avg_mae_points`, `avg_mfe_points` — and §8 of the
report shows the full distributions.

What each tells you:

**Average MAE** describes how much pain the average trade survives
before being closed. A strategy whose average MAE is close to its
stop distance is running every trade to the wire; a strategy whose
average MAE is a quarter of its stop distance is closing trades early
on target hits. Both are valid; neither is automatically wrong; but
they imply different things about how robust the stop placement is.

**Average MFE** is the corresponding number on the winning side: how
far did the trade move *for* the operator before being closed. A
strategy with average MFE far above its average winner has an exit
problem — it is giving back gains. A strategy with average MFE roughly
equal to its average winner is exiting close to the peak, which is
either skilful or curve-fit.

The §8 scatter plots (MAE vs final P&L, MFE vs final P&L) plus the
gave-back-winners table are the forensic tools for actually diagnosing
these patterns. The numbers in this chapter are the headline summary;
the report is where they are read.

> *Why MAE and MFE are reported in points, not USD:* per-trade
> excursion is a function of price movement; converting to dollars
> obscures the question "did this strategy give the market enough
> room?" Points are scale-free across years (within an instrument) and
> directly comparable to the ATR-scaled stops most strategies use.

---

## 20.5 Related references

### Code modules

- [`src/trading_research/eval/summary.py`](../../src/trading_research/eval/summary.py)
  — `compute_summary`, `_max_consecutive_losses`,
  `_longest_drawdown_duration`.
- [`src/trading_research/eval/drawdowns.py`](../../src/trading_research/eval/drawdowns.py)
  — `time_underwater` for the percent-of-time-below-peak number and
  longest-run computation; consumed by report §20.
- [`src/trading_research/data/schema.py`](../../src/trading_research/data/schema.py)
  — `TRADE_SCHEMA` fields `mae_points` and `mfe_points`.

### Other manual chapters

- **Chapter 15** — Trade Schema: where MAE and MFE are recorded per
  trade.
- **Chapter 17** — Trader's Desk Report: §10 (Streaks) and §8 (MAE/MFE
  Forensics) and §20 (Time Underwater).
- **Chapter 19** — Headline Metrics: drawdown depth and duration in
  calendar days.
- **Chapter 29** — Drawdown Forensics: per-drawdown decomposition.
- **Chapter 46** — Pass/Fail Criteria: how trades/week and max
  consecutive losses gate promotion.

---

*End of Chapter 20. Next: Chapter 21 — Bootstrap Confidence Intervals.*
