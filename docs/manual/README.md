# Trading Research Platform — Operator's Manual

**Status:** Draft v0.1 — Table of Contents and one sample chapter only
**Project:** trading-research
**Version applies to:** code at branch `session-39-h4-redesign-h6-exploration` (commit `2b49890`)
**Document date:** 2026-05-04

---

## What this manual is

This manual is the operator's reference for the trading research platform — the bench
that an experienced trader uses to author, test, validate, and report on systematic
trading strategies. It is written for one specific reader: Ibby, who is the platform's
sole operator. It is not a tutorial. It assumes a working knowledge of futures markets,
backtesting concepts, and the statistical bar at which a quantitative claim is made
seriously.

A reader of this manual should be able to:

- Bring up the platform from a clean clone of the repository, end to end, without
  outside help
- Pull historical 1-minute bars for any registered instrument and validate the result
- Author a new strategy in YAML and run a backtest, walk-forward, and bootstrap
  CI report against it
- Read a Trader's Desk report and decide whether a strategy passes the validation
  gate or fails it
- Add a new instrument, a new indicator, a new feature set, or a new regime filter
  without breaking the existing pipeline
- Recover from common error states (stale manifests, missing contracts, broken
  configs) without agent assistance

Where the platform does not currently support a capability the manual describes,
the gap is marked **[GAP — to be built]** with a reference to the specification
that future development should satisfy. The combined gap list at the end of the
Table of Contents is the backlog for completing the platform.

---

## How this manual was produced

The manual is being written *spec-first*, before completion of the remaining code,
on the explicit instruction of the project owner. The intent is that this document
becomes the authoritative description of the platform — what it does, how it
behaves, and what its conventions are. Any code change after the manual is
ratified must either match the manual or be accompanied by a manual revision.

This is the inverse of the typical "code first, document later" approach, and is
the right choice for a project whose owner is a former CISO with thirty years
in IT: he is not interested in another piece of software whose behavior is
discoverable only by reading source. He wants the document, then the code that
matches it.

The drafting protocol:

1. **Table of Contents (this revision).** Every chapter named, every section
   listed, every section marked as documenting an existing feature, a feature
   that needs surfacing in artifacts users see, or a feature that does not
   yet exist.
2. **Sample chapter (this revision).** One representative chapter — Chapter 4,
   *Data Pipeline & Storage* — written to the full quality bar so the project
   owner can judge whether the bar is correct.
3. **Iterative authoring (future revisions).** Once the TOC and quality bar are
   ratified, chapters are written one or two at a time, reviewed, corrected,
   and accepted. Chapters that document a gap include the spec for what
   needs to be built, which then drives a coding session.
4. **Cross-validation against code (continuous).** Every code reference in the
   manual cites a file path and, where appropriate, a line range. A pre-commit
   hook should eventually verify that every cited path exists; this is a
   later refinement.

---

## Document conventions

### Audience

Throughout, "you" refers to the platform's sole operator. The manual addresses
him directly. It does not pretend the platform has multiple users or speak in
the abstract third person. This is a deliberate choice — the manual is shorter,
sharper, and more useful when it knows who it's talking to.

### Marking conventions

Each section in the Table of Contents carries one of three status markers:

- **[EXISTS]** — The feature is implemented and works. The chapter documents
  what is already there. No code work is required.
- **[PARTIAL]** — The feature exists in code but is not surfaced in the
  artifacts an operator would see (the report, the leaderboard, the CLI
  output). The chapter documents what is computed; the work is to expose it.
- **[GAP]** — The feature does not yet exist. The chapter is a specification
  for it, written so that a future session can implement against the spec.

A summary list of all **[GAP]** and **[PARTIAL]** markers appears at the end
of the Table of Contents. This is the backlog for completing the platform.

### Code references

When the manual cites a source file, it uses the form
`src/trading_research/<module>/<file>.py` and where line precision matters the
form `src/.../engine.py:142`. These are repository-relative paths and are
expected to remain stable; the next major refactor should bump the manual.

When the manual shows a CLI command, the canonical form is

    uv run trading-research <subcommand> [options]

`uv run` is required because the project is managed with `uv` and dependencies
live in `.venv/`. A bare `trading-research` invocation outside `uv run` is not
supported and does not appear anywhere in this manual.

### Schemas

Bar, trade, manifest, and trial schemas are defined exactly once each and
referenced from elsewhere. The full schema definitions appear in the appendices.
Other chapters cite schemas by name (e.g., "see TRADE_SCHEMA in Appendix B")
rather than restating the field list.

### Reasoning callouts

Where a design choice is not self-evident, the manual includes a callout
explaining the reasoning. These are italicized and prefixed with **Why this:**
or **Why not the alternative:**. The intent is to preserve the rationale
behind the platform's decisions for any future operator (or future agent
session) reading the manual cold.

---

## Versioning

The manual is versioned independently of the code. A draft revision is denoted
`vX.Y-draft`; an accepted revision drops the `-draft` suffix. The current
revision is **v0.1-draft** and reflects the platform state at commit `2b49890`
on branch `session-39-h4-redesign-h6-exploration`.

When the manual reaches v1.0, the platform reaches v1.0. The two are tied:
the platform is "complete" when this manual is accepted in full and every
chapter marked **[EXISTS]** is verified against the code.

---

## Provisional contents

The structure proposed for this manual is:

| Part | Title | Approx. pages |
|------|-------|---------------|
| I    | Concepts and Architecture | 18 |
| II   | Data Foundation | 24 |
| III  | Strategy Authoring | 26 |
| IV   | Backtesting | 22 |
| V    | Validation and Statistical Rigor | 30 |
| VI   | Parameter Exploration | 12 |
| VII  | Risk and Position Sizing | 14 |
| VIII | Portfolio Analytics | 12 |
| IX   | The Validation Gate | 10 |
| X    | Reference | 26 |
| XI   | Operations and Troubleshooting | 12 |
|      | **Total (estimate)** | **206** |

The full chapter list with section descriptions is in
[`TABLE-OF-CONTENTS.md`](TABLE-OF-CONTENTS.md). The sample chapter is
[`04-data-pipeline.md`](04-data-pipeline.md).

---

## Document file layout

```
docs/manual/
├── README.md                          # this file
├── TABLE-OF-CONTENTS.md               # comprehensive TOC, every section described
├── 00-front-matter.md                 # title page, foreword, conventions, change log
├── 01-introduction.md                 # Chapter 1
├── 02-system-architecture.md          # Chapter 2
├── ...                                # one file per chapter
├── appendix-a-bar-schema.md           # appendices
├── appendix-b-trade-schema.md
├── appendix-c-manifest-schema.md
├── appendix-d-cli-reference.md
├── appendix-e-config-reference.md
├── appendix-f-glossary.md
└── appendix-g-index.md
```

When the manual is accepted, a build script combines the chapters into a single
PDF using pandoc, which is the deliverable form for archive purposes. The
Markdown files remain the source of truth.
