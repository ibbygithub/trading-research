"""Winner/loser classifier using LightGBM.

Trains a classifier on entry-bar context to predict trade outcomes,
using purged walk-forward cross-validation and Permutation Importance.

Purge semantics (Lopez de Prado AFML Ch. 7):
  For each test fold [val_start, val_end), train only on indices [0, val_start).
  Then drop the last `purge_bars` from that training window to prevent
  label overlap: any trade entered within purge_bars of val_start could have
  its label (outcome) span into the test period.

  Embargo (post-test blackout) is implicit: the next fold's val_start is
  val_end + gap, so the gap itself acts as the embargo between folds.
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import KFold
from sklearn.inspection import permutation_importance, partial_dependence


def _build_dataset(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Prepare features X and target y."""
    df = trades[trades["net_pnl_usd"] != 0].copy()

    y = (df["net_pnl_usd"] > 0).astype(int)

    feature_cols = [
        "rsi_14", "adx_14", "atr_14", "sma_200",
        "atr_14_pct_rank_252",
        "daily_range_used_pct",
        "vwap_distance_atr",
        "htf_bias_strength",
        "entry_hour",
        "hold_minutes",
    ]

    cols_to_use = [c for c in feature_cols if c in df.columns]
    X = df[cols_to_use].copy()

    categorical_cols = [
        "direction", "session_regime", "entry_dow",
        "vol_regime", "trend_regime", "fomc_regime",
    ]
    for cat_col in categorical_cols:
        if cat_col in df.columns:
            X[cat_col] = df[cat_col].astype("category")

    return X, y


def train_winner_classifier(
    trades: pd.DataFrame,
    cv_folds: int = 5,
    purge_bars: int = 100,
) -> dict:
    """Train classifier using purged walk-forward CV; return permutation importance.

    Parameters
    ----------
    trades:     Trade log DataFrame with net_pnl_usd and feature columns.
    cv_folds:   Number of walk-forward folds. Each fold uses all prior data
                (minus the purge window) as training.
    purge_bars: Number of observations to drop from the tail of each training
                window to prevent label leakage into the test fold.
    """
    X, y = _build_dataset(trades)

    if len(X) < 100:
        return {"error": "Not enough data to train classifier."}

    lgb_params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": 5,
        "feature_fraction": 0.8,
        "verbose": -1,
        "n_jobs": 1,
    }

    model = lgb.LGBMClassifier(**lgb_params)

    n_samples = len(X)
    kf = KFold(n_splits=cv_folds, shuffle=False)

    oof_preds = np.full(n_samples, np.nan)
    raw_importances: list[np.ndarray] = []
    folds_used = 0

    for _, val_idx in kf.split(X):
        val_start = int(val_idx[0])

        # Purge: train strictly before the test fold, drop last purge_bars.
        # This ensures no training label spans into the test window.
        train_end = max(0, val_start - purge_bars)
        if train_end < 20:
            # Insufficient training data for this fold; skip rather than
            # fit on noise. First fold(s) of walk-forward often hit this.
            continue

        train_idx = np.arange(0, train_end)
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        # Guard: need both classes in the training fold.
        if y_train.nunique() < 2:
            continue

        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )

        oof_preds[val_idx] = model.predict_proba(X_val)[:, 1]

        # Permutation importance on held-out fold (not training set).
        r = permutation_importance(
            model, X_val, y_val,
            n_repeats=5, random_state=42, n_jobs=1,
        )
        raw_importances.append(r.importances)
        folds_used += 1

    if folds_used == 0:
        return {"error": "All folds skipped — not enough pre-test training data after purge."}

    # Aggregate permutation importance across folds.
    all_imp = np.hstack(raw_importances)
    avg_imp = np.mean(all_imp, axis=1)
    std_imp = np.std(all_imp, axis=1)
    ci_imp = 1.96 * std_imp / np.sqrt(all_imp.shape[1])

    imp_df = pd.DataFrame({
        "feature": X.columns,
        "importance": avg_imp,
        "importance_ci": ci_imp,
    }).sort_values("importance", ascending=False)

    # Retrain on full dataset for SHAP and PDP.
    # OOF predictions above are out-of-sample; this refit is only for
    # feature attribution visualisation, not for eval.
    model.fit(X, y)

    pdp_data = {}
    top_5 = imp_df["feature"].head(5).tolist()
    for feat in top_5:
        try:
            pd_res = partial_dependence(model, X, features=[feat])
            grid_vals = pd_res.get("grid_values", pd_res.get("values", []))
            pdp_data[feat] = {
                "values": grid_vals[0].tolist() if len(grid_vals) > 0 else [],
                "average": pd_res["average"][0].tolist() if "average" in pd_res else [],
            }
        except Exception as e:
            pdp_data[feat] = {"error": str(e)}

    return {
        "model": model,
        "X_train": X,
        "oof_preds": oof_preds,
        "permutation_importance": imp_df,
        "pdp_data": pdp_data,
        "n_samples": n_samples,
        "folds_used": folds_used,
    }
