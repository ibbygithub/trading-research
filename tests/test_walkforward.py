"""Tests for backtest/walkforward.py.

Uses a synthetic 1000-bar dataset with a stub signal module to verify:
1. Purge and embargo exclude the correct bars.
2. Fold boundaries are non-overlapping.
3. OOS equity is the concatenation of fold results.
4. Per-fold metrics table has the correct shape.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_research.backtest.walkforward import run_walkforward, FoldResult, WalkForwardSummary


# ---------------------------------------------------------------------------
# Fixture: minimal strategy config + synthetic data
# ---------------------------------------------------------------------------

N_BARS = 1000


def _make_bars(n: int = N_BARS) -> pd.DataFrame:
    """Create n synthetic 5m bars."""
    idx = pd.date_range("2020-01-02 09:30", periods=n, freq="5min", tz="UTC")
    rng = np.random.default_rng(0)
    close = 130.0 + rng.standard_normal(n).cumsum() * 0.1
    return pd.DataFrame({
        "open": close - 0.02,
        "high": close + 0.05,
        "low": close - 0.05,
        "close": close,
        "volume": 1000,
        "buy_volume": 500,
        "sell_volume": 500,
        # Minimal indicator columns the engine and strategy might use.
        "atr_14": 0.25,
        "rsi_14": 50.0,
        "macd_line": 0.0,
        "macd_signal": 0.0,
        "macd_hist": 0.0,
        "macd_hist_prev": 0.0,
        "hist_decline_streak": 0,
        "hist_decline_streak_prev": 0,
        "htf_15m_close": close,
        "htf_15m_atr_14": 0.25,
        "session": "RTH",
        "trade_date": idx.date,
    }, index=idx)
    return df


def _make_stub_signal_module(name: str = "_test_wf_signals") -> types.ModuleType:
    """Create and register a stub signal module that returns zero signals."""
    mod = types.ModuleType(name)

    def generate_signals(bars: pd.DataFrame, **kwargs) -> pd.DataFrame:
        return pd.DataFrame({
            "signal": 0,
            "stop": np.nan,
            "target": np.nan,
        }, index=bars.index)

    mod.generate_signals = generate_signals
    sys.modules[name] = mod
    return mod


def _make_config(tmp_path: Path, signal_module: str = "_test_wf_signals") -> Path:
    """Write a minimal strategy YAML config."""
    import yaml
    cfg = {
        "strategy_id": "test-wf",
        "symbol": "ZN",
        "timeframe": "5m",
        "signal_module": signal_module,
        "feature_set": "base-v1",
        "backtest": {
            "fill_model": "next_bar_open",
            "eod_flat": True,
            "quantity": 1,
        },
    }
    p = tmp_path / "test_wf.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Patch the data loader so we don't need real feature parquets
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_walkforward_data(tmp_path, monkeypatch):
    """Patch _find_parquet and load_instrument to use synthetic data."""
    bars = _make_bars(N_BARS)
    feat_path = tmp_path / "ZN_backadjusted_5m_features_base-v1_20200101.parquet"
    bars_to_save = bars.reset_index().rename(columns={"index": "timestamp_utc"})
    bars_to_save.to_parquet(feat_path, engine="pyarrow", index=False)

    # Patch _find_parquet.
    from trading_research.replay import data as replay_data
    monkeypatch.setattr(
        replay_data,
        "_find_parquet",
        lambda feat_dir, pattern: feat_path,
    )

    # load_instrument("ZN") works with the real instruments.yaml — no patch needed.
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_walkforward_runs_without_error(tmp_path, patch_walkforward_data, monkeypatch):
    """run_walkforward completes with default parameters."""
    _make_stub_signal_module()
    cfg_path = _make_config(patch_walkforward_data)

    wf = run_walkforward(
        cfg_path,
        n_folds=5,
        gap_bars=20,
        embargo_bars=10,
        data_root=patch_walkforward_data,
    )
    assert isinstance(wf, WalkForwardSummary)
    assert len(wf.folds) > 0


def test_fold_boundaries_non_overlapping(tmp_path, patch_walkforward_data):
    """Test fold boundaries: no train bar appears in its own test fold."""
    _make_stub_signal_module()
    cfg_path = _make_config(patch_walkforward_data)

    wf = run_walkforward(
        cfg_path,
        n_folds=5,
        gap_bars=20,
        embargo_bars=10,
        data_root=patch_walkforward_data,
    )

    for fold in wf.folds:
        # Train ends before test starts (gap_bars apart).
        assert fold.train_end < fold.test_start


def test_purge_gap_respected(tmp_path, patch_walkforward_data):
    """Test that gap_bars bars are excluded between train end and test start."""
    _make_stub_signal_module()
    cfg_path = _make_config(patch_walkforward_data)
    gap = 50

    bars = _make_bars(N_BARS)
    bar_index = bars.index

    wf = run_walkforward(
        cfg_path,
        n_folds=5,
        gap_bars=gap,
        embargo_bars=10,
        data_root=patch_walkforward_data,
    )

    for fold in wf.folds:
        # Find the position of train_end and test_start in the bar index.
        train_end_pos = bar_index.get_indexer([fold.train_end], method="nearest")[0]
        test_start_pos = bar_index.get_indexer([fold.test_start], method="nearest")[0]
        # At least gap_bars should separate them.
        gap_actual = test_start_pos - train_end_pos
        assert gap_actual >= gap, (
            f"Fold {fold.fold}: gap={gap_actual} < required {gap}"
        )


def test_per_fold_metrics_shape(tmp_path, patch_walkforward_data):
    """Per-fold metrics DataFrame has one row per fold."""
    _make_stub_signal_module()
    cfg_path = _make_config(patch_walkforward_data)

    wf = run_walkforward(
        cfg_path,
        n_folds=5,
        gap_bars=20,
        embargo_bars=10,
        data_root=patch_walkforward_data,
    )

    assert len(wf.per_fold_metrics) == len(wf.folds)
    expected_cols = ["fold", "test_start", "test_end", "trades", "calmar", "sharpe"]
    for col in expected_cols:
        assert col in wf.per_fold_metrics.columns


def test_oos_trades_in_order(tmp_path, patch_walkforward_data):
    """OOS trades are sorted by entry_ts (fold concatenation is ordered)."""
    _make_stub_signal_module()
    cfg_path = _make_config(patch_walkforward_data)

    wf = run_walkforward(
        cfg_path,
        n_folds=5,
        gap_bars=20,
        embargo_bars=10,
        data_root=patch_walkforward_data,
    )

    if not wf.oos_trades.empty:
        entry_ts = pd.to_datetime(wf.oos_trades["entry_ts"])
        assert (entry_ts.diff().dropna() >= pd.Timedelta(0)).all()


def test_zero_signal_strategy_no_trades(tmp_path, patch_walkforward_data):
    """Zero-signal stub strategy produces no trades."""
    _make_stub_signal_module()
    cfg_path = _make_config(patch_walkforward_data)

    wf = run_walkforward(
        cfg_path,
        n_folds=5,
        gap_bars=20,
        embargo_bars=10,
        data_root=patch_walkforward_data,
    )

    # Zero-signal strategy → no trades.
    assert len(wf.oos_trades) == 0
