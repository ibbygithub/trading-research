═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           44
Required model:    Opus 4.7 + Sonnet 4.6 (split)
Effort:            L (~3-4 hr total)
Entry blocked by:  43 (DONE), calendar +30 trading days from window open
Hand off to:       45
Branch:            session-44-eow-evaluation
═══════════════════════════════════════════════════════════════

# 44 — End-of-window evaluation (the big one)

## Sub-split

| Sub | Model | Workload |
|---|---|---|
| 44a | Sonnet 4.6 | Generate comprehensive 30-day paper-trading report (data + bootstrap CIs + comparisons against sprint 33 backtest CIs + featureset hash drift incidents + heartbeat firings) |
| 44b | Opus 4.7 | Three-persona evaluation |

## 44a deliverable
`30-day-window-evaluation-report.html`:
- Equity curve.
- Trade-by-trade live-vs-shadow divergence statistics.
- Realised Calmar, Sharpe, max consecutive losses, drawdown duration with bootstrap CIs.
- Comparison against sprint 33 CIs: where did paper land?
- Featureset hash drift incidents (zero expected).
- Heartbeat firings count.

## 44b deliverable
`30-day-window-evaluation.md` with three persona blocks:
- **Mentor:** did Ibby psychologically handle the worst drawdown? Behavioural metrics support real money?
- **Data Scientist:** realised performance inside sprint 33's CI? If not, direction and structural reason?
- **Architect:** any operational surprises? Near-misses with circuit breakers? Data feed gaps?

Verdict: **PROCEED / EXTEND / HALT**.

## Acceptance
- [ ] Comprehensive report (44a) committed.
- [ ] Three persona blocks (44b) committed.
- [ ] Verdict explicit.
- [ ] If PROCEED: session 45 is unblocked.
- [ ] If EXTEND: cycle 39-44 repeats with explicit duration.
- [ ] If HALT: full halt, escalation to Ibby for next steps.
- [ ] Strategy still RUNNING (unless verdict is HALT).
- [ ] Handoff: `docs/execution/handoffs/44-handoff.md`.

## What you must NOT do
- Skip a persona.
- PROCEED without all CIs reported.
- Advance to live without an explicit verdict.
