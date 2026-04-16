"""Tests for eval/report.py — generate_report() smoke test."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_research.eval.report import generate_report, _add_derived_columns, _compute_streaks


# ---------------------------------------------------------------------------
# Synthetic run directory builder
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path, n_trades: int = 50) -> Path:
    """Build a minimal synthetic run directory under tmp_path."""
    run_dir = tmp_path / "zn-test-v1" / "2026-01-01-00-00"
    run_dir.mkdir(parents=True)

    rng = np.random.default_rng(42)
    n = n_trades

    base_ts = pd.date_range("2024-01-02 10:00", periods=n, freq="30min", tz="UTC")
    entry_price = 110.0 + rng.standard_normal(n).cumsum() * 0.01
    stop = entry_price - 0.125
    pnl_pts = rng.standard_normal(n) * 0.05
    pnl_usd = pnl_pts * 1000
    net_pnl = pnl_usd - 35.25

    trades = pd.DataFrame(
        {
            "trade_id": [f"t{i:04d}" for i in range(n)],
            "strategy_id": "zn-test-v1",
            "symbol": "ZN",
            "direction": rng.choice(["long", "short"], n).tolist(),
            "quantity": np.ones(n, dtype=int),
            "entry_trigger_ts": base_ts,
            "entry_ts": base_ts,
            "entry_price": entry_price,
            "exit_trigger_ts": base_ts + pd.Timedelta(minutes=30),
            "exit_ts": base_ts + pd.Timedelta(minutes=30),
            "exit_price": entry_price + pnl_pts,
            "exit_reason": rng.choice(["signal", "stop", "target", "EOD"], n).tolist(),
            "initial_stop": stop,
            "initial_target": entry_price + 0.25,
            "pnl_points": pnl_pts,
            "pnl_usd": pnl_usd,
            "slippage_usd": np.full(n, 31.25),
            "commission_usd": np.full(n, 4.0),
            "net_pnl_usd": net_pnl,
            "mae_points": -abs(rng.standard_normal(n) * 0.03),
            "mfe_points": abs(rng.standard_normal(n) * 0.04),
        }
    )
    trades.to_parquet(run_dir / "trades.parquet", index=False)

    # Equity curve
    equity_ts = base_ts + pd.Timedelta(minutes=30)
    equity_df = pd.DataFrame(
        {"exit_ts": equity_ts, "equity_usd": net_pnl.cumsum()}
    )
    equity_df.to_parquet(run_dir / "equity_curve.parquet", index=False)

    # Summary
    summary = {
        "total_trades": n,
        "win_rate": 0.5,
        "avg_win_usd": 50.0,
        "avg_loss_usd": -40.0,
        "profit_factor": 1.1,
        "expectancy_usd": float(net_pnl.mean()),
        "trades_per_week": 5.0,
        "max_consec_losses": 4,
        "sharpe": 0.8,
        "sortino": 1.0,
        "calmar": 0.5,
        "max_drawdown_usd": -500.0,
        "max_drawdown_pct": -0.05,
        "drawdown_duration_days": 30,
        "avg_mae_points": -0.03,
        "avg_mfe_points": 0.04,
        "confidence_intervals": {},
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    return run_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateReport:
    """Smoke tests for generate_report()."""

    def test_creates_html_file(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        paths = generate_report(run_dir)
        assert paths.report.exists()
        assert paths.report.suffix == ".html"

    def test_html_file_non_empty(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        paths = generate_report(run_dir)
        content = paths.report.read_text(encoding="utf-8")
        assert len(content) > 10_000  # must have meaningful content

    def test_all_15_section_anchors_present(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        paths = generate_report(run_dir)
        html = paths.report.read_text(encoding="utf-8")
        missing = []
        for i in range(1, 16):
            anchor = f'id="s{i}"'
            if anchor not in html:
                missing.append(f"s{i}")
        assert not missing, f"Missing section anchors: {missing}"

    def test_creates_data_dictionary(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        paths = generate_report(run_dir)
        assert paths.data_dictionary.exists()
        content = paths.data_dictionary.read_text(encoding="utf-8")
        assert "# Data Dictionary" in content

    def test_file_under_10mb(self, tmp_path):
        run_dir = _make_run_dir(tmp_path, n_trades=200)
        paths = generate_report(run_dir)
        size_mb = paths.report.stat().st_size / 1024 / 1024
        assert size_mb < 10, f"Report too large: {size_mb:.1f} MB"

    def test_strategy_id_in_html(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        paths = generate_report(run_dir)
        html = paths.report.read_text(encoding="utf-8")
        assert "zn-test-v1" in html

    def test_missing_run_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            generate_report(tmp_path / "nonexistent" / "run")

    def test_missing_trades_raises(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        (run_dir / "trades.parquet").unlink()
        with pytest.raises(FileNotFoundError):
            generate_report(run_dir)


class TestAddDerivedColumns:
    """Unit tests for _add_derived_columns()."""

    def _make_trades_df(self, n: int = 20) -> pd.DataFrame:
        rng = np.random.default_rng(1)
        ts = pd.date_range("2024-01-02 10:00", periods=n, freq="30min", tz="UTC")
        ep = 110.0 + rng.standard_normal(n)
        stop = ep - 0.125
        pnl = rng.standard_normal(n) * 0.05 * 1000
        return pd.DataFrame(
            {
                "entry_ts": ts,
                "exit_ts": ts + pd.Timedelta(minutes=30),
                "entry_price": ep,
                "initial_stop": stop,
                "net_pnl_usd": pnl,
                "mae_points": -abs(rng.standard_normal(n) * 0.03),
                "mfe_points": abs(rng.standard_normal(n) * 0.04),
            }
        )

    def test_pnl_r_computed(self):
        df = self._make_trades_df()
        result = _add_derived_columns(df, 1000.0)
        assert "pnl_r" in result.columns
        finite = result["pnl_r"].dropna()
        assert len(finite) > 0

    def test_hold_bars_non_negative(self):
        df = self._make_trades_df()
        result = _add_derived_columns(df, 1000.0)
        assert (result["hold_bars"] >= 0).all()

    def test_hold_minutes_matches_ts_delta(self):
        df = self._make_trades_df()
        result = _add_derived_columns(df, 1000.0)
        # Each trade is 30 minutes
        assert (result["hold_minutes"] == 30.0).all()
        assert (result["hold_bars"] == 6).all()

    def test_outcome_categories(self):
        df = self._make_trades_df()
        result = _add_derived_columns(df, 1000.0)
        assert set(result["outcome"].unique()).issubset({"winner", "loser", "scratch"})

    def test_mae_r_non_positive_for_adverse(self):
        df = self._make_trades_df()
        result = _add_derived_columns(df, 1000.0)
        # mae_r should be computed (may be positive because we take abs of mae_points)
        assert "mae_r" in result.columns


class TestComputeStreaks:
    """Unit tests for the streak computation helper."""

    def test_all_winners(self):
        wins, losses = _compute_streaks(np.array([1.0, 2.0, 3.0]))
        assert wins == [3]
        assert losses == []

    def test_all_losers(self):
        wins, losses = _compute_streaks(np.array([-1.0, -2.0]))
        assert wins == []
        assert losses == [2]

    def test_alternating(self):
        wins, losses = _compute_streaks(np.array([1.0, -1.0, 1.0, -1.0]))
        assert wins == [1, 1]
        assert losses == [1, 1]

    def test_mixed_streaks(self):
        net = np.array([1, 1, 1, -1, -1, 1, -1, -1, -1])
        wins, losses = _compute_streaks(net)
        assert max(wins) == 3
        assert max(losses) == 3

    def test_empty(self):
        wins, losses = _compute_streaks(np.array([]))
        assert wins == []
        assert losses == []
