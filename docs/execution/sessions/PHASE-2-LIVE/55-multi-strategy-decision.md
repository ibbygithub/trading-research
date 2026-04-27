═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           55
Required model:    Opus 4.7 + Ibby
Effort:            M (~2-3 hr)
Entry blocked by:  54 (DONE)
Hand off to:       (open-ended — sessions 56+)
Branch:            session-55-decision
═══════════════════════════════════════════════════════════════

# 55 — Multi-strategy operations + Track G/H decision point

Two strategies running live. Now Ibby chooses what comes next.

## Self-check
- [ ] I am Opus 4.7.
- [ ] 54 DONE; second strategy live.
- [ ] Ibby is present.

## Three options

**Track G — ML capability (sessions 56-60).**
- Meta-labeling on 6E rule-based strategy.
- Now defensible because we have ≥6 weeks of live trade data.
- Logistic baseline first; XGBoost only if it beats baseline meaningfully.
- Purged walk-forward + SHAP feature importance.

**Track H — Pairs framework (sessions 56-62).**
- 6A/6C correlation-based pairs strategy.
- Defensible because both single-instrument strategies validated.
- Margin-paired sizing; correlation-aware risk limits; broker-margin reality (not exchange-spread reduced).

**Stay simple — continue running both strategies, scale gradually, defer ML and pairs.**
- Operational maturity continues.
- Eventually iterate to a third instrument or new template.
- Track G and H deferred to session 60+.

## Decision criteria

Mentor: which gives more durable edge given Ibby's time and capital?
Data Scientist: which has better evidence base after two live strategies?
Architect: which has lower coupling cost to add?

## Output
`runs/.../55-decision.md`:
- Choice committed.
- Sessions 56+ scoped accordingly.
- This is Ibby's call. The plan supports any of the three.

## Acceptance
- [ ] Three persona observations.
- [ ] Decision committed.
- [ ] Sessions 56+ scope outlined.
- [ ] Both live strategies continue running unaffected.
- [ ] Handoff: `docs/execution/handoffs/55-handoff.md`.
- [ ] current-state.md: 55 → DONE.

## What you must NOT do
- Force a choice between G/H/simple. The plan supports any.
- Modify live strategies.
- Begin Track G or H implementation in this session.

## End of master execution plan

Sessions 56+ are not pre-planned at this fidelity. After session 55 the path
forks based on actual experience. The current intent (subject to change at
session 55):

- Sessions 56-60: chosen track (G ML, H pairs, or continued simple ops).
- Sessions 61-65: third instrument; portfolio-level position sizing across
  three strategies.
- Sessions 66+: further expansion and operational maturity.

Live capital + 5 weeks of evidence + a working multi-strategy platform is
the natural plateau. Anything beyond is gravy.
