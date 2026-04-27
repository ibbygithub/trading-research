# Session 38 — Trader's-desk polish + readiness review

**Status:** Spec — closes 10-sprint cycle
**Effort:** 1 day, four sub-sprints (M+M+S+S)
**Depends on:** Sprint 37 (hardening complete)
**Unblocks:** continuation of 30-day paper window; future Track G/H/I sprints
**Personas required:** Architect (38a audit), All three (38d readiness)
**Hard rule:** does NOT advance to live capital. Confirms platform readiness for the rest of the 30-day window.

## Goal

Make the platform feel like a finished trader's desk for the morning routine.
One CLI command or one HTML page should answer: what's running, how is the
strategy doing, what's the circuit-breaker state, what trades happened
yesterday. Then the three personas review the whole 10-sprint cycle and sign
off — or list the gaps that block readiness.

## In scope

### 38a — Audit + UX design pass (Opus 4.7, ~2 hr)

**Architect's catch (review §9):** there is already `src/trading_research/gui/`
and `src/trading_research/replay/`. Sprint 38 must NOT build a new HTML cockpit
without first auditing what exists.

**Audit deliverable:** `38a-gui-audit.md`:
- What does `gui/` contain? What does it render?
- What does `replay/` contain? What does it render?
- For each "trader's desk" need (status, P&L, last trades, breaker state),
  decide: **extend** existing, **reuse** existing, or **replace** existing.
- Any "replace" decision needs a written justification — replacement is the
  most expensive answer.

**UX design deliverable:** `38a-traders-desk-spec.md`:
- The morning routine: what does Ibby do at 8:30 AM ET?
- One CLI invocation OR one HTML page that answers all of:
  - Is the paper-trading loop running? Last heartbeat?
  - Today's P&L vs daily loss limit. Week's P&L vs weekly limit.
  - Open positions + combined risk.
  - Last 10 trades with live-vs-shadow divergence column.
  - Circuit-breaker state across all levels.
  - Featureset hash on the running data.
  - 30-day discipline window day count.
- `validate-strategy` linter: a CLI command that reads a strategy YAML and
  checks: knob ranges valid, instrument supported by template, featureset
  available, OU bounds available for instrument-timeframe, sizing model
  consistent with risk-limits config.

### 38b — Implementation (Sonnet 4.6, ~3 hr)

**Outputs (depend on 38a's reuse/extend/replace decisions):**
- `src/trading_research/cli/status.py` — the `trading-research status` command.
- `src/trading_research/cli/validate_strategy.py` — the linter.
- Either an extension to `gui/` (if 38a chose extend) OR a single
  `daily_summary.html` template (if 38a chose reuse + add).
- Tests under `tests/cli/`.

### 38c — Polish (Gemini 3.1, ~1 hr)

This sub-sprint follows `outputs/planning/gemini-validation-playbook.md`.

**Outputs:**
- HTML/CSS theming consistency (against existing replay app aesthetic).
- Copy edits in CLI help text.
- Error messages for the linter (clear "what failed and how to fix").

**What Gemini must NOT do:**
- Modify the strategy, risk, or execution layers.
- Add or remove tests beyond cosmetic copy edits in test names.

### 38d — Three-persona readiness review (Opus 4.7, ~1 hr)

**Inputs:**
- All sprint outputs 29–38.
- All work logs.
- Paper-trading day count (likely day 3–5 by now, depending on calendar).

**Each persona writes a verdict block:**

```
## <Persona> readiness verdict — <READY / NOT READY: <reasons>>

Platform readiness for the rest of the 30-day paper window:
- ...

Items still required before live capital (NOT this sprint):
- ...

Items that should NOT block continuation of paper window:
- ...

Signed: <persona>
Date: 2026-...
```

**Mentor:**
- Strategy is genuinely behaving as the 6E recommendation predicted?
- Cost realism in the live trades?
- Behavioural metrics (consecutive losses, hold times) tolerable?
- ML deferral defended: "is there ANY case for starting Track G now?" Answer
  expected: no, not until 30 days of paper completes.

**Data Scientist:**
- Are the metrics on the live trades consistent with sprint 33's CIs?
- Featureset hash drift?
- DSR cohort bookkeeping intact across 35–38?
- Per-trade divergence stays within 30b's tolerance?

**Architect:**
- Coupling integrity holds (registry, sizing, OU bounds)?
- Any new hardcodings in 35–38 sprint code?
- Test coverage on touched modules adequate?
- Health-check command surfaces every active component?

**Synthesis:**
If all three sign READY, the platform carries the strategy through the
remainder of the 30-day window with no further sprint work required (any
sprint work after this is bonus polish or next-strategy preparation).

If any persona signs NOT READY, the listed items become the next sprint's
backlog (sprint 39+, outside this 10-sprint plan's scope).

## Acceptance

- [ ] `38a-gui-audit.md` and `38a-traders-desk-spec.md` committed.
- [ ] `trading-research status` runs and shows all required data points.
- [ ] `trading-research validate-strategy <yaml>` runs and catches the
      common config errors (test coverage on the linter).
- [ ] Three persona verdicts committed.
- [ ] Final synthesis decision committed: READY / NOT READY + items.
- [ ] ML deferral explicitly defended in 38d work log.

## Out of scope

- Live capital decision (sprint 48 territory).
- ML capability (Track G, sprints 38–42 in roadmap — deferred until 30-day
  window completes per CLAUDE.md and per 38d verdict).
- Multi-strategy.
- Web dashboard / mobile / real-time WebSocket UI.

## References

- `outputs/planning/peer-reviews/architect-review.md` §9
- `outputs/planning/peer-reviews/quant-mentor-review.md` §6, §8
- `src/trading_research/gui/`
- `src/trading_research/replay/`
- `docs/roadmap/sessions-23-50.md` Track G/I gating
