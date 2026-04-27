═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           B1-gemini
Required model:    Gemini 3.1 (Antigravity)
Effort:            M (~3 hr)
Entry blocked by:  Sprint 25 (already done)
Parallel-OK with:  33a, any session
Hand off to:       (none — independent)
Branch:            session-B1-timeframe-catalog
═══════════════════════════════════════════════════════════════

# B1 — Add 3m, 10m, 30m, 120m timeframes

Follows [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md).

## Self-check
- [ ] I am Gemini 3.1 in Antigravity.
- [ ] OHLCV resample parity test fixture exists or I receive it pre-written.

## What you implement

Per the original spec (canonical reference document for this work):

- `src/trading_research/data/resampling.py` — add 3m, 10m, 30m, 120m resamplers.
- Update `configs/pipeline.yaml` to include new timeframes.
- Build CLEAN + FEATURES for ZN and 6E at new timeframes.
- Tests in `tests/data/test_resampling_new_timeframes.py` per spec.

## Validation contract per playbook
- Canonical reference: `pandas.DataFrame.resample(label="left", closed="left").agg(...)`.
- Parity test fixture: `tests/data/test_resample_canonical_parity.py` (Sonnet pre-writes; you implement against it).
- Tolerance: rtol=1e-12, atol=1e-12.

## Acceptance
- [ ] All tests in spec pass.
- [ ] 16 new parquet+manifest pairs (4 timeframes × 2 instruments × 2 layers).
- [ ] `uv run pytest` full suite green.
- [ ] Handoff: `docs/execution/handoffs/B1-handoff.md`.
- [ ] current-state.md: B1 → DONE.

## What you must NOT do
- Add timeframes beyond the four listed.
- Author your own validation tests against pandas reference.
- Loosen tolerance.

## References
- Original spec: [`../../../roadmap/session-specs/session-B1-timeframe-catalog.md`](../../../roadmap/session-specs/session-B1-timeframe-catalog.md)
- Playbook Example D for resample parity pattern.
