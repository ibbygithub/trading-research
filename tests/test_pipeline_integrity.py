"""Tests for eval/pipeline_integrity.py."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from trading_research.eval.pipeline_integrity import (
    generate_pipeline_integrity_report,
    _check_trade_date_boundaries,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path, n_trades: int = 20) -> Path:
    run_dir = tmp_path / "pi-test-v1" / "2026-01-01-00-00"
    run_dir.mkdir(parents=True)

    rng = np.random.default_rng(42)
    n = n_trades
    base_ts = pd.date_range("2024-01-02 14:00", periods=n, freq="30min", tz="UTC")
    entry_price = 110.0 + rng.standard_normal(n)
    stop = entry_price - 0.125

    trades = pd.DataFrame(
        {
            "trade_id": [f"t{i:04d}" for i in range(n)],
            "strategy_id": "pi-test-v1",
            "symbol": "ZN",
            "direction": "long",
            "quantity": 1,
            "entry_trigger_ts": base_ts,
            "entry_ts": base_ts,
            "entry_price": entry_price,
            "exit_trigger_ts": base_ts + pd.Timedelta(minutes=30),
            "exit_ts": base_ts + pd.Timedelta(minutes=30),
            "exit_price": entry_price + rng.standard_normal(n) * 0.05,
            "exit_reason": "signal",
            "initial_stop": stop,
            "initial_target": entry_price + 0.25,
            "pnl_points": rng.standard_normal(n) * 0.05,
            "pnl_usd": rng.standard_normal(n) * 50,
            "slippage_usd": 31.25,
            "commission_usd": 4.0,
            "net_pnl_usd": rng.standard_normal(n) * 50 - 35.25,
            "mae_points": -abs(rng.standard_normal(n) * 0.03),
            "mfe_points": abs(rng.standard_normal(n) * 0.04),
        }
    )
    trades.to_parquet(run_dir / "trades.parquet", index=False)
    return run_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGeneratePipelineIntegrityReport:
    """Smoke tests for generate_pipeline_integrity_report()."""

    def test_creates_markdown_file(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_pipeline_integrity_report(run_dir)
        assert path.exists()
        assert path.suffix == ".md"

    def test_contains_all_five_sections(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_pipeline_integrity_report(run_dir)
        content = path.read_text(encoding="utf-8")
        assert "## 1." in content
        assert "## 2." in content
        assert "## 3." in content
        assert "## 4." in content
        assert "## 5." in content

    def test_missing_trades_raises(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        (run_dir / "trades.parquet").unlink()
        with pytest.raises(FileNotFoundError):
            generate_pipeline_integrity_report(run_dir)

    def test_pipeline_header_present(self, tmp_path):
        run_dir = _make_run_dir(tmp_path)
        path = generate_pipeline_integrity_report(run_dir)
        content = path.read_text(encoding="utf-8")
        assert "# Pipeline Integrity Report" in content


class TestTradeDateBoundaries:
    """Unit tests for _check_trade_date_boundaries() helper."""

    def _make_trades(
        self,
        entry_times: list[str],
        exit_times: list[str],
        exit_reasons: list[str],
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "entry_ts": pd.to_datetime(entry_times, utc=True),
                "exit_ts": pd.to_datetime(exit_times, utc=True),
                "exit_reason": exit_reasons,
                "trade_id": [f"t{i}" for i in range(len(entry_times))],
            }
        )

    def test_same_day_pass(self):
        trades = self._make_trades(
            ["2024-01-02 14:00:00+00:00"],
            ["2024-01-02 15:00:00+00:00"],
            ["signal"],
        )
        lines = _check_trade_date_boundaries(trades)
        joined = " ".join(lines)
        assert "Non-EOD cross-session: 0" in joined

    def test_cross_midnight_non_eod_flagged(self):
        # Trade enters at 23:30 UTC Jan 2 (17:30 ET), exits at 00:30 UTC Jan 3 (18:30 ET)
        # +6h offset: entry trade_date = Jan 3, exit trade_date = Jan 3 → actually same
        # Let's use a clear cross-date example: entry 2024-01-02 20:00 UTC, exit 2024-01-03 04:00 UTC
        # +6h: entry = Jan 2 2024 02:00 AM → Jan 3 2024 02:00 AM trade date? No:
        # (20:00 UTC + 6h = 02:00 ET next day = Jan 3), exit (04:00 UTC + 6h = 10:00 ET = Jan 3)
        # Both Jan 3 → same trade date, so no cross-date.
        # For genuine cross: entry at 10:00 UTC Jan 2 (+6h = 16:00 ET Jan 2 → trade date Jan 2)
        # exit at 02:00 UTC Jan 3 (+6h = 08:00 ET Jan 3 → trade date Jan 3)
        trades = self._make_trades(
            ["2024-01-02 10:00:00+00:00"],
            ["2024-01-03 02:00:00+00:00"],
            ["signal"],
        )
        lines = _check_trade_date_boundaries(trades)
        joined = " ".join(lines)
        # Non-EOD cross: 1
        assert "Non-EOD cross-session: 1" in joined

    def test_eod_cross_not_flagged(self):
        # Same cross-date scenario but exit_reason is EOD — should NOT be flagged as a problem
        # (EOD exits from the early morning session may technically cross midnight UTC)
        trades = self._make_trades(
            ["2024-01-02 10:00:00+00:00"],
            ["2024-01-03 02:00:00+00:00"],
            ["EOD"],
        )
        lines = _check_trade_date_boundaries(trades)
        joined = " ".join(lines)
        assert "Non-EOD cross-session: 0" in joined

    def test_empty_trades(self):
        trades = pd.DataFrame(
            {
                "entry_ts": pd.Series([], dtype="datetime64[ns, UTC]"),
                "exit_ts": pd.Series([], dtype="datetime64[ns, UTC]"),
                "exit_reason": pd.Series([], dtype=str),
                "trade_id": pd.Series([], dtype=str),
            }
        )
        lines = _check_trade_date_boundaries(trades)
        assert any("No trades" in line for line in lines)


class TestHTFMergeAuditLogic:
    """Unit test for the shift(1) HTF audit concept on a synthetic dataset.

    We build a synthetic features parquet with a *known violation* (htf_bias
    column does NOT use shift(1)) and a clean dataset (it does).  Since the
    actual _check_htf_merge reads real disk parquets, these tests exercise the
    underlying arithmetic directly rather than the I/O wrapper.
    """

    def test_shift1_violation_detected(self):
        """The htf value at bar T should equal the daily value at bar T-1.
        A violation exists when htf_val == daily_val_at_T (no shift)."""
        n = 50
        daily_hist = np.array([i * 0.001 for i in range(n)])

        # WRONG: feature stores the current daily value (no shift)
        htf_stored_wrong = daily_hist  # same index, no shift

        # CORRECT: feature stores the previous daily value (shift(1))
        htf_stored_correct = np.concatenate([[np.nan], daily_hist[:-1]])

        violations_wrong = 0
        violations_correct = 0

        for t in range(5, n):
            stored = htf_stored_wrong[t]
            ref = daily_hist[t - 1]  # what shift(1) should give
            tol = 1e-8
            if abs(stored - ref) > tol:
                violations_wrong += 1

            stored2 = htf_stored_correct[t]
            if not np.isnan(stored2) and abs(stored2 - ref) > tol:
                violations_correct += 1

        # Wrong implementation has many violations; correct has zero
        assert violations_wrong > 0
        assert violations_correct == 0
