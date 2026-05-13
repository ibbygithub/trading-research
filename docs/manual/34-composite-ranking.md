# Chapter 34 — Composite Ranking

> **Chapter status:** [EXISTS] — the composite score formula and
> `top_x_strategies` function are in
> [`eval/ranking.py`](../../src/trading_research/eval/ranking.py). The
> HTML renderer is wired into the Trader's Desk Report. The design
> rationale is in
> [`docs/design/composite-ranking.md`](../../docs/design/composite-ranking.md).

---

## 34.0 What this chapter covers

When comparing a set of strategies or sweep variants, no single metric
tells the full story. A strategy with high Calmar but only 60 trades is
not comparable to one with moderate Calmar and 400 trades. Composite
ranking resolves this by scoring each strategy on profit factor,
drawdown, and sample size simultaneously. After reading this chapter you
will:

- Know the formula and what each component represents
- Know when to use composite ranking and when a single metric is enough
- Be able to invoke `composite_score` programmatically and via the HTML
  report

This chapter is roughly 2 pages. It is referenced by Chapter 31 (Sweep
Tool) and the Trader's Desk Report (Chapter 17).

---

## 34.1 Why composite ranking

After a sweep produces 20 variants, picking the highest-Calmar variant
ignores two important caveats:

- A strategy with 3× the drawdown of another may report a higher Calmar
  because its numerator (return) was disproportionately lucky
- A strategy with very few trades has a noisy Calmar that will regress
  hard out of sample

Composite ranking builds these caveats into the score:

```
score = ln(PF) × (1 − DD) × (1 + log₁₀(N / N_min))
```

where:
- `PF` = profit factor (gross win / gross loss), log-compressed so a
  PF of 10 isn't infinitely better than a PF of 3
- `DD` = max drawdown as a fraction of peak equity — a 20% drawdown
  keeps 80% of the score; a 50% drawdown halves it
- `N` = trade count; `N_min` = minimum threshold (default 100)
- Strategies with `N < N_min` score −∞ and are excluded from the ranking

A practical example: PF = 1.5, DD = 20%, N = 400 trades:

```
ln(1.5) × 0.80 × (1 + log₁₀(4)) ≈ 0.405 × 0.80 × 1.602 ≈ 0.52
```

A variant with PF = 3.0 but only 60 trades (below N_min = 100) scores
−∞ and is excluded.

> *Why this:* Calmar alone rewards lucky outliers. Profit factor alone
> rewards high win-rate strategies that win often but not enough.
> Trade count alone rewards high-frequency systems regardless of
> profitability. The composite score penalises each failure mode
> multiplicatively so that a strategy must be good on all three axes
> to rank highly.

---

## 34.2 The `eval/ranking.py` module

```python
from trading_research.eval.ranking import composite_score, top_x_strategies

# Single strategy
score = composite_score(
    profit_factor=1.5,
    max_dd_pct=0.20,    # fraction, not percent
    trade_count=400,
    min_trades=100,     # optional, default 100
)

# Top X from a list of trial objects
# Each trial must expose .profit_factor, .max_dd_pct, .trade_count
ranked = top_x_strategies(trials, x=10, min_trades=100)
```

The HTML renderer `render_composite_ranking_html` is called by the
Trader's Desk Report (§8 of the HTML output) and renders a dark-themed
table with rank, strategy ID, profit factor, max DD, trade count, and
composite score.

**When to override `min_trades`:** for short-window out-of-sample
periods (e.g., a walk-forward fold with 35 trades), lower `min_trades`
to 25–50. For full-dataset leaderboards, 100 is the appropriate floor.

**When a single metric is enough:** if you have one strategy and want to
know whether it passes the validation gate, read Calmar and its CI
directly — there is no "ranking" to do with one candidate. Composite
ranking is for comparing multiple variants to find the best candidate to
forward-test.

---

## Related references

- Code: [`eval/ranking.py`](../../src/trading_research/eval/ranking.py) —
  `composite_score`, `top_x_strategies`, `render_composite_ranking_html`
- Design note: [`docs/design/composite-ranking.md`](../../docs/design/composite-ranking.md)
- Chapter 31 — The Sweep Tool
- Chapter 17 — The Trader's Desk Report

---

*Chapter 34 of the Trading Research Platform Operator's Manual*
