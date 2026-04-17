# ADR-001 — Three-Layer Data Architecture (RAW / CLEAN / FEATURES)

**Status:** Accepted
**Date:** 2026-04-13
**Participants:** Ibby, quant-mentor persona, data-scientist persona, Claude (Opus 4.6)
**Context window:** session 05 planning conversation

---

## Context

Session 04 ended with a complete back-adjusted ZN 1m/5m/15m pipeline in `data/clean/`. Session 05 was planned to add indicators (ATR, RSI, Bollinger, MACD, VWAP, OFI) plus a multi-timeframe framework with daily trend bias projected onto intraday bars.

During session 05 planning, Ibby raised a concern that went beyond the indicator layer itself:

> "we went from downloading 1 minute historical values to now bolting on indicators and higher time frame. It seems to me that we need a clean non-indicator (OHLCV) historical dataset that can be used for future rebuilds. I know i will want to try out other indicators, maybe a different non-standard time (13 minutes?) to see what happens. the data scientist talking about rebuilding has me concerned and i don't want 30 versions of 16 years of data of ZN. how do we make this a pipeline that flows and if i don't use it for 3 months, can make it work just fine without having ai investigate all versions and features added?"

This is a real architectural question. The naive path — dropping indicator columns into the existing `data/clean/` parquets — would entangle raw price data with experimental features and force every indicator experiment to either mutate a shared file or fork a full 16-year copy. Within six months there would be a graveyard of `ZN_5m_with_rsi.parquet`, `ZN_5m_with_rsi_and_macd.parquet`, `ZN_5m_v2_final.parquet`, and nobody — human or AI — would remember which is canonical.

The data scientist persona also raised the rebuild question: if we change the ATR implementation, or fix a bug in the MACD signal, what gets recomputed, from what source, and how do we know the recompute is faithful? Without a rebuild path, every bug fix means an archaeological dig.

---

## Decision

Adopt a **three-layer data model**, enforced by directory structure, naming conventions, and (in session 06) CLI automation.

### Layer 1 — RAW

**Contents:** Immutable, API-sourced, per-contract downloads. One file per `(symbol, contract, timeframe, date-range)`.

**Location:** `data/raw/`

**Rules:**
- Never mutated after write. Ever.
- Never contains derived data (no back-adjustment, no indicators, no resampling).
- Cached indefinitely. A re-download is only done if the file is lost or a source-data bug is discovered at the vendor.
- Each file has a sibling `.manifest.json` describing: source (TradeStation), symbol, date range, download timestamp, row count, schema version.

**What lives here today:** `data/raw/contracts/TYH10.parquet` through `TYM26.parquet` (66 quarterly contracts), plus the original full 14-year raw ZN pull.

### Layer 2 — CLEAN

**Contents:** Canonical OHLCV. One file per `(symbol, timeframe, adjustment)`. Deterministic function of RAW plus the code that produces it.

**Location:** `data/clean/`

**Rules:**
- **CLEAN never contains indicators.** This is the single most important rule in the layering. If a column is computable from price alone (SMA, EMA, RSI, MACD, Bollinger, VWAP, ATR, OFI), it does not live in CLEAN.
- CLEAN contains only: `BAR_SCHEMA` columns (timestamps, OHLCV, buy/sell volume, tick counts).
- Per-timeframe files are first-class: `ZN_backadjusted_1m.parquet`, `_5m.parquet`, `_15m.parquet`, `_60m.parquet`, `_240m.parquet`, `_1D.parquet`. They exist so that feature-set iteration (adding a new indicator) doesn't force a full re-resample.
- CLEAN is rebuildable from RAW + the code at a given commit. A bug fix in back-adjustment or resampling means `rebuild clean` and nothing more.
- Each file has a `.manifest.json` sidecar recording: source RAW files, code commit hash, parameters, build timestamp, row count, date range, schema version.
- CLEAN is the contract that downstream layers depend on. Breaking changes require a schema version bump.

**What lives here today:** Back-adjusted and unadjusted ZN 1m, plus 5m/15m resamples. Session 05 will add 60m/240m/1D.

### Layer 3 — FEATURES

**Contents:** Flat per-bar matrices: CLEAN columns plus indicator columns plus higher-timeframe bias projections. One file per `(symbol, timeframe, feature-set)`.

**Location:** `data/features/`

**Rules:**
- **Disposable.** Feature files are outputs, not inputs. Any feature file can be deleted and rebuilt from CLEAN plus the feature-set config.
- Versioned by **feature-set tag**, not by date. A feature-set is defined in `configs/featuresets/<name>.yaml` listing the indicators, their parameters, and the HTF projections to include.
- Filename encodes the tag: `ZN_backadjusted_5m_features_base-v1.parquet`. Multiple feature-set versions can coexist (`base-v1`, `base-v2`, `experiment-13min`) without collision.
- Each file has a `.manifest.json` recording: source CLEAN file, feature-set tag, code commit, build timestamp, indicator list with parameters.
- **Fat files.** Each feature file is a complete flat matrix — it includes the HTF bias columns (daily EMA, daily ATR, etc.) projected down to the intraday timeframe. Strategies and ML code consume a single file per observation, no runtime joins required.

**What lives here today:** Nothing. `data/features/` does not yet exist. Session 05 creates it.

---

## Why this shape

### Why CLEAN has no indicators

If CLEAN contained indicators, every new indicator experiment would be one of:
1. A destructive mutation of a shared file (unsafe, not reproducible)
2. A new copy of CLEAN (the "30 versions of 16 years" problem)
3. An in-place schema addition (makes CLEAN files non-comparable across time)

None of those is acceptable. Forcing indicators into a separate layer means CLEAN stays small, canonical, and rebuildable. Experiments proliferate in FEATURES, where proliferation is cheap.

### Why per-timeframe CLEAN files

The alternative is keeping only 1m in CLEAN and resampling on the fly every time a feature build runs. That's slow (15m resample over 4.67M rows costs seconds; 1D costs more) and it couples feature iteration to resampling code. Caching the per-timeframe parquets as CLEAN ingredients makes feature iteration nearly instant and isolates resample bugs to a single rebuild step.

### Why fat feature files

A strategy that wants "current 5m RSI + prior-session daily EMA(20)" can read one parquet and get both columns side-by-side. The alternative (skinny files plus a runtime join on session boundaries) works for backtesting but becomes painful for future ML work where the natural representation is a single flat matrix per observation. Fat files win on both axes. The cost is disk space, and disk is cheap compared to research time.

### Why manifests

A manifest is how the pipeline answers the question "where did this file come from and is it still fresh?" without human memory. The manifest records: source file(s), code commit, parameters, build time. A `verify` command can walk the whole `data/` tree and flag any file whose source has changed, whose code commit is gone, or whose parameters don't match the current config. Three-months-dormant Ibby can type one command and know what's stale without digging.

### Why feature-set tags

Tags solve the versioning problem without timestamp-based directory sprawl. `base-v1` is the current canonical feature set; `experiment-13min` is a non-standard timeframe trial; `base-v2` is what replaces `base-v1` when a new indicator joins the baseline. Old tags are deleted when they're no longer interesting. The git history of the config file is the audit trail.

---

## The rebuild contract

The layering exists to support a simple mental model:

> **RAW is ground truth. CLEAN is a function of RAW. FEATURES is a function of CLEAN.**

Any bug in back-adjustment, resampling, or an indicator can be fixed by editing code and running the relevant `rebuild` command. No manual file surgery, no "which version was canonical," no AI archaeology. Three months of neglect is survivable because the recipe is explicit and the source data is immutable.

The CLI that enforces this contract is session 06's primary deliverable.

---

## Alternatives considered

**A. Flat `data/` with feature columns bolted onto CLEAN parquets.**
Rejected. This is the "30 versions" path. Every experiment either mutates shared state or copies 16 years of history. Within a month the directory is an unreadable slurry.

**B. Two layers (RAW + FEATURES), skip CLEAN.**
Rejected. Back-adjustment and resampling are nontrivial and change rarely; recomputing them on every feature build wastes time and couples bug surfaces. CLEAN pays for itself the first time an indicator bug requires only a FEATURES rebuild.

**C. Three layers with skinny feature files and runtime joins.**
Rejected. Adds complexity at query time for a disk-space saving that doesn't matter. Strategies and ML consumers both prefer flat matrices.

**D. Full three layers with session 05 also building the CLI automation (`rebuild`, `verify`).**
Deferred, not rejected. The CLI is session 06. Session 05 adopts the conventions (manifests, naming, layer discipline) manually so the habits are formed before they're automated. This is "Option C" in the session 05 plan.

---

## Consequences

**Positive:**
- Experiments are cheap. New indicator, new timeframe, new feature-set all cost exactly one rebuild pass on CLEAN, not a re-download.
- Bugs are fixable. A broken indicator does not contaminate the historical record.
- Dormancy-tolerant. Ibby can walk away for three months and come back to a pipeline that documents itself through manifests and configs.
- ML-ready. Flat feature matrices are the natural input to scikit-learn, xgboost, or any future ML stack.

**Negative:**
- Disk overhead: per-timeframe CLEAN files plus fat FEATURES files use more space than a minimal single-file approach. For ZN this is measured in gigabytes, not terabytes.
- Discipline required: the "CLEAN never contains indicators" rule has to be enforced by convention until the CLI automation lands in session 06. The session 05 plan acknowledges this risk.
- One-time migration: existing files in `data/raw/` and `data/clean/` need manifest sidecars backfilled. This is in session 06's scope.

---

## Related documents

- `docs/pipeline.md` — living reference for the layer conventions, directory layout, manifest schema, and cold-start checklist.
- `docs/session-plans/session-05-plan.md` — indicator layer and feature build work, adopting these conventions manually.
- `docs/session-plans/session-06-plan.md` — CLI automation, manifest backfill, `verify` and `rebuild` commands.
- `configs/featuresets/base-v1.yaml` — first feature-set definition.
