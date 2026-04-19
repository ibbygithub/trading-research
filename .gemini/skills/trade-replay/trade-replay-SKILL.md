---
name: trade-replay
description: Use when building, modifying, or debugging the interactive trade replay Dash application — the local web app that loads a backtest's trade log and lets the human scroll through trades sequentially with full chart context, indicator overlays, and as-of indicator snapshots from the trigger bar. Invoke when adding new features to the replay app, when designing the UX for trade forensics, when integrating new indicators into the replay views, or when debugging issues with how trades are visualized in the replay context. This skill defines the app's architecture, the interaction model, and the patterns that make trade forensics actually useful.
---

# Trade Replay

This skill owns the interactive trade replay Dash application. Its job is to close the gap that TradingView leaves open: the ability to look at any historical trade and see exactly what the chart and indicators looked like at the moment the decision was made — not the cleaned-up retrospective view that hindsight produces, but the actual as-of state the strategy saw.

The principle: **the replay app exists to defeat hindsight bias.** Every other tool in the trading workflow encourages looking at history with the benefit of knowing what came next. The replay app does the opposite: it shows you the chart as it would have looked at the moment of decision, with indicators computed only from data through that bar, and lets you ask the honest question: *given only what was knowable then, did this trade make sense?*

The second principle: **the human is doing forensic analysis, not entertainment.** This is not a chart-viewing app. It's a debugging tool for strategies and a learning tool for the human's own pattern recognition. The UX should optimize for: load fast, navigate fast, show everything relevant, hide everything else, and make it easy to capture findings.

## What this skill covers

- The Dash application architecture and entrypoint
- Loading and parsing trade logs
- The trade list and navigation UX
- The chart view (using `charting` skill conventions)
- As-of indicator rendering from trigger snapshots
- Trade context windows (N bars before, M bars after)
- Re-entry grouping (showing related trades together)
- The "freeze and export PNG" feature
- Keyboard shortcuts
- Local server lifecycle and the launch pattern

## What this skill does NOT cover

- The chart rendering primitives themselves (see `charting`)
- The trade log schema (see `data-management`)
- The backtest engine that produces trade logs (see `backtesting`)
- Live data streaming (see `streaming-bars`)

## Architecture

The app is a Dash application that runs locally on `http://127.0.0.1:8050`. It is launched by the human via a slash command (`/replay <run_id>`) or directly (`uv run trading-research replay --run-id <run_id>`). It is not exposed to any network beyond localhost, has no authentication, and stores no state on disk other than user-initiated PNG exports.

```
src/trading_research/replay/
├── __init__.py
├── app.py              # Dash app entrypoint and layout
├── components.py       # reusable Dash components
├── callbacks.py        # interaction callbacks
├── data_loader.py      # trade log + bar data loading
├── chart_builder.py    # builds Plotly figures using charting conventions
└── exports.py          # PNG export and trade-finding capture
```

**The launch flow:**

1. Human runs `/replay <run_id>` or the equivalent CLI command.
2. The app reads `runs/<run_id>/trades.parquet` and `runs/<run_id>/data_source.json`.
3. The app reads the bar data referenced in `data_source.json` from `data/clean/`.
4. The app starts the Dash server and prints the URL to the console.
5. The app optionally opens the browser automatically (configurable).
6. The human navigates to `http://127.0.0.1:8050` and the app is ready.

When the human is done, they `Ctrl+C` in the terminal where the app was launched. The app shuts down cleanly. No background process, no daemon, no system service. This is a tool you launch when you need it and close when you're done.

## The layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  trade-research replay  ·  run: 2025-01-15_zn_macd_rev_v1   ·  47 trades │
├─────────┬───────────────────────────────────────────────────────────────┤
│         │                                                               │
│  Trade  │                                                               │
│  List   │              Price pane (candlesticks + overlays)             │
│         │              with trade markers                               │
│  #1 ✓   │                                                               │
│  #2 ✗   │                                                               │
│  #3 ✓   ├───────────────────────────────────────────────────────────────┤
│  #4 ✓   │              Volume pane                                      │
│  #5 ✗   ├───────────────────────────────────────────────────────────────┤
│  #6 ✓   │              Delta pane (if order flow available)             │
│  ...    ├───────────────────────────────────────────────────────────────┤
│         │              Oscillator pane (strategy-specific)              │
│         │                                                               │
│         ├───────────────────────────────────────────────────────────────┤
│         │  Trade #4:  LONG entry @ 110.234, exit @ 110.484, +25 ticks  │
│         │  Trigger:   2024-08-12 10:32 NY  ·  RSI=28.4  MACD_hist=-0.012 │
│         │  Entry:     2024-08-12 10:33 NY  ·  fill at next_bar_open      │
│         │  Exit:      2024-08-12 10:51 NY  ·  reason: tp                 │
│         │  Notes:                                                        │
│         │                                                                │
│         │  [Prev]  [Next]  [Freeze PNG]  [Notes]  [Group]                │
└─────────┴───────────────────────────────────────────────────────────────┘
```

**Left rail: trade list.** A scrollable list of all trades in the run, showing trade ID, side, P&L, and a check or X for win/loss. Clicking a trade loads it in the main view. The currently-loaded trade is highlighted. Filters at the top let the human show only winners, only losers, only re-entries, only trades on a specific date range, or trades matching specific criteria.

**Main view: multi-pane chart.** Same canonical layout as the `charting` skill defines: price + volume + delta + oscillator. The chart shows a context window of bars: by default, 50 bars before the trigger bar and 50 bars after the exit bar (configurable). All four trade markers (trigger, entry, exit-trigger, exit) are displayed.

**Bottom: trade detail panel.** Shows the trade's metadata in human-readable form. Trigger bar timestamp and indicator snapshot (the as-of values stored in the trade log), entry bar timestamp and fill model used, exit bar timestamp and exit reason, P&L breakdown, and any notes. A free-form notes field lets the human add their own observations, which get saved alongside the run.

**Bottom controls.** Previous trade, next trade, freeze PNG (capture the current view as a PNG saved to `runs/<run_id>/replay_captures/`), notes (toggle the notes editor), and group (jump to the parent trade or related re-entries).

## The as-of rule in the replay app

This is the most important detail in the entire skill, and the reason the app exists.

When the replay app shows a trade, the indicators displayed in the chart **must be exactly the indicators the strategy saw at the trigger bar**, not freshly recomputed indicators on the visible window.

The way this works:

1. The trade log's `trigger_indicators_json` field contains the indicator values at the trigger bar, computed from bars up to and including the trigger bar. These were recorded at backtest time.
2. The replay app reads these values and uses them as the **anchor**.
3. For bars before the trigger bar, the app computes indicators using only data up to each bar (the as-of computation).
4. For bars after the trigger bar (the "what happened next" portion), the app computes indicators using data up to each bar — which is fine because the human is explicitly looking at what happened *after* the decision.

The crucial subtlety: the indicator values **at the trigger bar** in the chart must match the values **in the trade log**. If they don't, there's a bug — either in the indicator implementation (it's not computing the same thing twice), or in the trade log writer (it captured the wrong snapshot), or in the replay app's indicator computation. Any mismatch is a loud error, not a silent papering-over.

This guarantee is what makes the app trustworthy for forensic analysis. When the human looks at trade #17 and asks "did the strategy actually see RSI at 28.4 when it took this trade?", the answer is "yes, here's the chart, the RSI line at the trigger bar is at 28.4, and that matches the trade log exactly."

```python
# src/trading_research/replay/chart_builder.py
def build_trade_chart(
    trade: dict,                         # one row from the trade log
    bars: pl.DataFrame,                  # the full bar dataset
    strategy_indicators: dict,           # indicator definitions from the strategy
    context_bars_before: int = 50,
    context_bars_after: int = 50,
) -> go.Figure:
    """Build the Plotly figure for a single trade in the replay app.

    The chart shows a window around the trade with all four markers
    (trigger, entry, exit-trigger, exit) and the strategy's indicators
    computed as-of each bar in the window.

    The indicator values at the trigger bar are verified against the
    trade log's trigger_indicators_json. A mismatch raises an error.
    """
    trigger_idx = find_bar_index(bars, trade["trigger_bar_time_utc"])
    exit_idx = find_bar_index(bars, trade["exit_bar_time_utc"])

    window_start = max(0, trigger_idx - context_bars_before)
    window_end = min(len(bars), exit_idx + context_bars_after + 1)
    window_bars = bars[window_start:window_end]

    # Compute indicators as-of each bar in the window
    indicator_values = {}
    for name, indicator_def in strategy_indicators.items():
        # Compute on bars up to each position in the window
        computed = indicator_def.compute_asof(bars, up_to_indices=range(window_start, window_end))
        indicator_values[name] = computed

    # Verify trigger bar indicators match the trade log
    trigger_in_window = trigger_idx - window_start
    trade_log_snapshot = json.loads(trade["trigger_indicators_json"])
    for name, expected_value in trade_log_snapshot.items():
        actual_value = indicator_values[name][trigger_in_window]
        if not values_match(actual_value, expected_value):
            raise IndicatorMismatchError(
                f"Trade {trade['trade_id']}: indicator {name} at trigger bar "
                f"is {actual_value} in chart but {expected_value} in trade log. "
                f"This is a bug in the indicator implementation or the trade log writer."
            )

    # Build the figure using charting skill conventions
    fig = build_multi_pane_figure(
        bars=window_bars,
        indicators=indicator_values,
        trade_markers=build_four_marker_set(trade, window_bars),
        title=f"Trade {trade['trade_id']}: {trade['side']} {trade['symbol']}",
    )
    return fig
```

The `IndicatorMismatchError` is loud and unrecoverable. The replay app refuses to show a trade where the chart and the trade log disagree, because the entire point of the app is that they agree.

## Navigation and the trade list

**Trade list filters:** at the top of the left rail, the human can filter by:

- Win/loss
- Side (long/short)
- Exit reason (tp, sl, tp_sl_ambiguous, timeout, signal, eod_flat, manual)
- Date range
- Symbol (when a run includes multiple symbols)
- Re-entries only
- Parent trades only (i.e. trades that have re-entries attached)
- P&L range

**Sort options:** by trade index (default), by date, by P&L, by holding time, by drawdown depth.

**Keyboard shortcuts:**

- `←` / `→` — previous / next trade
- `↑` / `↓` — scroll up / down in the trade list
- `Enter` — load selected trade
- `f` — freeze and export current view as PNG
- `n` — toggle notes editor
- `g` — jump to parent trade (if current trade is a re-entry) or first re-entry (if current trade is a parent)
- `+` / `-` — zoom in / out on the chart's time axis
- `[` / `]` — narrow / widen the context window (fewer/more bars before and after)

## Re-entry grouping

When a trade is part of a re-entry sequence (parent trade plus one or more re-entries), the replay app handles them as a group:

1. **Visual grouping in the trade list.** Re-entries are indented under their parent trade and share a colored border.
2. **The "g" key** jumps between parent and re-entries within a group.
3. **An optional "show all in group" view** displays the parent and all re-entries on the same chart, with each entry/exit marked distinctly. This is the view that lets the human see "the strategy entered here, the trade went against me, the histogram rotated, the strategy added a re-entry here, and the combined position exited at the combined target here." That's the entire point of supporting planned re-entries — being able to forensically verify that the re-entry behaved as designed.

The "show all in group" view uses different colors for the parent trade markers (lighter) and the re-entry markers (darker) so the eye can easily distinguish them. The combined target and combined risk levels are drawn as horizontal reference lines.

## Context window

The default context window is 50 bars before the trigger bar and 50 bars after the exit bar. Both are configurable in the UI:

- A slider for `bars_before` (10 to 500)
- A slider for `bars_after` (10 to 500)
- A "fit to trade" button that sets both to just enough to show the entry-to-exit span
- A "wide context" button that sets both to 200 for big-picture view

The context window must respect session boundaries. If extending the window backward would cross a session boundary (e.g., into the previous day's session), the app stops at the session boundary by default. An override checkbox lets the human extend across sessions if they specifically want that view.

## The freeze PNG feature

Pressing `f` (or clicking the Freeze PNG button) captures the current chart view as a PNG file:

```
runs/<run_id>/replay_captures/
├── trade_017_freeze_20250115_153422.png
├── trade_023_freeze_20250115_154108.png
└── ...
```

The filename includes the trade ID, the word "freeze", and a timestamp so multiple captures of the same trade get unique filenames.

The captured PNG includes:
- The full multi-pane chart
- All trade markers
- A title block with trade ID, P&L, and date
- The trigger bar's indicator snapshot as a small text overlay in the corner
- The current notes (if any) as a footer

This is the workflow for capturing findings during forensic analysis: scroll through trades, find one that's interesting (a surprising winner, a confusing loser, a clean example of the strategy working as designed), freeze it, optionally add notes, and move on. At the end of the session, the `replay_captures/` directory is a curated set of teaching examples.

## The launch pattern

```bash
# Via CLI
uv run trading-research replay --run-id 2025-01-15_zn_macd_rev_v1

# Via slash command in Claude Code
/replay 2025-01-15_zn_macd_rev_v1
```

The CLI command does the following:

1. Verifies the run directory exists and contains a trade log
2. Verifies the data source is available and validated
3. Starts the Dash app on port 8050 (or the next available port if 8050 is taken)
4. Prints the URL and the trade count to the terminal
5. Optionally opens the browser via `webbrowser.open()` if `--open` is passed
6. Logs server startup and any callback errors to `runs/<run_id>/replay.log`

```python
# src/trading_research/replay/app.py
import click
import dash
from dash import dcc, html, Input, Output, State
from pathlib import Path
import polars as pl
import json

@click.command()
@click.option("--run-id", required=True, help="Run ID to replay")
@click.option("--port", default=8050, help="Port for the Dash server")
@click.option("--open/--no-open", default=False, help="Open browser automatically")
def replay(run_id: str, port: int, open: bool):
    """Launch the trade replay app for a backtest run."""
    run_dir = Path("runs") / run_id
    if not run_dir.exists():
        raise click.ClickException(f"Run directory not found: {run_dir}")

    trades = pl.read_parquet(run_dir / "trades.parquet")
    data_source = json.loads((run_dir / "data_source.json").read_text())
    bars = pl.read_parquet(data_source["parquet_path"])

    app = build_dash_app(trades, bars, run_id)

    click.echo(f"trade-research replay  ·  run: {run_id}  ·  {len(trades)} trades")
    click.echo(f"http://127.0.0.1:{port}")

    if open:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")

    app.run_server(host="127.0.0.1", port=port, debug=False)
```

## Notes editor

The notes field at the bottom of the trade detail panel saves to a sidecar JSON file in the run directory:

```
runs/<run_id>/replay_notes.json
```

```json
{
  "trade_017": {
    "notes": "Clean example of MACD divergence working. Histogram rotated and re-entered at the right moment. This is the behavior I want to see more of.",
    "tags": ["clean_example", "macd_rev"],
    "modified_utc": "2025-01-15T15:34:22Z"
  },
  "trade_023": {
    "notes": "Loser. Strategy entered on a divergence but the broader trend was strongly against it. Need a trend filter for this.",
    "tags": ["false_signal", "needs_trend_filter"],
    "modified_utc": "2025-01-15T15:41:08Z"
  }
}
```

The notes file is committed to git (it's documentation, not data), unlike the trade log itself. This means findings persist across machines and across runs.

## Standing rules this skill enforces

1. **The chart always uses as-of indicator computation.** Indicators are computed from bars up to each position, never from the full window.
2. **The trigger bar indicator values must match the trade log.** Any mismatch is a loud error, not a silent papering-over.
3. **The four-marker rule applies.** Trigger, entry, exit-trigger, exit are all marked when they differ.
4. **Session boundaries are respected.** Context windows do not silently span session boundaries.
5. **The app runs locally only.** No network exposure beyond localhost. No authentication. No persistent state other than user-initiated exports and notes.
6. **Re-entries are visually grouped with their parent trades.** The "show all in group" view exists.
7. **PNG exports include the indicator snapshot in the metadata overlay** so the captured image is self-documenting.
8. **The app refuses to load runs with missing or incomplete trade logs.** A trade log without trigger snapshots is unusable for forensics; the app says so explicitly rather than rendering broken charts.

## When to invoke this skill

Load this skill when the task involves:

- Building any part of the replay Dash app
- Adding new features (filters, views, navigation modes) to the app
- Designing the UX for a new forensic workflow
- Debugging issues with how trades are visualized
- Implementing the integration between the trade log and the chart
- Adding new keyboard shortcuts or controls

Don't load this skill for:

- The chart rendering primitives (use `charting`)
- The trade log schema (use `data-management`)
- Backtest engine modifications that don't directly affect what's in the trade log (use `backtesting`)

## Open questions for build time

1. **Whether to support multiple trade logs in one session.** Comparing two runs side by side is a useful workflow (e.g., comparing a parameter sweep). Defer until needed; the initial version handles one run at a time.
2. **Whether to add a "what if" mode** that lets the human modify the strategy parameters and see how the trade would have changed. This is interesting but adds significant complexity and is essentially "run a tiny backtest on demand." Defer to a much later phase if at all.
3. **Browser compatibility.** Dash works well in modern Chrome and Firefox. Edge is fine. Older browsers are not supported. Assume the human uses a current Chrome.
4. **Mobile/tablet view.** Not supported. The replay app is a desktop forensics tool; trying to make it mobile-friendly would compromise the desktop experience.
5. **Server-side caching of chart figures.** For runs with thousands of trades, regenerating the figure on every navigation could be slow. A simple LRU cache of recent figures would help. Implement when navigation feels sluggish.
