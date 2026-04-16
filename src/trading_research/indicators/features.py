"""Feature file builder — three-layer pipeline FEATURES layer.

Reads a target-timeframe CLEAN parquet, applies all indicators from
``configs/featuresets/<tag>.yaml``, projects daily HTF bias columns (shifted
by one session to prevent look-ahead), and writes a fat feature parquet to
``data/features/``.

See docs/pipeline.md for the feature file schema and the HTF look-ahead rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from trading_research.data.manifest import (
    build_features_manifest,
    write_manifest,
)
from trading_research.indicators.adx import compute_adx
from trading_research.indicators.atr import compute_atr
from trading_research.indicators.bollinger import compute_bollinger
from trading_research.indicators.donchian import compute_donchian
from trading_research.indicators.ema import compute_ema
from trading_research.indicators.macd import compute_macd
from trading_research.indicators.ofi import compute_ofi
from trading_research.indicators.rsi import compute_rsi
from trading_research.indicators.sma import compute_sma
from trading_research.indicators.vwap import (
    compute_monthly_vwap,
    compute_session_vwap,
    compute_weekly_vwap,
)
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------
# Trade-date helper — shared across vwap, daily join
# -----------------------------------------------------------------------


def trade_date_from_ny(ts_ny: pd.Series) -> pd.Series:
    """CME trade-date: shift timestamp_ny +6h so 18:00 ET → midnight."""
    ts = pd.to_datetime(ts_ny).dt.tz_convert("America/New_York")
    return (ts + pd.Timedelta(hours=6)).dt.date


# -----------------------------------------------------------------------
# Core feature builder
# -----------------------------------------------------------------------


def build_features(
    price_path: Path,
    price_1m_path: Path,
    daily_path: Path,
    output_dir: Path,
    symbol: str,
    feature_set_tag: str = "base-v1",
    feature_set_config: Path | None = None,
) -> Path:
    """Build a FEATURES parquet from CLEAN inputs.

    Parameters
    ----------
    price_path:
        CLEAN parquet at the target intraday timeframe (5m, 15m, etc.).
    price_1m_path:
        CLEAN 1-minute parquet — used for VWAP computation.
    daily_path:
        CLEAN 1D parquet — used for HTF bias projection.
    output_dir:
        Destination directory (``data/features/``).
    symbol:
        Instrument symbol (e.g., ``"ZN"``).
    feature_set_tag:
        Tag string for the feature set (e.g., ``"base-v1"``).
    feature_set_config:
        Path to the feature-set YAML. Used for manifest only; the
        indicators computed here are currently hardcoded to base-v1.

    Returns
    -------
    Path to the written feature parquet.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if feature_set_config is None:
        feature_set_config = (
            Path(__file__).parents[3] / "configs" / "featuresets" / f"{feature_set_tag}.yaml"
        )

    # ------------------------------------------------------------------
    # Load CLEAN data
    # ------------------------------------------------------------------
    df = pq.read_table(price_path).to_pandas()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = pd.to_datetime(df["timestamp_ny"]).dt.tz_convert(
        "America/New_York"
    )
    df = df.sort_values("timestamp_utc").reset_index(drop=True)

    df_1m = pq.read_table(price_1m_path).to_pandas()
    df_1m["timestamp_utc"] = pd.to_datetime(df_1m["timestamp_utc"], utc=True)
    df_1m["timestamp_ny"] = pd.to_datetime(df_1m["timestamp_ny"]).dt.tz_convert(
        "America/New_York"
    )
    df_1m = df_1m.sort_values("timestamp_utc").reset_index(drop=True)

    df_daily = pq.read_table(daily_path).to_pandas()
    df_daily["timestamp_utc"] = pd.to_datetime(df_daily["timestamp_utc"], utc=True)
    df_daily["timestamp_ny"] = pd.to_datetime(df_daily["timestamp_ny"]).dt.tz_convert(
        "America/New_York"
    )
    df_daily = df_daily.sort_values("timestamp_utc").reset_index(drop=True)

    # ------------------------------------------------------------------
    # Extract timeframe label from filename for output naming.
    # e.g. "ZN_backadjusted_5m_2010-01-03_2026-04-10.parquet" → "5m"
    # ------------------------------------------------------------------
    parts = price_path.stem.split("_")
    tf_label = _extract_tf_label(parts)
    adj_label = _extract_adj_label(parts)
    start_str = df["timestamp_utc"].min().strftime("%Y-%m-%d")
    end_str = df["timestamp_utc"].max().strftime("%Y-%m-%d")
    out_name = (
        f"{symbol}_{adj_label}_{tf_label}_features_{feature_set_tag}"
        f"_{start_str}_{end_str}.parquet"
    )
    out_path = output_dir / out_name

    # ------------------------------------------------------------------
    # Step 1 — Own-timeframe indicators
    # ------------------------------------------------------------------
    features = df.copy()

    features = pd.concat([features, compute_bollinger(features)], axis=1)
    features["atr_14"] = compute_atr(features)
    features["rsi_14"] = compute_rsi(features)
    features["sma_200"] = compute_sma(features["close"], 200)
    features = pd.concat([features, compute_donchian(features)], axis=1)
    features["adx_14"] = compute_adx(features)
    features["ofi_14"] = compute_ofi(features)
    macd_df = compute_macd(features)
    features = pd.concat([features, macd_df], axis=1)

    # ------------------------------------------------------------------
    # Step 2 — VWAP (computed on 1m, sampled at target-TF bar close)
    # ------------------------------------------------------------------
    vwap_session = compute_session_vwap(df_1m)
    vwap_weekly = compute_weekly_vwap(df_1m)
    vwap_monthly = compute_monthly_vwap(df_1m)

    df_1m_vwap = df_1m[["timestamp_utc"]].copy()
    df_1m_vwap["vwap_session"] = vwap_session.values
    df_1m_vwap["vwap_weekly"] = vwap_weekly.values
    df_1m_vwap["vwap_monthly"] = vwap_monthly.values

    # Use merge_asof to sample 1m VWAP at the close of each target-TF bar.
    features = pd.merge_asof(
        features,
        df_1m_vwap,
        on="timestamp_utc",
        direction="backward",
    )

    # ------------------------------------------------------------------
    # Step 3 — Daily HTF bias columns (shift(1) to prevent look-ahead)
    # ------------------------------------------------------------------
    df_daily = df_daily.copy()
    df_daily["_trade_date"] = trade_date_from_ny(df_daily["timestamp_ny"])

    daily_ema_20 = compute_ema(df_daily["close"], 20)
    daily_ema_50 = compute_ema(df_daily["close"], 50)
    daily_ema_200 = compute_ema(df_daily["close"], 200)
    daily_sma_200 = compute_sma(df_daily["close"], 200)
    daily_atr_14 = compute_atr(df_daily)
    daily_adx_14 = compute_adx(df_daily)
    daily_macd = compute_macd(df_daily)

    htf = df_daily[["_trade_date"]].copy()
    htf["daily_ema_20"] = daily_ema_20.shift(1).values
    htf["daily_ema_50"] = daily_ema_50.shift(1).values
    htf["daily_ema_200"] = daily_ema_200.shift(1).values
    htf["daily_sma_200"] = daily_sma_200.shift(1).values
    htf["daily_atr_14"] = daily_atr_14.shift(1).values
    htf["daily_adx_14"] = daily_adx_14.shift(1).values
    htf["daily_macd_hist"] = daily_macd["macd_hist"].shift(1).values

    # Assign trade_date to intraday bars.
    features["_trade_date"] = trade_date_from_ny(features["timestamp_ny"])

    # Left-join HTF columns by trade_date.
    features = features.merge(htf, on="_trade_date", how="left")
    features = features.drop(columns=["_trade_date"])

    # ------------------------------------------------------------------
    # Step 4 — Write parquet + manifest
    # ------------------------------------------------------------------
    # Convert bool column to regular bool (pyarrow-friendly).
    if "macd_hist_above_zero" in features.columns:
        features["macd_hist_above_zero"] = features["macd_hist_above_zero"].astype(
            object
        ).where(features["macd_hist_above_zero"].notna(), None)

    tbl = pa.Table.from_pandas(features, preserve_index=False)
    pq.write_table(tbl, out_path)

    indicator_list = _indicator_list()
    htf_projection_list = _htf_projection_list()

    manifest = build_features_manifest(
        parquet_path=out_path,
        source_paths=[price_path, price_1m_path, daily_path],
        symbol=symbol,
        timeframe=tf_label,
        adjustment=adj_label,
        feature_set_tag=feature_set_tag,
        feature_set_config=feature_set_config,
        indicators=indicator_list,
        htf_projections=htf_projection_list,
    )
    write_manifest(out_path, manifest)

    logger.info(
        "features_built",
        path=str(out_path),
        rows=len(features),
        columns=list(features.columns),
    )
    return out_path


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _extract_tf_label(parts: list[str]) -> str:
    """Extract timeframe label from filename stem parts."""
    known_tfs = {"1m", "5m", "15m", "60m", "240m", "1D", "13m"}
    for p in parts:
        if p in known_tfs:
            return p
    # Fallback: look for anything ending in 'm' or 'D'
    for p in parts:
        if p.endswith("m") or p.endswith("D"):
            try:
                int(p[:-1])
                return p
            except ValueError:
                pass
    return "unknown"


def _extract_adj_label(parts: list[str]) -> str:
    """Extract adjustment label from filename stem parts."""
    if "backadjusted" in parts:
        return "backadjusted"
    if "unadjusted" in parts:
        return "unadjusted"
    return "unknown"


def _indicator_list() -> list[dict[str, Any]]:
    return [
        {"name": "atr", "period": 14},
        {"name": "rsi", "period": 14},
        {"name": "bollinger", "period": 20, "num_std": 2.0},
        {"name": "macd", "fast": 12, "slow": 26, "signal": 9,
         "derived": ["hist_above_zero", "hist_slope", "bars_since_zero_cross",
                     "hist_decline_streak"]},
        {"name": "sma", "period": 200},
        {"name": "donchian", "period": 20},
        {"name": "adx", "period": 14},
        {"name": "ofi", "period": 14},
        {"name": "vwap_session"},
        {"name": "vwap_weekly"},
        {"name": "vwap_monthly"},
    ]


def _htf_projection_list() -> list[dict[str, Any]]:
    return [
        {
            "source_tf": "1D",
            "shift": 1,
            "columns": [
                {"name": "daily_ema_20", "indicator": "ema", "period": 20},
                {"name": "daily_ema_50", "indicator": "ema", "period": 50},
                {"name": "daily_ema_200", "indicator": "ema", "period": 200},
                {"name": "daily_sma_200", "indicator": "sma", "period": 200},
                {"name": "daily_atr_14", "indicator": "atr", "period": 14},
                {"name": "daily_adx_14", "indicator": "adx", "period": 14},
                {"name": "daily_macd_hist", "indicator": "macd_hist",
                 "fast": 12, "slow": 26, "signal": 9},
            ],
        }
    ]
