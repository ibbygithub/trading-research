# Session 28 — 6E Pipeline End-to-End + Stationarity Run on 6E

**Agent fit:** either
**Estimated effort:** L (4h+)
**Depends on:** 25 (generalized pipeline), 26 (stationarity suite)
**Unblocks:** 29 (strategy class decision for 6E)

## Goal

Pull 6E historical data from TradeStation, run it through the full pipeline (RAW → CLEAN → FEATURES), run the stationarity suite, and produce the artifacts session 29 uses to pick a strategy class for 6E.

This is also the acceptance gate for Track A: if this session completes end-to-end without code changes beyond what session 23-a put in `configs/instruments.yaml`, the hardening sprint succeeded.

## Context

6E (Euro FX) is Ibby's primary instrument going forward. ZN is shelved. This session:

1. Proves the pipeline is truly instrument-agnostic (the Track A acceptance gate).
2. Produces 6E data artifacts (RAW, CLEAN, FEATURES) for strategy work.
3. Produces the stationarity report that drives session 29's strategy-class decision.

## In scope

Run the pipeline:

- **Pull 6E RAW data** via the existing TradeStation downloader. Time range: 2015-01-01 to present (or longest available). Resolutions: 1m bars.
- **Validate** the 6E RAW data: calendar gaps, buy/sell volume completeness, no negative volumes, no inverted high/low.
- **Build CLEAN layer** for 6E: validated 1m parquet plus resampled 5m, 15m, 60m, 240m, 1D. All with manifests.
- **Build FEATURES layer** for 6E at 5m and 15m: apply base-v1 feature set, verify feature hash matches session 23-a's base-v1 FeatureSet hash, manifest links featureset_hash correctly.
- **Run stationarity suite** on 6E: per the design doc, covering returns at 5m/15m, VWAP-price spread at 5m, log-prices at 1D.
- **Write the strategy-class recommendation memo** at `docs/analysis/6e-strategy-class-recommendation.md`. Based on the stationarity results, the memo recommends mean reversion / momentum / breakout / noise regime / mixed as the starting strategy class for session 29.

Tests:

- `tests/data/test_6e_pipeline_integration.py`:
  - `test_6e_raw_exists` — verifies RAW parquet exists for recent date range.
  - `test_6e_clean_5m_has_expected_rows` — CLEAN 5m has the right bar count for a known period.
  - `test_6e_features_5m_has_base_v1_columns` — FEATURES 5m has the columns base-v1 declares.
  - `test_6e_manifest_has_featureset_hash` — manifest.json next to the FEATURES parquet contains the correct base-v1 hash.

## Out of scope

- Do NOT design or implement any 6E strategy. That's session 29.
- Do NOT add new features to base-v1. Use what exists.
- Do NOT modify the TradeStation downloader. If it fails for 6E, fix is in-scope but minimal — the session should not become "rewrite the downloader".
- Do NOT run on any instrument other than 6E.

## Acceptance tests

- [ ] `data/raw/6E_1m_*.parquet` (or equivalent path per 23-a config) exists and is non-empty for at least 2015-01-01 to 2024-12-31.
- [ ] `data/clean/6E_1m_*.parquet`, `data/clean/6E_5m_*.parquet`, `data/clean/6E_15m_*.parquet`, etc., all exist with manifests.
- [ ] `data/features/6E_5m_base-v1_*.parquet` exists with a manifest linking the base-v1 hash.
- [ ] `outputs/stationarity/6E_*.json` and `.md` exist.
- [ ] `docs/analysis/6e-strategy-class-recommendation.md` exists and names a strategy class with reasoning.
- [ ] **Track A acceptance gate:** The command `uv run trading-research pipeline --symbol 6E` completes without code changes beyond `configs/instruments.yaml`. If code changes were required, document them in the work log and escalate — this means Track A is not done.
- [ ] `uv run pytest tests/data/test_6e_pipeline_integration.py` passes.
- [ ] `uv run pytest` — full suite passes.

## Definition of done

- [ ] All pipeline stages complete without errors.
- [ ] Stationarity results show *something* — whether 6E is stationary, trending, or noisy. No null results.
- [ ] Recommendation memo is decisive (names a strategy class; does not equivocate).
- [ ] Work log includes: data pulled date range, CLEAN row counts per timeframe, feature count per FEATURES parquet, stationarity summary, strategy class recommendation.
- [ ] Committed on feature branch `session-28-6e-pipeline`.

## Persona review

- **Data scientist: required.** Reviews the stationarity results and concurs with the strategy-class recommendation. This is their call — mentor can disagree but data scientist signs off on the statistical reading.
- **Mentor: required.** Reviews the recommendation memo. May override if the stats say one thing but the mentor's market knowledge says another (e.g., "6E shows stationarity in this window but the ECB regime change in 2022 breaks it; the forward-looking recommendation should weight post-2022 data more").
- **Architect: required.** Reviews that the pipeline actually ran without code changes. This is the Track A acceptance gate — architect must confirm.

## Design notes

### If TradeStation downloader fails for 6E

The downloader should work for any symbol in the Instrument registry. If it fails:

- **If the failure is a bug in the downloader** (e.g., hardcoded ZN assumption): fix the downloader. This is in-scope.
- **If the failure is a TradeStation API error** (e.g., rate limit, authentication): diagnose, log, retry. Do not skip.
- **If the failure is data unavailability** (e.g., 6E history only goes back to 2019 on this account): document the actual start date in the work log and proceed with what's available.

### Buy/sell volume for 6E

Per status report, buy/sell volume has "HAS ISSUES" status. For 6E, expect similar — some dates will have the field populated, others null. Handle gracefully: the validation step should flag null volume bars but not reject them.

### Base-v1 on 6E

The base-v1 FeatureSet includes MACD, ATR, RSI, VWAP, ADX, OFI, EMA, SMA. All of these compute on any OHLCV series. No feature should fail to compute on 6E; if one does, that's a bug in the feature implementation, not a 6E-specific issue.

### Stationarity memo structure

`docs/analysis/6e-strategy-class-recommendation.md` must have:

1. **Stationarity summary** — one table, every series tested, stationary yes/no.
2. **Hurst summary** — one table, every series, H value, interpretation.
3. **OU half-life** — where applicable, the half-life in bars and hours.
4. **Interpretation** — in plain English. Example: "5-minute returns are stationary (ADF p=0.001), Hurst 0.47 indicates slight mean reversion, OU half-life of 23 bars (~1.9 hours) suggests intraday mean-reverting dynamics. Recommend mean reversion strategy class for 5-minute timeframe."
5. **Recommended strategy class:** One of {mean_reversion, momentum_breakout, event_driven, mixed_regime}.
6. **Suggested starting template knobs:** Rough guidance for session 29's template design.
7. **Caveats and risks:** What the stationarity tests don't show (regime changes, tail events, transaction cost sensitivity).

## Risks

- **6E data pull fails or is slow.** Mitigation: pull in chunks if needed. If a full pull is infeasible, get 2020–present and proceed.
- **Stationarity results are ambiguous.** Mitigation: memo explicitly says "mixed regime, recommend trying mean reversion first with regime filter." Don't force a binary answer if the data is ambiguous.
- **Pipeline requires code changes despite session 25.** This would mean Track A is incomplete. If it happens, document exactly what changed, open follow-up tickets, and flag in the work log that Track A acceptance has NOT been met.

## Reference

- Session 25 spec — pipeline generalization.
- Session 26 spec — stationarity suite.
- `docs/design/stationarity-suite.md` — design doc for the suite.
- `configs/instruments.yaml` — 6E registration from 23-a.
- `.claude/rules/data-scientist.md` — the section on stationarity assumptions.

## Success signal

A single command runs end-to-end:

```
uv run trading-research pipeline --symbol 6E && \
uv run trading-research stationarity --symbol 6E
```

Both complete without error. Output files exist. Memo is written. Track A is declared done by the architect in the session log.
