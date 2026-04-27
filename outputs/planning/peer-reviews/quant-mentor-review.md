# Peer Review — Sprints 29–38 Plan
## Reviewer: Quant Mentor persona
Date: 2026-04-26
Reviewing: `outputs/planning/sprints-29-38-plan.md` v1, `docs/analysis/6e-strategy-class-recommendation.md`, `docs/roadmap/sessions-23-50.md`

The data scientist and the architect did the heavy lifting on this one. I read their reviews and I agree with both. My push-back is on a couple of trading-substance points the others wouldn't catch, plus a sequencing concern about how sprint 33's gate decision actually works in practice.

---

## 1. The 6E recommendation is solid but the entry threshold is going to bite

The strategy class doc says `entry_threshold_atr: 1.5`. ZN equivalent was 1.0–1.2. The reasoning given is "6E is noisier so wider threshold reduces churn." That's right in direction, wrong in magnitude.

Real desks fade EUR/USD intraday at the **2σ-to-2.5σ** band of the session VWAP, not the 1.5σ. At 1.5σ on 5m bars during the London/NY overlap, you will trigger 5–8 times an hour during news drift days. The OU half-life is 165 minutes — you can't enter at every 1.5σ touch and survive the inventory cost. The bid-ask + commission burn at that frequency on M6E micros eats your edge.

**Recommendation for sprint 29a knob defaults:** `entry_threshold_atr: 2.2` as starting point, range 1.8–3.0 in walk-forward. Document the reasoning. The data scientist will then test whether the 1.5σ version would have done better — if it does after costs, I'm wrong, and the plan corrects.

This is exactly the kind of thing where a less-capable agent will paste the recommended config and ship. Make the threshold a knob with a *justified default*, not a hardcoded value.

---

## 2. The "21:00 UTC flatten" is wrong for 6E

The strategy doc says hard flatten at 21:00 UTC before CME settlement. CME FX settlement is 17:00 ET = 21:00 UTC during EST, **22:00 UTC during EDT**. The code needs to derive flatten time from the instrument's settlement time and current ET-vs-UTC offset, not hardcode 21:00.

Per CLAUDE.md: instrument facts in `instruments.yaml`, never hardcoded. Today the doc hardcodes. Sprint 29b implementation must pull this from the instrument registry's session schedule.

This is a small thing. It's also exactly the kind of small thing that produces a 4 PM ET surprise position the day daylight savings ends because the agent never thought about it.

---

## 3. The "London/NY overlap only" filter has a real-world wrinkle

Recommended entry window: 12:00–17:00 UTC. That is correct for "London/NY overlap" in the textbook sense.

The wrinkle: **the highest-quality 6E mean reversion entries are typically 13:00–15:30 UTC**, after the 12:00 ECB fixing window and before NY discretionary desks start unwinding into the close. The 12:00–13:00 hour has heavy fixing flows that often run the spread to 3σ and stay there — those entries are wrong-side trades against real money.

**Recommendation:** add a knob `entry_blackout_minutes_after_session_open: 60` so the strategy doesn't fire in the first hour of the entry window. Default it on. Walk-forward will reveal whether the blackout is helping; my prior says it does.

The 30-minute pre-release blackout is correctly specified — keep that.

---

## 4. The Mulligan logic for FX needs a directional filter

CLAUDE.md says re-entry on a fresh signal with combined risk defined. I've been saying that for the project. For 6E specifically, there's a refinement: **don't take a fresh same-direction signal if the new signal is at a better price than the original entry**.

The reason: in EUR/USD, "another fresh long signal at a better long price" 90% of the time means the market is trending against the original entry and the apparent fresh signal is a false reversion bounce in a real downtrend. Real desks taking the second long there are walking into the meat of the move.

The data scientist will say: "But that's price-conditioning the signal trigger, isn't it averaging down semantically?" No, because the original signal was acted on; the new signal is a new emission. But the *direction-and-price-relationship* of the new signal to the open position is information the strategy is allowed to use as a gate.

**Sprint 32a spec:** Mulligan accepts a fresh signal iff:
1. It is a new `Signal` emission from `generate_signals()` (data scientist's freshness invariant), AND
2. For longs: new entry price ≥ original entry price + N×ATR. For shorts: ≤ original − N×ATR.

This is the "scaling in only when the original thesis is winning, not losing" rule. It's a real-desk technique. Default N = 0.3.

---

## 5. The escape valve on sprint 33 needs better triggering criteria

Plan says: PASS → Track E, FAIL → escape valves (pivot to 6A/6C, switch class, or TradingView port).

Three escape paths is the right number. What's missing: **the criterion for which escape path**.

My recommendation:
- If v2 has positive aggregate equity but failing fold dispersion (5/10 positive but high variance): pivot to 6A/6C single-instrument first. Same strategy class on a different FX cross usually behaves more cleanly because the rate-differential drift is smaller.
- If v2 has negative aggregate equity and most folds losing: switch class. The hypothesis was wrong; mean reversion isn't the play. Sprint 34 picks momentum or breakout from session-28 stationarity follow-up.
- If v2 has positive aggregate but slim margins after costs and Ibby is anxious about June 30: TradingView port. Get a paper trade running on the next-best candidate; don't burn another sprint cycle hoping for v3.

Pre-commit these to the plan. When sprint 33b happens, I don't want a 90-minute discussion about which escape path. Decide the rule now, follow the rule then.

---

## 6. The sprint 36 "first paper trade" is going to feel like a non-event and that's a problem

Sprint 36 acceptance criterion is "at least one closed paper trade with a comparison report." That will happen on day one. Then sprint 37 starts cleanup.

What's missing: **a behavioural readiness check**. Before going from paper to live, you need to *psychologically watch the strategy run for several weeks*, see the drawdowns happen in real time, see the loss streaks happen, and confirm that you can sit through them without overriding. The roadmap's Track E says "minimum 30 trading days paper period before any live capital." Sprint 36 should not be "first paper trade and move on" — it should be "first paper trade and we are now in the 30-day window."

**Recommendation:** rename sprint 36 to "First paper trade + paper-trading discipline window opens." Sprint 37 does cleanup as scheduled. Sprint 38 readiness review explicitly does NOT advance toward live — it advances toward "platform is ready for the strategy to keep running for the rest of the 30-day window with minimal further changes."

This matches CLAUDE.md's standing rule and the data scientist's behavioural-metrics push. It also slows Ibby down at the moment most likely to produce overconfidence, which is right after the first profitable paper trade.

---

## 7. The single biggest missing thing in this plan: realistic cost modelling

I've reviewed both the data scientist's and architect's reviews. Neither flagged this directly so I will: **what's the assumed slippage and commission model in the sprint 30 backtest?**

For 6E mean reversion with 165-minute half-life:
- Round-turn commission on standard 6E at TradeStation retail is roughly $4.20 (broker fee + exchange fee).
- Slippage on a market order at 5m bar open: realistic estimate is 0.5–1 tick on a quiet session, 2+ ticks during the London/NY overlap.
- M6E (micro): commission roughly the same in absolute terms but the contract size is 1/10. Slippage in ticks is similar. So commission-as-percent-of-contract is **10× worse on micros**.

If sprint 30 runs with default slippage of 1 tick and ignores the commission asymmetry, the v1 result is going to look better on M6E than it should. When sprint 36's first paper trade happens, the real M6E fills will look meaningfully worse than the backtest, and Ibby will think he has a divergence problem when he actually has a cost-modelling problem.

**Sprint 30a must explicitly state the cost model and either:**
- Run the backtest under a *pessimistic* cost model (2-tick slippage during overlap, 1 tick otherwise, full commission, both directions) and report the result, OR
- Run sensitivity analysis: 0.5/1/2/3 ticks of slippage, see at which threshold the strategy breaks. If 1 tick is the break point, this is a marginal strategy.

The data scientist's bootstrap CIs do NOT capture this — they capture trade-return variance under a fixed cost model, not cost-model uncertainty.

**Add to sprint 30a deliverables:** cost-sensitivity table. Add to the gate at 33b: "strategy passes with realistic costs, not just optimistic costs."

---

## 8. The Track G ML deferral is correct

Plan defers ML to sprint 38+. Architect implicitly endorses, data scientist doesn't object. I want to underline it: **ML on a strategy that hasn't yet survived 30 days of paper trading is meta-labeling noise**. The plan's deferral is correct. Don't let any future session weaken it because someone wants to "kick the tires on XGBoost while we wait for paper-trading data."

---

## 9. What I want you to keep doing

- The persona-disagreement framing is genuinely useful. The data scientist and architect reviews are not redundant with each other or with mine. Three distinct critiques that overlap on some structural items but each surface their own points. Keep this protocol for future plans.
- Splitting design from implementation across models. From a market-knowledge angle this is exactly right — strategy design (the part where market structure matters) gets the deepest model; implementation (where the spec is the contract) gets the cheaper one.

---

## 10. Required updates I want to see in v2 of the plan

1. Default knobs in 29b reflect FX reality, not ZN reality: `entry_threshold_atr: 2.2`, `entry_blackout_minutes_after_session_open: 60`.
2. Flatten time derived from instrument settlement, not hardcoded 21:00 UTC.
3. Mulligan directional-and-price-relationship gate added to 32a spec.
4. Sprint 33 escape-path triggers pre-committed in the plan body, not at gate time.
5. Sprint 30a explicitly enumerates the cost model and runs sensitivity analysis on slippage.
6. Sprint 36 reframed as "first paper trade + 30-day discipline window opens"; sprint 38 readiness review does not advance to live.
7. ML deferral kept hard — defended in sprint 38d's readiness review.

---

## What I will sign off on

If the plan v2 incorporates these substance changes plus the data scientist's and architect's, I'll sign off. The hardest one is the cost-sensitivity work in sprint 30 — if that gets watered down to "default 1-tick slippage, ship it," I won't.

The 6E recommendation is a real piece of work. Let's not undermine it by skipping the parts that distinguish a real-desk strategy from a backtest curiosity.
