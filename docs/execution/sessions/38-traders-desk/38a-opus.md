═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           38a-opus
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  37b, 37c (DONE)
Hand off to:       38b-sonnet, 38c-gemini
Branch:            session-38-traders-desk
═══════════════════════════════════════════════════════════════

# 38a — gui/replay audit + UX design pass

## Self-check
- [ ] I am Opus 4.7.
- [ ] 37b, 37c DONE.

## What you produce

### 1. `38a-gui-audit.md` (architect's catch)

Before designing any new HTML, audit existing:
- What does `src/trading_research/gui/` contain? What does it render?
- What does `src/trading_research/replay/` contain? What does it render?

For each "trader's desk" need (status, P&L, last trades, breaker state),
decide: **extend** existing, **reuse** existing, or **replace** existing.
Any "replace" needs a written justification.

### 2. `38a-traders-desk-spec.md`

The morning routine: what does Ibby do at 8:30 AM ET?

One CLI command OR one HTML page that answers all of:
- Is paper-trading loop running? Last heartbeat?
- Today's P&L vs daily limit. Week's P&L vs weekly limit.
- Open positions + combined risk.
- Last 10 trades with live-vs-shadow divergence column.
- Circuit-breaker state across all levels.
- Featureset hash on running data.
- 30-day discipline window day count.

Plus `validate-strategy` linter spec.

## Acceptance
- [ ] `38a-gui-audit.md` committed with extend/reuse/replace decisions.
- [ ] `38a-traders-desk-spec.md` committed.
- [ ] Handoff: `docs/execution/handoffs/38a-handoff.md`.
- [ ] current-state.md: 38a → DONE; 38b, 38c → READY.

## What you must NOT do
- Build new HTML without auditing existing first.
- Halt the running paper strategy.

## References
- Architect §9 audit requirement.
