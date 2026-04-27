---
session: 17
title: Statistical Rigor Audit — DSR, Walk-Forward, Trials, Meta-Labeling
status: Draft
created: 2026-04-17
planner: Claude Code (Opus 4), with data-scientist lead and quant-mentor review
executor: Claude Code (Opus 4 strongly preferred — see Executor Notes)
reviewer: Ibby (human)
branch: session/17-statistical-rigor
depends_on:
  - session-16-antigravity-code-review (Session 16 produces the targeted file list for this audit)
  - session-15-repo-census (for test-baseline reference)
blocks:
  - any live-capital decision on Antigravity-produced metrics
  - session-18-indicator-census and later (downstream of a clean rigor verdict)
repo: https://github.com/ibbygithub/trading-research
---

# Session 17 — Statistical Rigor Audit

## Why this session exists

The Antigravity Sessions 11–13 push landed code that computes numbers Ibby will eventually use to make capital decisions: deflated Sharpe, probabilistic Sharpe, bootstrap confidence intervals, walk-forward out-of-sample metrics, meta-labeling probabilities, permutation importance, SHAP attributions. Each of these is a load-bearing statistic — if the math is wrong, the reports lie, and the lies compound through every downstream decision.

The **data-scientist** persona is the lead voice in this session. The question is not "does this code work" (that's Session 16's structural review). The question is "does this code compute what it claims to compute, under the assumptions the project cares about, without leakage".

This session is the rigor gate. Nothing Antigravity produced goes into a live-capital decision path until Session 17 closes with a verdict.

## Objective

Verify — with citations to primary sources (Bailey & Lopez de Prado 2014 for DSR, Lopez de Prado AFML Ch 7 for purged k-fold, etc.) — that each of the following is correctly implemented: the deflated Sharpe and PSR formulas, the walk-forward purge and embargo gaps, the trials registry semantics, the meta-labeling label construction, the permutation-importance protocol, and the look-ahead strictness of new indicators under the project's next-bar-open fill model. Produce a per-item verdict with evidence. At the end of the session, Ibby knows which Antigravity numbers he can trust, which he can't, and what fixes each problematic number requires.

## In Scope

Session 16 produces a targeted file list; this plan names the checks by topic. Topics in Session 17:

### 1. Deflated Sharpe Ratio (DSR) — `src/trading_research/eval/stats.py`

- Compare implementation against Bailey & Lopez de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality" (2014), equations (10)–(14).
- Check: variance of Sharpe estimator accounts for skew and kurtosis (equation 7), not just `sqrt(n)`.
- Check: expected-max-Sharpe uses the number of trials and their variance correctly (equation 10).
- Check: trial count `N` is sourced from the trials registry, not hardcoded.
- Produce a worked example: given known-distribution returns, DSR output matches the closed-form answer.

### 2. Probabilistic Sharpe Ratio (PSR) — `src/trading_research/eval/stats.py`

- Compare against Bailey & Lopez de Prado 2012.
- Check: benchmark Sharpe input is explicit (default: 0), not implicit.
- Check: handling of non-normal returns (skew, kurtosis) matches the published formula.

### 3. Bootstrap Confidence Intervals — `src/trading_research/eval/bootstrap.py` (and wherever called)

- Check: the bootstrap resamples at the trade level for Sharpe / Sortino / Calmar, and at the bar level (or block) for equity-curve metrics. Resampling bars for a trade metric is wrong.
- Check: number of bootstrap iterations is parameterized and defaulted to ≥1000.
- Check: CI method (percentile vs BCa) documented. Percentile is acceptable for this project; BCa preferred; anything else flagged.
- Check: reproducibility — is a seed accepted?

### 4. Walk-Forward Purge and Embargo — `src/trading_research/backtest/walkforward.py`

- Compare against Lopez de Prado, *Advances in Financial Machine Learning*, Chapter 7 (Cross-Validation in Finance).
- Check: purge gap removes training samples whose **labels** span into the test window. Purge of *features* only is insufficient.
- Check: embargo gap prevents training on samples whose label would be informative about the test window (backward-looking leakage through autocorrelation).
- Check: purge + embargo sizes are parameterized in units of bars, with defaults tied to the strategy's holding period, not a constant.
- Check: the runner produces separate equity curves per fold and does not smooth across fold boundaries.

### 5. Trials Registry — `src/trading_research/eval/trials.py` and `runs/.trials.json`

- Check: every variant run is recorded with parameters, seed, period, and resulting Sharpe (or equivalent).
- Check: the registry is idempotent — re-running an identical configuration does not create a new trial.
- Check: DSR consumes the trial count correctly (ties back to item 1).
- Check: the registry is committed to git (the file's tracked state matters — it is the project's memory of "how many things have we tried").
- Verify that the Antigravity handoff's claim "trials registry now tracked" is accurate.

### 6. Meta-Labeling — `src/trading_research/eval/meta_label.py`

- Compare against Lopez de Prado, AFML Chapter 3.
- Check: labels are constructed using the triple-barrier method or equivalent; label construction does not use future-of-test-bar information.
- Check: the meta-model is fit with purged k-fold that respects the primary model's holding period.
- Check: the reported "meta-labeling readout" is evaluated out-of-sample, not in-sample.
- Check: class imbalance is addressed (report shows class-balanced precision/recall, not just accuracy).

### 7. Permutation Importance and SHAP — `src/trading_research/eval/classifier.py`, `src/trading_research/eval/shap_analysis.py`

- Check: permutation importance is computed on a held-out set, not the training set (training-set permutation is biased and nearly useless).
- Check: multiple-testing correction when ranking features — Benjamini-Hochberg minimum, not raw p-value sorting.
- Check: SHAP values are computed on the held-out set and tied to the same model instance that produced the out-of-sample metrics, not a refit.
- Check: the classifier used (likely LightGBM per `pyproject.toml`) is configured with early stopping on a validation fold to avoid overfit SHAP attributions.

### 8. Look-Ahead Strictness Under Next-Bar-Open Fill

- Enumerate all new indicators added in Sessions 11–13 (Session 16 produces this list).
- For each: at what timestamp is the indicator value usable by the engine? If the strategy's default fill model is next-bar-open, the indicator value used at bar T+1 open must be computable from bars through T close.
- Check: the existing look-ahead-freedom tests cover this. If they do not, that is a finding.
- Deliverable: strict look-ahead test for every new indicator, either confirmed-existing or flagged as missing.

### 9. HTF Aggregation Validation — `resample_daily()` at CME trade-date boundary

- Named in the Antigravity handoff as an open risk. Verify the +6h ET trade-date offset is applied correctly at DST boundaries and at month/year boundaries.
- Produce a worked example: given a specific bar timestamped around 18:00 ET Sunday, which trade-date does it land on, does the code agree.

### 10. Omega / MAR / Calmar / Recovery Factor / Pain Ratio / Tail Ratio / UPI — `src/trading_research/eval/stats.py` (and related)

- Each is a reported metric with a textbook definition. Verify each against its textbook definition.
- Pay special attention to Calmar — the project's headline metric. Any bug here contaminates every evaluation.

## Out of Scope

- **Rewriting any of the audited modules.** Findings get documented. Fixes are separate sessions named after the finding.
- **Auditing pre-Antigravity code** (e.g., `eval/summary.py` is pre-existing; only audited if it shares code with an Antigravity module).
- **Running full backtests.** Session 17 runs synthetic / fixture-based tests that isolate the math. Full-pipeline runs are not the cheapest way to verify an equation.
- **Strategy work, data work, config changes.**
- **GUI review.** Covered in Session 16.
- **Indicator census across the full project.** That is Session 18 (formerly "Session 15 Indicator Census" in the old numbering). Session 17's look-ahead check is scoped to Antigravity-added indicators only.

## Preconditions

- Session 16 complete. Its "Files flagged for Session 17 statistical-rigor audit" section exists.
- `outputs/validation/session-16-antigravity-review.md` is the input list for this session.
- `uv sync` clean; `uv run pytest` baseline (from Session 15) documented.
- `runs/.trials.json` file exists (or is flagged absent by Session 16).

## Deliverables

1. **Statistical Rigor Audit** → `outputs/validation/session-17-statistical-rigor.md`
   - One section per topic (1–10 above).
   - Per topic: claim, reference-check, implementation read, verdict (Correct / Correct-with-caveats / Incorrect / Untestable-in-session), evidence citation (file:function:line), and a fix sketch if Incorrect.
   - Executive summary with a color-coded table: topic × verdict.
   - Explicit statement of what Ibby can and cannot trust from Antigravity-produced reports until fixes land.

2. **Worked Examples** → `outputs/validation/session-17-evidence/`
   - Small scripts that produce known-ground-truth inputs and compare to the implementation's outputs.
   - Example: generate 10,000 synthetic returns with known mean/std/skew/kurtosis → compute PSR via code → compare against analytic PSR computed directly from the distribution parameters.
   - Each script is a one-off audit artifact, not a permanent test in `tests/`. (Permanent tests land in a follow-up session after fixes.)

3. **Finding-to-fix map** → appended to the audit report.
   - For each `Incorrect` or `Correct-with-caveats` verdict, a one-line fix plan: which module, which function, what change.
   - Ordered by severity: a wrong DSR formula is severity-1; a missing seed parameter is severity-3.

4. **Revised DSR trial count source** (documented, not implemented).
   - If the trial count is currently hardcoded and should come from `runs/.trials.json`, document the required wiring. Implementation is a follow-up session.

5. **Session 17 work log** → `outputs/work-log/YYYY-MM-DD-HH-MM-session-17-summary.md`.

6. **CHANGELOG.md entry** for `[SESSION-17]`.

## Acceptance Criteria

- [ ] Each of the ten topics has a section in the audit report with an explicit verdict.
- [ ] Every `Incorrect` verdict cites a primary source (paper, book chapter) and shows where the implementation diverges.
- [ ] Every `Correct-with-caveats` verdict names the caveat precisely and says when the caveat bites.
- [ ] Every `Untestable-in-session` verdict says what additional work is required to move it to a definitive verdict.
- [ ] At least one worked example per numeric topic. A verdict unsupported by a worked example is not a verdict; it is an opinion.
- [ ] Finding-to-fix map orders findings by severity, with severity defined.
- [ ] The executive summary answers the question "which numbers from the Antigravity reports can Ibby currently trust" in plain English.
- [ ] No source code under `src/trading_research/` modified. (This is a reading session.)
- [ ] If Session 16 flagged a blocking issue that Session 17's scope cannot resolve, the audit report escalates it explicitly and proposes a session to fix it.

## Files / Areas Expected to Change

| Path | Change | Why |
|---|---|---|
| `outputs/validation/session-17-statistical-rigor.md` | Created | Deliverable 1 |
| `outputs/validation/session-17-evidence/` | Created | Deliverable 2 |
| `outputs/work-log/<new>-session-17-summary.md` | Created | Deliverable 5 |
| `CHANGELOG.md` | Entry added | Deliverable 6 |

Nothing under `src/`, `configs/`, `tests/`, `notebooks/`, `runs/`.

## Risks / Open Questions

- **DSR variance-of-estimator subtlety.** The Bailey-Lopez de Prado variance formula for the Sharpe estimator includes skew and kurtosis terms. A common implementation bug is to use the `sqrt(n)` approximation, which is only valid for normal returns — and mean-reversion return distributions are emphatically not normal. This is the highest-probability finding.
- **Purge gap may not match holding period.** If the purge gap is hardcoded to a constant (say 5 bars) but strategies hold for 3 hours on 5m bars, that's 36 bars of label overlap — purge of 5 is insufficient. Check the parameterization.
- **Trials registry may double-count.** If the registry records every call to `run_backtest()` regardless of whether the parameters match an existing entry, the trial count inflates and DSR deflates too aggressively. Check for dedup.
- **SHAP on training set is the default SHAP library behavior.** If Antigravity used the default, the attribution scores are biased toward whatever the model overfit. This is easy to check.
- **Meta-labeling class imbalance.** Triple-barrier labels are usually heavily imbalanced (most bars don't trigger). If the reported "meta-labeling readout" shows 95% accuracy, that's not a win; it's the class prior. Check for class-balanced metrics.
- **HTF aggregation at DST.** The +6h offset is tricky across DST transitions if the implementation uses naive arithmetic. Check for a specific DST boundary.
- **Session scope is big.** Ten topics is a lot for one session, but they are all the same kind of work — read an equation, read the code, build a worked example, compare. If the first five topics reveal systemic issues (multiple `Incorrect` verdicts), stop at the mid-session point and surface before proceeding — re-sequencing may be warranted.

## Executor Notes

**Model choice:** Opus 4 strongly preferred. This session is dense math verification with primary-source citation; Sonnet tends to produce plausible-looking verdicts without grounding them. If Opus is unavailable, Sonnet is acceptable for the mechanical comparison (read spec, read code, say "does it match") but the verdicts need human spot-checking before acceptance.

**Persona weighting:** Data-scientist is lead voice. Mentor voice contributes commentary on practical implications — e.g., "if DSR is over-aggressive the strategies look worse than they are, which is actually the safe failure mode; if it's under-aggressive it flatters strategies and puts real money at risk."

Order of work:

1. **Phase A — Read the targets.** Start from Session 16's ordered target list. Read each flagged file in full before writing any verdict.
2. **Phase A — Open the primary sources.** Bailey-Lopez de Prado 2014 (DSR), Bailey-Lopez de Prado 2012 (PSR), Lopez de Prado AFML (purged k-fold, meta-labeling, feature importance). Cite equation numbers or page numbers, not paraphrases.
3. **Phase B — Topic-by-topic verdicts.** Work through topics 1–10 in the order listed. Each topic: read code, read reference, build worked example, render verdict. Commit the audit report section-by-section as verdicts solidify.
4. **MID-SESSION CHECKPOINT after topic 5.** If three or more topics are `Incorrect` by that point, stop. Surface the pattern to Ibby; a systemic problem may need a different response than topic-by-topic fixes.
5. **Phase C — Finding-to-fix map.** Compile after all ten topics have verdicts.
6. **Phase C — Executive summary.** This is where the data-scientist voice writes plain-English trust statements. Mentor voice adds one sentence per item on practical implication.
7. **Phase D — Worked examples moved to `outputs/validation/session-17-evidence/`.** They are not committed as permanent tests; the follow-up fix session will move them to `tests/`.
8. **Phase D — Work log + CHANGELOG.**

If any finding reveals **an obvious look-ahead bug**, that is a severity-1 finding and gets escalated immediately, not left for the report.

## Completion Block

```
Session 17 — Completion

Branch: session/17-statistical-rigor at <SHA>

Commits:
- (sha : message) x6–10

Validation artifacts:
- outputs/validation/session-17-statistical-rigor.md
- outputs/validation/session-17-evidence/ (N scripts, N text outputs)

Topic verdicts (Correct / Correct-with-caveats / Incorrect / Untestable-in-session):
1. DSR: _____
2. PSR: _____
3. Bootstrap CIs: _____
4. Walk-forward purge/embargo: _____
5. Trials registry: _____
6. Meta-labeling: _____
7. Permutation importance / SHAP: _____
8. Look-ahead strictness (Antigravity indicators): _____
9. HTF aggregation at CME trade-date: _____
10. Omega / Calmar / MAR / Recovery Factor / Pain Ratio / Tail Ratio / UPI: _____

Severity-1 findings:
- (list or "none")

Severity-2 findings:
- (list or "none")

Severity-3 findings:
- (list or "none")

Finding-to-fix map: in audit report, section "Finding-to-fix".

Executive summary — what Ibby can trust right now:
(one paragraph, plain English)

Mid-session checkpoint observed: yes / no

Decisions made during execution:
- (any)

Known limitations:
- (any topic with Untestable-in-session verdict)

Follow-up sessions proposed:
- session-<N>-fix-<topic> for each severity-1 finding
- (others)

Next session: per follow-up list, typically starting with the highest-severity fix.
```
