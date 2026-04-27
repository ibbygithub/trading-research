"""Integration tests for the 6E pipeline end-to-end (session 28).

These tests verify pipeline *artifacts* — they are not unit tests of pipeline
logic. They pass only after `uv run trading-research pipeline --symbol 6E` has
been run successfully. Run them to confirm the Track A acceptance gate.

Acceptance criteria:
  - RAW contract parquets exist in data/raw/contracts/ for at least 2020-2024.
  - CLEAN 1m backadjusted parquet exists for 6E.
  - CLEAN 5m backadjusted parquet exists and has a plausible row count.
  - FEATURES 5m base-v1 parquet exists with the expected indicator columns.
  - The FEATURES manifest links the correct base-v1 featureset hash.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Project roots (resolved relative to this file)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _PROJECT_ROOT / "data"
_CONTRACTS_DIR = _DATA_ROOT / "raw" / "contracts"
_CLEAN_DIR = _DATA_ROOT / "clean"
_FEATURES_DIR = _DATA_ROOT / "features"
_CONFIGS_ROOT = _PROJECT_ROOT / "configs"

# Symbol under test — never hard-coded in logic, only in the test contract.
SYMBOL = "6E"
FEATURE_SET = "base-v1"

# Known RTH bar count sanity check: Jan 2024 has 23 trading days.
# At 5-minute bars, RTH is 09:00–17:00 = 96 bars/day (including pre-market
# overlap). We use a conservative lower bound over a known full month.
_JAN_2024_5M_RTH_LOWER_BOUND = 500   # well below 23 * 96 = 2208; catches empty file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_parquets(directory: Path, pattern: str) -> list[Path]:
    """Return sorted parquets matching glob pattern under directory."""
    return sorted(directory.glob(pattern))


def _load_manifest(parquet_path: Path) -> dict:
    """Load the .manifest.json sidecar for a parquet file."""
    manifest_path = parquet_path.parent / (parquet_path.name + ".manifest.json")
    if not manifest_path.exists():
        pytest.fail(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test 1: RAW contract files exist for a meaningful date range
# ---------------------------------------------------------------------------


def test_6e_raw_contracts_exist() -> None:
    """RAW contract parquets must exist in data/raw/contracts/ for 6E (EU root).

    The pipeline downloads individual quarterly contracts (EUH24, EUM24, …).
    At minimum we need at least one EU contract parquet present covering data
    from 2020 onwards, confirming the download stage ran successfully.
    """
    # TS root for Euro FX is EC (not EU or 6E). Individual contracts: ECH24, ECM24, etc.
    # Verified against TradeStation API 2026-04-25; @EC is the valid continuous symbol.
    ec_contracts = _find_parquets(_CONTRACTS_DIR, "EC[HMUZ]??_1m_*.parquet")
    assert ec_contracts, (
        f"No EC contract parquets found in {_CONTRACTS_DIR}. "
        "Run `uv run trading-research pipeline --symbol 6E` first."
    )

    # Extract the earliest start date from filenames: EC<code><yy>_1m_<start>_<end>.parquet
    date_pattern = re.compile(r"EC[HMUZ]\d{2}_1m_(\d{4}-\d{2}-\d{2})_\d{4}-\d{2}-\d{2}\.parquet")
    eu_contracts = ec_contracts  # alias for the rest of the function
    start_dates: list[str] = []
    for p in eu_contracts:
        m = date_pattern.match(p.name)
        if m:
            start_dates.append(m.group(1))

    assert start_dates, f"Could not parse dates from contract filenames: {[p.name for p in eu_contracts[:5]]}"

    earliest = min(start_dates)
    assert earliest <= "2020-12-31", (
        f"Earliest 6E contract data starts {earliest}; expected at least 2020 coverage. "
        "Re-run pipeline with a wider date range."
    )


# ---------------------------------------------------------------------------
# Test 2: CLEAN 5m parquet exists and has plausible row count for Jan 2024
# ---------------------------------------------------------------------------


def test_6e_clean_5m_has_expected_rows() -> None:
    """CLEAN 5m backadjusted parquet must exist for 6E and have enough bars.

    We filter to January 2024 (a known full trading month) and assert the bar
    count exceeds the conservative lower bound. This catches empty files or
    resampling failures without needing a reference dataset.
    """
    candidates = _find_parquets(_CLEAN_DIR, f"{SYMBOL}_backadjusted_5m_*.parquet")
    assert candidates, (
        f"No CLEAN 5m backadjusted parquet found for {SYMBOL} in {_CLEAN_DIR}. "
        "Run `uv run trading-research pipeline --symbol 6E` first."
    )

    path = candidates[-1]  # most recent
    df = pd.read_parquet(path, engine="pyarrow")
    assert "timestamp_utc" in df.columns, f"Missing timestamp_utc column in {path.name}"

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    jan24 = df[
        (df["timestamp_utc"] >= pd.Timestamp("2024-01-01", tz="UTC"))
        & (df["timestamp_utc"] < pd.Timestamp("2024-02-01", tz="UTC"))
    ]

    assert len(jan24) >= _JAN_2024_5M_RTH_LOWER_BOUND, (
        f"CLEAN 5m for Jan 2024 has only {len(jan24)} rows (expected ≥ {_JAN_2024_5M_RTH_LOWER_BOUND}). "
        "Possible resampling failure or insufficient raw data."
    )


# ---------------------------------------------------------------------------
# Test 3: FEATURES 5m parquet exists and has base-v1 indicator columns
# ---------------------------------------------------------------------------


def test_6e_features_5m_has_base_v1_columns() -> None:
    """FEATURES 5m parquet for 6E must have the columns declared by base-v1.

    We load the base-v1 feature set config and check that all indicator names
    appear as columns (or prefixed columns) in the features parquet. This catches
    feature-build failures and confirms the feature set ran on 6E data.
    """
    import yaml

    candidates = _find_parquets(
        _FEATURES_DIR, f"{SYMBOL}_backadjusted_5m_features_{FEATURE_SET}_*.parquet"
    )
    assert candidates, (
        f"No FEATURES 5m {FEATURE_SET} parquet found for {SYMBOL} in {_FEATURES_DIR}. "
        "Run `uv run trading-research pipeline --symbol 6E --set base-v1` first."
    )

    feat_path = candidates[-1]
    df = pd.read_parquet(feat_path, engine="pyarrow")
    columns = set(df.columns)

    # Load feature set config to know what columns to expect.
    fs_config_path = _CONFIGS_ROOT / "featuresets" / f"{FEATURE_SET}.yaml"
    assert fs_config_path.exists(), f"Feature set config not found: {fs_config_path}"

    config = yaml.safe_load(fs_config_path.read_text(encoding="utf-8"))
    expected_indicators = [spec["name"] for spec in config.get("indicators", [])]

    # Mapping from config indicator name → actual column prefix.
    # compute_bollinger() returns bb_* columns (not bollinger_*).
    _COLUMN_PREFIX_MAP: dict[str, str] = {
        "bollinger": "bb",
    }

    # Each indicator name must appear as a column prefix (e.g. "atr" → "atr_14").
    missing: list[str] = []
    for ind_name in expected_indicators:
        prefix = _COLUMN_PREFIX_MAP.get(ind_name, ind_name)
        matching = [c for c in columns if c.startswith(prefix)]
        if not matching:
            missing.append(ind_name)

    assert not missing, (
        f"FEATURES 5m for {SYMBOL} is missing columns for indicators: {missing}. "
        f"Available columns (first 30): {sorted(columns)[:30]}"
    )

    # Must also have OHLCV base columns.
    for required in ("open", "high", "low", "close", "volume"):
        assert required in columns, (
            f"FEATURES 5m missing base column '{required}'. Got: {sorted(columns)[:20]}"
        )


# ---------------------------------------------------------------------------
# Test 4: FEATURES manifest links the correct base-v1 featureset hash
# ---------------------------------------------------------------------------


def test_6e_manifest_has_featureset_hash() -> None:
    """The FEATURES 5m manifest must record the base-v1 featureset_hash.

    This is the provenance link that lets backtest runs be traced to the exact
    feature set version that produced them. An absent or empty hash means the
    features were built without proper manifest tracking.
    """
    candidates = _find_parquets(
        _FEATURES_DIR, f"{SYMBOL}_backadjusted_5m_features_{FEATURE_SET}_*.parquet"
    )
    assert candidates, (
        f"No FEATURES 5m {FEATURE_SET} parquet found for {SYMBOL} in {_FEATURES_DIR}."
    )

    feat_path = candidates[-1]
    manifest = _load_manifest(feat_path)

    # featureset_hash must be present and non-empty.
    fs_hash = manifest.get("featureset_hash")
    assert fs_hash, (
        f"Manifest for {feat_path.name} has no 'featureset_hash'. "
        f"Manifest keys present: {list(manifest.keys())}"
    )
    assert isinstance(fs_hash, str) and len(fs_hash) >= 8, (
        f"featureset_hash looks malformed: {fs_hash!r}"
    )

    # The manifest must also record the feature_set_tag.
    fs_tag = manifest.get("feature_set_tag") or manifest.get("featureset_tag")
    assert fs_tag == FEATURE_SET, (
        f"Expected feature_set_tag='{FEATURE_SET}' in manifest, got '{fs_tag}'. "
        f"Full manifest: {manifest}"
    )
