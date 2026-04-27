# Round 2 — Quant Mentor Review
Date: 2026-04-26
Question set: What product do we have at end of session 38? What can it do?
What can't it do? What's left to make it production-ready for live money trading?

---

## Q1 — At end of session 38, what product do I have?

You have a **paper-trading bench for one strategy on one instrument, with
real-desk-shaped guardrails and persona discipline baked in.** Specifically:

- A 6E intraday VWAP mean-reversion strategy that has either cleared a
  pre-committed gate honestly or has explicitly escaped to a different path.
  This is the strategy you watch and learn from for the next 30 trading days.
- A loop that respects the things that matter on a real desk: London/NY
  overlap entries only, hard flatten at settlement, no entries during the
  ECB fixing window, blackouts around major releases, pre-defined Mulligan
  with a directional gate (the real-desk technique, not the rationalisation
  of averaging-down).
- Behavioural metrics surfaced in plain numbers: max consecutive losses,
  drawdown duration, trade cadence. The metrics that actually predict
  whether you'll stay in your seat.
- A trade replay app and HTML reports that let you scroll through every
  trade and see what happened and why.

This is what a small, well-run prop firm gives a junior PM on day one.
Different scale, same shape.

## Q2 — What can it do?

Trader's-eye-view capabilities:

1. **Run a single 6E strategy live on paper with discipline rails.**
   Loss limits, kill switches, settlement-aware flatten, all on by default.
2. **Watch behavioural metrics in real time.** Today's consec losses,
   drawdown depth, week's trade count vs. expected.
3. **Distinguish "behaving wrong" from "in a normal losing streak."** The
   sprint 33 bootstrap CIs for max-consecutive-losses give you the band
   that's still normal vs. the band that says something's broken. If
   today's streak is inside the 95% band from the backtest, you sit
   through it. If it's outside, you halt.
4. **Choose between strategy templates from CLI** without touching code.
   `trading-research describe-template vwap-reversion-v1` is your menu.
5. **Compare backtest to paper performance trade-by-trade.** The shadow-
   backtest record next to every live trade makes the divergence visible
   immediately, not at end of week.
6. **Run a stationarity check before designing a new strategy.** ADF + Hurst
   + OU half-life on demand. So when you say "I want to try this on 6A,"
   the platform tells you within an hour whether 6A's spread looks tradeable
   the way 6E's did.

## Q3 — What can't it do?

Real things you can't do at end of session 38:

1. **Trade real money.** That's session 49, after 30 days of paper.
2. **Tell us your psychological readiness to sit through a paper drawdown.**
   That's not testable in software — that's testable in the 30-day window.
   Until you've watched a real drawdown happen and not closed positions
   prematurely, we don't know.
3. **Run an event blackout calendar automatically.** Sprint 31's regime
   filter handles time-of-day and (per choice) volatility regimes. It does
   NOT integrate the economic-event calendar (FOMC, NFP, ECB, CPI). You
   handle that manually today by checking the calendar in the morning. Per
   roadmap that's a Track F or post-50 enhancement.
4. **Run pairs trading.** Single instrument only. Pairs are Track H —
   sessions 56+. The platform supports it conceptually (instrument
   registry handles 6A and 6C cleanly) but the pairs-specific machinery
   isn't there.
5. **Run multiple simultaneous strategies live.** Single strategy in the
   paper loop. Sessions 51+ do second-strategy work.
6. **Track tax lots.** Futures are 60/40 1256 contracts in the US — easy
   to compute manually for low volume, painful at scale. The platform
   doesn't help with this yet.
7. **Generate a year-end P&L report for tax purposes.** Manual extraction
   from the trade log works but is awkward. Track I+.
8. **Tell you with confidence that the strategy will work in 2027 when the
   ECB rate cycle is different from 2024.** No software does this. The
   platform reports stationarity-over-time so you can see when the spread
   structure shifts; the decision to keep trading or halt is yours.

## Q4 — What's left to make it production-ready for live money trading?

Mentor's lens. Some of this overlaps with the data scientist's and
architect's lists; my framing is different — I care about what makes a
trader survive.

### 4.1 — 30 calendar days of paper trading actually completed
Not 30 sessions, not 30 simulated days. Thirty trading days where you
wake up, the strategy runs, you watch it. The window is the only honest
test of:
- Does the strategy behave like the backtest?
- Are your behavioural metrics inside the CIs?
- Can you sit through a drawdown without overriding?
- Does the platform stay running for 30 days or are there ops issues that
  mean it actually ran for 18 days with 12 days of "I had to fix
  something"?

### 4.2 — Personal evidence of sitting through at least one drawdown
This is item L5 in the live-readiness gate. I'm pulling it out because
it's the most likely single point of failure in this whole project.

You're a 25-year trader. You know markets. You also know yourself well
enough to know that watching your own paper account go red for three days
is different from watching a backtest go red on a chart. The 30-day window
is engineered to produce at least one drawdown of the magnitude the gate
criteria assume. Your job during that window is to NOT TOUCH anything.

If you do touch anything, the window restarts and we have evidence that
the system needs to be more autonomous for you to not override it. That's
useful evidence — it tells us to design for the operator we have, not the
operator we want to have. But it does not unlock live trading.

### 4.3 — A documented "first live trade" checklist (session 49)
Already in the plan. Mentor emphasis: this checklist is not a formality.
Real desks have real checklists. The first live trade in your career may
or may not work; the *checklist* working — every box honestly checked,
no shortcuts — is what tells us the system is ready to do this 100 more
times.

### 4.4 — A pre-committed scaling rule (session 50)
Already in the plan. Mentor emphasis: write it down BEFORE you've made any
money on the strategy. Once you've made money, the temptation is to scale.
The rule prevents you from giving in to that temptation. If the rule says
"5 successful days at 1 contract before scaling to 2," that's what you do,
even on day 3 when you've made $400 and want to ride it.

### 4.5 — A pre-committed halt rule
The opposite. Write down: "if drawdown reaches X% or consec losses reaches
Y, halt the strategy live and reconvene in a session." This is the rule
you need on day 12 of live when the strategy has been losing for a week
and your inner voice is telling you "it'll come back." It will or it
won't; the rule isn't about prediction, it's about not blowing up.

### 4.6 — An honest discussion of "money you can lose"
Before the first live trade, you and I (mentor) need to agree on what
amount of capital is "real but losable" for week 1 of live. The platform
defaults to 1 micro M6E ($1,250 notional, max loss per trade ~$25 at
2-tick stop). Your account can absorb that for 50 consecutive losers without
actually mattering financially. The point of the small size is to test the
system, not to make money. Internalise that distinction.

### 4.7 — Tax-treatment and broker reality check
Before live: confirm your TradeStation account is set up for futures
(separate from cash equity), confirm 60/40 1256 treatment is in effect,
confirm whether your account is margin or cash, confirm overnight margin
requirements (not just intraday — you flatten by EOD but in case of glitch
you might hold). One conversation with TS support if anything is unclear.

### 4.8 — Operational discipline question
Are you actually going to wake up at 12:00 UTC every day? That's 8 AM ET
in summer, 7 AM ET in winter. That's the entry window opening. If you're
asleep, the strategy enters without you watching. Three options:
- Be awake. Honest answer: probably yes for most days, not all.
- Make the system fully autonomous so you don't need to be awake. That
  has implications — kill switches must be drilled, broker outage handling
  must be hardened, you become more dependent on the platform's logic.
- Restrict entries to a window when you ARE awake. E.g., no entries before
  13:00 UTC. Costs some signals; gains your attention.

This is a real decision, not a software decision. Talk through it before
session 49. My recommendation: option 3 for the first live month. You
trade fewer signals; you trade them aware.

### 4.9 — Recovery rituals — what you do on a bad week
After a losing week you will want to *do something*. Real desks have a
ritual: review every trade, look for execution mistakes, look for missed
exits, look for over-trading. NOT: change the strategy. NOT: increase size
to "make it back." NOT: add a discretionary trade.

The ritual exists so you have something productive to do with the
emotional energy that doesn't damage the system. Write the ritual down
before live. It's a few bullet points.

### 4.10 — Knowing when to walk away
After session 50 the platform is running with live capital. There will be
a week or a month where the strategy is worse than expected. That's
inevitable; even good strategies have those. The question is at what point
do you accept the strategy is broken and stop trading it.

Pre-commit: "if realised Calmar's lower CI bound is below 0.0 over a
40-trade rolling window, the strategy is paused for review." Not the
strategy's fault, not your fault — the market changed or the assumption
broke. Pre-committing this rule is what separates a trader from a gambler.

---

## What I will sign off on

I will sign session 45's live-readiness gate (criteria L4, L5, L9) on the
condition that 4.1–4.6 above are visibly true and 4.7–4.10 have been
discussed in writing in a session log.

The platform at end of session 38 is genuinely good. It's built honestly,
it's instrumented honestly, it pushes back on bad trades honestly. What
it doesn't have is *trader survival evidence*. The 30-day paper window
is the only way to get that.

Don't rush past it. The June 30 deadline is real but it's not worth blowing
up your account to hit it.
