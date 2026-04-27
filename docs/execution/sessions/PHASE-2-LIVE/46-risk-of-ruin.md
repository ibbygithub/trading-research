═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           46
Required model:    Opus 4.7 + Ibby (joint session)
Effort:            M (~2 hr)
Entry blocked by:  45 (DONE) with all-READY verdict
Hand off to:       47
Branch:            session-46-risk-of-ruin
═══════════════════════════════════════════════════════════════

# 46 — Risk-of-ruin + first-live-trade size commitment

## Self-check
- [ ] I am Opus 4.7.
- [ ] 45 all-READY verdict.
- [ ] Ibby is present for this session (joint).

## What you produce

### Risk-of-ruin (DS lens)
Compute the probability of hitting -X% drawdown before reaching +Y% gain at the chosen position size, given:
- Account equity (Ibby specifies dollar amount in the session).
- Strategy expectancy (from session 44 paper data).
- Strategy variance (from session 44 paper data).
- Position size (the question — recommend 1 micro M6E by default).

Use Kelly fraction with 0.25× sub-Kelly haircut.

### First-live-trade size (Mentor lens)
- Default: 1 micro M6E contract.
- Justification: live execution may surface bugs. First trade is a system test, not a return engine.
- Scaling rule pre-committed in session 50; not negotiable mid-stream.

## Output
- `risk-of-ruin-analysis.md` with calculation method, inputs, output, and acceptance.
- A signed-by-Ibby commitment (literal text in the session log): "First live trade is 1 micro M6E contract. Scaling requires session 50's pre-committed rule. I have read the risk-of-ruin output and accept it."

## Acceptance
- [ ] Risk-of-ruin computed; result acceptable to all three personas + Ibby.
- [ ] First-trade size committed in writing.
- [ ] L8 and L9 of session 45 gate now satisfied.
- [ ] Handoff: `docs/execution/handoffs/46-handoff.md`.
- [ ] current-state.md: 46 → DONE; 47 → READY.

## What you must NOT do
- Recommend a first-trade size larger than 1 micro M6E without explicit Ibby override.
- Skip the signed commitment text.
- Compute risk-of-ruin without Ibby providing the actual account equity.
