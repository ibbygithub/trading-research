# Sprints 34–38 — Plan v3 (Research Lab Reflow)

**Status:** Active. Supersedes sessions 34–38 in plan v2.
**Authorized:** 2026-05-03 (Ibby in-conversation)
**Foundation doc:** `outputs/planning/34a-operating-model-reset.md`

This addendum replaces the bridge/paper/live trajectory in plan v2 sessions
34–38 with a research-lab capability buildout. The validation-gate
methodology (sprint 33 seven criteria) is retained but reserved for the
live-capital transition. See operating-model reset doc for the framing
rationale; this doc is the per-session contract.

---

## Session 34 — Operating-model reset + 6A/6C pipelines + first new strategies

**Status:** Active session.
**Effort:** ~1 day.
**Personas required:** Mentor (strategy design), Architect (planning sign-off), Data Scientist (validation/exploration distinction).

### Deliverables

1. **Operating-model reset doc** — `outputs/planning/34a-operating-model-reset.md`. Documents the lab-vs-pipeline distinction, drops June 30, defines exploration vs validation modes. Three persona sign-offs.
2. **Plan v3 addendum** — this file.
3. **6A and 6C pipelines** — full RAW → CLEAN → FEATURES for both instruments, 2010-01-01 → today. Validates that the Track A pipeline remains generic.
4. **Two mentor-designed strategies** — written design specs (rationale, market thesis, entry/exit rules, risk envelope), then implemented as Python modules + YAML configs. Mentor picks the ideas; data scientist signs off on the methodology surface; architect signs off on the implementation shape.
5. **Backtest evidence** — both strategies run on at least one of {6A, 6C} and produce a trade log, equity curve, and per-trial entry in the registry. Exploration mode, no validation gate applied.

### Acceptance

- [ ] Reset doc + plan v3 committed.
- [ ] 6A 1m CLEAN parquet covers 2010-01-01 → today with structural quality pass.
- [ ] 6C 1m CLEAN parquet covers 2010-01-01 → today with structural quality pass.
- [ ] 5m, 15m, 60m features parquets exist for both 6A and 6C.
- [ ] Two new strategy modules in `src/trading_research/strategies/` with passing unit tests on indicator math and signal generation.
- [ ] Two new YAML configs in `configs/strategies/`.
- [ ] At least one backtest per strategy logged in `runs/.trials.json` with `mode: "exploration"` (or noted in the work log if the schema field is not yet added).

### Out of scope

- The validation gate (no walk-forward + bootstrap + DSR ceremony in this session).
- Strategy template authoring system (session 36).
- Parameter sweeps (session 35).
- Bridge / paper / live work (deferred).

---

## Session 35 — Parameter-sweep tool + N-trial leaderboard

**Effort:** ~1 day.
**Personas required:** Architect (interface), Data Scientist (sweep semantics).

### Deliverables

1. **Sweep CLI** — `trading-research sweep --template <strat> --param key1=v1,v2,v3 --param key2=a,b --instrument 6A --timeframe 5m`. Generates the cartesian product of param values, runs each as an exploration trial, writes results to the registry.
2. **Leaderboard CLI** — `trading-research leaderboard --filter mode=exploration --filter instrument=6A --sort calmar` produces a sorted HTML and CLI table with columns: trial_id, strategy, instrument, timeframe, calmar, sharpe, max_dd, win_rate, n_trades, mode.
3. **Trial registry schema migration** — add `mode` field (exploration | validation) and `parent_sweep_id` field (groups variants from one sweep). Backfill existing trials as `mode: "validation"`.
4. **Tests** — sweep produces N trials for N parameter combinations; leaderboard reads them back and ranks correctly.

### Acceptance

- [ ] Sweep command runs a 12-variant cartesian product against an existing strategy and instrument; 12 trials appear in the leaderboard.
- [ ] Leaderboard supports filter and sort flags; HTML output is generated.
- [ ] Existing trials still load (backwards-compatible schema).

### Out of scope

- Multi-instrument sweeps in one command (can be done as separate sweeps).
- Optimization search (this is grid sweep; bayesian/random comes later if needed).

---

## Session 36 — YAML-only strategy authoring

**Effort:** ~1 day.
**Personas required:** Architect (template design), Mentor (semantics review).

### Deliverables

1. **Template strategy class** — `src/trading_research/strategies/template.py` parses a YAML file describing entry conditions (indicator-based predicates), exit conditions (target/stop/time/signal-flip), and position-sizing knobs. Implements the Strategy protocol so the existing engine runs it unmodified.
2. **YAML strategy schema** — documented in `docs/strategies/yaml-strategy-schema.md`. Supports: indicator references (by feature-set column name), comparison predicates (>, <, crossed_above, crossed_below), AND/OR composition, regime filters as composable layers.
3. **Three reference templates ported** — three of the existing Python strategies expressed as YAML to prove the schema covers real cases. The Python files remain as the engine but the new way to author is YAML.
4. **CLI** — `trading-research backtest --strategy-yaml configs/strategies/<file>.yaml --instrument 6A --timeframe 5m` runs the YAML strategy through the existing engine.

### Acceptance

- [ ] A new strategy can be authored in YAML alone, no Python edits, and run end-to-end.
- [ ] The three ported templates produce backtest results within rounding tolerance of their Python equivalents.
- [ ] Schema docs are clear enough that a non-author can write a new strategy from them.

### Out of scope

- Visual strategy builder (a UI is out of scope; YAML is the surface).
- ML-augmented strategies (rule-based templates only).

---

## Session 37 — Multi-timeframe + composable feature/regime layers

**Effort:** ~1 day.
**Personas required:** Mentor, Data Scientist.

### Deliverables

1. **Multi-timeframe signal logic** — YAML strategy schema extended to reference indicators from a higher timeframe (e.g. "use 60m EMA as bias filter, 5m for entries"). The features layer already produces multi-TF parquets; this exposes them in the strategy schema.
2. **Composable regime filter layer** — regime filters (volatility, trend, time-of-day, event-blackout) become reusable YAML blocks that any strategy can include by reference. Builds on the work from session 31.
3. **Feature set v2** — adds any indicators commonly requested but not yet in base-v1 (candidates: stochastic, CCI, Keltner channels, OBV, session VWAP variants). Decision in-session based on what the strategy designs in 34/36 actually need.
4. **Backwards compatibility** — strategies authored in session 34/36 with single-TF logic continue to run unchanged.

### Acceptance

- [ ] A strategy YAML can reference both 5m and 60m indicators in one config; engine joins them correctly with no look-ahead.
- [ ] A regime filter defined once can be included by reference in multiple strategy configs.
- [ ] Feature set v2 documented; v1 still loadable.

### Out of scope

- Adaptive regime detection (this is rule-based regime filtering; ML regime classifiers later if needed).

---

## Session 38 — First structured exploration

**Effort:** ~1 day; this is the payoff session for the lab.
**Personas required:** all three.

### Deliverables

1. **Five hypotheses, written and committed** — short market-structure-anchored strategy ideas the mentor proposes. Examples (placeholders, not commitments): 6A session-VWAP fade in London/NY overlap; ZN MACD pullback with ATR stop; 6E breakout on Asian-session range expansion; 6A/6C pairs spread mean reversion; 6N ATR-band mean reversion.
2. **Twenty variants per hypothesis** — parameter sweep for each (using session-35 tooling) producing ~100 exploration trials.
3. **Leaderboard report** — top variants by Calmar, by Sharpe, by profit factor, by max consecutive losses (lowest), and by trade count (filtered to a sensible range). All clearly tagged `mode: "exploration"`.
4. **Mentor + data scientist commentary** — short written notes on which results are interesting and why; which look like artifacts; which are surprising. No pass/fail; this is exploration.
5. **Candidate(s) shortlist** — zero, one, or more strategies identified as worth taking through the validation gate in a future session. If zero, that's a legitimate outcome — the lab worked, it just didn't find an edge yet.

### Acceptance

- [ ] ~100 exploration trials in the registry.
- [ ] Leaderboard report committed to `outputs/`.
- [ ] Written commentary from mentor and data scientist.
- [ ] Explicit decision (yes/no/maybe) on each hypothesis: shortlist for validation, drop, or iterate.

### What this session is NOT

- Not a validation gate run. None of these trials are being approved for capital.
- Not a deployment-readiness review. The lab proves out; live capital is a separate decision triggered by a successful validation run on a shortlisted candidate.

---

## What returns to the plan after session 38 (deferred work)

When a candidate strategy passes the validation gate, the following deferred
work is reactivated and slotted into a fresh sprint plan:

- TradeStation SIM API integration (was sprint 34b in v2).
- TradingView Pine port path (was sprint 34b alternate in v2).
- Paper-trading loop (was sprint 35 in v2).
- Live-vs-backtest divergence reconciliation (was sprint 36 in v2).
- Trader's-desk polish + readiness review (was sprint 38 in v2).

None of this is wasted. It is on hold.

---

## Summary table

| Session | Theme | Primary deliverable |
|---|---|---|
| 34 (this) | Reset + first instruments + first strategies | 6A/6C pipelines, two new strategies, plan v3 |
| 35 | Sweep + leaderboard | `sweep` and `leaderboard` CLIs, mode-tagged trials |
| 36 | YAML strategy authoring | Author strategies without writing Python |
| 37 | Multi-TF + composable regimes | Cross-timeframe logic, reusable regime filter blocks |
| 38 | Structured exploration | ~100 exploration trials, candidate shortlist |
| Deferred | Bridge / paper / live | Reactivated when a candidate passes validation |
