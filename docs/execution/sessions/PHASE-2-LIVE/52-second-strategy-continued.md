═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           52
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  51 (DONE)
Hand off to:       53
Branch:            session-52-second-strategy
═══════════════════════════════════════════════════════════════

# 52 — Second-strategy continued: regime filter + Mulligan + walk-forward

Mirrors sprints 31, 32, 33a (sub-sprints C through walk-forward) for the second strategy. Reuses the regime-filter module and Mulligan logic from 6E work.

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 51 DONE; second-strategy backtest v1 exists.
- [ ] Live 6E continues running.

## What you implement
- If 6A/6C stationarity classifies similarly to 6E: same template family, just retuned knobs.
- If different: select strategy class per session 28-style follow-up.
- Run walk-forward (true rolling-fit if any parameter is fitted).
- Trial registry records.

## Acceptance
- [ ] Walk-forward report for second strategy.
- [ ] Trial records committed.
- [ ] Live 6E unaffected.
- [ ] Handoff: `docs/execution/handoffs/52-handoff.md`.
- [ ] current-state.md: 52 → DONE; 53 → READY.

## What you must NOT do
- Touch live 6E code.
- Promote second strategy live.
