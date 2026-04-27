═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           35b-opus
Required model:    Opus 4.7
Effort:            M (~2 hr)
Entry blocked by:  35a (DONE)
Hand off to:       35c-sonnet
Branch:            session-35-paper-loop
═══════════════════════════════════════════════════════════════

# 35b — Failure-mode review

## Self-check
- [ ] I am Opus 4.7.
- [ ] 35a DONE; paper loop wired.

## What you produce

`runs/.../35b-failure-modes.md` enumerating 8 failure modes with detection + response + test for each:

1. **Duplicate fills** — broker reports a fill twice; reconciler dedupes by broker fill ID.
2. **Partial fills** — order for 5 fills 3 then 2; trade-log records both; position state is the sum.
3. **Missing fills** — order submitted, no fill within T sec; heartbeat fires; auto-flatten attempts; flag for manual review.
4. **Stale fills (race)** — fill arrives after position flagged exited; reconciler emergency-flattens unexpected exposure.
5. **Featureset version drift** — mid-day parquet rebuild changes hash; loader hard-halts; trader alerted.
6. **Clock drift** — broker timestamps and local timestamps differ >1 sec; tradelog records both; alerts at >5 sec.
7. **Loss-limit breach during open trade** — D1 fires; D4 flatten; conflict with strategy's natural exit; order: kill switch wins.
8. **Heartbeat false positive** — API silent in low activity; cost is one false-flatten/day; tradeoff documented.

For each: symptom, detection mechanism, response, test name 35c will implement.

## Acceptance
- [ ] All 8 failure modes documented.
- [ ] Each has a test name listed for 35c.
- [ ] Handoff: `docs/execution/handoffs/35b-handoff.md`.
- [ ] current-state.md: 35b → DONE; 35c → READY.

## What you must NOT do
- Implement code (35c's job).
- Skip a failure mode.

## References
- Architect's review §7 failure modes.
- Original spec §35b.
