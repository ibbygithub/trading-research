# Chapter 43 — Strategy Clustering

> **Chapter status:** [EXISTS] — HDBSCAN-based trade clustering is in
> [`eval/clustering.py`](../../src/trading_research/eval/clustering.py).
> SHAP-based feature attribution is in
> [`eval/shap_analysis.py`](../../src/trading_research/eval/shap_analysis.py).
> Note: `shap` and `numba` have a Windows compatibility issue; the
> SHAP tests are skipped on Windows (OI-013). The underlying module
> is functional but the test suite marks the skip.

---

## 43.0 What this chapter covers

Strategy clustering uses unsupervised learning to find natural groupings
in a trade population — "types" of trade that the entry criteria are
actually capturing. SHAP attribution identifies which features drove a
model's predictions. After reading this chapter you will:

- Know when clustering is useful and when it is not
- Know how to invoke `cluster_trades` and read its output
- Understand SHAP attribution and its limitations for rule-based
  strategies

This chapter is roughly 2 pages. It is referenced by the evaluation
workflow and the ML strategy authoring path.

---

## 43.1 Clustering by performance fingerprint

`cluster_trades` in
[`eval/clustering.py:12`](../../src/trading_research/eval/clustering.py)
uses HDBSCAN (hierarchical density-based clustering) to group trades
by their entry-bar feature vector:

```python
from trading_research.eval.clustering import cluster_trades

result = cluster_trades(
    trades=trades_df,    # trade log from a backtest
    X=features_df,       # feature matrix at entry bar (same index as trades)
)
# result: {"cluster_summary": DataFrame, "n_noise": int, "labels": array}
```

The feature matrix `X` should contain the indicator values at the entry
bar: ATR, RSI, MACD histogram, Bollinger %B, OFI, and whatever else is
in the feature set. HDBSCAN clusters on a standardised version of the
numeric features.

HDBSCAN labels noise points as cluster −1. Noise trades are entries
that did not fit any cluster; there are often many of these if the entry
criteria is broad.

**Reading the cluster summary:**
The output DataFrame has one row per cluster (plus the noise cluster)
with mean net P&L, win rate, trade count, and the top discriminating
features (features with the largest mean difference from the rest of
the population). A cluster with high win rate and low noise membership
represents a "type" of trade that the strategy captures well. A cluster
with low win rate but many members is a drag on performance — and an
indication that the entry criteria is too broad.

**When clustering is useful:**
- Identifying whether a strategy has a hidden "good" and "bad" trade
  type that could be separated by adding a regime filter
- Verifying that a ML model's positive predictions cluster in
  feature-space in a way that makes intuitive sense

**When clustering is not useful:**
- Small trade counts (the function requires at least 50 trades)
- Rule-based strategies with tight entry criteria — all trades will
  cluster together by construction

---

## 43.2 SHAP-based feature attribution

`eval/shap_analysis.py` computes SHAP values for tree-based ML
strategies. SHAP (SHapley Additive exPlanations) attributes each
prediction to individual features using the game-theoretic Shapley
value.

SHAP values answer: "for this specific trade, which features pushed
the model toward a positive prediction and by how much?"

**When to use SHAP:**
Only for ML strategies (strategies using `signal_module:` with a
trained model). SHAP is not meaningful for rule-based strategies
because rule-based strategies don't produce a model to explain.

**Pitfalls:**
- SHAP for gradient boosting is exact; SHAP for deep learning is
  approximate. The platform uses tree SHAP (`shap.TreeExplainer`).
- SHAP assumes feature independence at the margin, which is often
  violated by correlated indicators (ATR and Bollinger width are
  collinear). In a highly correlated feature space, SHAP values are
  unstable.
- SHAP answers "what the model used," not "what is causal." A model
  can latch onto a spurious correlation, produce high SHAP values for
  that feature, and still fail out of sample.

**Windows note:** the `shap` library's interaction with `numba` has a
Windows-specific compatibility issue (OI-013). The test for SHAP
analysis is marked `pytest.mark.skip` on Windows. The module is
functional; the test will be re-enabled when the upstream issue is
resolved.

---

## Related references

- Code: [`eval/clustering.py`](../../src/trading_research/eval/clustering.py) —
  `cluster_trades`
- Code: [`eval/shap_analysis.py`](../../src/trading_research/eval/shap_analysis.py) —
  SHAP attribution for ML strategies
- Chapter 44 — Meta-Labelling
- Chapter 27 — Regime Metrics & Classification

---

*Chapter 43 of the Trading Research Platform Operator's Manual*
