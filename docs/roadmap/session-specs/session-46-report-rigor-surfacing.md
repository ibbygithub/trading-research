# Session 46 — Chapter 17 + Report Rigor Surfacing (bundled)

**Status:** Spec
**Effort:** 1 session, chapter + code + tests
**Model:** Opus 4.7
**Depends on:** Sessions 41–45 (Parts I–IV minus Ch 17 done)
**Workload:** v1.0 manual completion

## Goal

Bundled session: Chapter 17 (Trader's Desk Report) and the code work
that closes its [PARTIAL] items in one shot. The chapter currently
has three [PARTIAL] markers — DSR not in the report header, fold
variance not in the HTML, CIs computed only on demand. The chapter
specifies the v1.0 behavior; the code lands to match within the
session.

This session also closes [PARTIAL] item §22.7 (walkforward fold
table in report), §23.5 (DSR in `format_with_ci`), and §32.4 (CI
columns in leaderboard) because they share the same code path.

## In scope

### Chapter 17 (~5 pages)

- §17.1 What the report shows: equity, drawdown, monthly heatmap,
  trade distribution, MAE/MFE scatter, per-fold walkforward,
  statistical headline.
- §17.2 Generating a report; auto-resolving the latest timestamp.
- §17.3 The pipeline integrity audit.
- §17.4 The data dictionary.
- §17.5 Headline statistical reporting — at v1.0 this includes
  raw Sharpe, deflated Sharpe, Calmar with bootstrap CIs, win-rate
  CI, fold variance, and a gate-check flag against the validation
  criteria from Chapter 46. All point estimates carry their CI;
  CIs that include zero are flagged.

### Code work

- `src/trading_research/eval/report.py` — add DSR, fold variance,
  and CI flags to the HTML report header. Add the walkforward fold
  table as a new section.
- `src/trading_research/eval/bootstrap.py` (`format_with_ci`) —
  include DSR alongside raw Sharpe in the headline output.
- `src/trading_research/eval/leaderboard.py` — add CI columns to
  the tabular and HTML leaderboard output.
- Tests: extend `tests/test_report.py` to cover the new sections;
  extend `tests/test_leaderboard.py` for CI columns.

### Manual touch-up

- Strip `[PARTIAL]` markers from Ch 17 §17.5, Ch 22 §22.7, Ch 23
  §23.5, Ch 32 §32.4 once the code lands. Update TOC gap list to
  match.

## Out of scope

- Walk-forward methodology chapters (Chapters 22, 23) — they get
  teaching prose in session 47.
- Trade-overlay charts in the report — explicitly post-v1.0.

## Hand-off after this session

- Chapter 17 ratified; rigor surfacing live in the report and
  leaderboard.
- Four [PARTIAL] markers closed.
- Next session: 47 (Part V — validation rigor chapters).
