"""Trade clustering using HDBSCAN.

Surfaces natural trade types by clustering on the entry-bar feature vector.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import hdbscan


def cluster_trades(trades: pd.DataFrame, X: pd.DataFrame) -> dict:
    """Cluster trades based on feature matrix X.
    
    X must be the same index as trades.
    """
    if len(X) < 50:
        return {"error": "Not enough data to cluster."}
        
    # Only use numeric features for clustering
    numeric_cols = X.select_dtypes(include=[np.number]).columns
    X_num = X[numeric_cols].copy()
    
    # Fill NAs
    X_num = X_num.fillna(X_num.median())
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_num)
    
    # Cluster using HDBSCAN
    # We use min_cluster_size proportional to dataset size
    min_size = max(10, int(len(X) * 0.05))
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_size, metric='euclidean')
    labels = clusterer.fit_predict(X_scaled)
    
    df = trades.loc[X.index].copy()
    df["cluster"] = labels
    
    # Generate summary per cluster
    summary = []
    for c in sorted(df["cluster"].unique()):
        subset = df[df["cluster"] == c]
        
        # HDBSCAN uses -1 for noise
        label_name = f"Cluster {c}" if c != -1 else "Noise (-1)"
        
        # Find defining features (just difference in means vs rest)
        if c != -1:
            rest = X_num[df["cluster"] != c]
            c_data = X_num[df["cluster"] == c]
            
            diffs = np.abs(c_data.mean() - rest.mean()) / rest.std()
            top_feats = diffs.nlargest(3).index.tolist()
            top_str = ", ".join(top_feats)
        else:
            top_str = "N/A"
            
        summary.append({
            "cluster": label_name,
            "count": len(subset),
            "total_pnl": float(subset["net_pnl_usd"].sum()),
            "avg_pnl": float(subset["net_pnl_usd"].mean()),
            "win_rate": float((subset["net_pnl_usd"] > 0).mean()),
            "top_features": top_str
        })
        
    # Generate 2D projection with UMAP
    import umap
    reducer = umap.UMAP(n_components=2, random_state=42)
    embedding = reducer.fit_transform(X_scaled)
    
    return {
        "labels": labels.tolist(),
        "summary": summary,
        "umap_x": embedding[:, 0].tolist(),
        "umap_y": embedding[:, 1].tolist()
    }
