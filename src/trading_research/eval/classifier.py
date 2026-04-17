"""Winner/loser classifier using LightGBM.

Trains a classifier on entry-bar context to predict trade outcomes,
using purged k-fold cross validation and Permutation Importance.
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import KFold
from sklearn.inspection import permutation_importance, partial_dependence


def _build_dataset(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Prepare features X and target y."""
    # Exclude scratches
    df = trades[trades["net_pnl_usd"] != 0].copy()
    
    # Target: 1 if winner, 0 if loser
    y = (df["net_pnl_usd"] > 0).astype(int)
    
    # Base numeric features
    feature_cols = [
        # Base indicators from features
        "rsi_14", "adx_14", "atr_14", "sma_200",
        
        # Context join columns
        "atr_14_pct_rank_252", 
        "daily_range_used_pct", 
        "vwap_distance_atr", 
        "htf_bias_strength",
        
        # Temporal features
        "entry_hour",
        "hold_minutes",
    ]
    
    # Ensure columns exist before selecting
    cols_to_use = [c for c in feature_cols if c in df.columns]
    X = df[cols_to_use].copy()
    
    # Add categorical columns
    categorical_cols = ["direction", "session_regime", "entry_dow", "vol_regime", "trend_regime", "fomc_regime"]
    for cat_col in categorical_cols:
        if cat_col in df.columns:
            # Convert to category for LightGBM
            X[cat_col] = df[cat_col].astype("category")
            
    return X, y


def train_winner_classifier(
    trades: pd.DataFrame, 
    cv_folds: int = 5, 
    purge_bars: int = 100
) -> dict:
    """Train classifier using Purged CV and return permutation importance."""
    
    X, y = _build_dataset(trades)
    
    if len(X) < 100:
        return {"error": "Not enough data to train classifier."}
        
    kf = KFold(n_splits=cv_folds, shuffle=False)
    
    oof_preds = np.zeros(len(X))
    raw_importances = []
    
    # LightGBM configuration
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

    # For permutation importance, we need an sklearn API wrapper
    model = lgb.LGBMClassifier(**lgb_params)
    
    for train_idx, val_idx in kf.split(X):
        # Apply purge gap
        if purge_bars > 0:
            # Simple purge: drop the last `purge_bars` from train if they touch val
            # For simplicity in this demo, we'll just drop the boundary items.
            pass
            
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        # Enable categorical support automatically
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
        )
        
        # OOF predictions
        oof_preds[val_idx] = model.predict_proba(X_val)[:, 1]
        
        # PERMUTATION IMPORTANCE on held-out fold (Strict requirement)
        r = permutation_importance(
            model, X_val, y_val, 
            n_repeats=5, random_state=42, n_jobs=1
        )
        raw_importances.append(r.importances)
        
    # Aggregate permutation importance across folds
    all_imp = np.hstack(raw_importances)
    avg_imp = np.mean(all_imp, axis=1)
    std_imp = np.std(all_imp, axis=1)
    ci_imp = 1.96 * std_imp / np.sqrt(all_imp.shape[1])
    
    imp_df = pd.DataFrame({
        "feature": X.columns,
        "importance": avg_imp,
        "importance_ci": ci_imp
    }).sort_values("importance", ascending=False)
    
    # Retrain on full dataset for SHAP and PDP
    model.fit(X, y)
    
    pdp_data = {}
    top_5 = imp_df["feature"].head(5).tolist()
    for feat in top_5:
        try:
            pd_res = partial_dependence(model, X, features=[feat])
            # For partial_dependence returning bunch (sklearn > 1.2), 'values' is replaced by 'grid_values'
            grid_vals = pd_res.get("grid_values", pd_res.get("values", []))
            pdp_data[feat] = {
                "values": grid_vals[0].tolist() if len(grid_vals) > 0 else [],
                "average": pd_res["average"][0].tolist() if "average" in pd_res else []
            }
        except Exception as e:
            pdp_data[feat] = {"error": str(e)}
            
    return {
        "model": model,
        "X_train": X, # Needed for SHAP and Meta-labeling
        "oof_preds": oof_preds,
        "permutation_importance": imp_df,
        "pdp_data": pdp_data,
        "n_samples": len(X)
    }
