"""Dash app factory for the replay cockpit.

Usage:
    from trading_research.replay.app import build_app

    app = build_app("ZN", from_dt, to_dt)
    app.run(debug=False, port=8050)

The CLI (`uv run trading-research replay`) is the normal entry point.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import dash

from trading_research.replay.callbacks import register_callbacks
from trading_research.replay.charts import build_5m_figure, build_candlestick, build_trade_markers, project_trades_to_tf
from trading_research.replay.data import DataNotFoundError, load_trades, load_window
from trading_research.replay.layout import build_layout


def build_app(
    symbol: str,
    from_dt: datetime,
    to_dt: datetime,
    trades_path: Path | None = None,
    data_root: Path | None = None,
) -> dash.Dash:
    """Build and return the configured Dash app.

    Parameters
    ----------
    symbol:      Instrument symbol (e.g. "ZN").
    from_dt:     Window start (tz-naive interpreted as UTC).
    to_dt:       Window end.
    trades_path: Optional JSON trade log.  Placeholder — trade markers are
                 added when the backtest engine (session 08) is ready.
    data_root:   Override for the data/ root directory (used in tests).

    Returns
    -------
    A configured `dash.Dash` instance.  Call `.run()` to start the server.
    """
    # Load data for the initial window.
    data = load_window(symbol, from_dt, to_dt, data_root=data_root)

    # Build initial figures.
    figs = {
        "5m": build_5m_figure(data["5m"]),
        "15m": build_candlestick(data["15m"], tf_label="15m", height=520),
        "60m": build_candlestick(data["60m"], tf_label="60m", height=400),
        "1D": build_candlestick(data["1D"], tf_label="1D", height=400),
    }

    # Add trade markers to the initial render when a trades file is provided.
    # Markers are added to all four charts; higher-TF charts get timestamp-snapped markers.
    if trades_path is not None:
        try:
            import pandas as pd
            trades_df = load_trades(trades_path)
            from_ts = pd.Timestamp(from_dt, tz="UTC") if from_dt.tzinfo is None else pd.Timestamp(from_dt)
            to_ts = pd.Timestamp(to_dt, tz="UTC") if to_dt.tzinfo is None else pd.Timestamp(to_dt)
            mask = (trades_df["entry_ts"] >= from_ts) & (trades_df["exit_ts"] <= to_ts)
            window_trades = trades_df[mask]
            # 5m and 15m: exact timestamps (bars align with entry/exit)
            for tf in ("5m", "15m"):
                build_trade_markers(figs[tf], window_trades, tf)
            # 60m and 1D: snap timestamps to the nearest containing bar open
            for tf, tf_key in (("60m", "60m"), ("1D", "1D")):
                snapped = project_trades_to_tf(window_trades, data[tf_key])
                build_trade_markers(figs[tf_key], snapped, tf)
        except DataNotFoundError:
            pass  # File not found — show charts without markers.

    app = dash.Dash(
        __name__,
        title=f"{symbol} Cockpit | {from_dt:%Y-%m-%d} – {to_dt:%Y-%m-%d}",
        # Suppress callback exceptions so Patch() callbacks on initial load
        # don't raise errors before the figures have rendered.
        suppress_callback_exceptions=True,
    )

    app.layout = build_layout(symbol, from_dt, to_dt, figs)

    register_callbacks(app, symbol=symbol, data_root=data_root, trades_path=trades_path)

    return app
