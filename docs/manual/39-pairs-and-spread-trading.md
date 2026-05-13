# Chapter 39 — Pairs and Spread Trading

> **Chapter status:** [EXISTS / GAP] — broker margin data
> (`configs/broker_margins.yaml`) and the margin helpers in
> `eval/capital.py` are implemented. The YAML grammar extension
> required for pairs strategy authoring (§39.1) is **[GAP]** and is
> post-v1.0. This chapter documents the reality of pairs margins and
> cross-references the post-v1.0 backlog item.

---

## 39.0 What this chapter covers

Pairs and spread trading is the highest-quality opportunity in the
current instrument universe for an operator with Ibby's capital,
temperament, and preference for mean reversion. The fundamental
challenge for retail is margin: the exchange-spread reductions that
make pairs cheap at institutional desks do not apply at TradeStation or
IBKR retail. After reading this chapter you will:

- Understand the spread margin reality for retail accounts
- Know how to read `configs/broker_margins.yaml` and compute actual
  margin requirements
- Know what the post-v1.0 pairs strategy capability will look like

This chapter is roughly 2 pages. It is referenced by Chapters 35 (Risk
Management Standards) and 37 (Capital Allocation).

---

## 39.1 Pairs strategy structure

**[GAP — post-v1.0]** The current YAML strategy grammar is
single-symbol. A pairs strategy requires:

- Two symbol declarations with a weight ratio
- A spread definition (e.g., `ZN_price - 0.6 × ZB_price`)
- Indicator computation on the spread series rather than the individual
  bars
- Two simultaneous order entries at execution time

The post-v1.0 specification for the YAML extension is:

```yaml
symbol: ZN/ZB                  # forward-slash notation for pairs
spread_definition: ZN - 0.6*ZB # expression evaluated per bar
legs:
  - symbol: ZN
    side: long
    weight: 1.0
  - symbol: ZB
    side: short
    weight: 0.6
```

This extension is not implemented in v1.0. Until it is, pairs
strategies must be authored as Python signal modules (`signal_module:`
path) that return simultaneous signals for both legs. The chapters that
reference pairs (Chapter 41, Chapter 42) treat them as two separately
tracked strategies that are correlated; portfolio analysis identifies
the correlation.

---

## 39.2 Spread margin reality

The CME Group offers reduced intercommodity spread margins for certain
pairs at member desks: a ZN/ZB spread that would cost $4,400 in
combined margin ($2,310 + $2,310) may cost $880 at the exchange level
under the spread margin programme. This is a 5:1 capital efficiency
advantage.

**This does not apply at TradeStation or IBKR retail.** Both brokers
charge full overnight initial margin on each leg independently.

For the instruments in `configs/broker_margins.yaml`:

**ZN/ZB yield curve spread (TradeStation):**
- ZN overnight initial: $2,310 per contract
- ZB overnight initial: not currently registered (add when needed)
- Combined pair margin at 1:1 ratio: ~$4,620

**6A/6C commodity currency spread:**
- 6A overnight initial: $2,090
- 6C overnight initial: $1,430
- Combined pair margin: $3,520

**6A/6N Antipodean spread:**
- 6A overnight initial: $2,090
- 6N overnight initial: $2,420
- Combined pair margin: $4,510

These are overnight margins. TradeStation's intraday margins are roughly
20–25% of overnight for single-instrument positions and apply to each
leg independently for pairs; the overnight margin is what matters for
pairs holds.

> *Why this matters:* a pairs strategy that looks capital-efficient at
> $880 margin on a real desk requires 5× more capital at retail. A
> strategy targeting 20% annual return on $4,620 of margin produces the
> same P&L as a strategy targeting 4% return on the same capital at an
> institutional desk. The hurdle is higher. The mentor persona's
> standing instruction: always compute actual broker margin before
> declaring a pairs strategy tradeable.

---

## 39.3 The `configs/broker_margins.yaml` reference

The file at
[`configs/broker_margins.yaml`](../../configs/broker_margins.yaml) is
hand-maintained; last updated 2026-04-16 from TradeStation and IBKR
official margin tables.

Schema:

```yaml
<broker>:
  <symbol>:
    overnight_initial:      # USD, initial margin for overnight holds
    overnight_maintenance:  # USD, maintenance margin
    day_trade_initial:      # USD, intraday initial (TradeStation uses ~25%)
    day_trade_maintenance:  # USD, intraday maintenance
```

To compute combined pair margin programmatically:

```python
from trading_research.eval.capital import load_broker_margins, margin_penalty_ratio

margins = load_broker_margins()
zn_margin = margins["tradestation"]["ZN"]["overnight_initial"]  # 2310
six_a_margin = margins["tradestation"]["6A"]["overnight_initial"]  # 2090
pair_margin = zn_margin + six_a_margin  # wrong example (ZN/6A isn't a natural pair)
```

The file must be refreshed periodically. CME and TradeStation adjust
margins several times per year, especially during volatility events. The
gold (GC) margin increase from ~$17,000 to $50,000+ in 2024–2025 is the
canonical example; that single adjustment put GC standard contracts out
of practical reach for a $25k–$50k account.

**To add a new instrument:** add the symbol under each broker key with
all four margin fields. Cross-reference `configs/instruments.yaml` to
ensure the symbol matches.

---

## Related references

- Config: [`configs/broker_margins.yaml`](../../configs/broker_margins.yaml)
- Code: [`eval/capital.py`](../../src/trading_research/eval/capital.py) —
  `load_broker_margins`, `margin_penalty_ratio`, `return_on_margin`
- Chapter 35 — Risk Management Standards
- Chapter 37 — Capital Allocation
- Chapter 41 — Correlation Analysis (identifying de-facto pairs)

---

*Chapter 39 of the Trading Research Platform Operator's Manual*
