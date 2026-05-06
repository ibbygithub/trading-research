# Session 42 — Part II finish: Bar Schema, Indicators, Feature Sets

**Status:** Spec
**Effort:** 1 session, ~17 pages
**Model:** Sonnet 4.6
**Depends on:** Sessions 40, 41 (Chapters 4, 5, Part I done)
**Workload:** v1.0 manual completion

## Goal

Complete Part II of the manual. Chapter 4 (data pipeline) and
Chapter 5 (instrument registry) are already done. This session adds
Chapters 6, 7, 8 to close out the data-foundation section, so anything
downstream (strategy authoring in Part III, backtesting in Part IV)
can cross-reference settled chapters rather than placeholders.

## In scope

- **Chapter 6 — Bar Schema & Calendar Validation (~4 pages).**
  Document `BAR_SCHEMA` from `src/trading_research/data/schema.py`,
  the two-timestamp design (UTC compute, NY display), the validation
  gate (what's fatal, what's informational), how to read a quality
  report. §6.5 (schema evolution / migration) is a `[GAP]` —
  document as the spec for the migration tooling to be built in
  session 52.
- **Chapter 7 — Indicator Library (~8 pages).** Catalogue of
  indicators in base-v1: ATR, RSI, Bollinger, MACD with derived
  columns, SMA, Donchian, ADX, OFI, the VWAP family, and HTF
  projections. Each indicator gets formula, parameters, columns
  produced, common interpretation. Cite
  `src/trading_research/indicators/`.
- **Chapter 8 — Feature Sets (~5 pages).** What a feature set is,
  the base-v1 and base-v2 specifications (annotate the YAML files),
  the fork-and-bump-tag discipline, the audit trail through git, the
  feature inventory. §8.6 ([PARTIAL] feature inventory in `status`)
  surfaces here as a forward reference to Ch 49.16.

## Out of scope

- Implementation of schema migration tooling (deferred to session 52)
- Implementation of feature-inventory in `status` CLI (deferred to
  session 49)

## Hand-off after this session

- Part II of the manual fully drafted (Chapters 4–8).
- The data-foundation section is the canonical reference for any
  later chapter that mentions schemas, indicators, or feature sets.
- Branch `session-42-part-ii-finish` committed locally.
- Next session: 43 (storage cleanup CLI implementation, bundled
  with re-confirmation of Ch 56.5).
