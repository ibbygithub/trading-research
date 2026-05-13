# Session 33b — Track C Gate Review

**Date:** 2026-05-03  
**Strategy under test:** `vwap-reversion-v1` + VolatilityRegimeFilter(P75 ATR) + Mulligan scale-in (v2)  
**Run artifacts:** `runs/vwap-reversion-v1-6E-v2-73d8514f/trial.json`  
**Git SHA:** 241bb05  
**Procedure status:** Pre-committed (sprints-29-38-plan-v2.md, sprint 33 spec)

---

## Input data summary

| Metric | v2 Realistic (2.0 tk, $4.20) | v2 Pessimistic (3.0 tk, $4.20) | v1 Reference (sprint 30 #4) |
|---|---|---|---|
| Folds positive | 0/10 | 0/10 | n/a (contiguous-seg) |
| Binomial p (vs p=0.5) | 1.0000 | n/a | n/a |
| Calmar (point) | −0.1382 | −0.1382 | −0.0984 |
| Calmar CI 95% | [−0.138, −0.138] | [−0.138, −0.138] | [−0.099, −0.098] |
| Sharpe | −15.19 | −17.45 | −5.34 |
| Win rate | 12.9% | n/a | 39.2% |
| Total trades | 6,839 | 6,349 | 5,041 |
| Max CL (point) | 87 | n/a | 13 |
| Max CL p95 (bootstrap) | 70.0 | n/a | n/a |
| Cohort DSR (n=12) | 0.0 | — | — |
| Per-fold stationarity | INDETERMINATE ×10 | — | — |

**Critical observation:** v2 is a significant deterioration from v1. Sharpe worsened from −5.34 to −15.19. Win rate collapsed from 39% to 13%. Max consecutive losses rose from 13 to 87. Mulligan amplified the strategy's core losing behavior rather than improving it.

---

## Gate criteria applied

### G1 — Fold count

**Criterion:** ≥6 of 10 folds positive AND binomial p-value < 0.10.

**Result:** 0/10 folds positive. Binomial p-value = 1.0000.

**FAIL.** Not even close. Every fold loses. The null hypothesis (random coin flip) cannot be rejected in any direction.

---

### G2 — Calmar CI

**Criterion:** Bootstrap 95% CI lower bound on aggregated Calmar ≥ 1.5.

**Result:** CI = [−0.1382, −0.1381]. Lower bound = −0.1382.

**FAIL.** The strategy is deeply in negative territory. The CI is pathologically tight (essentially no variance in the bootstrap) because the Calmar is consistently negative across all fold and cost configurations. The required threshold of 1.5 is not within reach by any analysis.

---

### G3 — Deflated Sharpe

**Criterion:** DSR (cohort n_trials = 12) CI must exclude zero.

**Result:** DSR = 0.0 exactly. Raw Sharpe = −15.19. The DSR formula maps any deeply negative Sharpe to probability 0.0 of exceeding the benchmark. CI trivially includes zero; it IS zero.

**FAIL.** The deflated Sharpe is mathematically bounded at 0.0 when the raw Sharpe is negative. n_trials = 12 (8 v1-cost-sweep sprint 30 + 2 session-31b + 2 v2 this run). No adjustment of trial count changes this result.

---

### G4 — Max consecutive losses

**Criterion:** 95th percentile of bootstrapped max-consecutive-losses distribution ≤ 8.

**Result:** Point estimate = 87. Bootstrap p95 = 70.0. Bootstrap p50 = 50+.

**FAIL, severely.** The p95 of 70 is approximately 9× the allowed threshold. For context: a solo retail trader watching a mean-reversion strategy produce 70 consecutive losses would have abandoned it long before trade 70. This is a strategy that cannot be operated in practice.

**Root cause (Mulligan interaction):** When the market trends away from VWAP, the VWAP spread widens continuously. Every bar where spread > entry_threshold crosses the threshold again, `exit_rules` emits `scale_in`, and the engine adds a second losing leg. The net effect is that a single trending move generates one original losing trade plus one Mulligan leg per valid scale-in bar — and because both legs lose, the consecutive loss count effectively doubles. M-2 gate (n_atr=0.3 ≈ 0.3 × 0.00025 ≈ 0.0001 on 6E) is insufficient to block this in a sustained trend; it only prevents the scale-in from entering if price has moved more than 0.0001 beyond the original entry.

---

### G5 — Per-fold stationarity preserved

**Criterion:** vwap_spread classification does not flip across folds. Mixed classification means regime-fitting.

**Result:** All 10 folds return INDETERMINATE. Unique classification set: {INDETERMINATE}. Consistent = True.

**PASS with caveat.** No flip occurred — classifications are consistent. However, INDETERMINATE is not a confirmation of stationarity. The session 28 full-dataset run (2018–2024) classified vwap_spread as STATIONARY. Per-fold INDETERMINATE results from 6-month test windows: the OU half-life and ADF test lack statistical power on ~6,000 bars of a single fold. The composite classification logic requires all three tests (ADF, Hurst, OU) to agree; when any test is inconclusive on a short window, the result is INDETERMINATE.

**Interpretation:** The stationarity property is present in the full dataset but not provable in 6-month slices. This is an expected artifact of the evaluation window length, not evidence that stationarity flipped. The G5 criterion (no flip) is technically satisfied.

---

### G6 — Cost robustness

**Criterion:** Strategy passes G1–G5 under realistic configuration. Pessimistic is reported but does not gate. If pessimistic Calmar CI lower bound < 0.5, surface as mentor concern.

**Result:** Realistic fails G1–G5 (evaluated above). Pessimistic Calmar CI lower bound = −0.138.

**FAIL (realistic does not pass G1–G5).** Pessimistic CI lower bound = −0.138 << 0.5 → **mentor concern triggered.** The strategy loses money at all cost configurations evaluated. There is no cost regime under which it becomes viable.

---

### G7 — Cohort consistency

**Criterion:** All trials in the current cohort share `engine_fingerprint`. If the engine changed mid-sprint, rerun affected trials or split cohort with explicit justification.

**Finding:** The cohort spans three code versions:
- `2e87e7e`: session 30 trials (8 variants, contiguous-segmentation walkforward). Engine state: no Mulligan wiring.
- `41efe0a`: session 31 trials (2 variants, rolling walkforward). Engine state: no Mulligan wiring.
- `241bb05`: session 33 trials (2 variants, rolling walkforward). Engine state: Mulligan wiring added (session 32).

**Justification for PASS:** The session 32 engine change added Mulligan wiring gated on `strategy.knobs["mulligan_enabled"]`. For all non-Mulligan strategies (sessions 30 and 31), the code path through the engine is identical before and after the session 32 change — the Mulligan block is `if self._strategy is not None and not mulligan_active` followed by `if exit_dec.action == "scale_in"`, which is dead code for strategies that always return `hold`. The fill logic (`fills.py`), P&L computation, stop/target resolution, and EOD flat logic are unchanged across all three versions. Additionally, sessions 30 and 31 used different evaluation methodologies (contiguous vs rolling walk-forward), but this difference is explicit, documented, and was mandated by the sprint specs.

**G7: PASS** — with written justification above. Recommendation: add explicit `engine_fingerprint` hash field to trial schema in a future session to make this verifiable programmatically rather than by inspection.

---

## Summary table

| Gate | Result | Gate Value | Required |
|---|---|---|---|
| G1 Fold count | **FAIL** | 0/10, p=1.000 | ≥6/10, p<0.10 |
| G2 Calmar CI | **FAIL** | CI lo = −0.138 | ≥1.5 |
| G3 DSR | **FAIL** | DSR = 0.0 | CI excludes zero |
| G4 Max CL p95 | **FAIL** | 70.0 | ≤8 |
| G5 Stationarity | PASS (caveat) | Consistent INDETERMINATE | No flip |
| G6 Cost robustness | **FAIL** | realistic fails G1–G5; pess. LB=−0.138 | realistic passes G1–G5 |
| G7 Cohort consistency | PASS (justified) | mixed versions, documented | same engine_fingerprint |

**ALL SEVEN: 5 FAIL, 2 PASS (G5 with caveat, G7 with justification).**

---

## Persona verdicts

---

## Quant Mentor verdict — FAIL

```
G1: FAIL — 0/10 folds positive, binomial p=1.0. The strategy is not extracting edge
    at any point in the seven-year evaluation window under any cost scenario.

G2: FAIL — Calmar CI lower bound −0.138. A CI this deep negative isn't even pointing
    at the right planet, let alone the right city. We need 1.5; we're at −0.138.

G3: FAIL — DSR 0.0. When raw Sharpe is −15, there's nothing to deflate. Zero.

G4: FAIL — Max consecutive losses p95 = 70. I've blown up accounts for less than
    this. No retail trader, no prop desk, nobody runs a strategy with 70 consecutive
    losers in its tail. This is not a psychological concern; it's a capital concern.
    At 1 contract per trade, 70 consecutive losses on 6E is approximately $70,000–
    $100,000 in drawdown depending on average loss size. On a $50k account this is
    a 100–200% drawdown. That's not a number; it's the end of the account.

G5: PASS (caveat) — All folds return INDETERMINATE. No flip, so the letter of the
    criterion is met. The spirit — confirming that the spread is stationary in each
    fold — is not. I'll take the technical pass but flag it.

G6: FAIL — Realistic fails G1–G5, so the gate language is met. Pessimistic also loses
    money. The cost concern is moot when the strategy loses before costs.

G7: PASS (justified) — Engine fingerprint argument is sound. Mulligan wiring is dead
    code for non-Mulligan strategies. The methodology difference (contiguous vs rolling)
    is documented and spec-required.

Recommendation: go to escape path.

Additional finding: Mulligan drastically worsened the strategy. Win rate dropped from
39% to 13%. This is not a Mulligan tuning problem — it's a strategy architecture
problem. When a mean-reversion strategy enters against a trend, the VWAP spread keeps
widening. Every bar that the position is held and the spread is still extended LOOKS
like a fresh entry opportunity. Mulligan fires on what is actually an averaging-down
into a trend. M-2's 0.3×ATR gate is too loose to prevent this on 6E. There is no
Mulligan parameter value that fixes this without also breaking the cases where Mulligan
is genuinely useful, because the entry signal (VWAP spread > threshold) and the
continuation-of-loss signal (VWAP spread still > threshold on the next bar) are
indistinguishable from the strategy's perspective.

The root problem is the strategy, not the parameters. The 6E VWAP reversion thesis
requires the spread to be mean-reverting within the session. The 2018–2024 data says
it isn't, at least not reliably enough to be tradeable after costs.

Escape path: negative aggregate equity, most folds losing (G2/G3 hard fail).
Pre-committed rule: Switch strategy class → sprint 34a picks momentum or breakout
from the session 28 stationarity follow-up.

Signed: Quant Mentor
Date: 2026-05-03
```

---

## Data Scientist verdict — FAIL

```
G1: FAIL — 0/10. Binomial p-value = 1.0 is as far from the rejection region as it is
    possible to be. Under H0 (strategy is a coin flip), observing 0 positive folds in
    10 trials has probability 0.001 under H1. We are observing it. The strategy's
    performance is not a coin flip — it's systematically negative.

G2: FAIL — Bootstrap CI = [−0.1382, −0.1381]. Note how pathologically tight this
    interval is. A tight CI around a negative number is not encouraging; it's a
    statement that the strategy consistently loses by about the same amount every
    sample. There is no sampling scenario in which it approaches 1.5. The distance
    between the CI upper bound and the required threshold is 1.638 Calmar units.

G3: FAIL — DSR = 0.0. Mathematical floor. Cannot be interpreted further. The
    probabilistic Sharpe Ratio formula requires a non-negative raw Sharpe to produce
    a meaningful probability. With raw Sharpe = −15.19, the probability of the true
    SR exceeding the multi-trial benchmark is indistinguishable from zero.

G4: FAIL — Max consecutive losses p95 = 70. I want to emphasize the bootstrap here.
    The point estimate of 87 consecutive losses could theoretically be an outlier.
    The bootstrap gives us the distribution. p95 = 70 means: in 95% of simulated
    trade sequences drawn from the realized distribution, you would see at most 70
    consecutive losses. In other words, the probability of experiencing more than
    8 consecutive losses in this strategy is approximately 1.0. The gate requires
    this to be approximately 0.05.

    The win_rate of 12.9% mathematically explains the consecutive-loss distribution.
    At win_rate = 0.129, the expected length of a losing run follows a geometric
    distribution with mean 1/(1−0.129) ≈ 1.15 runs of length ≥ k before a win. But
    consecutive losses scale with (1−win_rate)^k: P(≥20 consecutive losses) ≈ 0.077.
    P(≥50) ≈ 0.001. The realized values are far worse because the VWAP-deviation
    entries correlate temporally — the strategy tends to enter in trending periods
    when it's most likely to be wrong repeatedly.

G5: PASS (caveat) — Technically consistent (all INDETERMINATE). I'm not satisfied
    that INDETERMINATE is the same as STATIONARY. The session 28 result was STATIONARY
    on the full dataset. Per-fold INDETERMINATE reflects insufficient statistical power
    in 6-month windows, not a change in the underlying spread dynamics. I'll accept the
    technical pass but note that this criterion was designed to catch regime-flipping;
    it wasn't designed for the case where every fold is inconclusive.

G6: FAIL — Realistic fails G1–G5 before we even consider cost robustness.
    Pessimistic CI lower bound = −0.138 << 0.5. Mentor concern: surfaced.

G7: PASS (justified) — The argument that Mulligan wiring is dead code for non-Mulligan
    strategies is verifiable: `if self._strategy is not None and not mulligan_active`
    followed by `if exit_dec.action == "scale_in"` — for V1/filtered strategies,
    `exit_rules` returns `hold` and this branch is never taken. The P&L computation
    for those trades is identical across engine versions. I accept the justification.

The Mulligan deterioration is a methodological finding worth recording:
- Win rate: 39.2% → 12.9% (−26.3 percentage points)
- Sharpe: −5.34 → −15.19 (−9.85)
- This is not a parameter-tuning failure. With the regime filter blocking only the
  top 25% of high-ATR bars, the remaining 75% includes sustained directional moves.
  The Mulligan fires during those moves (spread widens → VWAP threshold crossed again
  → scale_in emitted → M-2 gate at 0.3×ATR insufficient to block). The second leg
  enters into the direction of the trend, at a worse price, and loses. The net effect
  is: the Mulligan converts what would have been a single losing trade into a losing
  trade + a losing scale-in, on a systematic basis.

Recommendation: escape path. The data is unambiguous.

Signed: Data Scientist
Date: 2026-05-03
```

---

## Platform Architect verdict — FAIL

```
G1: FAIL — 0/10 folds. No architectural point to add; the strategy does not work.

G2: FAIL — Calmar CI [−0.138, −0.138]. This CI being this tight is itself an
    architectural observation: the strategy's losses are highly consistent across
    the bootstrap samples, which means the trade return distribution has very low
    variance relative to the mean loss. In other words, it reliably loses a fixed
    amount per trade. That's a feature of a deterministic loser.

G3: FAIL — DSR = 0.0.

G4: FAIL — p95 = 70 consecutive losses. I want to record this as a systems finding,
    not just a performance finding: an engine that allows 87 consecutive trade
    closures in one direction without triggering any circuit breaker is an engine
    that needs circuit breakers before it goes anywhere near a live account. Track D
    (loss limits) is built; the daily loss limit would have triggered much earlier
    than trade 87 in a live account. But in the backtest, there is no circuit
    breaker, so the engine happily runs 87 losers. This is correct for backtest
    purposes — we want to see the full distribution — but it reinforces why Track D
    is not optional.

G5: PASS (caveat) — Consistent INDETERMINATE. My observation: the composite
    stationarity classification logic should handle the insufficient-sample case
    explicitly (return "INSUFFICIENT_WINDOW" rather than "INDETERMINATE") so that
    per-fold reports distinguish between "tests ran but were ambiguous" and "tests
    ran and contradicted each other." This is a minor schema debt item; logging it
    for a future session, not blocking the verdict.

G6: FAIL — as above.

G7: PASS (justified) — The engine_fingerprint problem is a real architectural gap.
    The trial schema does not include a hash of the engine's fill logic. Adding
    engine_fingerprint = hash(fills.py + engine.py core paths) to trial records
    would make G7 mechanically verifiable rather than requiring manual code inspection.
    Recommend adding this in a future session (not sprint 33 — out of scope).
    For the current cohort, the manual justification is sound.

Systems finding — Mulligan implementation:
The Mulligan correctly enforces M-1 (freshness) and M-2 (directional gate). The
problem is not the implementation — it's the assumption embedded in the design:
that a VWAP reversion strategy in a trending market will eventually produce "fresh"
signals in the position's direction. It does: `generate_signals` emits a new long
signal every time close − vwap < −2.2×ATR, regardless of the position state. In a
trending market, this happens repeatedly. Mulligan then systematically fires into
each of those "fresh" signals. The freshness rule (M-1) was designed to prevent
same-signal re-entry; it was not designed to prevent a trend from generating
multiple independent fresh signals that all happen to be on the same (losing) side.

This is a strategy architecture issue. The Mulligan infrastructure is correct;
the strategy feeding it produces the wrong class of signals.

Recommendation: escape path. The architecture is sound; the strategy has no edge.

Signed: Platform Architect
Date: 2026-05-03
```

---

## Pre-committed escape rule applied

**Failure shape:** Negative aggregate equity (Calmar = −0.138), all 10 folds losing (G2/G3 hard fail).

**Pre-committed rule from sprints-29-38-plan-v2.md:**

> *Negative aggregate equity, most folds losing (G2/G3 hard fail) → Switch strategy class → 34a picks momentum or breakout from session 28 stationarity follow-up.*

**Escape path activated:** Switch strategy class.

**Sprint 34 action:** Sprint 34a is a design conversation (Opus-model) that selects the next strategy class from the session 28 stationarity follow-up results. Candidates: momentum (Hurst > 0.5 regime), breakout (volatility expansion on range compression), or event-driven (release-calendar-anchored moves). The 6E data pipeline, feature set, and walk-forward infrastructure are fully in place and reusable. The VWAP reversion template is shelved — not deleted.

**TradingView port path (E1'):** Given the June 30, 2026 paper-trade deadline and the cost of another full strategy iteration cycle (sessions 34–36), Ibby should explicitly decide at the sprint 34 design conversation whether to:
1. Design and backtest a new rule-based strategy class (~3 sessions), or
2. Port the best available candidate to TradingView for manual paper trading now, and build the new strategy class in parallel.
The platform architect notes that both paths are viable; the decision belongs to Ibby.

---

## Final verdict

**FAIL. Escape path: Switch strategy class.**

All three personas agree. The procedure is applied as pre-committed. Sprint 34a entry condition: design conversation selecting next strategy class from session 28 stationarity outputs. The 6E VWAP mean reversion template is shelved.

Dated: 2026-05-03  
Ibby's override: not applicable (unanimous FAIL, no synthesizer judgment required).
