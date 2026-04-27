# Session B1 — Timeframe Catalog Expansion

**Agent fit:** gemini (ideal spec-shape work)
**Estimated effort:** M (2–4h)
**Depends on:** 25 (generalized pipeline)
**Unblocks:** strategy work that wants non-standard timeframes

## Goal

Extend the timeframe resampler to support **3m, 10m, 30m, 120m** in addition to the current 1m, 5m, 15m, 60m, 240m, 1D. Apply to every instrument in the registry. Build CLEAN and FEATURES layers for the new timeframes on ZN and 6E.

This is pure spec-driven work with no design judgment. Perfect Gemini session.

## Context

Current timeframes: 1m (base), 5m, 15m, 60m, 240m, 1D. These cover the common cases but omit some that traders use:
- **3m** — Ibby's MT4 bot used 3m, noted in planning conversation.
- **10m** — filling the gap between 5m and 15m.
- **30m** — bridging 15m and 60m, useful for swing signals.
- **120m** — bridging 60m and 240m.

The existing resampler infrastructure handles arbitrary minute-based resampling; this session just wires in the new timeframes, adds configuration, builds the resulting parquets, and tests invariants.

## In scope

- `src/trading_research/data/resampling.py` (or wherever the resampler lives):
  - Add `3m`, `10m`, `30m`, `120m` to the list of supported timeframes.
  - Ensure the resampling logic correctly aggregates OHLCV, buy_volume, sell_volume for each new timeframe.
  - Ensure timestamp alignment follows CME session semantics (18:00 ET session open).

- Configuration:
  - Update `configs/pipeline.yaml` (or wherever default timeframes are listed) to include the new timeframes.

- Build artifacts:
  - Run CLEAN layer build for ZN and 6E at new timeframes. Commit the resulting `data/clean/*.parquet` files and manifests.
  - Run FEATURES layer build for ZN and 6E at new timeframes with base-v1 featureset. Commit parquets and manifests.
  - Total new parquets: 4 timeframes × 2 instruments × 2 layers = 16 new parquet+manifest pairs.

- Tests in `tests/data/test_resampling_new_timeframes.py`:
  - `test_3m_bar_count` — expected bar count for a known day.
  - `test_10m_bar_count`
  - `test_30m_bar_count`
  - `test_120m_bar_count`
  - `test_resample_ohlc_invariants` — for each new timeframe: high of aggregated bar == max of source highs; low == min; open == first; close == last.
  - `test_resample_volume_sum` — volume in resampled bar equals sum of source volumes.
  - `test_resample_buy_sell_volume_sum` — same for buy_volume and sell_volume, handling nulls.
  - `test_timestamp_alignment` — 3m bars align to :00, :03, :06, ...; 10m to :00, :10, :20; 30m to :00, :30; 120m to session-start + multiples.
  - `test_session_boundary_no_cross` — a resampled bar does not cross a session-close/open boundary.

## Out of scope

- Do NOT add timeframes beyond the four listed.
- Do NOT change the base timeframe (1m).
- Do NOT add non-minute timeframes (tick bars, volume bars, range bars) — those are different machinery.
- Do NOT rebuild historical CLEAN/FEATURES for the old timeframes. Only the new four.

## Acceptance tests

- [ ] `uv run pytest tests/data/test_resampling_new_timeframes.py -v` passes.
- [ ] `uv run pytest` — full suite passes.
- [ ] For ZN: `data/clean/ZN_3m_*.parquet`, `..._10m_*.parquet`, `..._30m_*.parquet`, `..._120m_*.parquet` exist with manifests.
- [ ] Same four for 6E (dependent on session 28 having pulled 6E data; if not yet run, this session for 6E is deferred).
- [ ] Same four for both instruments in FEATURES layer.
- [ ] Manifest integrity check passes on all new parquets.

## Definition of done

- [ ] All tests pass.
- [ ] All parquet artifacts exist and are committed.
- [ ] Work log lists the exact row counts for each new parquet.
- [ ] Committed on feature branch `session-B1-timeframe-catalog`.

## Persona review

- **Architect: optional** — reviews that no hardcoded timeframe strings were introduced.
- **Data scientist: optional** — reviews that buy/sell volume aggregation handles nulls correctly.
- **Mentor: optional**.

## Design notes

### Resampling semantics

OHLCV aggregation is standard: O=first, H=max, L=min, C=last, V=sum. For buy_volume and sell_volume, sum with null-handling: if any source bar has null buy_volume, the aggregated bar's buy_volume is also null (or imputed per pipeline config, if that's in place).

### Session boundary handling

A resampled 120m bar starting at 16:00 ET must not include 18:00 ET session-open bars. The resampler should respect the session calendar from the instrument's `calendar_name`. If the existing resampler already does this, verify; if not, fix.

### Timestamp alignment

Timestamps label the *start* of the bar (OHLC convention in this project — verify against existing parquets). A 3m bar timestamped 09:06 covers 09:06–09:09.

## Risks

- **Existing resampler doesn't cleanly support arbitrary intervals.** Mitigation: test with the four new intervals; fix if resampler only supports specific powers. Should be fine since pandas resample handles arbitrary frequencies.
- **Session boundary bugs.** Mitigation: the test `test_session_boundary_no_cross` catches this.
- **Parquet size growth.** Mitigation: new parquets are smaller than 1m base, so minimal impact.

## Reference

- Existing resampler implementation under `src/trading_research/data/`.
- `configs/pipeline.yaml` — default timeframe list.
- Session 25 spec — for how Instrument-aware session boundaries work.

## Success signal

```
uv run trading-research build-clean --symbol 6E --timeframes 3m,10m,30m,120m
uv run trading-research build-features --symbol 6E --timeframes 3m,10m,30m,120m --featureset base-v1
```

Both run clean. Eight new parquets appear for 6E with manifests. Tests pass. Ibby can now reference `6E_3m` in a strategy config without extra plumbing.
