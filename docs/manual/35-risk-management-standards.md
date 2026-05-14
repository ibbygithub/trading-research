# Chapter 35 — Risk Management Standards

> **Chapter status:** [EXISTS / PARTIAL] — the standing rules (§35.1)
> are from `CLAUDE.md` and are platform-wide. Per-trade risk via stops
> is enforced by the backtest engine (§35.2). Daily loss limits in the
> simulator are **[GAP]** — the hook is specified here for session 52.
> Broker-side live limits (§35.3) are out of scope for v1.0.

---

## 35.0 What this chapter covers

Risk management in this platform operates at three levels: per-trade
(enforced by stops), per-session (daily loss limit, currently a gap),
and portfolio-level (capital limits and kill switches). After reading
this chapter you will:

- Know the platform's standing risk rules and why they are non-negotiable
- Know which rules are currently enforced in the simulator and which are
  not
- Know the daily loss limit specification that session 52 will implement
- Understand the live execution risk requirements at a high level

This chapter is roughly 3 pages. It is referenced by Chapters 36
(Position Sizing), 38 (Re-entries vs Averaging Down), and 46 (Pass/Fail
Criteria).

---

## 35.1 The standing rules

The following rules apply to all strategies on this platform. Overriding
any of them requires explicit in-conversation consent and must be logged
in the Trader's Desk Report for any affected backtest or live run.

**Per-trade risk via stops**
Every strategy must define a stop expression in the `exits.stop` block
of its YAML config. A strategy without a stop does not pass the
validation gate. The stop defines the thesis-invalidation level; the
platform has no mechanism for "mental stops" or "close at discretion."

**Flat by end of day (default)**
Single-instrument intraday strategies have `eod_flat: true` in the
backtest block. This means the engine closes any open position at the
session close, regardless of P&L. The rule exists because overnight
gaps in single-instrument futures can be severe and unpredictable; the
trader cannot react. See Chapter 14.5 for the implementation.

**No averaging down**
Adding to a position because it has moved against you, without a fresh
entry signal, is forbidden. The Mulligan controller enforces this in the
simulator; see Chapter 38 for the mechanics. The distinction is the
trigger, not the P&L state.

**Pairs and spreads may hold overnight**
Pairs and spread positions partially hedge against headline shocks
because the legs move together. Multi-day holds are permitted for pairs
strategies. Single-instrument positions are intraday only.

**Volatility targeting by default**
Position sizing defaults to volatility targeting, not fixed quantity or
Kelly. See Chapter 36. The rationale: volatility targeting auto-scales
size down when market vol increases, preventing over-leverage at exactly
the moments when risk is highest.

**Daily and weekly loss limits required for paper and live**
Any strategy promoted to paper trading or live must have daily and weekly
loss limits configured. Backtest-only strategies may omit them with a
warning. The limits are part of the strategy config, not the platform
defaults, because the appropriate loss tolerance depends on account size
and strategy frequency.

---

## 35.2 What the platform enforces today

**Enforced in the simulator:**
- Stops: the engine checks the stop expression at each bar and exits
  when triggered (Chapter 14.4)
- EOD flat: the engine closes positions at session close when
  `eod_flat: true` (Chapter 14.5)
- Time-limit stops: the engine exits after `max_holding_bars` bars if
  set (Chapter 14.6)
- Mulligan rules M-1 through M-3: the controller rejects re-entries
  that violate the fresh-signal or directional-gate rules (Chapter 38)

**Not yet enforced in the simulator:**
- **Daily loss limit** — the engine does not track intraday P&L and stop
  accepting entries after a loss threshold is breached. **[GAP]** This
  is the session 52 code deliverable. The spec: add a `daily_loss_limit`
  field to `BacktestConfig`; after each trade close, compute realised
  P&L for the current trading day; if the day's loss exceeds the limit,
  suppress entry signals for the remainder of the day. Flat any open
  position via the EOD flat mechanism.

> *Why this matters now:* a backtest without a daily loss limit
> over-reports performance on strategies with occasional large losing
> days. The gap makes every backtest result slightly optimistic. The
> data scientist persona will flag any strategy where the daily loss
> distribution is fat-tailed and the loss limit is absent.

---

## 35.3 What the platform will enforce in live

The following items are out of scope for v1.0 but are documented here
so they are not lost when the live execution phase begins:

**Broker-side limits** — kill switches that act at the broker level,
not just at the strategy level. These prevent a software bug from
generating runaway orders even if the strategy-level kill switch fails.

**Idempotent order routing** — every order submission is tagged with a
client order ID that the platform checks before resubmitting. A restart
or crash cannot double an order.

**Daily loss limit at the broker** — configuring the broker's own
native daily loss limit as a backstop behind the platform's limit. Belt
and suspenders: the platform's limit fires first; the broker's limit
catches any failure in the platform's enforcement.

**Reconciliation** — after every fill, the platform compares its
internal position record against the broker's. Any discrepancy triggers
a manual review flag.

These specifications belong in the live-execution phase documentation,
which is a separate project from v1.0.

---

## Related references

- Code: [`backtest/engine.py`](../../src/trading_research/backtest/engine.py) —
  stop enforcement, EOD flat logic
- Code: [`strategies/mulligan.py`](../../src/trading_research/strategies/mulligan.py) —
  Mulligan controller (M-1, M-2, M-3)
- Chapter 14 — The Backtest Engine
- Chapter 36 — Position Sizing
- Chapter 38 — Re-entries vs Averaging Down
- Chapter 46 — Pass/Fail Criteria

---

*Chapter 35 of the Trading Research Platform Operator's Manual*
