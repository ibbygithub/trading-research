# Chapter 44 — Meta-Labelling

> **Chapter status:** [EXISTS] — `evaluate_meta_labeling` is in
> [`eval/meta_label.py`](../../src/trading_research/eval/meta_label.py).
> This chapter explains the Lopez de Prado framework and the platform's
> implementation. Cross-reference Chapter 23 (Deflated Sharpe) for
> the statistical context.

---

## 44.0 What this chapter covers

Meta-labelling is a secondary ML layer that filters a primary strategy's
signals by predicting which trades are likely to win. It amplifies a
real edge; it cannot create one from noise. After reading this chapter
you will:

- Know what meta-labelling is and where the idea comes from
- Know when to consider applying it and when it is premature
- Be able to invoke `evaluate_meta_labeling` and read the threshold
  sweep output

This chapter is roughly 2 pages. It is referenced by Chapter 9
(Strategy Design Principles — rules before ML) and Chapter 23
(Deflated Sharpe — additional trials increase deflation).

---

## 44.1 The Lopez de Prado approach

Meta-labelling (Lopez de Prado, *Advances in Financial Machine
Learning*, 2018) introduces a two-stage pipeline:

**Stage 1 — Primary model:** a rule-based strategy (or any existing
signal) that identifies which side to trade and when. This model
produces the entry signals and the direction.

**Stage 2 — Secondary model (the meta-label):** a classifier that
takes the primary signal as a feature alongside market context features
(ATR, RSI, volume regime, etc.) and predicts the probability that the
primary signal's trade will be a winner. Only trades where the
classifier's confidence exceeds a threshold are executed.

The key insight: the secondary model doesn't decide which direction to
trade; only the primary does. The secondary model decides whether to
take the trade at all. This constraint prevents the secondary model
from learning the direction from the features (which would be leakage)
and focuses it on a simpler question: given that the primary model
already decided to go long, is this a good time to go long?

---

## 44.2 When to consider meta-labelling

**Prerequisites that must be met first:**

1. The primary strategy has passed the validation gate (Chapter 46) —
   it has a positive Calmar after costs with walk-forward validation
   and DSR > 0.5. A meta-label on a failing strategy is overfitting
   on top of noise.

2. The trade count is large enough to train a classifier. A minimum of
   500–1,000 trades is a practical floor; below this, the classifier's
   out-of-fold estimates have confidence intervals too wide to be
   useful.

3. The features used by the secondary model are *not* the same features
   used to fit the primary signal. If the primary signal uses Bollinger
   %B and the secondary model also uses Bollinger %B, the secondary
   model is just fitting on the same decision the primary already made.

**Signs that meta-labelling may add value:**
- The strategy has a moderate win rate (50–60%) but a clearly bimodal
  outcome distribution — some entries are strong, others are marginal
- The clustering analysis (Chapter 43) identified a "bad trade" cluster
  that the primary signal cannot distinguish from the "good trade"
  cluster using existing features

---

## 44.3 The `eval/meta_label.py` module

`evaluate_meta_labeling` in
[`eval/meta_label.py:13`](../../src/trading_research/eval/meta_label.py)
takes out-of-fold classifier predictions and sweeps a probability
threshold from 0.30 to 0.90, reporting metrics at each cutoff:

```python
from trading_research.eval.meta_label import evaluate_meta_labeling

results = evaluate_meta_labeling(
    trades=trades_df,         # trade log
    X_index=oof_index,        # subset of trades used in training
    oof_preds=oof_proba,      # out-of-fold win-probability predictions
)
# results: list of {"threshold", "count", "win_rate", "calmar",
#                   "precision", "recall", "f1"} dicts
```

The threshold sweep shows the trade-off between coverage (how many
trades pass the filter) and quality (win rate and Calmar of filtered
trades). At threshold 0.30, most trades pass and the filtered metrics
are close to the unfiltered baseline. At threshold 0.80, few trades
pass but those that do have substantially higher win rate.

The optimal threshold is **not** the one that maximises Calmar on the
training data. It is the one that produces the best trade-off between
sample size (needed for CI reliability) and quality improvement — and
it must be validated out of sample. The training threshold is a form of
leakage if it is applied to the test set.

> *Why this:* meta-labelling is seductive because the threshold sweep
> always shows some threshold with a higher Calmar than the baseline.
> That is guaranteed — any filter that removes trades will shift the
> distribution. The question is whether the improvement holds out of
> sample, and that question requires an honest train/test split. A
> threshold fit on the same data it's evaluated on is a leakage
> exactly as dangerous as a fitted percentile cutoff on the same data
> (the original data-scientist persona's example, Chapter 3).

---

## Related references

- Code: [`eval/meta_label.py`](../../src/trading_research/eval/meta_label.py) —
  `evaluate_meta_labeling`
- Chapter 9 — Strategy Design Principles (rules first, ML second)
- Chapter 22 — Walk-Forward Validation (train/test split for the
  secondary model)
- Chapter 23 — Deflated Sharpe (each meta-label threshold is a trial)
- Chapter 43 — Strategy Clustering (identifying the feature basis for
  meta-labelling)

---

*Chapter 44 of the Trading Research Platform Operator's Manual*
