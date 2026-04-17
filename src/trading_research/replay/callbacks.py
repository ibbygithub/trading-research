"""Dash callbacks for the replay cockpit.

Two callback groups:

1. Crosshair sync
   Trigger: hoverData on any of the four charts.
   Action:  Store the hovered timestamp, then add a vline shape to every chart
            via Patch() to avoid a full figure re-render on each hover event.

2. Date-range update
   Trigger: DatePickerRange value change.
   Action:  Reload data for the new window, rebuild all four figures from
            scratch.  This is the only full-redraw callback.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import dash
from dash import Input, Output, Patch, ctx
from dash.exceptions import PreventUpdate

from trading_research.replay.charts import build_5m_figure, build_candlestick, build_ofi_bar, build_trade_markers, project_trades_to_tf
from trading_research.replay.data import DataNotFoundError, load_trades, load_window

# Shape spec for the crosshair vline — applied via Patch to every chart.
_VLINE = {
    "type": "line",
    "xref": "x",
    "yref": "paper",
    "x0": None,
    "x1": None,
    "y0": 0,
    "y1": 1,
    "line": {"color": "rgba(148,163,184,0.55)", "width": 1, "dash": "dot"},
}


def _extract_x(hover_data: dict | None) -> str | None:
    """Pull the x value (timestamp string) from a hoverData dict."""
    if hover_data and hover_data.get("points"):
        return hover_data["points"][0].get("x")
    return None


def register_callbacks(
    app: dash.Dash,
    symbol: str,
    data_root: Path | None = None,
    trades_path: Path | None = None,
) -> None:
    """Register all callbacks on *app*.

    Parameters
    ----------
    app:        The Dash app instance.
    symbol:     Instrument symbol (e.g. "ZN") — used when reloading data on
                date-range change.
    data_root:  Override for the data/ directory (used in tests).
    """

    # ------------------------------------------------------------------
    # 1. Crosshair: capture hovered timestamp into the store
    # ------------------------------------------------------------------

    @app.callback(
        Output("hover-ts", "data"),
        Input("chart-5m", "hoverData"),
        Input("chart-15m", "hoverData"),
        Input("chart-60m", "hoverData"),
        Input("chart-1d", "hoverData"),
        prevent_initial_call=True,
    )
    def store_hover_ts(h5m, h15m, h60m, h1d):
        triggered = ctx.triggered_id
        hover_map = {
            "chart-5m": h5m,
            "chart-15m": h15m,
            "chart-60m": h60m,
            "chart-1d": h1d,
        }
        ts = _extract_x(hover_map.get(triggered))
        if ts is None:
            raise PreventUpdate
        return ts

    # ------------------------------------------------------------------
    # 2. Crosshair: draw vline on all four charts via Patch
    # ------------------------------------------------------------------

    @app.callback(
        Output("chart-5m", "figure"),
        Output("chart-15m", "figure"),
        Output("chart-60m", "figure"),
        Output("chart-1d", "figure"),
        Input("hover-ts", "data"),
        prevent_initial_call=True,
    )
    def sync_crosshair(ts: str):
        if not ts:
            raise PreventUpdate

        shape = {**_VLINE, "x0": ts, "x1": ts}

        results = []
        for _ in range(4):
            p = Patch()
            p["layout"]["shapes"] = [shape]
            results.append(p)

        return results

    # ------------------------------------------------------------------
    # 3. Date-range update: full redraw of all four charts
    # ------------------------------------------------------------------

    @app.callback(
        Output("chart-5m", "figure", allow_duplicate=True),
        Output("chart-15m", "figure", allow_duplicate=True),
        Output("chart-60m", "figure", allow_duplicate=True),
        Output("chart-1d", "figure", allow_duplicate=True),
        Input("date-picker", "start_date"),
        Input("date-picker", "end_date"),
        prevent_initial_call=True,
    )
    def update_date_range(start_date: str | None, end_date: str | None):
        if not start_date or not end_date:
            raise PreventUpdate

        from_dt = datetime.fromisoformat(start_date)
        to_dt = datetime.fromisoformat(end_date)

        try:
            data = load_window(symbol, from_dt, to_dt, data_root=data_root)
        except DataNotFoundError as exc:
            # Return no-update so existing charts stay visible.
            raise PreventUpdate from exc

        fig_5m = build_5m_figure(data["5m"])
        fig_15m = build_candlestick(data["15m"], tf_label="15m", height=520)
        fig_60m = build_candlestick(data["60m"], tf_label="60m", height=400)
        fig_1d = build_candlestick(data["1D"], tf_label="1D", height=400)

        # Add trade markers when a trade log is loaded; all four charts get markers.
        if trades_path is not None:
            try:
                trades_df = load_trades(trades_path)
                from_ts = pd.Timestamp(from_dt, tz="UTC") if from_dt.tzinfo is None else pd.Timestamp(from_dt)
                to_ts = pd.Timestamp(to_dt, tz="UTC") if to_dt.tzinfo is None else pd.Timestamp(to_dt)
                mask = (trades_df["entry_ts"] >= from_ts) & (trades_df["exit_ts"] <= to_ts)
                window_trades = trades_df[mask]
                # Exact timestamps for 5m and 15m
                build_trade_markers(fig_5m, window_trades, "5m")
                build_trade_markers(fig_15m, window_trades, "15m")
                # Snapped timestamps for 60m and 1D
                build_trade_markers(fig_60m, project_trades_to_tf(window_trades, data["60m"]), "60m")
                build_trade_markers(fig_1d,  project_trades_to_tf(window_trades, data["1D"]),  "1D")
            except DataNotFoundError:
                pass  # Trades file disappeared — show charts without markers.

        return fig_5m, fig_15m, fig_60m, fig_1d

    # ------------------------------------------------------------------
    # 4. Timeframe focus toggle: hide/show chart panels
    # ------------------------------------------------------------------

    @app.callback(
        Output("chart-panel-5m",  "style"),
        Output("chart-panel-15m", "style"),
        Output("chart-panel-60m", "style"),
        Output("chart-panel-1d",  "style"),
        Input("tf-focus", "value"),
        Input("tf-focus-all", "n_clicks"),
        prevent_initial_call=False,
    )
    def toggle_tf_focus(tf_value: str | None, _n_all: int):
        """Show only the selected timeframe panel at full width, or all 4 in a grid."""
        triggered_id = ctx.triggered_id

        # "All" button or no selection → 2×2 grid
        show_all = (triggered_id == "tf-focus-all") or (tf_value is None)

        grid_cell = {"display": "block"}
        hidden    = {"display": "none"}
        full_width = {"display": "block", "gridColumn": "span 2"}

        if show_all or tf_value not in ("5m", "15m", "60m", "1D"):
            return grid_cell, grid_cell, grid_cell, grid_cell

        mapping = {"5m": 0, "15m": 1, "60m": 2, "1D": 3}
        selected = mapping.get(tf_value, -1)
        return tuple(full_width if i == selected else hidden for i in range(4))
