"""Tests for `trading-research validate-strategy`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from trading_research.cli.main import app
from trading_research.cli.validate_strategy import validate_strategy

runner = CliRunner()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _write_features_parquet(
    data_root: Path, symbol: str, timeframe: str, feature_set: str, columns: list[str]
) -> Path:
    """Write a tiny features parquet exposing the requested columns to the linter."""
    feat_dir = data_root / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)
    path = (
        feat_dir
        / f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_2026-01-01_2026-01-02.parquet"
    )
    df = pd.DataFrame({c: [0.0, 0.0] for c in columns})
    df["timestamp_utc"] = pd.to_datetime(
        ["2026-01-02T14:00:00", "2026-01-02T14:01:00"]
    ).tz_localize("UTC")
    tbl = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(tbl, path)
    return path


def _write_strategy_yaml(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_help():
    result = runner.invoke(app, ["validate-strategy", "--help"])
    assert result.exit_code == 0
    assert "validate" in result.output.lower()


def test_missing_yaml_file_exits_2(tmp_path: Path):
    result = runner.invoke(
        app, ["validate-strategy", str(tmp_path / "does-not-exist.yaml")]
    )
    assert result.exit_code == 2


def test_invalid_yaml_exits_2(tmp_path: Path):
    p = _write_strategy_yaml(tmp_path / "bad.yaml", "this is: : not valid: yaml: [")
    result = runner.invoke(app, ["validate-strategy", str(p)])
    assert result.exit_code == 2


def test_dispatch_conflict_exits_1(tmp_path: Path):
    """A config with both entry: and template: is rejected at cross-key check."""
    p = _write_strategy_yaml(
        tmp_path / "conflict.yaml",
        """\
strategy_id: bad-conflict
symbol: 6A
timeframe: 60m
feature_set: base-v1
entry:
  long:
    all:
      - "close > 100"
template: some-template
""",
    )
    result = runner.invoke(
        app, ["validate-strategy", str(p), "--data-root", str(tmp_path / "data")]
    )
    assert result.exit_code in (1, 2)
    assert "only one" in result.output.lower() or "conflict" in result.output.lower()


def test_clean_strategy_exits_0(tmp_path: Path):
    data_root = tmp_path / "data"
    _write_features_parquet(
        data_root, "6A", "60m", "base-v1", ["close", "vwap_monthly", "atr_14"]
    )
    p = _write_strategy_yaml(
        tmp_path / "ok.yaml",
        """\
strategy_id: ok-strategy
symbol: 6A
timeframe: 60m
feature_set: base-v1
knobs:
  band: 1.0
entry:
  long:
    all:
      - "close < vwap_monthly - band * atr_14"
  short:
    all:
      - "close > vwap_monthly + band * atr_14"
exits:
  stop:
    long: "close - atr_14"
    short: "close + atr_14"
  target:
    long: "vwap_monthly"
    short: "vwap_monthly"
""",
    )
    result = runner.invoke(
        app, ["validate-strategy", str(p), "--data-root", str(data_root)]
    )
    assert result.exit_code == 0, result.output
    assert "No errors" in result.output


def test_unknown_column_exits_1(tmp_path: Path):
    """A condition referencing a missing column produces a validation error."""
    data_root = tmp_path / "data"
    _write_features_parquet(data_root, "6A", "60m", "base-v1", ["close"])
    p = _write_strategy_yaml(
        tmp_path / "bad-col.yaml",
        """\
strategy_id: bad-col
symbol: 6A
timeframe: 60m
feature_set: base-v1
entry:
  long:
    all:
      - "close < not_a_column"
exits:
  stop:
    long: "close - 1.0"
""",
    )
    result = runner.invoke(
        app, ["validate-strategy", str(p), "--data-root", str(data_root)]
    )
    assert result.exit_code == 1
    assert "not_a_column" in result.output or "not a column" in result.output


def test_missing_features_parquet_exits_2(tmp_path: Path):
    p = _write_strategy_yaml(
        tmp_path / "no-features.yaml",
        """\
strategy_id: no-features
symbol: XX
timeframe: 60m
feature_set: base-v1
entry:
  long:
    all:
      - "close > 100"
exits:
  stop:
    long: "close - 1.0"
""",
    )
    result = runner.invoke(
        app, ["validate-strategy", str(p), "--data-root", str(tmp_path / "data")]
    )
    assert result.exit_code == 2
    assert "features parquet not found" in result.output


def test_programmatic_returns_result(tmp_path: Path):
    """validate_strategy() is callable as a library function and returns a result."""
    data_root = tmp_path / "data"
    _write_features_parquet(data_root, "6A", "60m", "base-v1", ["close", "atr_14"])
    p = _write_strategy_yaml(
        tmp_path / "lib.yaml",
        """\
strategy_id: lib-test
symbol: 6A
timeframe: 60m
feature_set: base-v1
entry:
  long:
    all:
      - "close > 0"
exits:
  stop:
    long: "close - atr_14"
""",
    )
    result = validate_strategy(p, data_root=data_root)
    assert result.errors == []
    assert result.symbol == "6A"
    assert result.timeframe == "60m"
    assert result.dispatch == "yaml-template"
    assert result.features_path is not None
