# Session 51 — Part IX + Part X finish + appendices

**Status:** Spec
**Effort:** 1 session, ~18 pages
**Model:** Sonnet 4.6
**Depends on:** Sessions 41–50
**Workload:** v1.0 manual completion

## Goal

Author Part IX (the Validation Gate workflow at v1.0 depth), close
out Part X (reference chapters not yet covered), and assemble the
appendices. All reference work, no code, no design decisions.
Sonnet throughout.

## In scope

### Part IX — The Validation Gate (Chapters 45, 46 only)

- **Chapter 45 — The Gate Workflow (~3 pages).** Exploration →
  candidate → gate three-stage lifecycle; mode field; pre-gate
  checklist.
- **Chapter 46 — Pass/Fail Criteria (~3 pages).** Backtest, walk-
  forward, statistical, behavioural criteria; the override path.

Chapters 47 (paper) and 48 (live) are explicitly post-v1.0; each
gets a one-paragraph placeholder at the end of Part IX pointing
to the future paper-and-live phase. Do not flesh them out.

### Part X — Reference (Chapters 50, 51, 53)

Chapter 49 was done in session 49. This session covers:

- **Chapter 50 — Configuration Reference (~6 pages).** Full schema
  for every YAML file under `configs/`: `instruments_core.yaml`,
  `featuresets/<tag>.yaml`, `strategies/<name>.yaml`,
  `regimes/<name>.yaml`, `calendars/<event>_dates.yaml`,
  `broker_margins.yaml`, `retention.yaml` (new in session 43).
- **Chapter 51 — File Layout Reference (~3 pages).** The
  repository tree; what's committed vs rebuilt vs ignored; run
  output structure; outputs structure; `.trials.json` location.
- **Chapter 53 — Schema Reference (~3 pages).** Reproduce
  BAR_SCHEMA, TRADE_SCHEMA, manifest schema with field-by-field
  documentation. (Appendix A/B/C are the canonical full
  references.)

### Appendices (~12 pages)

- **Appendix A** — BAR_SCHEMA full dump from
  `src/trading_research/data/schema.py`.
- **Appendix B** — TRADE_SCHEMA full dump.
- **Appendix C** — Manifest schema full dump.
- **Appendix D** — CLI command reference: full `--help` output for
  every subcommand. Generate by running each command with `--help`
  and pasting; verify reproducible by re-running.
- **Appendix E** — Configuration reference: every YAML key, type,
  default. Cross-references to Ch 50 sections.
- **Appendix F** — Glossary. Terms used across the manual: bar,
  contract, continuous contract, back-adjusted, feature set,
  knob, regime filter, mulligan, MAE/MFE, deflated Sharpe,
  walk-forward, purge, embargo, fold, mode, validation gate.
- **Appendix G** — Index. Generate from chapter headings + key
  terms; manual entry for cross-references that aren't headings.

## Out of scope

- Code work
- Chapters 47, 48 at full depth (post-v1.0)

## Hand-off after this session

- Parts IX and X complete (47/48 placeholders only).
- All appendices drafted.
- Next session: 52 (Part XI operations chapters + final code gaps).
