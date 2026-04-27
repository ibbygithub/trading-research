"""SHAP analysis for trade attribution.

Computes SHAP values per trade and attaches the top positive and
negative contributing features to the trade log.

Note: ``shap`` is imported lazily inside the function body rather than at
module level.  The shap library's dependency on numba/llvmlite can trigger
a fatal JIT access violation on Windows with certain package combinations.
Deferring the import means the rest of the codebase can safely import this
module even when the shap environment is broken; ``compute_shap_per_trade``
will surface the error only when it is actually called.
"""

import numpy as np
import pandas as pd


def compute_shap_per_trade(model, X: pd.DataFrame) -> pd.DataFrame:
    """Compute SHAP values for each trade and extract top 3 positive/negative.
    
    Returns a DataFrame with the same index as X, containing new SHAP columns.
    """
    import shap  # lazy import — see module docstring

    if len(X) == 0:
        return pd.DataFrame()

    # Check if LightGBM classifier
    if hasattr(model, "booster_"):
        explainer = shap.TreeExplainer(model.booster_)
        # TreeExplainer for LightGBM binary classification returns values 
        # in log-odds space (usually margin).
        shap_values = explainer.shap_values(X)
        
        # If binary classification, shap_values might be a list of arrays [class_0, class_1]
        # or a single array for class 1. LightGBM usually returns a list of arrays for multiclass
        # and a single array for binary. Let's handle both.
        if isinstance(shap_values, list):
            shap_vals = shap_values[1]  # positive class
        else:
            shap_vals = shap_values
    else:
        # Fallback to general explainer if it's something else
        explainer = shap.Explainer(model, X)
        shap_vals = explainer(X).values

    feature_names = X.columns.tolist()
    
    # We will build rows of dicts to convert into a DataFrame
    shap_results = []
    
    for i in range(len(X)):
        row_vals = shap_vals[i]
        
        # Sort by value
        sorted_idx = np.argsort(row_vals)
        
        # Top 3 negative (lowest values)
        neg_idx = sorted_idx[:3]
        # Top 3 positive (highest values)
        pos_idx = sorted_idx[-3:][::-1]
        
        res = {}
        for k, idx in enumerate(pos_idx):
            val = row_vals[idx]
            fname = feature_names[idx]
            if val > 0:
                res[f"shap_top_pos_{k+1}"] = f"{fname}: {val:+.2f}"
            else:
                res[f"shap_top_pos_{k+1}"] = ""
                
        for k, idx in enumerate(neg_idx):
            val = row_vals[idx]
            fname = feature_names[idx]
            if val < 0:
                res[f"shap_top_neg_{k+1}"] = f"{fname}: {val:+.2f}"
            else:
                res[f"shap_top_neg_{k+1}"] = ""
                
        shap_results.append(res)
        
    return pd.DataFrame(shap_results, index=X.index)
