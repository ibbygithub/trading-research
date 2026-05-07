# Chapter 18 — The Replay App

> **Chapter status:** [EXISTS] — documents the replay Dash app at its
> current state. All features described here exist in the codebase.

---

## 18.0 What this chapter covers

The replay app is a browser-based trade forensics cockpit. It shows the
instrument's price bars across four timeframes simultaneously, with trade
markers indicating trigger bars and fill bars from a backtest trade log.
This chapter covers what the app shows, how to launch it, when to use
it (two distinct purposes: pre-backtest sanity and post-backtest
forensics), and a reference of every control in the UI.

---

## 18.1 What replay shows

The cockpit renders a 2×2 grid of interactive candlestick charts:

```
┌──────────────────────────┬──────────────────────────┐
│  5m  (+ OFI subplot)     │  15m                     │
├──────────────────────────┼──────────────────────────┤
│  60m                     │  1D                      │
└──────────────────────────┴──────────────────────────┘
```

All four charts span the same date window, set by the date-picker in
the header. Zooming or panning one chart does not lock the others —
each is an independent Plotly figure that the operator can scroll
independently.

### 18.1.1 Trade markers

When a `--trades` parquet is provided, the app adds trade markers to
all four charts:

- **Entry markers**: triangle pointing in the trade direction (up for
  long, down for short), placed at `entry_ts` (the fill bar, not the
  trigger bar). The colour is green for long, red for short.
- **Exit markers**: inverted triangle placed at `exit_ts`, coloured by
  exit reason (green = target, red = stop, grey = signal/eod/time_limit).

On the 5m and 15m charts, markers are placed at the exact `entry_ts`
and `exit_ts` timestamps. On the 60m and 1D charts, timestamps are
snapped to the nearest containing bar open — a 5m entry at 10:23 would
appear on the 10:00 60m bar.

### 18.1.2 The OFI subplot

The 5m chart includes a second panel below the candlesticks: the
Order-Flow Imbalance ratio `(buy_volume - sell_volume) / (buy_volume +
sell_volume)`. Where the ratio is positive (buying dominates), the bar
is green. Where negative (selling dominates), the bar is red.

The OFI panel is visible only when `buy_volume` and `sell_volume` data
is present in the loaded FEATURES parquet. For older contract data
where TradeStation did not report order-flow volume, the panel renders
as a flat zero line with a note in the chart title.

---

## 18.2 Launching replay

```
uv run trading-research replay --symbol ZN [OPTIONS]
```

### 18.2.1 Full option reference

| Option | Default | Purpose |
|--------|---------|---------|
| `--symbol` | required | CME root symbol |
| `--from` | 90 days ago (UTC) | Window start date |
| `--to` | today (UTC) | Window end date |
| `--trades` | none | Path to a `trades.parquet` for overlaying markers |
| `--port` | 8050 | Port for the Dash dev server |

When `--from` and `--to` are omitted, the app defaults to the last 90
calendar days from today. This default is designed for "I'm reviewing
recent market behaviour" sessions. For forensics on a specific backtest
period, always supply explicit dates.

### 18.2.2 Example invocations

```bash
# Basic chart review — no trade overlay, last 90 days:
uv run trading-research replay --symbol ZN

# Forensics window for a specific backtest period:
uv run trading-research replay \
    --symbol ZN \
    --from 2024-01-02 \
    --to 2024-03-29

# Full forensics: price chart + trade markers from a backtest run:
uv run trading-research replay \
    --symbol 6A \
    --from 2024-06-01 \
    --to 2024-09-30 \
    --trades runs/6a-vwap-fade-v2/2026-05-01-09-00/trades.parquet
```

After launching, the terminal prints:

```
Starting cockpit for ZN  2024-01-02 → 2024-03-29
Open http://localhost:8050/ in your browser.  Ctrl-C to stop.
```

Open the URL in any browser. Ctrl-C in the terminal stops the server.

### 18.2.3 Data requirements

The replay app loads CLEAN parquets for the specified symbol. It
requires at minimum:

- `data/clean/<symbol>_backadjusted_5m_*.parquet`
- `data/clean/<symbol>_backadjusted_15m_*.parquet`
- `data/clean/<symbol>_backadjusted_60m_*.parquet`
- `data/clean/<symbol>_backadjusted_1D_*.parquet`

If any of these files is missing, the command exits with:

```
ERROR: no clean data found for symbol <S>
```

Run `rebuild clean --symbol <S>` to produce the CLEAN parquets before
launching replay (Chapter 4.7.2).

---

## 18.3 When to use replay

Replay serves two purposes with different use patterns.

### 18.3.1 Pre-backtest sanity

**Use:** before running a backtest on a new strategy or a significant
parameter change.

**Goal:** confirm that the entry and exit logic, as it will fire in the
backtest, looks visually plausible on real price bars.

**Process:**

1. Launch replay without a `--trades` overlay.
2. Scroll through the recent 90-day window looking at the 5m and 15m
   charts.
3. Mentally identify bars where your strategy's conditions would have
   been met — does the signal make sense given the price action?
4. Look specifically at bars where the signal *should not* fire: are
   there obvious cases where the conditions accidentally trigger?

> *The chart bias problem:* be aware that visual inspection on a
> historical chart is compromised by hindsight. You can see where price
> went after every bar. Your entry conditions may look brilliant on the
> chart precisely because you're unconsciously selecting the bars where
> the pattern worked. The replay app shows you bars in sequence, but
> it cannot remove the hindsight you bring to the session. This is why
> the backtest (with honest forward-fill and bootstrap CIs) is the
> authoritative test, not the chart. Use replay to catch obvious
> signal-logic bugs, not to build conviction.

### 18.3.2 Post-backtest forensics

**Use:** after a backtest produces results you want to understand or
question.

**Goal:** visually inspect specific trades — especially losers and
outliers — to understand what the market was doing when the strategy
triggered.

**Process:**

1. Run the backtest first, note the run directory.
2. Load the trades parquet into the replay app with `--trades`.
3. Use the date-picker to navigate to specific dates of interest:
   the worst drawdown period, the longest losing streak, or any trade
   where the P&L is an outlier.
4. On the 5m chart, find the entry marker and examine what the price
   action was in the bars leading up to it. Did the signal fire into
   a trend, not against one? Did it fire at a session gap?
5. For stop exits, check whether the stop hit on a wick or on a real
   momentum move. Wick stops are recoverable; momentum stops are not.

The two pairs of timestamps in `TRADE_SCHEMA` (§15.2) make this
forensics possible: the trigger bar arrow shows you *when the signal
fired*, and the fill bar arrow shows you *when you were actually in the
market*. The gap between them is visible in the replay.

---

## 18.4 Layout reference

The cockpit header contains three controls:

| Control | Type | Effect |
|---------|------|--------|
| Date-picker range | Start/end date | Reloads all four charts to the new window |
| Timeframe focus toggle | Radio button (5m / 15m / 60m / Daily) | Expands the selected timeframe to full-width; collapses the others |
| (Implicit) Trade markers | Rendered from `--trades` parquet | Present if `--trades` was supplied at launch; cannot be toggled in-session |

### 18.4.1 Date-picker interaction

Changing the date range triggers a Dash callback that reloads CLEAN
data from disk and re-renders all four figures. For long date windows
(several years), the reload can take a few seconds. The app does not
cache across date-range changes.

### 18.4.2 Timeframe focus

The focus toggle is useful when inspecting a specific bar on the 5m
chart — clicking "5m" expands it to fill the viewport, making the
candlestick bars larger and easier to read. Click "5m" again (or
select another timeframe) to restore the 2×2 grid.

### 18.4.3 Chart interactivity

Each chart is a Plotly figure with standard Plotly controls:

- **Zoom:** click and drag to select a rectangular area to zoom into.
- **Pan:** hold Shift and drag, or use the Plotly toolbar.
- **Reset:** double-click to return to the full date range.
- **Hover tooltip:** hover over a bar to see OHLCV values and
  (when present) OFI data.
- **Trade marker hover:** hover over a trade marker to see the trade
  direction, entry/exit price, and exit reason.

---

## 18.5 Related references

### Code modules

- [`src/trading_research/replay/app.py`](../../src/trading_research/replay/app.py)
  — `build_app()`: the Dash app factory. Where the data load, figure
  build, and trade-marker overlay happen.

- [`src/trading_research/replay/layout.py`](../../src/trading_research/replay/layout.py)
  — `build_layout()`: the complete Dash component tree, including the
  2×2 grid and header controls.

- [`src/trading_research/replay/charts.py`](../../src/trading_research/replay/charts.py)
  — `build_5m_figure()`, `build_candlestick()`,
  `build_trade_markers()`, `project_trades_to_tf()`.

- [`src/trading_research/replay/callbacks.py`](../../src/trading_research/replay/callbacks.py)
  — Dash callbacks for date-range updates and timeframe focus toggle.

- [`src/trading_research/replay/data.py`](../../src/trading_research/replay/data.py)
  — `load_window()`, `load_trades()`, `_find_parquet()`. Data loading
  helpers that the app and the backtest CLI both use.

### CLI reference

- **Chapter 49.7** — full CLI reference for the `replay` subcommand,
  including exit codes and all environment interactions.

### Other chapters

- **Chapter 15** — Trade Schema & Forensics: the `TRADE_SCHEMA` fields
  that the replay app reads to position trade markers.
- **Chapter 16** — Running a Single Backtest: how to produce the
  `trades.parquet` that replay overlays.
- **Chapter 17** — The Trader's Desk Report: the HTML report, which
  provides a static version of some replay views without requiring
  the app server.

---

*End of Chapter 18. Next: Chapter 19 — Headline Metrics.*
