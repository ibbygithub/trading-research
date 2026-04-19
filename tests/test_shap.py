"""SHAP per-trade attribution test.

SKIP REASON (OI-013):
  shap 0.51.0 pulls in numba 0.65.0 + llvmlite 0.47.0.  On Windows this
  combination causes a fatal JIT access violation in
  llvmlite.binding.executionengine.check_jit_execution at the moment shap's
  clustering module first exercises the LLVM JIT.  This is an OS-level crash
  (not a Python exception) and cannot be guarded with try/except.

  Fix: pin a compatible numba + llvmlite combination via `uv add`, re-lock,
  and remove the skip marker.  Candidate pin:
      numba>=0.60.0,<0.61  llvmlite>=0.43.0,<0.44
  Validate with `uv run python -c "import shap"` before re-enabling.

  The two-bug fix below is also applied so that when the marker is removed
  the test exercises real behaviour:
    1. purge_bars=10  (was 100 — skipped every fold on 100-sample input)
    2. Correct key checks on the classifier result dict
"""

import numpy as np
import pandas as pd
import pytest


@pytest.mark.skip(
    reason=(
        "OI-013: shap 0.51.0 / numba 0.65.0 / llvmlite 0.47.0 JIT crash on "
        "Windows. Remove skip after pinning a compatible numba version."
    )
)
def test_shap():
    from trading_research.eval.classifier import train_winner_classifier
    from trading_research.eval.shap_analysis import compute_shap_per_trade

    n = 200
    rng = np.random.default_rng(42)
    trades = pd.DataFrame({
        "net_pnl_usd": rng.normal(0, 1, n),
        "atr_14_pct_rank_252": rng.uniform(0, 1, n),
        "rsi_14": rng.uniform(0, 100, n),
        "direction": ["long"] * n,
    })

    # purge_bars=10 so folds actually run on a 200-sample dataset
    cls_res = train_winner_classifier(trades, cv_folds=2, purge_bars=10)

    # Guard: if the classifier still couldn't run, fail informatively
    if "error" in cls_res:
        pytest.fail(f"Classifier returned error: {cls_res['error']}")

    shap_df = compute_shap_per_trade(cls_res["model"], cls_res["X_train"])
    assert len(shap_df) == len(cls_res["X_train"])
    assert "shap_top_pos_1" in shap_df.columns
