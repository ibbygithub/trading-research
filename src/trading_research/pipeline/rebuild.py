"""Rebuild pipeline: regenerate CLEAN and FEATURES files from source data.

All rebuilds are deterministic — running twice on the same source data
produces identical parquet content (differing only in built_at timestamps).
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import yaml

from trading_research.data.manifest import (
    build_clean_manifest,
    write_manifest,
)
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

_DATA_ROOT = Path(__file__).parents[3] / "data"
_CONFIGS_ROOT = Path(__file__).parents[3] / "configs"


# ---------------------------------------------------------------------------
# rebuild clean
# ---------------------------------------------------------------------------


def rebuild_clean(
    symbol: str = "ZN",
    data_root: Path = _DATA_ROOT,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """Rebuild all CLEAN files for *symbol* from cached RAW contracts.

    Does not call the TradeStation API — all contracts must already be cached
    in ``data/raw/contracts/``. Raises if any required contract is missing.

    Steps
    -----
    1. Build back-adjusted + unadjusted 1m series from contracts cache.
    2. Resample to 5m, 15m, 60m, 240m.
    3. Resample to 1D using CME trade-date convention.
    4. Write manifests for every output file.
    """
    from trading_research.data.continuous import (
        build_back_adjusted_continuous,
        DEFAULT_CONTRACTS_DIR,
    )
    from trading_research.data.resample import resample_and_write, resample_daily, write_resampled

    clean_dir = data_root / "clean"
    contracts_dir = data_root / "raw" / "contracts"

    if start_date is None:
        start_date = date(2010, 1, 1)
    if end_date is None:
        end_date = date.today()

    t0 = time.perf_counter()
    logger.info("rebuild_clean_start", symbol=symbol, start=str(start_date), end=str(end_date))

    # Step 1: back-adjusted continuous 1m
    result = build_back_adjusted_continuous(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        output_dir=clean_dir,
        contracts_dir=contracts_dir,
    )

    # result.adjusted_path / result.unadjusted_path are the output files
    adj_path = result.adjusted_path
    unadj_path = result.unadjusted_path
    source_contract_paths = sorted(contracts_dir.glob(f"{result.ts_root}*.parquet"))

    for path, adjustment in [(adj_path, "backadjusted"), (unadj_path, "unadjusted")]:
        manifest = build_clean_manifest(
            parquet_path=path,
            source_paths=source_contract_paths,
            symbol=symbol,
            timeframe="1m",
            adjustment=adjustment,
            parameters={
                "method": "back_adjusted_continuous" if adjustment == "backadjusted" else "stitched_unadjusted",
                "roll_days_before": 5,
            },
        )
        write_manifest(path, manifest)
        logger.info("manifest_written", path=str(path))

    logger.info("rebuild_clean_1m_done", elapsed=f"{time.perf_counter() - t0:.1f}s")

    # Step 2: intraday resamples (5m, 15m, 60m, 240m)
    resampled_paths = resample_and_write(
        source_path=adj_path,
        output_dir=clean_dir,
        freqs=["5min", "15min", "60min", "240min"],
        symbol=f"{symbol}_backadjusted",
    )

    for freq, resample_path in resampled_paths.items():
        timeframe = freq.replace("min", "m")
        manifest = build_clean_manifest(
            parquet_path=resample_path,
            source_paths=[adj_path],
            symbol=symbol,
            timeframe=timeframe,
            adjustment="backadjusted",
            parameters={"freq": freq},
        )
        write_manifest(resample_path, manifest)
        logger.info("manifest_written", path=str(resample_path))

    logger.info("rebuild_clean_resamples_done", elapsed=f"{time.perf_counter() - t0:.1f}s")

    # Step 3: daily resample
    import pandas as pd
    import pyarrow.parquet as pq

    tbl = pq.read_table(adj_path)
    df = tbl.to_pandas()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_ny"] = pd.to_datetime(df["timestamp_ny"]).dt.tz_convert("America/New_York")

    daily_df = resample_daily(df)
    start_str = df["timestamp_utc"].min().strftime("%Y-%m-%d")
    end_str = df["timestamp_utc"].max().strftime("%Y-%m-%d")
    daily_path = clean_dir / f"{symbol}_backadjusted_1D_{start_str}_{end_str}.parquet"
    write_resampled(daily_df, daily_path)

    manifest = build_clean_manifest(
        parquet_path=daily_path,
        source_paths=[adj_path],
        symbol=symbol,
        timeframe="1D",
        adjustment="backadjusted",
        parameters={"method": "resample_daily", "convention": "CME_trade_date"},
    )
    write_manifest(daily_path, manifest)
    logger.info("manifest_written", path=str(daily_path))

    elapsed = time.perf_counter() - t0
    logger.info("rebuild_clean_complete", symbol=symbol, elapsed=f"{elapsed:.1f}s")
    print(f"rebuild clean {symbol}: done in {elapsed:.1f}s")
    print(f"  {adj_path.name}")
    print(f"  {unadj_path.name}")
    for freq, p in resampled_paths.items():
        print(f"  {p.name}")
    print(f"  {daily_path.name}")


# ---------------------------------------------------------------------------
# rebuild features
# ---------------------------------------------------------------------------


def rebuild_features(
    symbol: str = "ZN",
    feature_set_tag: str = "base-v1",
    data_root: Path = _DATA_ROOT,
    configs_root: Path = _CONFIGS_ROOT,
) -> None:
    """Rebuild FEATURES files for *symbol* from CLEAN data.

    Uses the feature set defined in ``configs/featuresets/{feature_set_tag}.yaml``.
    """
    from trading_research.indicators.features import build_features

    clean_dir = data_root / "clean"
    features_dir = data_root / "features"
    config_path = configs_root / "featuresets" / f"{feature_set_tag}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Feature set config not found: {config_path}\n"
            f"Available configs: {[p.name for p in (configs_root / 'featuresets').glob('*.yaml')]}"
        )

    with open(config_path) as f:
        config = yaml.safe_load(f)

    target_timeframes: list[str] = config.get("target_timeframes", [])
    if not target_timeframes:
        raise ValueError(f"No target_timeframes in {config_path}")

    # Locate required CLEAN inputs
    adj_1m_candidates = sorted(clean_dir.glob(f"{symbol}_1m_backadjusted_*.parquet"))
    daily_candidates = sorted(clean_dir.glob(f"{symbol}_backadjusted_1D_*.parquet"))

    if not adj_1m_candidates:
        raise FileNotFoundError(f"No CLEAN 1m backadjusted parquet found for {symbol} in {clean_dir}")
    if not daily_candidates:
        raise FileNotFoundError(f"No CLEAN 1D parquet found for {symbol} in {clean_dir}")

    price_1m_path = adj_1m_candidates[-1]  # most recent
    daily_path = daily_candidates[-1]

    t0 = time.perf_counter()
    logger.info(
        "rebuild_features_start",
        symbol=symbol,
        feature_set_tag=feature_set_tag,
        target_timeframes=target_timeframes,
    )

    for tf in target_timeframes:
        # Map timeframe label to pandas freq for file glob
        tf_glob = tf.replace("m", "min") if tf not in ("1D",) else tf
        # Try clean file naming patterns
        candidates = sorted(
            clean_dir.glob(f"{symbol}_backadjusted_{tf}_*.parquet")
        )
        # Also try the alternative naming (e.g. ZN_backadjusted_5m_*)
        if not candidates:
            candidates = sorted(
                clean_dir.glob(f"{symbol}_backadjusted_{tf}_*.parquet")
            )

        if not candidates:
            logger.warning("rebuild_features_no_source", symbol=symbol, timeframe=tf)
            print(f"  WARNING: no CLEAN {tf} parquet found for {symbol} — skipping")
            continue

        price_path = candidates[-1]
        t1 = time.perf_counter()

        output_path = build_features(
            price_path=price_path,
            price_1m_path=price_1m_path,
            daily_path=daily_path,
            output_dir=features_dir,
            symbol=symbol,
            feature_set_tag=feature_set_tag,
            feature_set_config=config_path,
        )

        elapsed_tf = time.perf_counter() - t1
        logger.info("rebuild_features_tf_done", timeframe=tf, elapsed=f"{elapsed_tf:.1f}s")
        print(f"  {output_path.name}  ({elapsed_tf:.1f}s)")

    elapsed = time.perf_counter() - t0
    logger.info("rebuild_features_complete", symbol=symbol, elapsed=f"{elapsed:.1f}s")
    print(f"rebuild features {symbol}/{feature_set_tag}: done in {elapsed:.1f}s")
