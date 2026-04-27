import numpy as np
import pandas as pd
import pytest

from trading_research.eval.monte_carlo import shuffle_trade_order


def _make_trades(n: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({
        "net_pnl_usd": [100, -50, 200, 100, -50, 200, 100, -50, 200, 100][:n],
        "exit_ts": dates,
        "entry_ts": dates - pd.Timedelta(hours=1),
        "mae_points": [-10] * n,
        "mfe_points": [20] * n,
    })


def test_shuffle_trade_order_returns_dict():
    trades = _make_trades()
    result = shuffle_trade_order(trades, n_iter=5, seed=42)
    assert isinstance(result, dict)


def test_shuffle_trade_order_keys_present():
    """All expected keys are present in the returned dict."""
    trades = _make_trades()
    result = shuffle_trade_order(trades, n_iter=5, seed=42)
    for key in ("n_trades", "n_iter", "max_dd_dist", "calmar_dist",
                "actual_max_dd", "actual_calmar", "interpretation"):
        assert key in result, f"Missing key: {key}"


def test_shuffle_trade_order_n_iter_matches():
    """Distribution arrays have length equal to n_iter."""
    trades = _make_trades()
    n_iter = 5
    result = shuffle_trade_order(trades, n_iter=n_iter, seed=42)
    assert len(result["max_dd_dist"]) == n_iter
    assert len(result["calmar_dist"]) == n_iter


def test_shuffle_total_pnl_invariant():
    """Shuffling order doesn't change total PnL — last equity value is identical."""
    trades = _make_trades()
    result = shuffle_trade_order(trades, n_iter=10, seed=42)
    total_pnls = {round(curve[-1], 8) for curve in result["equity_curves"]}
    assert len(total_pnls) == 1, (
        f"Total PnL should be the same across all shuffles, got {total_pnls}"
    )


def test_shuffle_empty_trades():
    """Empty trades DataFrame returns a no-data sentinel dict."""
    empty = pd.DataFrame(columns=["net_pnl_usd", "exit_ts", "entry_ts"])
    result = shuffle_trade_order(empty, n_iter=5, seed=42)
    assert isinstance(result, dict)
    assert result.get("n_trades") == 0
