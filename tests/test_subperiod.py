import pandas as pd
import numpy as np
import pytest

from trading_research.eval.subperiod import subperiod_analysis


def _make_trades_and_equity():
    """10 trades spanning ~900 days → 3 calendar years (2020, 2021, 2022)."""
    dates = pd.date_range("2020-01-01", periods=10, freq="100D", tz="UTC")
    trades = pd.DataFrame({
        "net_pnl_usd": [100, -50, 200, 100, -50, 200, 100, -50, 200, 100],
        "exit_ts": dates,
        "entry_ts": dates - pd.Timedelta(days=1),
        "mae_points": [-10] * 10,
        "mfe_points": [20] * 10,
    })
    equity = trades.set_index("exit_ts")["net_pnl_usd"].cumsum()
    return trades, equity


def test_subperiod_returns_dict():
    trades, equity = _make_trades_and_equity()
    result = subperiod_analysis(trades, equity, splits="yearly")
    assert isinstance(result, dict)


def test_subperiod_dict_keys():
    """Result contains 'table', 'degradation_flag', 'degradation_message'."""
    trades, equity = _make_trades_and_equity()
    result = subperiod_analysis(trades, equity, splits="yearly")
    for key in ("table", "degradation_flag", "degradation_message"):
        assert key in result, f"Missing key: {key}"


def test_subperiod_table_is_dataframe():
    trades, equity = _make_trades_and_equity()
    result = subperiod_analysis(trades, equity, splits="yearly")
    assert isinstance(result["table"], pd.DataFrame)


def test_subperiod_table_has_period_column():
    trades, equity = _make_trades_and_equity()
    result = subperiod_analysis(trades, equity, splits="yearly")
    assert "period" in result["table"].columns


def test_subperiod_yearly_splits_three_years():
    """Trades spanning 2020-01-01 → 2022-06-19 produce 3 yearly rows."""
    trades, equity = _make_trades_and_equity()
    result = subperiod_analysis(trades, equity, splits="yearly")
    table = result["table"]
    assert len(table) == 3, f"Expected 3 years, got {len(table)}: {table['period'].tolist()}"


def test_subperiod_empty_trades():
    """Empty trades returns a no-data sentinel dict with an empty table."""
    empty = pd.DataFrame(columns=["net_pnl_usd", "exit_ts", "entry_ts"])
    equity = pd.Series(dtype=float)
    result = subperiod_analysis(empty, equity, splits="yearly")
    assert isinstance(result, dict)
    assert isinstance(result["table"], pd.DataFrame)
    assert len(result["table"]) == 0
