# Master Execution Plan
Last updated: 2026-04-26
Status: Draft — incorporates round-1 peer reviews; awaiting Ibby red-line on plan-level commitments.
Supersedes: `outputs/planning/sprints-29-38-plan.md` v1, `sprints-29-38-plan-v2.md`.

This plan covers two phases:

- **Phase 1 — Hardening + paper-trading ready (sessions 29–38, ~11 working days).**
  Land a paper-trading platform with one validated 6E strategy, 30-day
  discipline window opened.
- **Phase 2 — Paper window operations + live readiness + first live trades
  (sessions 39–55, ~30 calendar days + ~10 working days for live ramp).**
  Run the 30-day paper window, complete the live-readiness gate, plumb live
  execution, place the first micro-contract live trade, scale by rule.

After Phase 2 the platform is operating with live capital on a single
strategy. Track G (ML), Track H (pairs / second strategy), and further
expansion live beyond session 55.

---

## Phase 1 — sessions 29–38

### Goal
- 6E strategy `vwap-reversion-v1` validated through pre-committed gate (sprint 33).
- Paper-trading loop end-to-end with circuit breakers, reconciliation,
  featureset hash check.
- CLI status + daily HTML + validate-strategy linter.
- 30-day paper window OPEN at sprint 36.

### Daily schedule (11 working days)

| Day | Sub-sprints | Models | Hard constraint |
|---|---|---|---|
| 1 | 29a → 29b ‖ D1 | Opus, Sonnet, Sonnet | Track A done |
| 2 | 29c ‖ 29d | Sonnet, Gemini | 29a/b DONE |
| 3 | 30a → 30b ‖ D2 | Sonnet, Opus, Sonnet | 29 fully DONE |
| 4 | 31a → 31b ‖ D3 | Opus, Sonnet, Sonnet | 30 DONE |
| 5 | 32a → 32b ‖ D4 ‖ F2 | Opus, Sonnet, Sonnet, Gemini | 31 DONE |
| 6 | 33a → 33b ‖ F1 ‖ B1 | Sonnet, Opus, Gemini, Gemini | 31, 32 DONE |
| 7 | 34a → 34b ‖ F3 | Opus, Sonnet, Gemini | 33 PASS or escape |
| 8 | 35a → 35b → 35c | Sonnet, Opus, Sonnet | Track D complete |
| 9 | 36a → 36b | Sonnet, Opus | 35 DONE |
| 10 | 37a → 37b ‖ 37c | Opus, Sonnet, Gemini | 36 DONE; window OPEN |
| 11 | 38a → 38b ‖ 38c → 38d | Opus, Sonnet, Gemini, Opus | 37 DONE |

‖ = parallel-eligible. See [`dependency-dag.md`](dependency-dag.md).

### Per-session navigation

| Session | Folder | Goal |
|---|---|---|
| 29 | [`../sessions/29-strategy-foundation/`](../sessions/29-strategy-foundation/) | Strategy Protocol coupling, sizing, OU bounds, naming |
| 30 | [`../sessions/30-6e-backtest-v1/`](../sessions/30-6e-backtest-v1/) | First v1 backtest with cost-sensitivity sweep |
| 31 | [`../sessions/31-regime-filter/`](../sessions/31-regime-filter/) | Regime filter + true walk-forward |
| 32 | [`../sessions/32-mulligan/`](../sessions/32-mulligan/) | Mulligan scale-in with directional gate |
| 33 | [`../sessions/33-track-c-gate/`](../sessions/33-track-c-gate/) | The pre-committed 7-criterion gate |
| 34 | [`../sessions/34-bridge-pick/`](../sessions/34-bridge-pick/) | TS SIM vs TV Pine port |
| 35 | [`../sessions/35-paper-loop/`](../sessions/35-paper-loop/) | End-to-end paper-trading loop |
| 36 | [`../sessions/36-first-paper-trade/`](../sessions/36-first-paper-trade/) | First paper trade; 30-day window opens |
| 37 | [`../sessions/37-hardening/`](../sessions/37-hardening/) | Cleanup punch-list |
| 38 | [`../sessions/38-traders-desk/`](../sessions/38-traders-desk/) | Trader's-desk polish + readiness review |
| B1 | [`../sessions/B1-timeframe-catalog/`](../sessions/B1-timeframe-catalog/) | Gemini side-quest |
| D1–D4 | [`../sessions/D1-loss-limits/`](../sessions/D1-loss-limits/) etc. | Circuit breaker family |
| F1–F3 | [`../sessions/F1-html-enhancements/`](../sessions/F1-html-enhancements/) etc. | UX polish |

### Phase 1 acceptance gate

Phase 1 is complete when ALL are true:
- [ ] Sprint 33 gate verdict committed (PASS or named escape path).
- [ ] If PASS path taken: paper-trading loop running on real-time SIM/TV with
      first trade closed.
- [ ] All Track D circuit breakers drilled successfully.
- [ ] `trading-research status` and `trading-research validate-strategy`
      commands work.
- [ ] 30-day paper discipline window declared open.
- [ ] Three-persona readiness review (38d) signed READY for "platform carries
      strategy through rest of window."

If any of the above is NOT true at sprint 38, Phase 2 entry is gated until
they are.

---

## Phase 2 — sessions 39–55

Detailed plan: [`product-roadmap-to-live.md`](product-roadmap-to-live.md).

### Phase 2 phases (terminology overload — sub-phases of Phase 2)

**Phase 2A: 30-day paper window operations (sessions 39–44, ~30 calendar days)**
- Daily morning checks; weekly reviews; mid-window cost-model recalibration
  if needed; no knob changes (would restart window).

**Phase 2B: Live readiness gate (sessions 45–46, ~2 days intensive)**
- Three-persona evaluation of 30 days of paper evidence; risk-of-ruin
  analysis; first-live-trade size determination.

**Phase 2C: Live execution plumbing + drill (sessions 47–48, ~3 days)**
- TS LIVE API (distinct from SIM); kill switches drilled against real broker
  account fingerprints; idempotent live order submission.

**Phase 2D: First live trades + scaling (sessions 49–50, ~2 days + ongoing)**
- One micro-contract live trade; post-trade review; scaling rule documented
  before adding a second contract.

**Phase 2E: Multi-strategy expansion (sessions 51–55)**
- Second strategy on 6A or 6C in paper while 6E continues live; promote when
  it clears its own 30-day window; Track G/H decision point.

---

## Plan-level commitments requiring Ibby red-line

These shape every per-model spec. Confirm before any sub-sprint begins.

| # | Commitment | Source |
|---|---|---|
| 1 | Walk-forward terminology fix: sprint 30 is contiguous-test; sprint 31, 33 are walk-forward when fitted | DS round-1 |
| 2 | Sprint 29 spans two days (four sub-sprints) | Architect round-1 |
| 3 | Cost-sensitivity sweep grid {0.5, 1.0, 2.0, 3.0} ticks for sprint 30 | Mentor round-1 |
| 4 | Knob defaults: `entry_threshold_atr=2.2`, `entry_blackout_minutes_after_session_open=60`, flatten time from instrument settlement | Mentor round-1 |
| 5 | Track C gate has seven criteria, all pre-committed | DS + Mentor round-1 |
| 6 | Sprint 36 is the START of the 30-day discipline window, not its end | Mentor round-1 |
| 7 | Multi-model handoff protocol + Gemini playbook + dispatcher routing rules adopted as policy | All round-1 |
| 8 | Phase 2 plan (sessions 39–55) added to roadmap | Round-2 product question |
| 9 | First live trade uses one micro contract (M6E) only; scaling requires explicit rule | Round-2 mentor |
| 10 | Live capital decision is Phase 2D, not Phase 1 | All round-1 + round-2 |

---

## Risks

See [`risk-register.md`](risk-register.md).

## Persona reviews

- **Round 1** (plan-quality review): see [`../peer-reviews/round-1-summary.md`](../peer-reviews/round-1-summary.md).
- **Round 2** (product-question review — what we'll have, what we won't, what's still needed for live): see [`../peer-reviews/round-2-synthesis.md`](../peer-reviews/round-2-synthesis.md) plus per-persona files.

## Out of scope (explicit)

Phase 1 + Phase 2 deliver paper trading + first micro-contract live trade
+ second-strategy paper. The following remain out of scope through session 55:

- ML capability in production (Track G — sessions 56+).
- Pairs trading framework (Track H — sessions 56+).
- Web dashboard, mobile, real-time WebSocket UI.
- Multi-user / cloud deployment.
- Tax-lot tracking and P&L reporting for tax purposes (manual until session 56+).
- Third instrument beyond the 6E + 6A/6C set.
- CI/CD beyond local `uv run pytest`.
