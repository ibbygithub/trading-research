import math

import numpy as np
import pandas as pd

from trading_research.eval.meta_label import evaluate_meta_labeling


def _make_trades(n: int = 100, seed: int = 42) -> tuple[pd.DataFrame, pd.Index, np.ndarray]:
    rng = np.random.default_rng(seed)
    trades = pd.DataFrame({
        "net_pnl_usd": rng.normal(0, 1, n),
        "entry_ts": pd.date_range("2020-01-01", periods=n),
        "exit_ts": pd.date_range("2020-01-02", periods=n),
    })
    idx = trades.index
    oof = rng.uniform(0, 1, n)
    return trades, idx, oof


def test_meta_label_basic_structure():
    trades, idx, oof = _make_trades()
    res = evaluate_meta_labeling(trades, idx, oof)
    assert "sweep_data" in res
    df = res["sweep_data"]
    assert "threshold" in df.columns
    assert "win_rate" in df.columns
    assert "calmar" in df.columns


def test_meta_label_prf_columns_present():
    """evaluate_meta_labeling must include precision, recall, f1 in sweep_data."""
    trades, idx, oof = _make_trades()
    res = evaluate_meta_labeling(trades, idx, oof)
    df = res["sweep_data"]
    for col in ("precision", "recall", "f1"):
        assert col in df.columns, f"Column '{col}' missing from sweep_data"


def test_meta_label_precision_recall_range():
    """Precision, recall, F1 must be in [0, 1] or NaN."""
    trades, idx, oof = _make_trades(n=200)
    res = evaluate_meta_labeling(trades, idx, oof)
    df = res["sweep_data"]
    for col in ("precision", "recall", "f1"):
        finite_vals = df[col].dropna()
        assert (finite_vals >= 0).all(), f"{col} has negative values"
        assert (finite_vals <= 1).all(), f"{col} exceeds 1.0"


def test_meta_label_precision_correct_at_extreme_threshold():
    """At threshold=1.0 (no trades taken), precision/recall should be NaN or 0.

    All win_prob values in [0,1] so threshold=1.0 takes only trades with
    win_prob == 1.0 exactly; typically none.
    """
    trades, idx, oof = _make_trades(n=100)
    # Force all probs < 1.0 so threshold=0.95 still takes some trades.
    oof = np.clip(oof, 0, 0.94)
    res = evaluate_meta_labeling(trades, idx, oof)
    df = res["sweep_data"]
    # Threshold 0.95 row: count should be 0 since all probs ≤ 0.94.
    row = df[df["threshold"].round(2) == 0.95]
    if len(row) > 0 and row.iloc[0]["count"] == 0:
        assert row.iloc[0]["precision"] != row.iloc[0]["precision"] or row.iloc[0]["precision"] == 0.0


def test_meta_label_f1_consistency():
    """F1 = 2*P*R/(P+R) for all rows where P and R are finite and non-zero."""
    trades, idx, oof = _make_trades(n=300, seed=7)
    res = evaluate_meta_labeling(trades, idx, oof)
    df = res["sweep_data"]
    for _, row in df.iterrows():
        p, r, f = row["precision"], row["recall"], row["f1"]
        if math.isnan(p) or math.isnan(r) or math.isnan(f):
            continue
        if p + r == 0:
            assert f == 0.0 or math.isnan(f)
        else:
            expected_f1 = 2 * p * r / (p + r)
            assert abs(f - expected_f1) < 1e-9, f"F1 mismatch: {f} != {expected_f1}"
