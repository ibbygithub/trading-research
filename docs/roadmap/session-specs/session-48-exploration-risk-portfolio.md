# Session 48 — Parts VI, VII, VIII condensed

**Status:** Spec
**Effort:** 1 session, ~30 pages across 14 chapters
**Model:** Sonnet 4.6
**Depends on:** Sessions 41–47
**Workload:** v1.0 manual completion

## Goal

Author Parts VI (Parameter Exploration), VII (Risk and Position
Sizing), VIII (Portfolio Analytics) at reference depth. Fourteen
chapters total, almost all describe-what-exists work. No teaching-
prose-heavy chapters in this batch — every module is well-defined
in code, the chapters surface what's there with module pointers and
operator-facing interpretation.

## In scope

### Part VI — Parameter Exploration (~12 pages)

- **Chapter 31 — The Sweep Tool (~4 pages).** When to sweep, when
  not to; the `sweep` CLI; sweep ID tracking; reading a gradient;
  common sweep mistakes.
- **Chapter 32 — Trial Registry & Leaderboard (~4 pages).** The
  trial JSON format; mode tagging; the `leaderboard` CLI; CI
  columns are surfaced as of session 46 (close [PARTIAL] §32.4);
  `migrate-trials` CLI is forward-referenced to session 49.
- **Chapter 33 — Multiple-Testing Correction (~2 pages).**
  Bonferroni vs Benjamini-Hochberg; module reference.
- **Chapter 34 — Composite Ranking (~2 pages).** When and how;
  module reference.

### Part VII — Risk and Position Sizing (~14 pages)

- **Chapter 35 — Risk Management Standards (~3 pages).** The
  standing rules; what the platform enforces today; §35.2 daily
  loss limit is documented as the spec for session 52 code.
- **Chapter 36 — Position Sizing (~4 pages).** Volatility
  targeting (default), fixed quantity, Kelly (`eval/kelly.py`);
  module reference; §36.5 adaptive sizing flagged as post-v1.0.
- **Chapter 37 — Capital Allocation (~2 pages).** Per-strategy
  capital; portfolio-level constraints; module reference.
- **Chapter 38 — Re-entries vs Averaging Down (~3 pages).** The
  distinction; the Mulligan controller (cross-reference Ch 14.7);
  authoring a re-entry strategy.
- **Chapter 39 — Pairs and Spread Trading (~2 pages).** Spread
  margin reality; broker margins reference. §39.1 (YAML extension
  for pairs) is post-v1.0; the chapter notes the gap and points to
  the post-v1.0 backlog.

### Part VIII — Portfolio Analytics (~12 pages)

- **Chapter 40 — Portfolio Reports (~3 pages).** The `portfolio`
  CLI; module reference; data dictionary.
- **Chapter 41 — Correlation Analysis (~2 pages).** Strategy
  correlation; the diversification myth.
- **Chapter 42 — Portfolio Drawdown (~2 pages).** Aggregated
  drawdown; recovery characteristics.
- **Chapter 43 — Strategy Clustering (~2 pages).** Clustering by
  fingerprint; SHAP-based attribution.
- **Chapter 44 — Meta-Labelling (~2 pages).** Lopez de Prado's
  approach; when to consider; cross-reference Ch 23.

## Out of scope

- Daily loss limit code (session 52)
- Pairs YAML extension (post-v1.0)
- Adaptive sizer (post-v1.0)

## Hand-off after this session

- Parts VI, VII, VIII drafted at reference depth.
- §32.4 [PARTIAL] closed (CI columns in leaderboard surfaced in
  Ch 32 prose).
- Next session: 49 (Chapter 49 CLI reference + ship validate-
  strategy / status / migrate-trials).
