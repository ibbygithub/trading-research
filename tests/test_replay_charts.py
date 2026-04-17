"""Tests for replay.charts — figure builders."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

from trading_research.replay.charts import (
    build_5m_figure,
    build_candlestick,
    build_ofi_bar,
    build_trade_markers,
)
from trading_research.replay.data import load_window

_DATA_ROOT = Path(__file__).parents[1] / "data"
_FROM = datetime(2024, 1, 2)
_TO = datetime(2024, 1, 31)


@pytest.fixture(scope="module")
def window():
    return load_window("ZN", _FROM, _TO, data_root=_DATA_ROOT)


# ------------------------------------------------------------------
# build_candlestick
# ------------------------------------------------------------------


def test_build_candlestick_returns_figure(window):
    fig = build_candlestick(window["15m"], tf_label="15m", height=400)
    assert isinstance(fig, go.Figure)


def test_build_candlestick_has_candlestick_trace(window):
    fig = build_candlestick(window["15m"], tf_label="15m")
    trace_types = [type(t).__name__ for t in fig.data]
    assert "Candlestick" in trace_types


def test_build_candlestick_5m_has_vwap_and_bb(window):
    """5m DataFrame has VWAP + BB columns; they should produce overlay traces."""
    fig = build_candlestick(window["5m"], tf_label="5m")
    names = [t.name for t in fig.data if t.name]
    assert any("VWAP" in n for n in names), "No VWAP trace found for 5m"
    assert any("BB" in n for n in names), "No Bollinger trace found for 5m"


def test_build_candlestick_60m_has_sma_200(window):
    """60m CLEAN DataFrame has sma_200; it should produce an SMA trace."""
    fig = build_candlestick(window["60m"], tf_label="60m")
    names = [t.name for t in fig.data if t.name]
    assert any("SMA" in n for n in names), "No SMA 200 trace found for 60m"


def test_build_candlestick_height(window):
    fig = build_candlestick(window["1D"], tf_label="1D", height=350)
    assert fig.layout.height == 350


def test_build_candlestick_uirevision(window):
    fig = build_candlestick(window["60m"], tf_label="60m")
    assert fig.layout.uirevision == "60m"


# ------------------------------------------------------------------
# build_ofi_bar
# ------------------------------------------------------------------


def test_build_ofi_bar_returns_figure(window):
    fig = build_ofi_bar(window["5m"])
    assert isinstance(fig, go.Figure)


def test_build_ofi_bar_has_bar_trace(window):
    fig = build_ofi_bar(window["5m"])
    trace_types = [type(t).__name__ for t in fig.data]
    assert "Bar" in trace_types


def test_build_ofi_bar_empty_on_no_ofi_column():
    """When the DataFrame has no OFI column the figure is still valid."""
    df = pd.DataFrame(
        {"open": [1.0], "close": [1.0], "high": [1.0], "low": [1.0]},
        index=pd.DatetimeIndex(["2024-01-02"], tz="UTC"),
    )
    fig = build_ofi_bar(df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


# ------------------------------------------------------------------
# build_5m_figure
# ------------------------------------------------------------------


def test_build_5m_figure_returns_figure(window):
    fig = build_5m_figure(window["5m"])
    assert isinstance(fig, go.Figure)


def test_build_5m_figure_has_candlestick_and_bar(window):
    fig = build_5m_figure(window["5m"])
    trace_types = [type(t).__name__ for t in fig.data]
    assert "Candlestick" in trace_types
    assert "Bar" in trace_types


def test_build_5m_figure_is_two_rows(window):
    """The figure must have two subplot rows (candlestick + OFI)."""
    fig = build_5m_figure(window["5m"])
    # Plotly subplot figures have a grid layout with rows/cols defined.
    assert fig.layout.grid is not None or len(fig.layout.annotations) >= 0
    # Check that traces are assigned to row 1 and row 2.
    rows = set()
    for trace in fig.data:
        yaxis = getattr(trace, "yaxis", None)
        if yaxis:
            rows.add(yaxis)
    assert len(rows) >= 2, "Expected traces on at least two y-axes (subplots)"


# ------------------------------------------------------------------
# build_trade_markers
# ------------------------------------------------------------------


def test_build_trade_markers_adds_traces():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[], y=[], name="base"))

    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(["2024-01-03 14:00"], utc=True),
            "exit_ts": pd.to_datetime(["2024-01-03 16:00"], utc=True),
            "entry_price": [112.0],
            "exit_price": [112.5],
            "stop_price": [111.5],
            "target_price": [113.0],
            "direction": ["long"],
        }
    )

    original_count = len(fig.data)
    build_trade_markers(fig, trades, tf="5m")
    assert len(fig.data) > original_count, "No traces added by build_trade_markers"


def test_build_trade_markers_noop_on_empty():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[], y=[], name="base"))
    before = len(fig.data)
    build_trade_markers(fig, pd.DataFrame(), tf="5m")
    assert len(fig.data) == before


def test_build_trade_markers_noop_on_none():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[], y=[], name="base"))
    before = len(fig.data)
    build_trade_markers(fig, None, tf="5m")
    assert len(fig.data) == before
