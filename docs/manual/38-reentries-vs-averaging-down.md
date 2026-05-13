# Chapter 38 — Re-entries vs Averaging Down

> **Chapter status:** [EXISTS] — the Mulligan controller is fully
> implemented in
> [`strategies/mulligan.py`](../../src/trading_research/strategies/mulligan.py).
> The engine instantiates a `MulliganController` at entry time and
> enforces Rules M-1 through M-3. This chapter is the operator's
> reference for why the distinction matters and how to author a
> re-entry strategy correctly.

---

## 38.0 What this chapter covers

Averaging down — adding to a losing position without a fresh signal —
is one of the most reliable ways to ruin an otherwise sound strategy.
Planned re-entries on fresh signals are a legitimate and widely-used
technique. The platform enforces the distinction mechanically. After
reading this chapter you will:

- Know the precise definition of the distinction and why it is the
  trigger, not the P&L
- Understand the three Mulligan rules (M-1, M-2, M-3) and what each
  prevents
- Know how to author a YAML strategy that allows re-entries
- Understand what the trade log shows for a Mulligan-scaled position

This chapter is roughly 3 pages. It is referenced by Chapter 14
(Backtest Engine §14.7), Chapter 35 (Risk Management Standards), and
Chapter 39 (Pairs and Spread Trading).

---

## 38.1 The distinction

**Averaging down (forbidden):** the existing position is a long, the
market has moved against you, and you want to add more because the
price is now "even cheaper" and you expect it to recover. The trigger
is the adverse price movement. The motivation is anchored to the entry
price. The result is maximum exposure at the worst point.

**Re-entry on a fresh signal (legitimate):** the existing position is a
long, the market has moved against you within your stop distance, and
the entry indicator subsequently re-fires in the long direction. The
trigger is a new signal, not the price action. The motivation is new
evidence confirming the original thesis. The exposure increase happens
because the signal says to, not because you want your money back.

The practical test: *What generated the scale-in decision?* If the
answer is "the signal re-fired," the re-entry is legitimate. If the
answer is "I'm down and I want it to come back," it is averaging down.
The Mulligan controller can only check mechanical rules; the operator
is responsible for ensuring the strategy config does not encode
disguised averaging-down.

---

## 38.2 The Mulligan controller

`MulliganController` in
[`strategies/mulligan.py:60`](../../src/trading_research/strategies/mulligan.py)
is instantiated by the engine at the time of the original entry. It
enforces three rules before permitting a scale-in:

**Rule M-1 — Fresh signal required.**
The candidate signal's timestamp must be strictly later than the last
consumed signal timestamp. The controller maintains `last_consumed_ts`
internally; strategy code cannot advance it. A signal that was already
used to enter the original position cannot be reused.

Rule M-1b: the candidate signal's direction must match the open
position's direction. You cannot add to a long on a short signal.

**Rule M-2 — Directional price gate.**
For longs: `new_entry_price >= orig.entry_price - n_atr × ATR`. For
shorts: the inverse. This prevents adding to a position that has moved
so far against the original entry that the average entry price would
exceed the stop.

The gate width `n_atr` (default 0.3) is a sweepable knob in the
strategy config. A wider gate (e.g. 2.0 ATR) permits scale-ins deeper
into the adverse move; a tighter gate (0.1) only permits scale-ins
essentially at the original price.

**Rule M-3 — Combined risk pre-defined.**
Before the scale-in fill is applied, `combined_risk()` computes the
combined stop (unchanged from the original, because the
thesis-invalidation level does not change) and the combined target
(anchored to the weighted-average entry). This computation is logged
before the order is placed.

When any rule fails, `MulliganViolation` is raised
([`strategies/mulligan.py:46`](../../src/trading_research/strategies/mulligan.py))
and the scale-in is rejected. The exit reason recorded in the trade log
is `"mulligan"` when this rejection causes the engine to exit the
original position at the stop.

> *Why M-2 specifically:* the most dangerous averaging-down pattern is
> the "martingale add" — adding at every N-ATR adverse step. M-2
> blocks scale-ins that are more than `n_atr` ATR worse than the
> original entry, which cuts off the martingale at the first step.
> Setting `n_atr=0` would block all adverse-price scale-ins entirely.

---

## 38.3 Authoring a re-entry strategy

To allow Mulligan re-entries, the strategy YAML must set the
`max_scale_ins` knob and optionally `mulligan_n_atr` and
`mulligan_target_atr`:

```yaml
knobs:
  mulligan_n_atr: 0.5          # gate width in ATR multiples (M-2)
  mulligan_target_atr: 2.0     # combined target distance from avg entry
  max_scale_ins: 1             # hard cap: one re-entry per position
```

The `entry:` block defines the primary signal. When `max_scale_ins` is
set to 1 or greater, the engine checks for re-entry at every subsequent
bar while the position is open, using the same entry expression.

**What the trade log shows:**
For a position with one Mulligan scale-in, the trade log records two
entries with the same `trade_id` prefix:
- Leg 1: original entry bar, original size, original entry price
- Leg 2: scale-in bar, scale-in size, scale-in price

The combined stop and combined target are stored in the Leg 2 record.
MAE/MFE are measured from the weighted-average entry price of both legs
combined.

---

## 38.4 What the platform refuses

The platform has no direct way to detect averaging-down in a strategy
config — it can only enforce the mechanical rules. Strategies that pass
Rule M-1 but are effectively encoding averaging-down (e.g., a signal
expression that is always True when the position is at a loss) will not
be caught by the Mulligan controller.

The data scientist persona will flag this pattern when reviewing signal
statistics: if the scale-in fill bar's price is consistently far below
the original entry, and the signal correlation with prior-bar adverse
move is high, that is evidence of disguised averaging-down.

The operator's responsibility: ensure the entry expression for re-entry
is identical to the expression for the initial entry, and that the
signal is derived from indicators, not from price-versus-entry.

---

## Related references

- Code: [`strategies/mulligan.py`](../../src/trading_research/strategies/mulligan.py) —
  `MulliganController`, `combined_risk`, `MulliganViolation`
- Chapter 14 — The Backtest Engine (§14.7 Mulligan controller)
- Chapter 15 — Trade Schema (exit reasons: `"mulligan"`)
- Chapter 35 — Risk Management Standards

---

*Chapter 38 of the Trading Research Platform Operator's Manual*
