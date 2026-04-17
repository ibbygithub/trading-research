"""Dash layout builder for the replay cockpit.

`build_layout(symbol, from_dt, to_dt, figs)` returns the complete component
tree for the app.  The 2×2 grid is:

    ┌──────────────────────┬──────────────────────┐
    │  5m  (+ OFI subplot) │  15m                 │
    ├──────────────────────┼──────────────────────┤
    │  60m                 │  1D                  │
    └──────────────────────┴──────────────────────┘
"""

from __future__ import annotations

from datetime import datetime

import plotly.graph_objects as go
from dash import dcc, html

# Timeframe options for the toggle radio
_TF_OPTIONS = [
    {"label": "5m",  "value": "5m"},
    {"label": "15m", "value": "15m"},
    {"label": "60m", "value": "60m"},
    {"label": "Daily","value": "1D"},
]

# Map timeframe value → chart component ID
_TF_TO_CHART_ID = {"5m": "chart-5m", "15m": "chart-15m", "60m": "chart-60m", "1D": "chart-1d"}


def build_layout(
    symbol: str,
    from_dt: datetime,
    to_dt: datetime,
    figs: dict[str, go.Figure],
) -> html.Div:
    """Return the full Dash layout component tree.

    Parameters
    ----------
    symbol:   Instrument label shown in the header (e.g. "ZN").
    from_dt:  Initial window start (used to pre-populate the date picker).
    to_dt:    Initial window end.
    figs:     Pre-built figures keyed by timeframe: "5m", "15m", "60m", "1D".
    """
    return html.Div(
        style={"backgroundColor": "#0f172a", "minHeight": "100vh", "padding": "12px"},
        children=[
            # ── Header ────────────────────────────────────────────────────
            html.Div(
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "20px",
                    "marginBottom": "10px",
                    "flexWrap": "wrap",
                },
                children=[
                    html.H2(
                        f"{symbol} Forensic Cockpit",
                        style={
                            "color": "#f1f5f9",
                            "margin": "0",
                            "fontFamily": "monospace",
                            "fontSize": "18px",
                        },
                    ),
                    dcc.DatePickerRange(
                        id="date-picker",
                        start_date=from_dt.date() if hasattr(from_dt, "date") else from_dt,
                        end_date=to_dt.date() if hasattr(to_dt, "date") else to_dt,
                        display_format="YYYY-MM-DD",
                        style={"fontSize": "13px"},
                    ),
                    # ── Timeframe focus toggle ─────────────────────────────
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "8px"},
                        children=[
                            html.Span(
                                "Focus:",
                                style={"color": "#64748b", "fontFamily": "monospace",
                                       "fontSize": "12px"},
                            ),
                            dcc.RadioItems(
                                id="tf-focus",
                                options=_TF_OPTIONS,
                                value="all",  # "all" = show 2×2 grid
                                inline=True,
                                inputStyle={"marginRight": "3px"},
                                labelStyle={
                                    "color": "#94a3b8",
                                    "fontFamily": "monospace",
                                    "fontSize": "12px",
                                    "marginRight": "12px",
                                    "cursor": "pointer",
                                },
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            # Extra "All" option to restore 2×2 grid
                            html.Button(
                                "All",
                                id="tf-focus-all",
                                n_clicks=0,
                                style={
                                    "background": "rgba(100,116,139,0.15)",
                                    "border": "1px solid #334155",
                                    "color": "#94a3b8",
                                    "padding": "2px 10px",
                                    "borderRadius": "4px",
                                    "fontFamily": "monospace",
                                    "fontSize": "11px",
                                    "cursor": "pointer",
                                },
                            ),
                        ],
                    ),
                ],
            ),
            # ── Hidden stores ──────────────────────────────────────────────
            dcc.Store(id="hover-ts"),
            # ── 2 × 2 chart grid ──────────────────────────────────────────
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "gridTemplateRows": "auto auto",
                    "gap": "8px",
                },
                children=[
                    # Top-left: 5m with OFI
                    html.Div(
                        id="chart-panel-5m",
                        children=[
                            html.Div(
                                "5m",
                                style={"color": "#64748b", "fontSize": "11px", "marginBottom": "2px"},
                            ),
                            dcc.Graph(
                                id="chart-5m",
                                figure=figs.get("5m", go.Figure()),
                                config={"displayModeBar": True, "scrollZoom": True},
                                style={"height": "520px"},
                            ),
                        ]
                    ),
                    # Top-right: 15m
                    html.Div(
                        id="chart-panel-15m",
                        children=[
                            html.Div(
                                "15m",
                                style={"color": "#64748b", "fontSize": "11px", "marginBottom": "2px"},
                            ),
                            dcc.Graph(
                                id="chart-15m",
                                figure=figs.get("15m", go.Figure()),
                                config={"displayModeBar": True, "scrollZoom": True},
                                style={"height": "520px"},
                            ),
                        ]
                    ),
                    # Bottom-left: 60m
                    html.Div(
                        id="chart-panel-60m",
                        children=[
                            html.Div(
                                "60m",
                                style={"color": "#64748b", "fontSize": "11px", "marginBottom": "2px"},
                            ),
                            dcc.Graph(
                                id="chart-60m",
                                figure=figs.get("60m", go.Figure()),
                                config={"displayModeBar": True, "scrollZoom": True},
                                style={"height": "400px"},
                            ),
                        ]
                    ),
                    # Bottom-right: 1D
                    html.Div(
                        id="chart-panel-1d",
                        children=[
                            html.Div(
                                "1D",
                                style={"color": "#64748b", "fontSize": "11px", "marginBottom": "2px"},
                            ),
                            dcc.Graph(
                                id="chart-1d",
                                figure=figs.get("1D", go.Figure()),
                                config={"displayModeBar": True, "scrollZoom": True},
                                style={"height": "400px"},
                            ),
                        ]
                    ),
                ],
            ),
        ],
    )
