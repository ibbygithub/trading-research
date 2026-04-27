---
name: charting
description: Use when visualizing bar data, indicators, trades, equity curves, drawdowns, or any market data in chart form. This skill defines which Python charting library to use for which purpose, the canonical multi-pane layout for price/volume/order-flow/oscillators, indicator overlay conventions, and the patterns used by both static archival outputs and the interactive trade-replay app. Invoke when creating any visualization of market data, when adding a new indicator that needs a chart pane, when designing chart-based debugging tools, or when deciding how to display backtest results visually.
---

# Charting

This skill owns visual representation of market data in the project. Its job is to make sure that whenever the human or the agent looks at a chart, they're looking at something that's honest, consistent, and tells them what they need to know. Bad charts mislead. Good charts reveal. The difference is mostly convention and discipline, not artistry.

The principle: **the chart should show what was knowable at the moment depicted, not what's knowable in retrospect.** This is the visual equivalent of the look-ahead bias rule from `data-scientist.md`. A chart that draws a moving average across a historical window using data from after each point is the same lie as a backtest that uses future data — and it's the lie that tricks traders into believing strategies work when they don't. The replay app and the static charts both enforce as-of correctness.

## What this skill covers

- Library selection: when to use mplfinance, when Plotly, when Plotly+Dash
- Canonical multi-pane layout (price + volume + order flow + oscillators)
- Candlestick conventions and color scheme
- Indicator overlay patterns
- Trade marker conventions for backtest visualization
- Equity curve and drawdown chart patterns
- Saving charts as artifacts of a backtest run
- The chart-as-debugger workflow

## What this skill does NOT cover

- The interactive replay app's specific features (see `trade-replay`)
- The math of indicators being charted (see `indicators`)
- The trade log schema being visualized (see `data-management`)
- Statistical reports and metrics (see `strategy-evaluation`)

## Library selection

There are three Python charting libraries this project uses, each for a different purpose. Picking the wrong one is the most common charting mistake.

**mplfinance** — for static, archival, reproducible chart images.

Use mplfinance when:
- The chart will be saved to disk as a PNG and referenced later
- The chart is part of a backtest run's output artifacts
- The chart needs to look identical every time it's regenerated
- Print or document embedding is the destination
- The audience is "future you reviewing what happened"

Don't use mplfinance for:
- Interactive exploration (it's static)
- Anything you'll want to zoom, pan, or hover over
- Real-time or streaming data display

Strengths: precise control, reliable rendering, small file sizes, no JavaScript dependency. Weaknesses: slow for large datasets, no interactivity.

**Plotly** — for interactive in-notebook or in-script exploration.

Use Plotly when:
- You're exploring data in a notebook and want to zoom, pan, hover
- The chart will be embedded in a single HTML file you can open in a browser
- The audience is "you, right now, trying to figure something out"
- Multiple panes with linked x-axes are needed

Don't use Plotly for:
- Archival charts (HTML files are large and version awkwardly)
- The replay app (use Dash for that)
- Anything that needs to look identical across regenerations (Plotly's defaults change between versions)

Strengths: interactive, hovers show exact values, multi-pane charts with linked zoom. Weaknesses: large output files, slower than mplfinance for static use.

**Plotly + Dash** — for the trade-replay app and any other persistent local web UI.

Use Plotly+Dash when:
- You need a UI with controls (buttons, sliders, dropdowns) alongside the chart
- The chart needs to update in response to user input
- The audience will want to scroll through trades, instruments, or time periods
- The application runs locally as a long-lived process

Don't use Plotly+Dash for:
- One-shot chart generation (overkill)
- Anything that needs to be embedded as a static image

Strengths: full app capabilities, real interactivity, the foundation of the trade-replay forensics workflow. Weaknesses: more setup, requires running a local server.

**The decision flowchart:**

1. Will this chart be saved as a PNG and referenced from a report or document? → **mplfinance**
2. Is this an interactive exploration in a notebook? → **Plotly**
3. Does the user need controls (buttons, sliders, scrolling) alongside the chart? → **Plotly + Dash**
4. None of the above? → Default to **mplfinance**, you probably want a static chart.

## The canonical multi-pane layout

Every chart that shows market data in this project uses the same vertical layout. Consistency matters because the eye learns to read a layout it sees repeatedly, and switching layouts forces re-orientation every time.

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│                                                      │
│              PRICE PANE (candlesticks)               │
│           with overlay indicators (EMA, BB, VWAP)    │
│                                                      │
│                                                      │
├──────────────────────────────────────────────────────┤
│              VOLUME PANE (bars)                      │
├──────────────────────────────────────────────────────┤
│              DELTA PANE (cumulative or per-bar)      │
│              (optional, only when order flow exists) │
├──────────────────────────────────────────────────────┤
│              OSCILLATOR PANE (RSI, MACD hist, etc.)  │
│              (optional, strategy-dependent)          │
└──────────────────────────────────────────────────────┘
```

**Pane height ratios:** price gets the most real estate (60-65% of total height), volume gets 10-15%, delta gets 10-15% when present, oscillator gets 15-20% when present.

**X-axis is shared and linked across all panes.** Zoom in the price pane, the volume/delta/oscillator panes zoom too. This is non-negotiable because it's how the eye correlates events across panes.

**Time axis:** display in America/New_York. Every chart in this project shows NY local time, regardless of where the human is sitting. Internal storage is UTC, display is NY. The time format on the x-axis is `MM-DD HH:MM` for intraday charts and `YYYY-MM-DD` for daily-or-longer charts.

**Session boundaries are visible.** Daily breaks in CME futures (the 5pm-6pm NY pause) appear as small gaps on the x-axis, not as continuous time. Weekend gaps and holiday gaps also appear as gaps. This is honest — it shows the real time structure of the market — and it prevents the eye from merging Sunday evening's first bars with Friday afternoon's last bars.

**Color scheme (light theme by default):**

- Bullish candle body: white fill, black border
- Bearish candle body: black fill, black border
- Wicks: black, 1px
- Volume bars (bullish): light gray
- Volume bars (bearish): dark gray
- Cumulative delta line: blue
- Indicator overlays: color-coded by family (trend = orange, mean reversion = purple, volatility bands = light blue)
- Trade markers: green up-triangle for long entries, red down-triangle for short entries, large green/red X for exits
- Stop-loss line: red dashed
- Take-profit line: green dashed

**Color scheme (dark theme):** invert the candle fills (green/red instead of black/white), keep everything else readable on dark background. The user's preference is configurable; the default is light theme because static archival charts are typically viewed on light backgrounds.

**Why monochrome candles by default and not green/red?** Because green/red candles trigger pre-cognitive emotional reactions that bias visual analysis. Black/white forces the eye to actually look at the structure of the bar rather than its color. This is a small thing but it matters when you're trying to do honest forensic analysis. Override with green/red if the human prefers, but the default is monochrome.

## Indicator overlay conventions

Indicators that share the price scale (moving averages, Bollinger Bands, VWAP, support/resistance levels) are drawn in the price pane as line overlays.

Indicators that have a different scale (RSI, MACD, stochastic, ATR in absolute terms) get their own pane below the price pane.

**Overlay drawing rules:**

- Moving averages: solid line, 1.5px, color by speed (faster = lighter shade of orange/yellow, slower = darker shade)
- Bollinger Bands: thin lines (1px) for upper and lower, light fill between them at 10% opacity
- VWAP: solid line, 2px, distinct color (typically purple)
- Support/resistance: dashed horizontal lines, 1px, gray
- Trendlines: solid lines, 1.5px, dark gray

**Pane indicator rules:**

- RSI: line plot 0-100, with horizontal reference lines at 30 and 70 (or whatever the strategy uses)
- MACD: histogram bars for the histogram component, two lines for MACD and signal
- Stochastic: %K and %D as lines, reference lines at 20 and 80
- ATR: line plot, no reference lines (ATR is contextual, not threshold-based)

**The "as-of" rule for indicator drawing.** This is critical and it's the technical implementation of the look-ahead bias prevention.

When drawing an indicator on a historical chart, the value at bar N must be computed using only bars 1 through N (or 1 through N-1, depending on the strategy's fill model). The default is *bar N inclusive*, meaning the indicator at bar N reflects what would have been computable at bar N's close.

This sounds obvious. The trap is that vectorized indicator calculations (which is how every modern library computes them) are *forward-only* in their math, but they're computed *all at once* over the whole series. If you compute an EMA over the full series and then chart it, every point on the line is correct as-of its own bar. But if you compute a centered moving average, or a rolling z-score with a centered window, or any indicator that uses future data in its math, the chart is lying.

The chart layer doesn't enforce this — the indicator layer does. But the chart layer must use the indicator values as-stored, never recomputing them in a way that could introduce centering or smoothing across the visible window.

**Trade marker conventions:**

When charts visualize backtest results (which is most of them), trades are marked with the following conventions:

- **Trigger bar marker:** small hollow circle at the trigger bar's close price, color = side (green long, red short)
- **Entry bar marker:** filled triangle at the entry fill price, color = side, size larger than trigger circle
- **Exit bar marker:** large X at the exit fill price, color = exit reason (green = TP, red = SL, gray = timeout, purple = signal exit)
- **Connecting line:** dashed line from entry marker to exit marker, color = P&L (green if profitable, red if not)
- **Stop-loss line:** horizontal dashed red line at the stop price, drawn from entry bar to exit bar
- **Take-profit line:** horizontal dashed green line at the TP price, drawn from entry bar to exit bar

**The four-marker rule** (trigger, entry, exit-trigger, exit) is the visual implementation of the trade log schema's distinction between trigger bars and fill bars. The replay app must show all four. Static chart outputs may simplify to entry+exit if the trigger and entry bars are adjacent (which is the common case for next-bar-open fills), but when they're separated (rare cases, e.g. limit orders that take time to fill), all four markers are shown.

## Equity curve and drawdown charts

These are different from price charts and have their own conventions.

**Equity curve:**

- X-axis: time (trade entry time, not trade index — this matters because trades are not evenly spaced)
- Y-axis: cumulative net P&L in USD
- Single line, blue, 1.5px
- Horizontal zero line in light gray
- Filled area between the curve and its running maximum, in light red (this visualizes drawdown directly)

**Drawdown chart (separate, paired with equity curve):**

- X-axis: time, same scale as the equity curve above
- Y-axis: drawdown in USD (always negative or zero)
- Filled area chart, red, opacity 0.6
- Running max drawdown marked with a horizontal dashed line
- Drawdown duration regions marked with vertical bands

These two charts are typically displayed stacked, equity on top, drawdown below, sharing the x-axis.

**Why drawdown gets its own chart instead of just being implied by the equity curve:** because the eye consistently underestimates drawdown depth and duration when looking at an equity curve alone. A 15% drawdown looks like a small dip on a curve that goes from 100 to 200. Plotted on its own axis, the same drawdown looks like the disaster it actually is. This visual separation is part of the framework's pessimistic-default philosophy: make the painful numbers visible.

## Saving charts as run artifacts

Every backtest run produces chart artifacts as part of its output, written to `runs/<run_id>/charts/`:

```
runs/<run_id>/charts/
├── equity_curve.png
├── drawdown.png
├── trade_distribution.png      # histogram of trade P&Ls
├── monthly_returns.png         # heatmap of monthly returns
├── trade_examples/
│   ├── best_trade.png          # chart of the best trade with full context
│   ├── worst_trade.png
│   ├── median_trade.png
│   └── most_recent_trades.png  # the last 10 trades stacked
└── full_period.png             # the entire backtest period as one wide chart
```

These are generated automatically at the end of every backtest run by the `eval` module, using mplfinance for everything because they're static archival artifacts. The `report.html` for the run embeds these as `<img>` tags so the full report is self-contained.

**Naming convention:** descriptive, lowercase, underscored. No timestamps in filenames (the run_id directory provides that context).

**Format:** PNG at 1200x800 default resolution, 150 DPI. SVG is also acceptable for charts that will be embedded in documents and need to scale.

## The chart-as-debugger workflow

A common debugging pattern: a backtest produces a result that looks weird, and you want to understand why a specific trade fired (or didn't fire) at a specific bar. The chart-as-debugger workflow is:

1. Open the relevant trade in the replay app (or generate a static chart of the bar's context)
2. Display the price pane with all indicators the strategy uses
3. Display the strategy's signal as a separate annotation (e.g. "RSI < 30 = TRUE", "MACD divergence = TRUE")
4. Display the trade decision logic in plain text alongside the chart
5. Compare what the strategy thought it saw against what was actually true at that bar

This is the workflow that catches the bugs your old code had: indicator values computed slightly wrong, fills priced at the trigger bar instead of the entry bar, signals that fired one bar early or late. The chart is the debugger, not the print statement.

The replay app implements this workflow as its primary mode. Static charts can implement it for one-off debugging by adding annotations to a standard multi-pane chart.

## Implementation patterns

**mplfinance multi-pane skeleton:**

```python
# src/trading_research/eval/charts.py
import mplfinance as mpf
import polars as pl
import pandas as pd
from pathlib import Path
from trading_research.data.schema import BAR_SCHEMA

def render_static_chart(
    bars: pl.DataFrame,
    indicators: dict[str, pl.Series],
    trades: pl.DataFrame | None = None,
    output_path: Path | None = None,
    title: str = "",
    pane_config: PaneConfig | None = None,
) -> Path:
    """Render a multi-pane chart to PNG using mplfinance.

    bars: polars DataFrame conforming to BAR_SCHEMA
    indicators: dict of name -> series, will be placed in the appropriate pane
        based on indicator family (overlay vs separate pane)
    trades: optional trade log subset to mark on the chart
    output_path: where to write the PNG. Required for archival; can be None
        for in-memory rendering (returns the figure).

    Returns the path written, or the figure object if output_path is None.
    """
    # Convert to pandas for mplfinance compatibility
    df = bars.to_pandas().set_index("timestamp_ny")
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})

    # Build addplots for indicators
    addplots = []
    for name, series in indicators.items():
        family = _classify_indicator(name)
        if family == "overlay":
            addplots.append(mpf.make_addplot(series, panel=0, color=_color_for(name)))
        elif family == "oscillator":
            addplots.append(mpf.make_addplot(series, panel=2, color=_color_for(name)))
        # ... etc

    # Build trade markers if trades provided
    if trades is not None:
        marker_addplots = _build_trade_markers(trades, df.index)
        addplots.extend(marker_addplots)

    # Render
    style = mpf.make_mpf_style(base_mpf_style="classic", rc={"font.size": 9})
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=addplots,
        volume=True,
        panel_ratios=(6, 1.5, 2),  # price, volume, oscillator
        figsize=(12, 8),
        title=title,
        returnfig=True,
    )

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        return output_path
    return fig
```

**Plotly interactive skeleton:**

```python
def render_interactive_chart(
    bars: pl.DataFrame,
    indicators: dict[str, pl.Series],
    trades: pl.DataFrame | None = None,
    title: str = "",
) -> "plotly.graph_objects.Figure":
    """Render a multi-pane interactive Plotly chart with linked x-axes."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.65, 0.15, 0.20],
        subplot_titles=("Price", "Volume", "Oscillator"),
    )

    df = bars.to_pandas()

    # Candlesticks
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp_ny"],
            open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="Price",
            increasing_line_color="black",
            decreasing_line_color="black",
            increasing_fillcolor="white",
            decreasing_fillcolor="black",
        ),
        row=1, col=1,
    )

    # Indicators (overlays in row 1, oscillators in row 3)
    for name, series in indicators.items():
        family = _classify_indicator(name)
        row = 1 if family == "overlay" else 3
        fig.add_trace(
            go.Scatter(x=df["timestamp_ny"], y=series, name=name,
                       line=dict(color=_color_for(name), width=1.5)),
            row=row, col=1,
        )

    # ... volume bars, trade markers, layout config
    return fig
```

The skeletons are intentionally incomplete — the build agent fills in the details following the conventions in this skill. The skeletons exist to lock in the *shape* of the API and the multi-pane layout, not to be copy-pasted as final code.

## Standing rules this skill enforces

1. **Time display is always America/New_York.** Internal storage is UTC; display is NY. No exceptions.
2. **Session gaps are visible.** Daily breaks, weekends, holidays appear as gaps in the time axis, not as continuous time.
3. **Indicators are drawn as-of, never centered or smoothed across the visible window.** If an indicator value at bar N uses data from bar N+1, it's a bug in the indicator code, and the chart layer must not paper over it.
4. **The four-marker rule.** Backtest visualizations show trigger bar, entry bar, exit-trigger bar, exit bar markers when they differ. The replay app always shows all four; static charts may simplify only when bars are adjacent.
5. **mplfinance for static, Plotly for interactive notebooks, Dash for the replay app.** Don't mix.
6. **Multi-pane layout is consistent across all charts.** Price on top, volume next, then optional delta, then optional oscillator.
7. **Color scheme is consistent across all charts.** Indicator family determines color. Trade markers follow the green-long / red-short / X-for-exit convention.
8. **Charts are saved as artifacts of every backtest run.** Not optional. The eval module produces them automatically.

## When to invoke this skill

Load this skill when the task involves:

- Generating any chart of market data, indicators, trades, or backtest results
- Choosing a charting library for a new use case
- Adding a new indicator pane or overlay to an existing chart pattern
- Designing a chart-based debugging workflow
- Modifying the canonical multi-pane layout
- Configuring colors, styling, or output formats for charts

Don't load this skill for:

- The replay app's specific feature work (use `trade-replay`)
- Computing the indicator values being charted (use `indicators`)
- Statistical reports without visual components (use `strategy-evaluation`)

## Open questions for build time

1. **Default theme: light or dark?** Lean light for static archival (matches print and document embedding), but the replay app should respect the OS theme. Confirm at build time.
2. **Resolution defaults for archival PNGs.** 1200x800 at 150 DPI is the proposed default. May need adjustment based on where the charts get viewed.
3. **Whether to use `mplfinance`'s built-in styles or define a custom one.** Lean custom for consistency control, but the built-in `classic` style is close enough that it may not be worth the maintenance.
4. **Chart caching.** Should generated chart PNGs be cached based on input hash to avoid re-rendering identical charts? Probably overkill for now; defer until charting becomes a bottleneck.
