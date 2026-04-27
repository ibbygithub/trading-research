# Track D — Alignment with Plan v2

**Status:** Addendum to `track-D-circuit-breakers.md`
**Date:** 2026-04-26

The existing `track-D-circuit-breakers.md` spec was written before plan v2 and
remains the canonical spec for D1–D4. This addendum captures the v2-driven
adjustments. When in conflict, this addendum wins.

## Adjustments

### D1 — Daily/weekly loss limits

**Plan v1 vs v2 difference:** D1 now consumes **sized P&L** from sprint 29c's
`Strategy.size_position` path, not the hardcoded `BacktestConfig.quantity`.

- The `LossLimitMonitor` receives realised P&L per closed trade. The P&L is
  computed using the actual sized position from `size_position`, not the
  fallback quantity.
- Synthetic test in D1 acceptance must construct a `PortfolioContext` and a
  Strategy whose `size_position` returns a known integer; the monitor's
  trip-point must match that sizing.

### D2 — Inactivity heartbeat

**No v2 change.** Implementation as specified in the original Track D doc.

### D3 — Order idempotency + reconciliation

**Plan v2 addition:** the reconciler also verifies `featureset_hash` consistency
on every fill cycle. If the strategy's expected featureset hash and the
loaded data's hash diverge mid-day (parquet swap), the reconciler raises and
D4 account-level kill switch fires. Per architect S10.

### D4 — Kill-switch hierarchy

**Plan v2 addition:** drill test in acceptance must include a featureset-hash
mismatch scenario (added to the existing D4 drill list of API-outage and
loss-limit-breach scenarios).

## Parallel-day pairing (from plan v2 daily-throughput table)

- D1: Day 1 alongside sprint 29.
- D2: Day 3 alongside sprint 30.
- D3: Day 4 alongside sprint 31.
- D4: Day 5 alongside sprint 32.

Each is a Sonnet sub-sprint with its own branch, commit, and work log.

## References

- `docs/roadmap/session-specs/track-D-circuit-breakers.md` (canonical spec)
- `outputs/planning/sprints-29-38-plan-v2.md`
- `outputs/planning/peer-reviews/architect-review.md` §7 (featureset hash)
