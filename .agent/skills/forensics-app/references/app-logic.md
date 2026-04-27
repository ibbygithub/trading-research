# Visual Forensics & Replay Protocol

This document defines the technical execution for the `forensics-app`, migrated from the legacy `trade-replay` and `charting` standards.

## Implementation Standards

### 1. Dash App Architecture
The app must be built using **Dash** and **Plotly** for high-interactivity charting.

```python
# Logic from src/trading_research/replay/app.py
import dash
from dash import dcc, html
import plotly.graph_objects as go

def build_trade_chart(bars_df, trade_log):
    # Architect: Ensure indicators are plotted from the FEATURES matrix
    # Mentor: Highlight the Trigger Bar vs Entry Bar
    fig = go.Figure(data=[go.Candlestick(
        x=bars_df['timestamp'],
        open=bars_df['Open'], high=bars_df['High'],
        low=bars_df['Low'], close=bars_df['Close']
    )])
    return fig
```

### 2. Forensic Log Consumption
The app must parse the JSON-line output from the `backtest-engine` skill.

Mandatory fields for visualization:
- `trigger_timestamp`: The bar where the signal fired.
- `entry_timestamp`: The bar where the fill occurred.
- `exit_reason`: `"Upper Barrier"`, `"Lower Barrier"`, or `"Timeout"`.

## Visual Guardrails
- **Indicator Synchronization**: Indicators displayed must match the exact version of the FEATURES parquet used in the backtest.
- **Equity Curve Drill-Down**: Clicking a point on the equity curve must navigate the chart to the specific trade responsible for that P&L change.
- **Pessimism Check**: Visually verify that if a bar hit both SL and TP, the app displays the SL being hit first by default.

## Running the App
Always invoke via `uv run` to ensure all Dash/Plotly dependencies are correctly mapped.
