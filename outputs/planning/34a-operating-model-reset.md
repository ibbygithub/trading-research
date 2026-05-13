# Operating-Model Reset — Trading Research is a Research Lab, Not a Deployment Pipeline

**Session:** 34a
**Date:** 2026-05-03
**Status:** Decision committed; supersedes the bridge/paper/live framing in plan v2 sprint 33–38
**Authorized by:** Ibby (in-conversation, 2026-05-03)
**Persona sign-offs:** Quant Mentor, Data Scientist, Platform Architect

---

## 1. The decision in one paragraph

Sessions 34–38 are reframed. The project is a **research lab for designing,
testing, and iterating on trading strategies**, not a pipeline that pushes a
single chosen strategy from backtest to paper to live on a calendar deadline.
The validation gate (walk-forward, deflated Sharpe, max consecutive losses,
cohort consistency) applies **only at the live-capital transition**. Every
strategy iteration before that point is exploration, not validation. The
**June 30, 2026 paper-trade deadline is dropped.** The trigger for paper
trading is "Ibby has a strategy he believes in after honest exploration,"
not a date.

## 2. What changed and why

### What the v2 plan assumed

Plan v2 (sprints 29–38) was written assuming `vwap-reversion-v1` was a viable
candidate that needed validation, not invention. Sprints 29–33 hardened the
candidate; sprints 34–38 took it through bridge → paper → live. Every
strategy iteration ran through the full validation gate (sprint 33's seven
criteria). The June 30 paper-trade deadline was the calendar discipline
attached to that trajectory.

### What sprint 33 revealed

The validation gate is correct. It worked exactly as designed — sprint 33
returned a unanimous FAIL on `vwap-reversion-v1` with all three personas
agreeing. The math is honest.

What revealed itself in sprint 34a's reframe conversation is that **applying
the validation gate to every strategy iteration is the wrong calibration**.
The validation gate is calibrated for "is this strategy ready for live
capital?" That's the right question to ask once. It's the wrong question to
ask of every variant during exploration.

### Ibby's reframe (verbatim, 2026-05-03)

> the whole point of me making a trading desk with back testing is to develop
> a winning strategy. […] I want to be able to start working with features,
> different time frames, run thousands of monte Carlo test but i can't because
> see need to go thru another 10 sessiosn of work but you guys keep flagging
> that the one example of a trade is not producing good results.

Ibby is correct. The v2 framing pushed every test through a validation gate
calibrated for capital allocation. That gate is correct *as a gate*; it is
wrong *as a step in iteration*.

## 3. The operating model going forward

### Two run modes, distinct rules

**Exploration runs.** The default. Used during strategy design, parameter
tuning, indicator/timeframe experimentation, regime-filter prototyping.

- Recorded in the trial registry with `mode: "exploration"`.
- Bootstrap CIs computed because they're cheap.
- **No pass/fail gate.** Output is "interesting / not interesting / surprise."
- No deflation applied at this stage; trial count accumulates against the
  candidate when it's eventually validated.
- Mentor and data scientist comment qualitatively, not categorically.

**Validation runs.** Used once a candidate strategy has been chosen for
paper-trading consideration.

- Recorded with `mode: "validation"`.
- Full ceremony: rolling walk-forward, bootstrap CIs, deflated Sharpe with
  `n_trials` set to the count of variants tested in exploration, per-fold
  stationarity, cost sensitivity, cohort consistency.
- The seven-criterion gate from sprint 33 applies here, and only here.
- Pass → eligible for paper trading. Fail → back to exploration with what
  was learned.

### Trigger conditions, not deadlines

Paper trading begins when *any* of the following becomes true:

1. A strategy passes the validation gate cleanly (all seven criteria) on
   exploration data, AND the data scientist signs off that the deflated
   Sharpe survives the cohort multi-testing correction.
2. Ibby explicitly authorizes paper-trading a candidate that passes a
   subset of criteria with documented overrides (his judgment call, not
   a calendar's).
3. A pairs/spread strategy with positive expected value and structurally
   bounded risk emerges, even if its single-leg metrics are unimpressive
   (different regime, different evaluation).

Live capital follows a successful paper-trading window of agreed length,
which is a separate decision.

### The June 30 deadline is dropped

The deadline was a mentor instinct ("real desks ship") applied to a project
that is still in the lab phase. It was wrong as written. It is removed from
the plan and from any persona's pushback list.

## 4. What this changes about sessions 34–38

### Old (v2)

| Session | Old contract |
|---|---|
| 34 | Bridge option pick (TS SIM vs TV Pine), begin E1/E1' |
| 35 | E2 paper-trading loop |
| 36 | First paper trade + 30-day discipline window |
| 37 | Hardening pass + monitoring polish |
| 38 | Trader's-desk polish + readiness review |

### New (v3)

| Session | New contract |
|---|---|
| **34** (this) | Operating-model reset doc; plan v3 addendum; 6A and 6C 16-year pipelines; two new mentor-designed strategies |
| **35** | Parameter-sweep tool + N-trial leaderboard (architect items 2 + 3) |
| **36** | YAML-only strategy authoring system (architect item 1) |
| **37** | Multi-timeframe + composable feature/regime layers |
| **38** | First structured exploration: ~5 hypotheses × ~20 variants, logged and compared |

The bridge/paper/live work (TS SIM API, Pine port, kill-switch hierarchy
integration with execution) is **deferred, not deleted**. It returns to the
plan when a candidate passes validation. Track D loss limits and the kill
switches built in earlier sessions remain in `src/` and are not regressed.

## 5. What is preserved from v2

- **Trial registry** continues. Schema gets a `mode` field added in session 35
  to distinguish exploration vs validation runs. Existing trials are
  retroactively tagged "validation" since they were run under the old gate.
- **Walk-forward harness** continues to be the default for any backtest
  reported with a Sharpe/Calmar number, exploration or validation.
- **Three personas** continue. Their tone changes during exploration: less
  categorical pass/fail, more "interesting because…" / "watch out for…".
  At validation time they go back to their gate posture.
- **Sprint 33 verdict on `vwap-reversion-v1`** stands. The strategy is
  shelved, not deleted. A future session may revisit if a new feature or
  regime filter materially changes the hypothesis.
- **Track A pipeline genericity** is preserved. The 6A and 6C downloads in
  this session prove again that the pipeline takes any registered instrument
  with no code changes.

## 6. What this enables (concretely)

By end of session 34 (this one):

- 6A and 6C are downloaded for 16 years (2010-01-01 → today), at 1m base
  with 5m/15m/60m/240m/1D resamples and base-v1 features applied.
- Two new strategies — designed by the quant mentor, in writing, with
  rationale anchored in market structure — are implemented as Python
  modules and YAML configs.
- Both strategies are runnable via the existing `backtest` CLI command.
- The replay app remains available for visual trade verification.

By end of session 36:

- Ibby can sit down, write a strategy in a YAML config (no Python), run
  it against any registered instrument and timeframe, see metrics, and
  click through every trade on a chart.

By end of session 38:

- Multiple hypotheses have been tested in a structured exploration. The
  trial registry contains 50+ tagged exploration runs. Any candidate that
  shows promise is one validation run away from paper-trading consideration.

## 7. Persona sign-offs

### Quant Mentor

> Approved. The June 30 deadline was mine and it was wrong for a desk
> that's still being built. Lab phase first; deadline-driven shipping
> when there's a candidate. I'll keep pushing on market structure, but
> I'll stop demanding pass/fail on every iteration. Exploration is for
> learning, not for proving — that's a distinction I should have drawn
> three sessions ago.
>
> One condition: if Ibby asks me to design strategies in a session, I
> design them honestly — which means I'll sometimes propose ideas that
> may not work in this market regime. The lab is where you find that
> out. That's the job.
>
> Signed: Quant Mentor — 2026-05-03

### Data Scientist

> Approved. The validation gate I built and operated in sprint 33 was
> applied at the wrong stage. I should have insisted earlier on a
> separation between exploration and validation runs. The gate is correct
> as a gate; it was wrong as a per-iteration filter.
>
> Two technical conditions:
> 1. The trial registry needs a `mode` field by end of session 35 so
>    exploration and validation runs are distinguishable. Until then, any
>    new exploration trials get tagged in the work log narrative.
> 2. When a candidate emerges from exploration and goes to validation,
>    `n_trials` for the deflated Sharpe must equal the actual exploration
>    variant count. The deflation belongs to the candidate; we do not
>    cheat on this just because the count is large.
>
> Signed: Data Scientist — 2026-05-03

### Platform Architect

> Approved. The architectural gaps I named earlier (no template authoring,
> no parameter sweep, no multi-trial leaderboard, no exploration tag) are
> real and they are the actual blockers to research velocity. The reflowed
> sessions 35–37 close those gaps. Three sessions, not eight.
>
> One condition: deferred work (TS SIM, Pine port, execution-side
> kill-switch integration) must remain *deferred*, not *forgotten*.
> Track D loss-limit code stays in `src/` and is not regressed by any
> session 35–38 change. When a candidate passes validation and we
> reactivate the bridge work, that code should still build and pass
> tests as written.
>
> Signed: Platform Architect — 2026-05-03

---

## 8. References

- `docs/roadmap/session-specs/session-33-track-c-gate.md` — the validation
  gate that defines what "validation" means.
- `outputs/planning/33b-gate-review.md` — sprint 33 verdict; the failure
  shape that triggered this reframe.
- `outputs/planning/sprints-29-38-plan-v2.md` — superseded by plan v3
  addendum (this session).
- `CLAUDE.md` — project standing rules; this doc does not override any of
  them, only the v2 plan's session-by-session contract.
