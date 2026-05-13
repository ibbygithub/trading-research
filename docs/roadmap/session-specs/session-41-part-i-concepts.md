# Session 41 — Part I: Concepts and Architecture

**Status:** Spec
**Effort:** 1 session, ~18 pages of finished prose
**Model:** Sonnet 4.6
**Depends on:** Session 40 (Chapters 5, 56.5, quick-start ratified)
**Workload:** v1.0 manual completion

## Goal

Author Part I of the operator's manual — the conceptual frame every
later chapter hangs off. Three chapters: Introduction, System
Architecture, Operating Principles. Mostly assembly of existing
material from `CLAUDE.md` and the persona files into manual prose at
the Chapter-4 quality bar. No code work, no gap items, no design
decisions blocking ratification — a low-risk warm-up that establishes
the model split (Sonnet for describe-what-exists chapters).

## In scope

- **Chapter 1 — Introduction (~4 pages).** What the platform is, who
  it's for, what it is *not*, the ten-stage pipeline at a glance, the
  v1.0 completeness criterion. Source: §1.1–1.5 of TOC; `CLAUDE.md`
  intro.
- **Chapter 2 — System Architecture (~8 pages).** Component map, data
  flow diagram (Mermaid), the three-layer data model (cross-reference
  to Ch 4), technology stack with rationale, where state lives, the
  CLI surface. Source: TOC §2.1–2.6; project layout in `CLAUDE.md`.
- **Chapter 3 — Operating Principles (~6 pages).** The honesty bar,
  the standing rules in detail (one paragraph per rule with reason),
  what the platform refuses to do, persona-driven reasoning, the
  CLI-as-API design contract. Most of this is `CLAUDE.md`'s standing
  rules section restructured into manual prose. Source: TOC §3.1–3.6;
  `CLAUDE.md` standing rules; `.claude/rules/*.md`.

## Out of scope

- Any code change
- §3.5 ("What changes in live") — this is a [GAP] placeholder for
  post-v1.0 work; written as a one-paragraph "out of scope for v1.0,
  see Part XII when paper-trading work begins."
- Cross-references to chapters not yet written are to TOC sections,
  not to the chapters themselves.

## Hand-off after this session

- Part I drafted at quality bar, ready for operator review.
- Memory updated only if new feedback is given mid-session.
- Branch `session-41-part-i-concepts` committed locally; not pushed.
- Next session: 42 (Part II finish — Ch 6, 7, 8).
