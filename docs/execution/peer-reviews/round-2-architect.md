# Round 2 — Architect Review
Date: 2026-04-26
Question set: What product do we have at end of session 38? What can it do?
What can't it do? What's left to make it production-ready for live money trading?

---

## Q1 — At end of session 38, what product do I have?

**An instrument-agnostic research and paper-trading platform with a clean
core:**

Core layer:
- `core/instruments.py` — Pydantic Instrument with tick_size, contract_multiplier,
  session schedule, settlement time, trading calendar, and (post sprint 29d)
  `tradeable_ou_bounds_bars` per timeframe. Single source of truth for every
  per-instrument fact.
- `core/strategies.py` — Strategy Protocol with three methods
  (`generate_signals`, `size_position`, `exit_rules`) and a Mulligan-freshness
  invariant promoted to docstring contract.
- `core/templates.py` — TemplateRegistry with Pydantic-validated knobs.
- `core/featuresets.py` — versioned featureset registry with hash-based
  identity.

Data layer:
- RAW → CLEAN → FEATURES three-layer model with manifest sidecars.
- `featureset_hash` propagated to features manifest.
- Calendar-aware quality validation.

Backtest layer:
- `BacktestEngine` consuming Strategy Protocol via `size_position` (post 29c).
- `walkforward.py` consuming TemplateRegistry (post 29b).
- Cost-sensitivity sweep machinery (post sprint 30).
- Trial registry with cohort fingerprinting on engine + code.

Risk layer:
- LossLimitMonitor with daily/weekly limits per scope (account / instrument
  / strategy).
- Inactivity heartbeat.
- Order idempotency + reconciler.
- Three-level kill-switch hierarchy.
- All four are drilled against fixtures.

Execution layer (paper):
- `Broker` Protocol with TS SIM concrete implementation (or TV reconciliation
  if escape path taken at sprint 33).
- Paper-trading loop with featureset hash check on every parquet swap (hard
  halt on mismatch).
- Trade-by-trade live + shadow-backtest record.
- Daily reconciliation report.

UX layer:
- `trading-research status` — one CLI command shows running state.
- `trading-research describe-template` / `list-templates` — knob-aware
  introspection.
- `trading-research validate-strategy` — config linter.
- HTML reports with composite ranking, DSR with trader-language, CI bars.
- Trial-comparison report with cross-cohort warnings.

This is a **mature research platform with a paper-trading bench attached**.
It is not yet a production trading system.

## Q2 — What can it do?

System capabilities at end of session 38:

1. **Add a new instrument by editing one config file.** No code changes
   needed. 6A/6C/6N enter as YAML entries in `instruments.yaml` plus a data
   download.
2. **Add a new strategy by registering a template.** Decorator-based
   registration, Pydantic knobs, walkforward and engine pick it up
   automatically.
3. **Run backtests with full provenance** via CLI. Every result reconstructable.
4. **Operate paper trading** with circuit breakers and reconciliation.
5. **Audit any historical run by trial ID** — code SHA, engine fingerprint,
   featureset hash, knobs, seed, results all linked.
6. **Catch featureset version drift** at runtime, not after a bad backtest.
7. **Drill kill switches** against fixtures. Each scenario has a test.
8. **Compare two trials side-by-side** with cross-cohort warnings.
9. **Validate a strategy config** before running it (catches knob ranges,
   instrument support, featureset availability).
10. **Open the platform fresh** and have a dispatcher route per-model work
    via routing-headed specs.

## Q3 — What can't it do?

Real architectural gaps for live trading:

1. **Live broker integration is missing.** TS SIM ≠ TS LIVE. Different auth,
   different endpoints, different settlement mechanics. Session 47 plumbs
   this; we haven't done it yet.
2. **Multi-strategy portfolio coordination — limited.** The execution loop
   in sprint 35 is single-strategy. Two strategies running simultaneously
   would share Engine state in a way that hasn't been designed for. Session
   54 addresses; until then, single-strategy live.
3. **Distributed deployment — none.** This is a local laptop platform. There
   is no service-node deployment, no high availability, no cloud failover.
   Per CLAUDE.md ground rules, that's intentional — but if Ibby's laptop
   crashes mid-trade, the strategy is offline until restart.
4. **Real-time data ingestion at scale — not load-tested.** One instrument,
   one timeframe, one strategy is fine. Multiple instruments simultaneously
   has not been pressure-tested.
5. **Model registry / ML deployment — Track G work.** No infrastructure for
   versioned ML model artifacts, retraining cadence, or feature-importance
   surfacing in production.
6. **Pairs strategy framework — Track H work.** Every strategy today is
   single-instrument. Pairs require margin-paired sizing, correlation-aware
   risk limits, and broker-margin reality checks not in scope.
7. **Backups / disaster recovery — not designed.** If the trial registry
   file is corrupted, history is lost. There is no automatic backup.
8. **Audit/compliance reporting — not designed.** Tax-lot tracking, year-end
   1256 reporting, regulator-ready trade history — none of this is built.
   Manual extraction from the trade log works; structured tax reports do not.
9. **Multi-user — single-user assumed throughout.** Locking, permissions,
   shared state mediation: none.
10. **Configuration immutability during a live session.** If Ibby edits
    a YAML during a live session, there is no lockfile preventing it.
    Probably a bug-class waiting to happen.

## Q4 — What's left to make it production-ready for live money trading?

In priority order, architect lens:

### 4.1 — TS LIVE API wrapper distinct from SIM (session 47)
Concrete `Broker` implementation against TS LIVE endpoints. Featureset
hash check applied at every order; preflight checks before any live order
submission; manual confirmation flag in execution config.

### 4.2 — Hard-tested kill switches against real broker (session 48)
Drill every D1–D4 scenario against the real (paper-mode-flagged) TS LIVE
account. Real-broker silence behaves differently than fixture silence;
real-broker order rejection messages differ from SIM. The drill catches
these before money moves.

### 4.3 — Backup + restore for trial registry, configs, paper-trading state
Currently `runs/.trials.json` is a single file. If it dies, history dies.

Required:
- Daily git commit of `runs/.trials.json` (it's small).
- Daily snapshot of `data/features/*.manifest.json` (also small).
- Paper-trading day-end state preserved as a parquet, not just a JSON line.
- Restore procedure documented: which file, where, how to verify.

This is one session of work, can be added to sprint 37 punch-list or
sprint 40 (paper window cleanup).

### 4.4 — Operational runbook
Plain markdown. "What to do when X breaks":
- Heartbeat fires falsely (D2 false positive) → check logs, dismiss, log
  the false positive count, escalate if rate > 1/day.
- Featureset hash mismatch → root cause: parquet rebuild during session.
  Procedure: halt, identify the rebuild source, restart the strategy with
  the new hash if intentional.
- Account-state mismatch → halt immediately. Reconcile against broker
  statement. Resume only after sign-off.
- Order rejected by broker → catalog of common reasons; what each means.
- Laptop crashed during open position → broker state is the truth; reconcile
  by reading positions from broker on restart.

This is one session of writing, not coding. Can slot at sprint 38 (38a UX
design) or session 50 (post-first-trade review).

### 4.5 — Recovery from broker outage
The heartbeat detects silence. The auto-flatten attempts to flatten. But
if the broker is down for an hour, the flatten itself can't complete.
Required:
- A "stuck" state distinct from "silent" — broker reachable but rejecting
  orders.
- Manual override path to acknowledge stuck state and proceed without
  flatten (Ibby's call, not the system's).
- Persistent state: if the system restarts during stuck-state, it remembers
  and does not silently re-arm.

Session 47 or 48 needs this.

### 4.6 — Account-state reconciliation against statements (T+1 reality)
At end of every trading day, compare:
- The platform's view of account equity, open positions, day's realised P&L.
- The broker's account statement (downloadable next day).

Mismatch is a HALT, not a "look at it later." T+1 mismatches happen because
fees post late, settlements move money, etc. The platform should distinguish
"fee posted late" (auto-resolve) from "position differs" (halt).

### 4.7 — Time-sync verification (NTP)
Live trading depends on accurate timestamps. A laptop clock that drifts
by 30 seconds during a session can produce a "trade that closed before it
opened" in the log. Required:
- On session start, verify system time is within 1 second of an NTP source.
- If not, halt and tell Ibby to sync.

One-line check, but it must be there.

### 4.8 — Failover thinking
"If my laptop crashes mid-trade, what happens?"
- Open positions exist on the broker side.
- Strategy state is gone; restart will reload.
- Pending orders may exist that the strategy state doesn't know about.

Required: on restart, query broker for all open positions and pending
orders, reconcile against strategy state, and either adopt-and-continue
or halt with a manual prompt. Default: HALT and prompt.

### 4.9 — Configuration immutability during a live session
Lockfile mechanism: live trading enabled requires `live-trading.lock` file
absent; system creates it at session start; system removes on clean
shutdown; if a YAML changes while lockfile present, the system halts.

Prevents the "I tweaked one parameter while the strategy was running and
everything went weird" failure mode.

### 4.10 — Per-instrument margin headroom check before order submission
Already in Phase 2C session 47 spec. Architect emphasis: this is not
"check available margin" — it's "check available margin × 2× safety factor"
because TradeStation can change margin requirements intraday.

---

## What I will sign off on

I will sign session 45's live-readiness gate (criteria L6, L7) on the
condition that 4.1–4.5 above are satisfied. 4.6–4.10 are mostly Phase 2C
work and can be in scope of sessions 47–48; if they aren't, I sign with
explicit caveat.

The platform at end of session 38 is structurally sound for paper trading.
It is structurally incomplete for live trading. The increment is real,
finite, and manageable across sessions 47–48. It is not optional.

What I want to flag for Ibby personally: the architectural debt that
matters most is the LIVE/SIM split. Don't let session 47 turn into "we'll
basically reuse the SIM code." TS LIVE is a different code path with
different failure modes. Treat it as such.
