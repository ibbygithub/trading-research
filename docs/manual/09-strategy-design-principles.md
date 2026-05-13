# Chapter 9 — Strategy Design Principles

> **Chapter status:** [EXISTS] — all sections describe conventions and
> postures already operative in the platform. No code work is required;
> the chapter codifies what the codebase and persona files already enforce.

---

## 9.0 What this chapter covers

This chapter explains the design posture behind strategy authoring in this
platform. Before you write your first YAML condition, you should understand
why the platform is opinionated about how strategies are built — what it
encourages, what it discourages, and what it refuses.

After reading this chapter you will:

- Know why the platform insists on rules before ML and simple before complex
- Understand the cost of every parameter knob in deflation terms
- Be able to recognise the overfitting smell in your own work and in
  historical strategy files
- Know the three paths a strategy can take through the dispatch system
  and when to use each
- Understand why YAML is the default expression medium and what the
  YAML evaluator is trying to prevent

This chapter is roughly 4 pages. It is prerequisite reading for
Chapters 10–13 (strategy authoring and configuration) and is referenced
by Chapters 22–23 (walk-forward validation and deflated Sharpe).

---

## 9.1 Rules first, ML second

The standing rule: **a rule-based version of the strategy must work before
any ML wraps it.**

This is not a preference for simplicity as an end in itself. It is a
diagnostic discipline. A strategy that cannot be expressed in a dozen
readable conditions probably doesn't have a clean edge — it has a pattern
that looks like an edge because it was discovered by staring at charts
with enough flexibility to find one. Wrapping that non-edge in XGBoost
will not create an edge; it will create an XGBoost model that memorises
the non-edge with more parameters.

The correct sequence is:

1. State the market hypothesis in plain English.
2. Express it as rule-based entry/exit conditions.
3. Verify the rule-based version in walk-forward. If it doesn't survive,
   the hypothesis is wrong.
4. If the rule-based version survives, consider whether ML improves
   on the signal timing or the exit sizing — not the signal existence.

ML is appropriate when there is already evidence of a real edge and the
question is "can we pick the better trades within this edge?" — not as a
discovery tool for finding the edge in the first place.

> *Why this:* Feature-based ML models optimised on backtest metrics tend
> to learn the test set, not the market. The walk-forward validation step
> exists precisely to catch this — but only if the model is not already
> overfitting the design choices to the test period. A rule-based model
> exposes the hypothesis directly; an ML model encodes it in weights that
> are harder to interrogate when something goes wrong.

This posture also has a practical consequence: rule-based strategies are
debuggable. When a trade fires at an obviously wrong time, the rule that
fired is visible in the YAML. When an ML strategy fires at an obviously
wrong time, the explanation is a SHAP plot. The first is fixable in five
minutes; the second requires a retraining cycle.

---

## 9.2 Parameter discipline

Every knob is a potential mechanism for overfitting. This is not an
argument against knobs — they are how strategies adapt to instrument
differences and regime changes — but it is an argument for consciously
deciding whether something should be a knob.

The test for whether a value should be a knob:

| Test | If yes | If no |
|------|--------|-------|
| Would a different instrument almost certainly use a different value? | Knob | Hard-code |
| Would a different regime almost certainly use a different value? | Regime filter, not a knob | Hard-code |
| Did I choose this value after looking at backtest results? | Danger — see §9.3 | It might be structural |
| Is this the same value every reasonable mean-reversion strategy would use? | Hard-code it | Knob |

The ATR multiplier on a stop is a knob — 1.5× ATR might be right for
6A at 15m but wrong for ZN at 5m. The decision to use ATR as the stop
scale is not a knob — that's a structural choice. If you find yourself
parameterising the *type* of stop (ATR vs fixed ticks vs percentile of
recent range), stop and ask whether you're making a decision or searching
for the best answer on the training set.

**The deflation cost of knobs.** Every knob that is swept across values
and then set to the "best" value adds to the trial count that deflated
Sharpe draws from. One sweep over five values of `target_mult` uses five
of your deflation budget. A strategy with three knobs, each swept across
five values, has already spent 125 trials on a single hypothesis. The
deflated Sharpe for the chosen variant will be substantially below the
raw Sharpe, not because the strategy is bad but because the selection
process inflated the raw number.

The discipline: **decide knob values before you run the backtest on the
test set.** Structural knobs (ATR period 14, Bollinger sigma 2.0, VWAP
bands at 1.0σ intervals) are pre-committed structural defaults, not
sweepable parameters. Knobs that genuinely must be calibrated belong in a
hold-out sweep *before* the test set is touched, with the chosen value
committed in writing before the test set is evaluated.

---

## 9.3 The overfitting smell

Overfitting announces itself through a recognisable pattern: every time
a strategy has a bad stretch, a new filter appears that would have avoided
those specific losing trades.

The diagnostic question: **is this filter solving a real problem or fitting
recent losers?** The four-test battery:

1. **Gradient shape.** Sweep the filter's threshold across its plausible
   range and look at the Calmar gradient. A structural filter produces a
   monotone gradient — more filter → less drawdown, more linearly. A
   data-mined threshold produces a gradient with a sharp peak at the
   "optimised" value and a plateau or decline on either side. The peak
   is noise.

2. **Fold variance.** If the filter helps in some walk-forward folds and
   hurts in others, it is not structural. A structural filter should help
   in the same direction across a majority of folds because it is tracking
   a real market phenomenon (e.g., "high-ATR bars are trending — don't
   fade them") rather than a historical coincidence.

3. **Win-rate confidence interval.** If the win-rate change introduced by
   the filter is not significant at the 95% bootstrap CI level (wide CI
   around the filtered trade set), the filter is not helping in any
   statistically meaningful sense.

4. **The pre-commit test.** Could you have written this filter's logic
   before seeing the losing trades? If the answer is "probably not —
   I noticed the pattern after seeing the losses," the filter is fitting
   the losses, not expressing a market hypothesis.

None of these four tests is individually conclusive. A filter that passes
all four — monotone gradient, consistent fold direction, significant CI
change, pre-committable logic — is a structural gate worth including. A
filter that fails two or more is almost certainly a chart pattern that
will not survive out of sample.

The mentors are opinionated about this. When the data scientist says "fold
variance is inconsistent" and the mentor says "the logic makes sense to
me," the right answer is more walk-forward, not more arguing. The evidence
is the oracle.

---

## 9.4 Three dispatch paths

The backtest engine does not know or care how signals are produced. It
consumes a DataFrame with columns `signal` (int8: 1=long, −1=short, 0=flat),
`stop` (float), and `target` (float), indexed on a tz-aware timestamp.
Anything that produces this DataFrame can be a strategy.

Three paths exist, in recommended order:

**Path A — YAML template.** A `strategy_id.yaml` file contains an `entry:`
block. `YAMLStrategy` in
[`src/trading_research/strategies/template.py`](../../src/trading_research/strategies/template.py)
evaluates the entry/exit expressions with `ExprEvaluator` and produces the
signal DataFrame. No Python is required. This is the default path for all
new strategies. Chapters 10–13 describe this path in full.

**Path B — Registered StrategyTemplate.** A strategy class is decorated
with `@register_template` in
[`src/trading_research/core/templates.py`](../../src/trading_research/core/templates.py)
and the YAML references it via a `template:` key instead of `entry:`.
The template class receives a Pydantic-validated knobs model and returns
signals from Python code. This path is appropriate when the signal logic
requires Python that the YAML evaluator cannot express — multi-step state
machines, rolling computations that cannot be pre-computed in the feature
set, conditional logic involving previous trade history.

**Path C — Python signal_module (legacy).** The YAML specifies a
`signal_module:` key pointing to an importable module path
(e.g., `trading_research.strategies.vwap_reversion_v1`). The module
must expose a `generate_signals(df)` function or compatible interface.
This path exists for compatibility with strategies written before the YAML
evaluator was introduced. New strategies should not use it.

The dispatch is mutually exclusive: exactly one of `entry:`, `template:`,
or `signal_module:` must be present. The engine raises an error if two are
present or none are present. The dispatch logic lives in
[`src/trading_research/backtest/walkforward.py:140`](../../src/trading_research/backtest/walkforward.py)
and
[`src/trading_research/cli/main.py:461`](../../src/trading_research/cli/main.py).

---

## 9.5 Why YAML by default

The YAML `entry:` path (Path A) is the default for three reasons:

**Legibility.** A strategy's signal logic is visible at a glance in the
config file. An operator returning after six months can read the YAML
entry conditions and understand what the strategy is doing. A Python
module requires reading the code — possibly spread across multiple files —
to answer the same question.

**Git provenance.** YAML files are small, human-readable, and
diff-friendly. Every change to a strategy's entry conditions, knob values,
or backtest settings is visible in `git log`. Reconstructing the exact
conditions that produced a given backtest run is possible by checking out
the YAML at the run's recorded code commit (see §16.4).

**Look-ahead prevention by construction.** The expression evaluator is
deliberately restricted. It can only reference columns that exist in the
features DataFrame — columns that were computed by the feature builder from
strictly prior data (because the feature builder enforces the look-ahead
rule — see §4.6). There is no way to accidentally reference a
forward-looking value in a YAML expression, because the evaluator has no
mechanism for it. A Python module can introduce look-ahead by computing
something inline from bar T's close. The YAML evaluator cannot.

> *Why this:* The most common source of a backtest that looks too good is
> an indicator or expression that quietly uses information not available at
> trade time. Restricting the evaluator to a safe arithmetic subset over
> pre-computed feature columns is the structural defence. It is not the
> only defence — the feature builder's look-ahead unit test is the other
> half — but it makes accidental look-ahead in the YAML path essentially
> impossible.

**Non-programmer-readable.** The YAML syntax is close enough to English
that the strategy's logic can be reviewed by someone who knows trading but
does not write Python. That is useful for a desk-level sanity check and
for the operator reviewing a session's work.

The trade-off is expressiveness. When a strategy genuinely requires
Python — because the signal depends on position history, on a rolling
state machine, or on a computation too expensive to pre-compute in the
feature set — Path B (StrategyTemplate) is the correct choice. The rule
is: default to YAML; reach for Python only when YAML cannot express it.

---

## 9.6 Related references

### Code modules

- [`src/trading_research/strategies/template.py`](../../src/trading_research/strategies/template.py)
  — `ExprEvaluator` and `YAMLStrategy`; the full implementation of Path A.

- [`src/trading_research/core/templates.py`](../../src/trading_research/core/templates.py)
  — `StrategyTemplate`, `TemplateRegistry`, `@register_template`; the
  infrastructure for Path B.

- [`src/trading_research/backtest/walkforward.py`](../../src/trading_research/backtest/walkforward.py)
  — dispatch logic for all three paths in the walk-forward runner.

- [`src/trading_research/cli/main.py`](../../src/trading_research/cli/main.py)
  — dispatch logic for all three paths in the single-backtest CLI path.

### Configuration

- [`configs/strategies/`](../../configs/strategies/) — the full set of
  registered strategy YAML files. `6a-monthly-vwap-fade-yaml-v2b.yaml`
  is the worked example in Chapter 10.

### Other manual chapters

- **Chapter 10** — YAML strategy authoring: the grammar and full example.
- **Chapter 11** — Expression evaluator: the exact syntax rules enforced
  by the evaluator; what it refuses and why.
- **Chapter 22** — Walk-forward validation: why gradient shape and fold
  variance are the honest tests for filters discussed in §9.3.
- **Chapter 23** — Deflated Sharpe: quantifying the knob-proliferation
  cost mentioned in §9.2.

---

*End of Chapter 9. Next: Chapter 10 — YAML Strategy Authoring.*
