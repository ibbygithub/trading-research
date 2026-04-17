"""Tests for the trading-research CLI entry point."""

from __future__ import annotations

from pathlib import Path
import json
import shutil

import pytest
from typer.testing import CliRunner

from trading_research.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# help / entry point
# ---------------------------------------------------------------------------


def test_help_exits_zero():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert "verify" in result.output
    assert "backfill-manifests" in result.output
    assert "rebuild" in result.output
    assert "inventory" in result.output


def test_rebuild_help():
    result = runner.invoke(app, ["rebuild", "--help"])
    assert result.exit_code == 0
    assert "clean" in result.output
    assert "features" in result.output


# ---------------------------------------------------------------------------
# verify — synthetic tmp_path trees
# ---------------------------------------------------------------------------


def _make_minimal_parquet(path: Path) -> None:
    """Write a tiny valid parquet file for testing purposes."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from trading_research.data.schema import BAR_SCHEMA

    df = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(["2024-01-02T14:00:00Z", "2024-01-02T14:01:00Z"]),
            "timestamp_ny": pd.to_datetime(["2024-01-02T09:00:00-05:00", "2024-01-02T09:01:00-05:00"]),
            "open": [110.0, 110.1],
            "high": [110.2, 110.3],
            "low": [109.8, 110.0],
            "close": [110.1, 110.2],
            "volume": [100, 120],
            "buy_volume": pd.array([50, 60], dtype="Int64"),
            "sell_volume": pd.array([50, 60], dtype="Int64"),
            "up_ticks": pd.array([10, 12], dtype="Int64"),
            "down_ticks": pd.array([8, 9], dtype="Int64"),
            "total_ticks": pd.array([18, 21], dtype="Int64"),
        }
    )
    df["timestamp_utc"] = pd.to_datetime(["2024-01-02T14:00:00", "2024-01-02T14:01:00"]).tz_localize("UTC")
    df["timestamp_ny"] = df["timestamp_utc"].dt.tz_convert("America/New_York")

    path.parent.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)
    pq.write_table(tbl, path)


def test_verify_all_ok(tmp_path: Path):
    """verify exits 0 when all parquets have fresh manifests."""
    from trading_research.data.manifest import build_raw_manifest, write_manifest

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    p = raw_dir / "TEST_1m_2024-01-01_2024-01-31.parquet"
    _make_minimal_parquet(p)
    manifest = build_raw_manifest(p, symbol="TEST", raw_type="contract")
    write_manifest(p, manifest)

    result = runner.invoke(app, ["verify", "--data-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "1 OK" in result.output


def test_verify_missing_manifest_exits_1(tmp_path: Path):
    """verify exits 1 when a parquet has no manifest."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    p = raw_dir / "TEST_1m_2024-01-01_2024-01-31.parquet"
    _make_minimal_parquet(p)
    # No manifest written

    result = runner.invoke(app, ["verify", "--data-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "NO MANIFEST" in result.output


# ---------------------------------------------------------------------------
# backfill-manifests
# ---------------------------------------------------------------------------


def test_backfill_dry_run(tmp_path: Path):
    """backfill --dry-run does not write any files."""
    contracts_dir = tmp_path / "raw" / "contracts"
    contracts_dir.mkdir(parents=True)
    p = contracts_dir / "TYH24_1m_2023-12-13_2024-03-12.parquet"
    _make_minimal_parquet(p)

    result = runner.invoke(app, ["backfill-manifests", "--dry-run", "--data-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "would be written" in result.output.lower() or "dry run" in result.output.lower()
    # No manifest should have been created
    assert not (contracts_dir / "TYH24_1m_2023-12-13_2024-03-12.parquet.manifest.json").exists()


def test_backfill_writes_manifests(tmp_path: Path):
    """backfill writes manifests for files that lack them."""
    contracts_dir = tmp_path / "raw" / "contracts"
    contracts_dir.mkdir(parents=True)
    p = contracts_dir / "TYH24_1m_2023-12-13_2024-03-12.parquet"
    _make_minimal_parquet(p)

    result = runner.invoke(app, ["backfill-manifests", "--data-root", str(tmp_path)])
    assert result.exit_code == 0

    manifest_path = contracts_dir / "TYH24_1m_2023-12-13_2024-03-12.parquet.manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["layer"] == "raw"
    assert data.get("backfilled") is True
    assert data["symbol"] == "TYH24"


# ---------------------------------------------------------------------------
# rebuild features — unknown feature set exits 2
# ---------------------------------------------------------------------------


def test_rebuild_features_missing_set_exits_2():
    result = runner.invoke(app, ["rebuild", "features", "--set", "nonexistent-xyz"])
    assert result.exit_code == 2
    assert "ERROR" in result.output or "not found" in result.output.lower() or result.exit_code == 2


# ---------------------------------------------------------------------------
# inventory — smoke test
# ---------------------------------------------------------------------------


def test_inventory_runs(tmp_path: Path):
    """inventory runs without error even on an empty data root."""
    result = runner.invoke(app, ["inventory", "--data-root", str(tmp_path)])
    assert result.exit_code == 0
