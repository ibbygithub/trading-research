"""Tests for eval/data_dictionary.py."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from trading_research.eval.data_dictionary import (
    generate_data_dictionary,
    documented_columns,
    TRADE_LOG_COLUMNS,
    REPORT_METRICS,
)
from trading_research.data.schema import TRADE_SCHEMA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "dd-test-v1" / "2026-01-01-00-00"
    run_dir.mkdir(parents=True)
    # Minimal trades.parquet not needed; generate_data_dictionary only uses run_dir path
    return run_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDocumentedColumns:
    """Verify every column in TRADE_SCHEMA is documented."""

    def test_trade_schema_columns_documented(self):
        """Every column defined in TRADE_SCHEMA must appear in the data dictionary."""
        documented = documented_columns()
        # TRADE_SCHEMA is a pyarrow Schema; iterate by field name
        schema_cols = [TRADE_SCHEMA.field(i).name for i in range(len(TRADE_SCHEMA))]
        missing = [c for c in schema_cols if c not in documented]
        assert not missing, f"TRADE_SCHEMA columns not in data dictionary: {missing}"

    def test_context_columns_documented(self):
        """Context join output columns must be documented."""
        documented = documented_columns()
        context_cols = [
            "atr_14_pct_rank_252",
            "daily_range_used_pct",
            "vwap_distance_atr",
            "htf_bias_strength",
            "session_regime",
            "entry_atr_14",
        ]
        missing = [c for c in context_cols if c not in documented]
        assert not missing, f"Context columns not in data dictionary: {missing}"

    def test_derived_columns_documented(self):
        """Derived report columns must be documented."""
        documented = documented_columns()
        derived = ["pnl_r", "mae_r", "mfe_r", "hold_minutes", "hold_bars", "outcome"]
        missing = [c for c in derived if c not in documented]
        assert not missing, f"Derived columns not in data dictionary: {missing}"


class TestGenerateDataDictionary:
    """Smoke tests for generate_data_dictionary()."""

    def test_creates_file(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_data_dictionary(run_dir)
        assert path.exists()
        assert path.suffix == ".md"

    def test_contains_headers(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_data_dictionary(run_dir)
        content = path.read_text(encoding="utf-8")
        assert "# Data Dictionary" in content
        assert "## Trade Log Columns" in content
        assert "## Report Metrics" in content

    def test_all_trade_schema_columns_in_output(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_data_dictionary(run_dir)
        content = path.read_text(encoding="utf-8")
        for col in [TRADE_SCHEMA.field(i).name for i in range(len(TRADE_SCHEMA))]:
            assert col in content, f"Column '{col}' not found in data dictionary output"

    def test_key_metrics_in_output(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_data_dictionary(run_dir)
        content = path.read_text(encoding="utf-8")
        for metric in ["Calmar", "Sharpe", "Sortino", "Expectancy"]:
            assert metric in content, f"Metric '{metric}' not found in data dictionary"

    def test_column_definitions_non_empty(self):
        """Every entry in TRADE_LOG_COLUMNS must have non-empty definition."""
        for col in TRADE_LOG_COLUMNS:
            assert col.get("definition"), f"Column {col['name']} has empty definition"
            assert col.get("dtype"), f"Column {col['name']} has empty dtype"
            assert "units" in col, f"Column {col['name']} missing units"

    def test_metric_definitions_non_empty(self):
        """Every entry in REPORT_METRICS must have non-empty interpretation."""
        for m in REPORT_METRICS:
            assert m.get("interpretation"), f"Metric {m['name']} has empty interpretation"
            assert m.get("formula"), f"Metric {m['name']} has empty formula"


class TestDocumentedColumnsAPI:
    """Tests for the documented_columns() helper."""

    def test_returns_set(self):
        cols = documented_columns()
        assert isinstance(cols, set)

    def test_non_empty(self):
        cols = documented_columns()
        assert len(cols) > 10

    def test_contains_basic_cols(self):
        cols = documented_columns()
        for c in ("trade_id", "entry_ts", "exit_ts", "net_pnl_usd"):
            assert c in cols, f"'{c}' not in documented_columns()"
