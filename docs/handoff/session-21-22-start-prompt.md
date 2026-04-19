# Session 21 + 22 Start Prompt
# Copy everything below this line into a fresh Claude Code terminal.
# ─────────────────────────────────────────────────────────────────────────────

You are starting a combined Session 21 + Session 22 for the trading-research
project. Both sessions happen in this terminal. Do them in order — finish 21
completely before starting 22.

## Where everything lives

Project root: C:\git\work\Trading-research\
Active branch: develop
CLAUDE.md (project rules + personas): C:\git\work\Trading-research\CLAUDE.md
Global rules: C:\Users\toddi\.claude\CLAUDE.md

Read these before doing anything else:
1. CLAUDE.md (project rules, personas, standing rules)
2. docs/handoff/platform-status-2026-04-19.md — complete platform status
3. docs/handoff/next-actions.md — what's pending and why

## Current state (end of Session 20)

Sessions 02–20 complete. Test suite: **386 passed, 1 skipped** (OI-013,
SHAP/numba Windows bug — not a code bug), 0 failed.

The platform is now instrument-agnostic. ZN has a 14-year history through
CLEAN and FEATURES. 6A has a Jan 2024 CLEAN sample (pipeline confirmed
working; full historical pull is a future data task).

The `verify` command shows 4 stale ZN CLEAN files — pre-existing path
mismatch in manifests from an earlier session, not a code bug. The 6A CLEAN
files all show OK.

---

## SESSION 21 — docs/pipeline.md Refresh

### Objective

`docs/pipeline.md` is the "read after three months away" document. The data
architecture sections are accurate, but the document was written after
Sessions 05–06 and does not cover anything built in Sessions 11–20.

Refresh it so a cold reader (or Claude in a new session) understands the
full current pipeline without needing to reconstruct it from work logs.

### What to add

**Statistical rigor layer** (Sessions 11–13, 17–18):
- Probabilistic Sharpe Ratio (PSR) and Deflated Sharpe Ratio (DSR) — what
  they compute, why Calmar is the headline metric but DSR is the honest
  Sharpe, where they appear in the report
- Bootstrap confidence intervals on all key metrics — how they're computed,
  what the CI columns mean in output
- Trials registry (`runs/.trials.json`) — what it is, why it exists (DSR
  requires knowing how many strategy variants were tested), how the registry
  is written and read, what happens when you skip it

**Walk-forward engine** (Sessions 10, 12–13):
- Purge/embargo gaps — why they exist (label leakage from multi-bar exits),
  how they're sized (default 5 bars), what "purged walk-forward" means
- Per-fold output — what the fold table in the report shows, what to look for
- How to run: `uv run trading-research walkforward --strategy <yaml>`

**Event-day blackout system** (Session 19):
- Three calendars: `configs/calendars/fomc_dates.yaml`, `cpi_dates.yaml`,
  `nfp_dates.yaml` — 2010–2025, manually verified
- `src/trading_research/strategies/event_blackout.py` — `load_blackout_dates()`
  returns a `frozenset[date]`; zero external dependencies
- How it wires into strategy code: entry signals suppressed on blackout dates,
  exit signals preserved so open positions can close

**Instrument generalization** (Session 20):
- The pipeline is now instrument-agnostic. `rebuild clean --symbol 6A` works.
- RTH windows are read from `InstrumentRegistry` (instruments.yaml), not
  hardcoded. ZN: 08:20–15:00 ET; 6A/6C/6N: 08:00–17:00 ET.
- `last_trading_day_quarterly_cme()` applies to any CME quarterly contract
  (ZN, 6A, 6C, 6N).
- 6A full historical pull is a future task — the code is ready.

**Updated cold-start checklist** — add steps 8–10:
```
8.  uv run trading-research backtest --strategy configs/strategies/<name>.yaml
    # run the backtest; output goes to runs/
9.  uv run trading-research walkforward --strategy configs/strategies/<name>.yaml
    # run purged walk-forward; same output directory
10. uv run trading-research report <strategy-id>
    # generate the 24-section HTML report from the backtest run
```

**Updated related documents** — add:
- `src/trading_research/strategies/event_blackout.py`
- `configs/calendars/` — FOMC, CPI, NFP dates
- `src/trading_research/eval/` — PSR/DSR, bootstrap CI, walk-forward engine

### What NOT to change

- The three-layer model explanation — it's accurate and clean
- The directory layout section — update the example listing to add 6A files,
  but do not change the structure explanation
- The manifest schema — it's accurate
- The "What NOT to do" section — still correct
- The worked example (13-minute experiment) — keep it, it's still valid

### Success criteria

- One reader, cold, can understand the full pipeline end-to-end from the doc
- All CLI commands are documented with examples
- The data-scientist would not flag a missing validation step
- The quant-mentor would not find a strategy workflow step not covered

---

## SESSION 22 — ZN Strategy v2: Design Conversation + Implementation

### Before writing any code: read the evidence

**The v1 result** (Session 19 backtest + walk-forward):
```
Total trades:        10,631     Win rate:           3.9%
Calmar:               -0.04     Sharpe (ann.):    -21.32
Expectancy/trade:    -$64.38    Trades/week:        12.64
Max consec. losses:      300    Max drawdown:   -$684,366
```

Walk-forward: 10 folds, 10 failures. Sharpe -20 to -23 across all folds,
all time periods 2010–2024. Not a regime problem. A hypothesis problem.

**The two structural causes** (from the data scientist's diagnosis):

1. **No RTH filter.** 75.5% of entries were overnight (outside 08:20–15:00
   ET). These generate near-immediate EOD flat losses (commission + slippage
   only). The 24h feature parquet fires signals on every bar including 11pm.
   RTH win rate is 11.2% — still deeply negative, so this alone won't fix it,
   but it's mandatory regardless.

2. **MACD zero-cross exit is not a price exit.** The histogram can cross zero
   while price is below entry. The pattern: enter long when histogram is
   fading toward zero (momentum uncertain), exit when histogram crosses back
   above zero (momentum confirmed) — but at whatever price that is, which is
   frequently below entry. The strategy enters when momentum is uncertain and
   exits when momentum confirms, but price doesn't follow on the same
   timeframe. This is the root cause of the 11.2% win rate.

### The design conversation

Before the data scientist or the quant mentor weigh in on implementation,
*think through the v2 hypothesis together*. There are two candidate
directions:

**Candidate A — Flip the entry (quant mentor's suggestion):**
Enter on confirmed zero-cross (histogram crosses above zero from below =
momentum has turned bullish). Exit at a price target (session VWAP, ATR
multiple from entry, or prior resistance). RTH only.

The logic: the v1 failure was "enter before confirmation, exit on
confirmation." Candidate A flips it: "enter on confirmation, exit at price."
This has a long pedigree in trend-following. The risk is that zero-cross
entries often chase moves — you're buying after the turn, not before it.

**Candidate B — VWAP structural mean reversion (Ibby's suggestion):**
Entry trigger: price reaches VWAP ± 2σ (the outer Bollinger band on VWAP).
Confirmation: MACD histogram is fading (in the direction of mean reversion)
or has turned. Exit: price reverts to VWAP (the mean). RTH only.

The logic: ZN is a mean-reverting instrument. 2σ from VWAP is a structural
level — institutions defend it. The entry is at a price extreme, not a
momentum signal. The target is explicit (VWAP). This is closer to the
original mean-reversion thesis.

**The quant mentor should:**
- Give his honest take on A vs B, or a hybrid
- Identify what he'd want to see in the data before committing to either
- Point out the failure modes in both (A: chase risk; B: trending days where
  price blows through 2σ and doesn't revert)
- Ask: what does ZN actually do at VWAP 2σ during RTH? Is there a mean-
  reversion tendency we can measure, or is this just a chart pattern?

**The data scientist should:**
- State the conditions under which each hypothesis would be falsifiable
- Identify what the minimum viable test looks like (trade count, OOS period)
- Ask: are VWAP and Bollinger bands available in the current FEATURES parquet
  for 5m? (Yes — VWAP and Bollinger are in base-v1)
- Flag the look-ahead risk in VWAP 2σ: the daily VWAP at bar T is computed
  from bars 1..T, so it's valid for real-time use. The σ bands use the same
  rolling window. No look-ahead if implemented correctly.

**Ibby decides** which direction (or hybrid) to proceed with.

### Implementation (after the design conversation settles on a hypothesis)

Write the strategy hypothesis precisely before touching code:
  "When ZN reaches [price level] within RTH, and [momentum condition],
   enter [direction] with stop at [price] and target at [price]."

Then implement:

1. If proceeding with a new hypothesis, create a new strategy file:
   `src/trading_research/strategies/zn_[name].py`
   `configs/strategies/zn-[name]-v1.yaml`
   Do NOT modify the v1 files — they're the baseline for comparison.

2. The RTH filter is non-negotiable regardless of direction. Zero signals
   outside 13:20–20:00 UTC (08:20–15:00 ET). The instruments.yaml RTH hours
   are the source of truth; use them via InstrumentRegistry.

3. Exit must be price-based. No indicator-based exits (that's what killed v1).
   Options: VWAP (already in features), ATR multiple from entry, fixed ticks.

4. Run the backtest on the full ZN history (2010–2026).
   File: `data/features/ZN_backadjusted_5m_features_base-v1.parquet`

5. Report the headline numbers vs. v1:
   - Win rate (v1: 3.9% full, 11.2% RTH-only)
   - Calmar (v1: -0.04)
   - Trades/week (v1: 12.64)
   - Max consecutive losses (v1: 300)

6. If the backtest passes the "looks real" bar (Calmar > 0, win rate > 40%,
   trades/week > 2), run the walk-forward.

7. Update the trials registry (`runs/.trials.json`) so DSR accounts for the
   number of variants tested.

### What NOT to do in Session 22

- Do not tune parameters to improve a result that already looks broken.
  If the first backtest shows Calmar < 0 and win rate < 30%, the hypothesis
  is wrong — redesign, don't optimize.
- Do not add more than one new filter at a time. If you add an RTH filter
  AND a VWAP filter AND a regime filter in one go, you can't diagnose which
  one helped.
- Do not touch the v1 strategy files. They are the comparison baseline.
- Do not start on 6A strategy work — this session is ZN only.

### Success criteria for Session 22

Minimum acceptable outcome:
- A precisely stated v2 hypothesis (one or two sentences, testable)
- RTH filter implemented and verified
- First backtest run with an honest result reported

Good outcome:
- Win rate > 40% on the RTH-filtered backtest
- Calmar > 0

Excellent outcome:
- Walk-forward passes with DSR > 0 on at least 6 of 10 folds
- The data scientist calls it "this one might actually be real"

---

## Personas (always active)

Both persona files are always loaded:
- .claude/rules/quant-mentor.md
- .claude/rules/data-scientist.md

In Session 22, the quant mentor should be vocal about the v2 hypothesis — he's
the one who said "the 'enter before confirmation, exit on confirmation' pattern
consistently fails." In the design conversation, push him for a concrete
take, not a balanced presentation of options.

The data scientist should flag any look-ahead risk in the v2 indicator setup
and state the minimum sample size needed before any result is meaningful.

---

## Write work logs before stopping

Session 21 work log: outputs/work-log/YYYY-MM-DD-HH-MM-session-21-summary.md
Session 22 work log: outputs/work-log/YYYY-MM-DD-HH-MM-session-22-summary.md

Write each log when its session completes, before starting the next one.
