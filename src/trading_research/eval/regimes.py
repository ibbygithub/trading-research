"""Regime tagging module.

Attaches regime tags to each trade based on entry-bar context:
- Volatility regime
- Trend regime
- Calendar regime
- Fed-cycle regime
"""

import numpy as np
import pandas as pd


def tag_regimes(trades: pd.DataFrame, fomc_dates: list[str]) -> pd.DataFrame:
    """Attach regime tags to each trade based on the enriched trade log.

    Assumes `trades` has already been joined with the feature context 
    (e.g., `atr_14_pct_rank_252`, `htf_bias_strength`, etc.).
    """
    df = trades.copy()

    # 1. Volatility regime (from context join: atr_14_pct_rank_252)
    if "atr_14_pct_rank_252" in df.columns:
        df["vol_regime"] = pd.cut(
            df["atr_14_pct_rank_252"],
            bins=[-np.inf, 0.33, 0.66, np.inf],
            labels=["vol_low", "vol_mid", "vol_high"]
        ).astype(str)
        # NaN is often seen in the first year of data
        df.loc[df["atr_14_pct_rank_252"].isna(), "vol_regime"] = "vol_unknown"
    else:
        df["vol_regime"] = "vol_unknown"

    # 2. Trend regime (from context join: daily_adx_14)
    # The session plan says we use daily ADX. The daily ADX was projected
    # into the features as `daily_adx_14`. We'll use that.
    if "daily_adx_14" in df.columns:
        df["trend_regime"] = pd.cut(
            df["daily_adx_14"],
            bins=[-np.inf, 20, 40, np.inf],
            labels=["trend_weak", "trend_moderate", "trend_strong"]
        ).astype(str)
        df.loc[df["daily_adx_14"].isna(), "trend_regime"] = "trend_unknown"
    else:
        df["trend_regime"] = "trend_unknown"

    # 3. Calendar regime
    if "entry_ts" in df.columns:
        ts = pd.to_datetime(df["entry_ts"]).dt.tz_convert("America/New_York")
        df["cal_dow"] = ts.dt.day_name()
        df["cal_month"] = ts.dt.month_name()
        df["cal_quarter"] = "Q" + ts.dt.quarter.astype(str)
        # Approximate week of month (1-5)
        df["cal_week_of_month"] = "W" + ((ts.dt.day - 1) // 7 + 1).astype(str)

        # 4. Fed-cycle regime
        if fomc_dates:
            fomc_ts = pd.to_datetime(fomc_dates).tz_localize("America/New_York")
            entry_dates = ts.dt.normalize()
            
            # Compute distance in days to nearest FOMC
            distances = []
            for d in entry_dates:
                diffs = (fomc_ts - d).days
                if len(diffs) > 0:
                    # Find nearest by absolute distance, but preserve sign
                    # A negative sign means FOMC is in the past (e.g. -1 = 1 day after FOMC)
                    # Wait, if FOMC = 20th and entry = 21st, diff = -1 (FOMC is 1 day ago)
                    # Let's define distance = FOMC - entry
                    # So negative means entry is AFTER FOMC. Positive means entry is BEFORE FOMC.
                    idx = np.argmin(np.abs(diffs))
                    nearest = diffs[idx]
                    distances.append(nearest)
                else:
                    distances.append(np.nan)
            
            df["fomc_distance"] = distances
            
            def tag_fomc(d: float) -> str:
                if pd.isna(d): return "fomc_far"
                if d == 0: return "fomc_today"
                if d == -1: return "fomc_tp1"  # Entry is 1 day after FOMC
                if d == 1: return "fomc_tm1"   # Entry is 1 day before FOMC
                if abs(d) <= 5: return "fomc_week"
                return "fomc_far"
                
            df["fomc_regime"] = df["fomc_distance"].apply(tag_fomc)
        else:
            df["fomc_regime"] = "fomc_far"
            
    return df
