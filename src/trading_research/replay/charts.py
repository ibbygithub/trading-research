"""Plotly figure builders for the replay cockpit.

Three public functions:
    build_candlestick(df, tf_label, height)  → go.Figure (OHLC + overlays)
    build_ofi_bar(df)                        → go.Figure (OFI bar chart)
    build_trade_markers(fig, trades_df, tf)  → None (mutates fig in-place)

Plus one composite builder for the 5m pane:
    build_5m_figure(df)  → go.Figure (candlestick + OFI as two subplots)

Overlay logic is driven by column presence, so the same functions work for
both FEATURES DataFrames (rich) and CLEAN DataFrames (OHLCV + sma_200 only).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ------------------------------------------------------------------
# Colour palette
# ------------------------------------------------------------------
_VWAP_SESSION = "rgba(99,102,241,0.8)"    # indigo
_VWAP_WEEKLY = "rgba(249,115,22,0.8)"     # orange
_VWAP_MONTHLY = "rgba(34,197,94,0.8)"     # green
_BB_LINE = "rgba(148,163,184,0.9)"        # slate-400
_BB_FILL = "rgba(148,163,184,0.08)"
_SMA_200 = "rgba(234,179,8,0.9)"          # amber
_OFI_POS = "#22c55e"                      # green-500
_OFI_NEG = "#ef4444"                      # red-500
_CROSSHAIR = "rgba(148,163,184,0.6)"
_ENTRY_ARROW = "#22c55e"
_EXIT_ARROW = "#ef4444"
_STOP_LINE = "#ef4444"
_TARGET_LINE = "#22c55e"

_CANDLE_UP = "#22c55e"
_CANDLE_DOWN = "#ef4444"

# Default number of calendar days to show in the initial viewport per TF.
# The user loaded a wide window; we open zoomed in so candles are visible.
_ZOOM_DAYS: dict[str, int] = {
    "5m":  10,   # ~780 bars
    "15m": 15,   # ~260 bars
    "60m": 45,   # ~720 bars
    "1D":  365,  # show the full year
}


def _default_x_range(df: pd.DataFrame, tf_label: str) -> list | None:
    """Return [start, end] for the initial xaxis viewport, or None if df is empty."""
    if df.empty:
        return None
    days = _ZOOM_DAYS.get(tf_label, 30)
    end = df.index[-1]
    start = end - pd.Timedelta(days=days)
    return [start.isoformat(), end.isoformat()]


def _ofi_column(df: pd.DataFrame) -> str | None:
    """Return the name of the first OFI column found, or None."""
    for col in df.columns:
        if col.startswith("ofi"):
            return col
    return None


def build_candlestick(
    df: pd.DataFrame,
    tf_label: str,
    height: int = 400,
) -> go.Figure:
    """Build a candlestick figure with VWAP / BB / SMA overlays.

    Overlays are added only when the relevant columns are present:
    - vwap_session, vwap_weekly, vwap_monthly  → VWAP lines (5m / 15m)
    - bb_upper, bb_lower, bb_mid               → Bollinger Bands (5m / 15m)
    - sma_200                                  → SMA(200) (all timeframes)
    """
    x = df.index

    fig = go.Figure()

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=x,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=tf_label,
            increasing_line_color=_CANDLE_UP,
            decreasing_line_color=_CANDLE_DOWN,
            increasing_fillcolor=_CANDLE_UP,
            decreasing_fillcolor=_CANDLE_DOWN,
            showlegend=False,
        )
    )

    # Bollinger Bands (fill first so candlesticks render on top)
    if "bb_upper" in df.columns and "bb_lower" in df.columns:
        # Upper band
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df["bb_upper"],
                mode="lines",
                line=dict(color=_BB_LINE, width=1, dash="dash"),
                name="BB Upper",
                showlegend=False,
            )
        )
        # Lower band with fill back to upper
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df["bb_lower"],
                mode="lines",
                line=dict(color=_BB_LINE, width=1, dash="dash"),
                fill="tonexty",
                fillcolor=_BB_FILL,
                name="BB Lower",
                showlegend=False,
            )
        )

    # VWAP overlays
    if "vwap_session" in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=df["vwap_session"],
                mode="lines",
                line=dict(color=_VWAP_SESSION, width=1.5),
                name="VWAP Session",
                showlegend=True,
            )
        )
    if "vwap_weekly" in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=df["vwap_weekly"],
                mode="lines",
                line=dict(color=_VWAP_WEEKLY, width=1.5),
                name="VWAP Weekly",
                showlegend=True,
            )
        )
    if "vwap_monthly" in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=df["vwap_monthly"],
                mode="lines",
                line=dict(color=_VWAP_MONTHLY, width=1.5),
                name="VWAP Monthly",
                showlegend=True,
            )
        )

    # SMA(200)
    if "sma_200" in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=df["sma_200"],
                mode="lines",
                line=dict(color=_SMA_200, width=1.5),
                name="SMA 200",
                showlegend=True,
            )
        )

    x_range = _default_x_range(df, tf_label)

    fig.update_layout(
        height=height,
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(50,50,50,0.3)",
            type="date",
            range=x_range,
        ),
        yaxis=dict(showgrid=True, gridcolor="rgba(50,50,50,0.3)", autorange=True),
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#94a3b8", size=11),
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=60, r=20, t=30, b=30),
        uirevision=tf_label,
    )

    return fig


def build_ofi_bar(df: pd.DataFrame) -> go.Figure:
    """Build an OFI bar chart, coloured green / red by sign.

    Uses the first column whose name starts with 'ofi'.
    Returns an empty figure if no OFI column is found.
    """
    ofi_col = _ofi_column(df)
    fig = go.Figure()

    if ofi_col is not None:
        ofi = df[ofi_col]
        colors = [_OFI_POS if v >= 0 else _OFI_NEG for v in ofi]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=ofi,
                marker_color=colors,
                name="OFI",
                showlegend=False,
            )
        )

    fig.update_layout(
        height=120,
        xaxis_rangeslider_visible=False,
        xaxis=dict(showgrid=True, gridcolor="rgba(50,50,50,0.3)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(50,50,50,0.3)"),
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#94a3b8", size=11),
        margin=dict(l=60, r=20, t=10, b=30),
        uirevision="ofi",
    )

    return fig


def build_5m_figure(df: pd.DataFrame) -> go.Figure:
    """Build the combined 5m pane: candlestick (75%) + OFI bar (25%).

    Returns a single go.Figure with two vertically-stacked subplots sharing
    the x-axis.  This is used in the layout's left-upper cell.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.02,
    )

    x = df.index

    # --- Row 1: candlestick ---
    fig.add_trace(
        go.Candlestick(
            x=x,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="5m",
            increasing_line_color=_CANDLE_UP,
            decreasing_line_color=_CANDLE_DOWN,
            increasing_fillcolor=_CANDLE_UP,
            decreasing_fillcolor=_CANDLE_DOWN,
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Bollinger Bands on row 1
    if "bb_upper" in df.columns and "bb_lower" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df["bb_upper"],
                mode="lines",
                line=dict(color=_BB_LINE, width=1, dash="dash"),
                showlegend=False,
                name="BB Upper",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df["bb_lower"],
                mode="lines",
                line=dict(color=_BB_LINE, width=1, dash="dash"),
                fill="tonexty",
                fillcolor=_BB_FILL,
                showlegend=False,
                name="BB Lower",
            ),
            row=1,
            col=1,
        )

    # VWAP lines on row 1
    for col, color, label in [
        ("vwap_session", _VWAP_SESSION, "VWAP Session"),
        ("vwap_weekly", _VWAP_WEEKLY, "VWAP Weekly"),
        ("vwap_monthly", _VWAP_MONTHLY, "VWAP Monthly"),
    ]:
        if col in df.columns:
            fig.add_trace(
                go.Scattergl(
                    x=x,
                    y=df[col],
                    mode="lines",
                    line=dict(color=color, width=1.5),
                    name=label,
                    showlegend=True,
                ),
                row=1,
                col=1,
            )

    if "sma_200" in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=df["sma_200"],
                mode="lines",
                line=dict(color=_SMA_200, width=1.5),
                name="SMA 200",
                showlegend=True,
            ),
            row=1,
            col=1,
        )

    # --- Row 2: OFI bars ---
    ofi_col = _ofi_column(df)
    if ofi_col is not None:
        ofi = df[ofi_col]
        colors = [_OFI_POS if v >= 0 else _OFI_NEG for v in ofi]
        fig.add_trace(
            go.Bar(
                x=x,
                y=ofi,
                marker_color=colors,
                name="OFI",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    x_range = _default_x_range(df, "5m")

    fig.update_layout(
        height=520,
        xaxis_rangeslider_visible=False,
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#94a3b8", size=11),
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=60, r=20, t=30, b=30),
        uirevision="5m",
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(50,50,50,0.3)",
        type="date",
        range=x_range,
    )
    fig.update_yaxes(showgrid=True, gridcolor="rgba(50,50,50,0.3)", autorange=True)

    return fig


def project_trades_to_tf(
    trades_df: pd.DataFrame,
    tf_df: pd.DataFrame,
) -> pd.DataFrame:
    """Snap trade entry/exit timestamps to the nearest bar open in *tf_df*.

    For higher timeframes (60m, Daily), a trade that entered at 09:35 should
    have its marker land on the 09:00 bar, not float between bars.  This
    function replaces entry_ts / exit_ts with the index timestamp of the
    nearest containing bar.

    The original prices are preserved — only the x-axis timestamps are snapped.

    Parameters
    ----------
    trades_df:
        Trade log with entry_ts and exit_ts columns (tz-aware UTC).
    tf_df:
        DataFrame with a tz-aware UTC DatetimeIndex (bar open times).

    Returns
    -------
    A copy of trades_df with entry_ts and exit_ts snapped to tf_df bar times.
    Empty if trades_df is empty.
    """
    if trades_df is None or trades_df.empty or tf_df.empty:
        return trades_df.copy() if trades_df is not None else pd.DataFrame()

    bar_times = tf_df.index.sort_values()
    result = trades_df.copy()

    def _snap(ts: object) -> object:
        """Find the last bar open ≤ ts."""
        if pd.isna(ts):
            return ts
        ts = pd.Timestamp(ts)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        idx = bar_times.searchsorted(ts, side="right") - 1
        if idx < 0:
            return bar_times[0]
        return bar_times[idx]

    result["entry_ts"] = result["entry_ts"].apply(_snap)
    result["exit_ts"]  = result["exit_ts"].apply(_snap)
    return result


def build_trade_markers(
    fig: go.Figure,
    trades_df: pd.DataFrame,
    tf: str,
) -> None:
    """Add entry/exit arrows and stop/target lines to an existing figure.

    Expected trades_df columns:
        entry_ts   : datetime-like, timestamp of entry
        exit_ts    : datetime-like, timestamp of exit
        entry_price: float
        exit_price : float
        stop_price : float
        target_price: float
        direction  : "long" or "short"

    Missing columns are silently skipped.  This function is a no-op when
    trades_df is empty.

    Bug fix: subplot figures (make_subplots) require explicit xaxis/yaxis
    on every trace.  Traces with xaxis=None / yaxis=None are invisible even
    though Plotly places them in the figure data — the renderer skips them.
    We force xaxis='x', yaxis='y' so markers land on the first subplot
    (the candlestick row) regardless of whether the figure has subplots.
    """
    if trades_df is None or trades_df.empty:
        return

    # Entry arrows
    if {"entry_ts", "entry_price"}.issubset(trades_df.columns):
        fig.add_trace(
            go.Scatter(
                x=trades_df["entry_ts"],
                y=trades_df["entry_price"],
                mode="markers",
                marker=dict(
                    symbol="triangle-up",
                    size=12,
                    color=_ENTRY_ARROW,
                    line=dict(width=1, color="white"),
                ),
                name="Entry",
                showlegend=True,
                xaxis="x",
                yaxis="y",
            )
        )

    # Exit arrows
    if {"exit_ts", "exit_price"}.issubset(trades_df.columns):
        fig.add_trace(
            go.Scatter(
                x=trades_df["exit_ts"],
                y=trades_df["exit_price"],
                mode="markers",
                marker=dict(
                    symbol="triangle-down",
                    size=12,
                    color=_EXIT_ARROW,
                    line=dict(width=1, color="white"),
                ),
                name="Exit",
                showlegend=True,
                xaxis="x",
                yaxis="y",
            )
        )

    # Stop and target horizontal lines — one segment per trade
    for _, row in trades_df.iterrows():
        if "stop_price" in trades_df.columns and pd.notna(row.get("stop_price")):
            x0 = row.get("entry_ts")
            x1 = row.get("exit_ts", x0)
            fig.add_shape(
                type="line",
                x0=x0,
                x1=x1,
                y0=row["stop_price"],
                y1=row["stop_price"],
                line=dict(color=_STOP_LINE, width=1, dash="dash"),
            )
        if "target_price" in trades_df.columns and pd.notna(row.get("target_price")):
            x0 = row.get("entry_ts")
            x1 = row.get("exit_ts", x0)
            fig.add_shape(
                type="line",
                x0=x0,
                x1=x1,
                y0=row["target_price"],
                y1=row["target_price"],
                line=dict(color=_TARGET_LINE, width=1, dash="dash"),
            )
