"""Tests for eval/leaderboard.py — CI columns and core functionality."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from trading_research.eval.leaderboard import (
    build_leaderboard,
    format_table,
    generate_html,
    _format_ci_range,
)
from trading_research.eval.trials import Trial


def _write_registry(tmp_path: Path, trials: list[dict]) -> Path:
    registry = tmp_path / ".trials.json"
    registry.write_text(json.dumps({"trials": trials}), encoding="utf-8")
    return registry


def _sample_trial(**overrides) -> dict:
    base = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "strategy_id": "zn-test-v1",
        "config_hash": "abc123",
        "sharpe": 1.2,
        "trial_group": "zn-test-v1",
        "code_version": "deadbeef",
        "featureset_hash": None,
        "cohort_label": "deadbeef",
        "mode": "exploration",
        "calmar": 0.8,
        "max_drawdown_usd": -500.0,
        "win_rate": 0.55,
        "total_trades": 150,
        "instrument": "ZN",
        "timeframe": "5m",
    }
    base.update(overrides)
    return base


class TestBuildLeaderboard:
    def test_loads_and_sorts(self, tmp_path):
        trials = [
            _sample_trial(strategy_id="a", calmar=0.5),
            _sample_trial(strategy_id="b", calmar=1.5),
        ]
        path = _write_registry(tmp_path, trials)
        result = build_leaderboard(registry_path=path, sort_key="calmar")
        assert result[0].strategy_id == "b"
        assert result[1].strategy_id == "a"

    def test_filter_by_mode(self, tmp_path):
        trials = [
            _sample_trial(strategy_id="a", mode="exploration"),
            _sample_trial(strategy_id="b", mode="validation"),
        ]
        path = _write_registry(tmp_path, trials)
        result = build_leaderboard(
            registry_path=path, filters=["mode=validation"]
        )
        assert len(result) == 1
        assert result[0].strategy_id == "b"

    def test_empty_registry(self, tmp_path):
        path = _write_registry(tmp_path, [])
        result = build_leaderboard(registry_path=path)
        assert result == []


class TestCIColumns:
    def test_ci_in_format_table(self, tmp_path):
        trials = [
            _sample_trial(
                sharpe_ci_lo=0.5,
                sharpe_ci_hi=1.8,
                calmar_ci_lo=0.2,
                calmar_ci_hi=1.3,
            ),
        ]
        path = _write_registry(tmp_path, trials)
        rows = build_leaderboard(registry_path=path)
        text = format_table(rows)
        assert "Calmar CI" in text
        assert "Sharpe CI" in text
        assert "[0.20, 1.30]" in text
        assert "[0.50, 1.80]" in text

    def test_ci_missing_shows_na(self, tmp_path):
        trials = [_sample_trial()]
        path = _write_registry(tmp_path, trials)
        rows = build_leaderboard(registry_path=path)
        text = format_table(rows)
        assert "Calmar CI" in text
        # Missing CIs render as N/A
        assert "N/A" in text

    def test_ci_in_html(self, tmp_path):
        trials = [
            _sample_trial(
                sharpe_ci_lo=0.3,
                sharpe_ci_hi=2.0,
                calmar_ci_lo=-0.1,
                calmar_ci_hi=1.5,
            ),
        ]
        path = _write_registry(tmp_path, trials)
        rows = build_leaderboard(registry_path=path)
        html = generate_html(rows)
        assert "[0.30, 2.00]" in html
        assert "[-0.10, 1.50]" in html


class TestFormatCIRange:
    def test_valid_range(self):
        assert _format_ci_range(0.5, 1.5) == "[0.50, 1.50]"

    def test_none_returns_none(self):
        assert _format_ci_range(None, 1.5) is None
        assert _format_ci_range(0.5, None) is None

    def test_nan_returns_none(self):
        assert _format_ci_range(float("nan"), 1.5) is None

    def test_negative_range(self):
        assert _format_ci_range(-0.5, 0.5) == "[-0.50, 0.50]"
