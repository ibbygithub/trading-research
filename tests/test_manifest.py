"""Tests for the manifest module."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trading_research.data.manifest import (
    is_stale,
    manifest_path_for,
    read_manifest,
    write_manifest,
)


class TestManifestRoundtrip:
    def test_write_creates_sidecar(self, tmp_path: Path):
        parquet = tmp_path / "test.parquet"
        parquet.touch()
        manifest = {"layer": "clean", "symbol": "ZN", "timeframe": "5m"}
        mp = write_manifest(parquet, manifest)
        assert mp == manifest_path_for(parquet)
        assert mp.exists()

    def test_read_returns_dict(self, tmp_path: Path):
        parquet = tmp_path / "test.parquet"
        parquet.touch()
        original = {"layer": "clean", "symbol": "ZN", "timeframe": "5m"}
        write_manifest(parquet, original)
        result = read_manifest(parquet)
        assert result is not None
        assert result["symbol"] == "ZN"
        assert result["timeframe"] == "5m"

    def test_write_injects_built_at_and_commit(self, tmp_path: Path):
        parquet = tmp_path / "test.parquet"
        parquet.touch()
        write_manifest(parquet, {"layer": "raw"})
        result = read_manifest(parquet)
        assert "built_at" in result
        assert "code_commit" in result
        assert "schema_version" in result

    def test_read_missing_returns_none(self, tmp_path: Path):
        parquet = tmp_path / "nonexistent.parquet"
        result = read_manifest(parquet)
        assert result is None

    def test_manifest_path_convention(self, tmp_path: Path):
        parquet = tmp_path / "ZN_5m.parquet"
        mp = manifest_path_for(parquet)
        assert mp.name == "ZN_5m.parquet.manifest.json"
        assert mp.parent == tmp_path


class TestStaleness:
    def test_no_manifest_is_stale(self, tmp_path: Path):
        parquet = tmp_path / "test.parquet"
        parquet.touch()
        stale, reasons = is_stale(parquet)
        assert stale
        assert "NO_MANIFEST" in reasons

    def test_fresh_file_not_stale(self, tmp_path: Path):
        source = tmp_path / "source.parquet"
        source.touch()
        source_manifest = {
            "layer": "raw",
            "built_at": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
        write_manifest(source, source_manifest)

        derived = tmp_path / "derived.parquet"
        derived.touch()
        write_manifest(derived, {
            "layer": "clean",
            "sources": [{"path": str(source)}],
            "built_at": datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat(),
        })

        stale, reasons = is_stale(derived)
        assert not stale
        assert reasons == []

    def test_stale_when_source_newer(self, tmp_path: Path):
        source = tmp_path / "source.parquet"
        source.touch()
        write_manifest(source, {
            "layer": "raw",
            "built_at": datetime(2024, 1, 3, tzinfo=timezone.utc).isoformat(),
        })

        derived = tmp_path / "derived.parquet"
        derived.touch()
        write_manifest(derived, {
            "layer": "clean",
            "sources": [{"path": str(source)}],
            "built_at": datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat(),
        })

        stale, reasons = is_stale(derived)
        assert stale
        assert any("source_newer" in r for r in reasons)

    def test_stale_when_source_missing(self, tmp_path: Path):
        ghost_source = tmp_path / "ghost.parquet"
        derived = tmp_path / "derived.parquet"
        derived.touch()
        write_manifest(derived, {
            "layer": "clean",
            "sources": [{"path": str(ghost_source)}],
            "built_at": datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat(),
        })

        stale, reasons = is_stale(derived)
        assert stale
        assert any("source_missing" in r for r in reasons)
