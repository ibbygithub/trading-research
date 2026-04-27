═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           38b-sonnet
Required model:    Sonnet 4.6
Effort:            M (~3 hr)
Entry blocked by:  38a (DONE)
Parallel-OK with:  38c
Hand off to:       38d-opus
Branch:            session-38-traders-desk
═══════════════════════════════════════════════════════════════

# 38b — Status + linter implementation

## Self-check
- [ ] I am Sonnet 4.6.
- [ ] 38a DONE; gui-audit and traders-desk-spec exist.

## What you implement

Per 38a's extend/reuse/replace decisions:
- `src/trading_research/cli/status.py` — `trading-research status` command.
- `src/trading_research/cli/validate_strategy.py` — config linter:
  - knob ranges valid
  - instrument supported by template
  - featureset available
  - OU bounds available for instrument-timeframe
  - sizing model consistent with risk-limits config
- HTML: extend `gui/` (if 38a chose extend) or single `daily_summary.html` template (if reuse + add).
- Tests: `tests/cli/`.

## Acceptance
- [ ] `trading-research status` runs and shows all required data.
- [ ] `trading-research validate-strategy <yaml>` catches common config errors.
- [ ] CLI tests pass.
- [ ] `uv run pytest` full suite green.
- [ ] Handoff: `docs/execution/handoffs/38b-handoff.md`.
- [ ] current-state.md: 38b → DONE.

## What you must NOT do
- Implement what 38c is responsible for (theming/copy).
- Halt paper strategy.
- Override 38a's gui audit decision.

## References
- 38a artifacts.
