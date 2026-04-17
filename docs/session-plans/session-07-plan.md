# Session 07 — Visual Forensics: The Cockpit

## Objective

Build the Dash-based visual replay application. By end of session:
`uv run trading-research replay --symbol ZN` opens a browser window showing a
4-pane multi-timeframe chart (5m / 15m / 60m / 1D) with synced crosshairs,
VWAP and Bollinger overlays, an OFI subplot beneath the 5m pane, and support
for an optional trade-marker overlay. This is the "eyes" for all future
backtest forensics and strategy validation.

**This session is visual infrastructure only. No strategy code, no backtest
engine, no live data. Every chart renders from existing FEATURES/CLEAN parquets.**

---

## Entry Criteria

- Session 06 complete: `uv run trading-research verify` reports all files OK
- `data/features/` has valid `ZN_5m_base-v1_*.parquet` and `ZN_15m_base-v1_*.parquet`
- `data/clean/` has valid `ZN_60m_*.parquet` and `ZN_1D_*.parquet`

---

## Context

The `replay/` module has been a stub since session 02. It now gets built.
The 4-pane layout, synced crosshairs, and OFI subplot are the canonical
forensic tools for reviewing backtest trades — they exist before the backtest
engine so that when the engine ships (Floor 2 / session 08), the cockpit is
already ready to show its output.

Data availability at session 07 start:
- 5m and 15m: load from FEATURES parquets (42 columns including all indicators)
- 60m and 1D: load from CLEAN parquets (OHLCV only); SMA(200) computed on the fly
- Trade markers: not available yet; placeholder support via `--trades` flag

---

## Dependencies to Add

Edit `pyproject.toml`:

```toml
dependencies = [
    ...
    "dash>=2.17",
    "plotly>=5.22",
]
```

`uv sync` after edit. Verify `import dash` and `import plotly` work in the venv.

---

## Step 1 — Module scaffold

Create the following files (empty stubs with docstrings at this stage):

```
src/trading_research/replay/
    __init__.py          # exports: run_app
    app.py               # Dash app factory: build_app(symbol, from_date, to_date, trades_path)
    layout.py            # build_layout(symbol) → dash layout component tree
    callbacks.py         # register_callbacks(app) → crosshair sync, date-range update
    data.py              # load_window(symbol, from_dt, to_dt) → dict of DataFrames per TF
    charts.py            # build_candlestick(), build_ofi_bar(), build_overlay()
```

Add `replay` subcommand to the CLI (`src/trading_research/cli/main.py`):

```
uv run trading-research replay --symbol ZN [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--trades path/to/trades.json]
```

Defaults: `--from` = 90 calendar days before today, `--to` = today.

---

## Step 2 — Data loading (`data.py`)

`load_window(symbol: str, from_dt: datetime, to_dt: datetime) -> dict[str, pd.DataFrame]`

Returns a dict keyed by timeframe string: `{"5m": df, "15m": df, "60m": df, "1D": df}`

Rules:
- 5m and 15m: load from `data/features/<symbol>_<tf>_base-v1_*.parquet`, filter to window
- 60m and 1D: load from `data/clean/<symbol>_<tf>_backadjusted_*.parquet`, filter to window
  - Compute SMA(200) on the fly for 60m and 1D (not in CLEAN by design)
- All timestamps returned as tz-aware UTC; display layer converts to America/New_York
- If no parquet found for a timeframe, raise `DataNotFoundError` with a clear message

Tests (`tests/test_replay_data.py`):
- Load a 30-day window, assert all four keys present and DataFrames non-empty
- Assert index is DatetimeTzDtype UTC
- Assert 5m and 15m DataFrames contain expected indicator columns (vwap_session, bb_upper, ofi, etc.)
- Assert 60m and 1D DataFrames contain sma_200

---

## Step 3 — Chart builders (`charts.py`)

Three functions:

### `build_candlestick(df, tf_label, height)`
Returns a `go.Figure` with:
- `go.Candlestick` trace (OHLC data) — x-axis is the timestamp
- VWAP overlays as translucent line traces:
  - 5m/15m: session VWAP, weekly VWAP, monthly VWAP (use scattergl for performance)
  - 60m/1D: SMA(200) line only
- Bollinger Bands: upper and lower as dashed lines, fill between as translucent shade
- `uirevision` set to `tf_label` so zoom state persists across callbacks

### `build_ofi_bar(df)`
Returns a `go.Figure` with:
- `go.Bar` trace of the `ofi` column, colored green (positive) / red (negative)
- Height ~25% of the 5m pane — this is a subplot, not a standalone chart

### `build_trade_markers(fig, trades_df, tf)`
Adds `go.Scatter` traces to an existing figure:
- Entry arrows (green triangle-up), exit arrows (red triangle-down)
- Stop level as a horizontal dashed red line segment
- Target level as a horizontal dashed green line segment
- Called only when `--trades` JSON is loaded; no-op otherwise

---

## Step 4 — Layout (`layout.py`)

`build_layout(symbol, from_dt, to_dt) → dash.html.Div`

Structure:

```
┌─────────────────────────────────────┐
│  Header: "ZN Forensic Cockpit"      │
│  Symbol | Date range picker         │
├──────────────────┬──────────────────┤
│  5m chart        │  15m chart       │
│  (+ OFI subplot) │                  │
├──────────────────┼──────────────────┤
│  60m chart       │  1D chart        │
└──────────────────┴──────────────────┘
```

The 5m pane is implemented as a single figure with two subplots (candlestick +
OFI bar) using `make_subplots(rows=2, cols=1, row_heights=[0.75, 0.25])`.

All four chart components use `dcc.Graph` with `id="chart-5m"`, `"chart-15m"`,
`"chart-60m"`, `"chart-1d"` respectively.

A `dcc.Store(id="hover-ts")` holds the current hovered timestamp for crosshair sync.

---

## Step 5 — Callbacks (`callbacks.py`)

`register_callbacks(app, data: dict[str, pd.DataFrame]) -> None`

### Crosshair sync callback
Trigger: `hoverData` on any of the four charts.
Action: Update `dcc.Store("hover-ts")` with the hovered timestamp.
Separate callback: for each chart, add a vertical line shape at the stored timestamp.

Implementation note: Plotly's `relayoutData` / `add_vline` approach is simpler
than custom scatter traces for crosshairs. Use `fig.add_vline()` via a figure
patch callback (`Patch()`) to avoid re-rendering the entire figure on hover.

### Date-range update callback
Trigger: date range picker changes.
Action: reload data for new window, rebuild all four figures.
This is the only full-redraw callback.

---

## Step 6 — App factory and CLI wiring (`app.py`, `cli/main.py`)

`build_app(symbol, from_dt, to_dt, trades_path=None) -> dash.Dash`

- Calls `load_window()`, `build_layout()`, `register_callbacks()`
- Sets `app.title = f"ZN Cockpit | {from_dt:%Y-%m-%d} – {to_dt:%Y-%m-%d}"`
- Returns the app object (not `app.run_server()` — that's the CLI's job)

CLI command:
```python
@app.command()
def replay(
    symbol: str = typer.Option("ZN"),
    from_date: str = typer.Option(None),
    to_date: str = typer.Option(None),
    trades: Path = typer.Option(None),
    port: int = typer.Option(8050),
):
    ...
    app = build_app(symbol, from_dt, to_dt, trades_path=trades)
    app.run(debug=False, port=port)
```

---

## Step 7 — Tests

`tests/test_replay_data.py` — data loading (see Step 2)

`tests/test_replay_charts.py`:
- `build_candlestick()` returns a `go.Figure` with at least one trace
- `build_ofi_bar()` returns a `go.Figure` with a bar trace
- `build_trade_markers()` adds traces to an existing figure (use a synthetic trades DataFrame)

`tests/test_replay_cli.py`:
- `replay --help` exits 0
- `replay --symbol INVALID` exits with error code 2 and a clear message

No browser or Selenium testing. Visual correctness is verified manually by Ibby.

---

## Step 8 — Manual verification (Ibby runs this)

```
uv run trading-research replay --symbol ZN --from 2024-01-02 --to 2024-03-29
```

Expected: browser opens at `http://localhost:8050` showing:
- 4-pane layout with ZN candlesticks across all timeframes
- VWAP lines visible on 5m and 15m panes
- Bollinger Bands shaded on 5m and 15m panes
- OFI bars beneath 5m pane, colored by sign
- Hovering over any chart shows a vertical line on all four panes at that timestamp
- SMA(200) visible on 60m and 1D panes
- Date range picker allows changing the window without restarting

---

## Out of Scope for Session 07

- Live data / real-time streaming
- Portfolio P&L overlay
- Order entry buttons or manual trade logging
- Settings UI or saved view states
- Performance profiling or WebGL optimization (test with a 90-day window first)
- 6A / 6C / 6N instrument support (architecture supports it, data not yet in FEATURES)
- Backtest trade replay (that requires the backtest engine from session 08)

---

## Success Criteria

| Item | Done when |
|---|---|
| Dependencies | `dash` and `plotly` in `pyproject.toml`, `uv sync` clean |
| Data loading | `load_window("ZN", ...)` returns four DataFrames with correct columns |
| Chart builders | All three builder functions return valid Plotly figures |
| Layout | 4-pane 2×2 grid renders without errors |
| Crosshair sync | Hover on one chart draws vertical line on all four |
| OFI subplot | Visible below 5m candlestick pane, colored by sign |
| CLI command | `uv run trading-research replay --symbol ZN` opens browser |
| Tests | New tests pass; existing 154 tests still pass |
| Manual review | Ibby confirms layout and crosshairs work as expected |
