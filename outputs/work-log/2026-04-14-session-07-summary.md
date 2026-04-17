# Session Summary — 2026-04-14 Session 07

## Completed

- Added `dash>=2.17` and `plotly>=5.22` to `pyproject.toml`; `uv sync` resolves to dash 4.1.0 / plotly 6.7.0
- Built `src/trading_research/replay/data.py` — `load_window(symbol, from_dt, to_dt)` returns 4 DataFrames (5m/15m from FEATURES, 60m/1D from CLEAN with SMA(200) computed on full history before window filter)
- Built `src/trading_research/replay/charts.py` — `build_candlestick`, `build_ofi_bar`, `build_5m_figure` (2-subplot combined), `build_trade_markers`
- Built `src/trading_research/replay/layout.py` — 2×2 CSS grid with `dcc.Graph`, `dcc.DatePickerRange`, `dcc.Store(id="hover-ts")`
- Built `src/trading_research/replay/callbacks.py` — crosshair sync via Patch (no full re-render on hover) + date-range full-redraw callback
- Built `src/trading_research/replay/app.py` — `build_app` factory: loads data, builds figures, assembles layout + callbacks
- Added `replay` subcommand to `cli/main.py` — `--symbol`, `--from`, `--to`, `--trades`, `--port` flags; DataNotFoundError → exit 2
- 26 new tests across `test_replay_data.py`, `test_replay_charts.py`, `test_replay_cli.py`
- **189 total tests passing** (was 163 before this session)

## Files changed

- `pyproject.toml` — added dash, plotly dependencies
- `src/trading_research/replay/__init__.py` — exports `build_app`
- `src/trading_research/replay/data.py` — new: `load_window`, `DataNotFoundError`
- `src/trading_research/replay/charts.py` — new: all four chart builder functions
- `src/trading_research/replay/layout.py` — new: `build_layout`
- `src/trading_research/replay/callbacks.py` — new: `register_callbacks`
- `src/trading_research/replay/app.py` — new: `build_app`
- `src/trading_research/cli/main.py` — added `replay` command
- `tests/test_replay_data.py` — new: 8 tests
- `tests/test_replay_charts.py` — new: 15 tests
- `tests/test_replay_cli.py` — new: 3 tests

## Decisions made

- `build_5m_figure` is a dedicated function (not handled in `app.py`) because the combined subplot figure is architecturally a chart concern, not a factory concern
- SMA(200) for CLEAN data: computed on **full history** before window filter — this avoids warm-up NaN at the left edge of any display window
- Crosshair sync uses `Patch()` to update only `layout.shapes` — avoids full figure re-serialisation on every hover event
- OFI column resolved by name prefix (`ofi_14` → first column starting with `ofi`), so it survives future column renames
- Dark theme throughout (`#0f172a` background, slate palette) — consistent with Bloomberg-style trading tooling

## Next session starts from

- Session 07 complete. Manual review step pending: `uv run trading-research replay --symbol ZN --from 2024-01-02 --to 2024-03-29`
- Session 08 = backtest engine: fill model, TP/SL resolution, trade log schema, equity curve
- `src/trading_research/backtest/` is a stub; `replay/charts.py`'s `build_trade_markers` is ready to accept the trade log output
