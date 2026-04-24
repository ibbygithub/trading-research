"""trading-research CLI entry point.

Usage:
    uv run trading-research --help
    uv run trading-research verify
    uv run trading-research backfill-manifests [--dry-run]
    uv run trading-research rebuild clean [--symbol ZN]
    uv run trading-research rebuild features [--symbol ZN] [--set base-v1]
    uv run trading-research inventory
    uv run trading-research replay --symbol ZN [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    uv run trading-research backtest --strategy configs/strategies/example.yaml
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer

from trading_research.core.instruments import InstrumentRegistry

app = typer.Typer(
    name="trading-research",
    help="Trading Research Platform — pipeline automation.",
    no_args_is_help=True,
    add_completion=False,
)

rebuild_app = typer.Typer(help="Rebuild CLEAN or FEATURES data from sources.", no_args_is_help=True)
app.add_typer(rebuild_app, name="rebuild")

_DATA_ROOT = Path(__file__).parents[3] / "data"


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


@app.command()
def verify(
    data_root: Annotated[Optional[Path], typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Walk all manifests in data/ and report staleness.

    Exit code 0 = all OK. Exit code 1 = stale or missing manifests.
    """
    from trading_research.pipeline.verify import verify_all, print_verify_result

    root = data_root or _DATA_ROOT
    result = verify_all(root)
    print_verify_result(result)

    if not result.clean:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# backfill-manifests
# ---------------------------------------------------------------------------


@app.command(name="backfill-manifests")
def backfill_manifests(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print what would be written; don't write.")] = False,
    data_root: Annotated[Optional[Path], typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Write manifest sidecars for data files that predate the manifest convention.

    Files built in sessions 02-04 have no manifests. This command backfills them
    using file mtime as built_at and marks each as 'backfilled: true'.

    Run --dry-run first to preview. Then run without --dry-run to write.
    """
    from trading_research.pipeline.backfill import backfill_all

    root = data_root or _DATA_ROOT
    count = backfill_all(data_root=root, dry_run=dry_run)

    if dry_run:
        typer.echo(f"Dry run: {count} manifests would be written.")
    else:
        typer.echo(f"Backfill complete: {count} manifests written.")


# ---------------------------------------------------------------------------
# rebuild clean
# ---------------------------------------------------------------------------


@rebuild_app.command(name="clean")
def rebuild_clean(
    symbol: Annotated[str, typer.Option(help="Instrument symbol (e.g. 6E).")],
    data_root: Annotated[Optional[Path], typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Rebuild all CLEAN files for SYMBOL from cached RAW contracts.

    Does not call the TradeStation API. All contracts must already be cached
    in data/raw/contracts/. Rebuilds: 1m (back-adjusted + unadjusted),
    5m, 15m, 60m, 240m, 1D.
    """
    from trading_research.pipeline.rebuild import rebuild_clean as _rebuild_clean

    root = data_root or _DATA_ROOT
    try:
        registry = InstrumentRegistry()
        instrument = registry.get(symbol)
        _rebuild_clean(instrument=instrument, data_root=root)
    except KeyError as e:
        typer.echo(f"ERROR: unknown symbol — {e}", err=True)
        raise typer.Exit(code=2)
    except FileNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# rebuild features
# ---------------------------------------------------------------------------


@rebuild_app.command(name="features")
def rebuild_features(
    symbol: Annotated[str, typer.Option(help="Instrument symbol (e.g. 6E).")],
    feature_set: Annotated[str, typer.Option("--set", help="Feature set tag.")] = "base-v1",
    data_root: Annotated[Optional[Path], typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Rebuild FEATURES files for SYMBOL using the named feature set.

    Example: uv run trading-research rebuild features --symbol 6E --set base-v1
    """
    from trading_research.pipeline.rebuild import rebuild_features as _rebuild_features

    root = data_root or _DATA_ROOT
    try:
        registry = InstrumentRegistry()
        instrument = registry.get(symbol)
        _rebuild_features(instrument=instrument, feature_set_tag=feature_set, data_root=root)
    except KeyError as e:
        typer.echo(f"ERROR: unknown symbol — {e}", err=True)
        raise typer.Exit(code=2)
    except FileNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------


@app.command()
def inventory(
    data_root: Annotated[Optional[Path], typer.Option(help="Override data/ root.")] = None,
) -> None:
    """Print a table of all data files with sizes, row counts, and manifest status."""
    from trading_research.pipeline.inventory import print_inventory

    root = data_root or _DATA_ROOT
    print_inventory(root)


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------


@app.command()
def replay(
    symbol: Annotated[str, typer.Option(help="Instrument symbol (e.g. 6E).")],
    from_date: Annotated[Optional[str], typer.Option("--from", help="Window start YYYY-MM-DD.")] = None,
    to_date: Annotated[Optional[str], typer.Option("--to", help="Window end YYYY-MM-DD.")] = None,
    trades: Annotated[Optional[Path], typer.Option(help="Path to a trades JSON log.")] = None,
    port: Annotated[int, typer.Option(help="Port for the Dash dev server.")] = 8050,
) -> None:
    """Open the visual forensic cockpit for SYMBOL in a browser.

    Defaults to the last 90 calendar days when --from / --to are omitted.

    Example:
        uv run trading-research replay --symbol ZN --from 2024-01-02 --to 2024-03-29
    """
    from trading_research.replay.app import build_app
    from trading_research.replay.data import DataNotFoundError

    today = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    try:
        from_dt = datetime.fromisoformat(from_date) if from_date else today - timedelta(days=90)
        to_dt = datetime.fromisoformat(to_date) if to_date else today
    except ValueError as exc:
        typer.echo(f"ERROR: Invalid date format — {exc}", err=True)
        raise typer.Exit(code=2)

    try:
        dash_app = build_app(symbol, from_dt, to_dt, trades_path=trades)
    except DataNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Starting cockpit for {symbol}  {from_dt:%Y-%m-%d} → {to_dt:%Y-%m-%d}")
    typer.echo(f"Open http://localhost:{port}/ in your browser.  Ctrl-C to stop.")
    dash_app.run(debug=False, port=port)


# ---------------------------------------------------------------------------
# backtest
# ---------------------------------------------------------------------------


@app.command()
def backtest(
    strategy: Annotated[Path, typer.Option(help="Path to strategy YAML config.")],
    from_date: Annotated[Optional[str], typer.Option("--from", help="Start date YYYY-MM-DD.")] = None,
    to_date: Annotated[Optional[str], typer.Option("--to", help="End date YYYY-MM-DD.")] = None,
    out: Annotated[Optional[Path], typer.Option(help="Output root (default: runs/).")] = None,
) -> None:
    """Run a backtest from a strategy YAML config.

    Writes trades.parquet, equity_curve.parquet, and summary.json to
    runs/<strategy_id>/<YYYY-MM-DD-HH-MM>/ and prints a summary table.

    Example:
        uv run trading-research backtest --strategy configs/strategies/example.yaml
    """
    import importlib
    import json
    import math
    from datetime import datetime, timezone

    import yaml

    from trading_research.backtest.engine import BacktestConfig, BacktestEngine
    from trading_research.backtest.fills import FillModel
    from trading_research.backtest.signals import SignalFrame
    from trading_research.data.instruments import load_instrument
    from trading_research.eval.bootstrap import bootstrap_summary, format_with_ci
    from trading_research.eval.summary import compute_summary, format_summary

    # --- Load strategy config ---
    if not strategy.is_file():
        typer.echo(f"ERROR: strategy file not found: {strategy}", err=True)
        raise typer.Exit(code=2)

    cfg_raw = yaml.safe_load(strategy.read_text(encoding="utf-8"))

    strategy_id = cfg_raw["strategy_id"]
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    signal_module_path = cfg_raw["signal_module"]
    bt_cfg_raw = cfg_raw.get("backtest", {})

    fill_model_str = bt_cfg_raw.get("fill_model", "next_bar_open")
    try:
        fill_model = FillModel(fill_model_str)
    except ValueError:
        typer.echo(f"ERROR: unknown fill_model '{fill_model_str}'. Use 'next_bar_open' or 'same_bar'.", err=True)
        raise typer.Exit(code=2)

    bt_config = BacktestConfig(
        strategy_id=strategy_id,
        symbol=symbol,
        fill_model=fill_model,
        same_bar_justification=bt_cfg_raw.get("same_bar_justification", ""),
        max_holding_bars=bt_cfg_raw.get("max_holding_bars"),
        eod_flat=bt_cfg_raw.get("eod_flat", True),
        use_ofi_resolution=bt_cfg_raw.get("use_ofi_resolution", False),
        quantity=bt_cfg_raw.get("quantity", 1),
    )

    # --- Load instrument ---
    try:
        inst = load_instrument(symbol)
    except KeyError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)

    # --- Load features data ---
    feature_set = cfg_raw.get("feature_set", "base-v1")
    data_root = _DATA_ROOT

    import pandas as pd
    from trading_research.replay.data import DataNotFoundError, _find_parquet

    feat_dir = data_root / "features"
    try:
        feat_path = _find_parquet(
            feat_dir,
            f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet",
        )
    except DataNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Loading features: {feat_path.name}")
    bars = pd.read_parquet(feat_path, engine="pyarrow")
    bars = bars.set_index("timestamp_utc")
    bars.index = pd.DatetimeIndex(bars.index, tz="UTC")
    bars = bars.sort_index()

    # Apply date filters.
    if from_date:
        bars = bars[bars.index >= pd.Timestamp(from_date, tz="UTC")]
    if to_date:
        bars = bars[bars.index <= pd.Timestamp(to_date, tz="UTC")]

    if bars.empty:
        typer.echo("ERROR: No bars in the specified date range.", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Bars: {len(bars):,}  ({bars.index[0].date()} to {bars.index[-1].date()})")

    # --- Generate signals ---
    try:
        mod = importlib.import_module(signal_module_path)
    except ImportError as e:
        typer.echo(f"ERROR: cannot import signal_module '{signal_module_path}': {e}", err=True)
        raise typer.Exit(code=2)

    signal_params = cfg_raw.get("signal_params", {})
    if signal_params:
        signals_df = mod.generate_signals(bars, **signal_params)
    else:
        signals_df = mod.generate_signals(bars)

    sf = SignalFrame(signals_df)
    try:
        sf.validate()
    except ValueError as e:
        typer.echo(f"ERROR: invalid signals — {e}", err=True)
        raise typer.Exit(code=2)

    # --- Run engine ---
    engine = BacktestEngine(bt_config, inst)
    typer.echo("Running backtest…")
    result = engine.run(bars, signals_df)

    typer.echo(f"Completed: {len(result.trades)} trades.")

    # --- Write outputs ---
    run_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d-%H-%M")
    out_root = out or (Path(__file__).parents[3] / "runs")
    run_dir = out_root / strategy_id / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)

    trades_path = run_dir / "trades.parquet"
    equity_path = run_dir / "equity_curve.parquet"
    summary_path = run_dir / "summary.json"

    result.trades.to_parquet(trades_path, engine="pyarrow", index=False)
    typer.echo(f"Trades written: {trades_path}")

    eq_df = result.equity_curve.reset_index()
    eq_df.columns = ["exit_ts", "equity_usd"]
    eq_df.to_parquet(equity_path, engine="pyarrow", index=False)
    typer.echo(f"Equity curve written: {equity_path}")

    summary = compute_summary(result)

    typer.echo("Computing bootstrap confidence intervals (n=1000)...")
    cis = bootstrap_summary(result, n_samples=1000, seed=42)

    # Persist both summary and CIs.
    summary_out = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in summary.items()}
    ci_out = {k: [None if math.isnan(v) else v for v in vs] for k, vs in cis.items()}
    summary_out["confidence_intervals"] = ci_out
    summary_path.write_text(
        json.dumps(summary_out, indent=2),
        encoding="utf-8",
    )
    typer.echo(f"Summary written: {summary_path}")

    # --- Print summary table with CIs ---
    typer.echo("")
    typer.echo(format_with_ci(summary, cis))

    # --- Record trial ---
    from trading_research.eval.trials import record_trial
    trial_group_val: str | None = None  # default: use strategy_id
    record_trial(
        runs_root=out_root,
        strategy_id=strategy_id,
        config_path=strategy,
        sharpe=summary.get("sharpe", float("nan")),
        trial_group=trial_group_val,
    )


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


@app.command()
def report(
    run_id: Annotated[str, typer.Argument(help="Run ID (directory under runs/, e.g. zn-macd-pullback-v1).")],
    ts: Annotated[Optional[str], typer.Option("--ts", help="Timestamp subdirectory (default: latest).")] = None,
    out: Annotated[Optional[Path], typer.Option(help="Override runs/ root directory.")] = None,
) -> None:
    """Generate the Trader's Desk HTML report for a backtest run.

    Reads trades.parquet, equity_curve.parquet, and summary.json from
    runs/<run-id>/<ts>/  and writes three files:
        report.html            — self-contained offline HTML report
        pipeline_integrity.md  — pipeline audit
        data_dictionary.md     — column and metric definitions

    Example:
        uv run trading-research report zn-macd-pullback-v1
    """
    from trading_research.eval.report import generate_report
    from trading_research.eval.pipeline_integrity import generate_pipeline_integrity_report

    runs_root = out or (Path(__file__).parents[3] / "runs")
    run_root = runs_root / run_id

    if not run_root.is_dir():
        typer.echo(f"ERROR: run directory not found: {run_root}", err=True)
        raise typer.Exit(code=2)

    # Resolve timestamp subdirectory
    if ts:
        run_dir = run_root / ts
    else:
        subdirs = sorted(d for d in run_root.iterdir() if d.is_dir())
        if not subdirs:
            typer.echo(f"ERROR: no timestamp directories found under {run_root}", err=True)
            raise typer.Exit(code=2)
        run_dir = subdirs[-1]

    if not run_dir.is_dir():
        typer.echo(f"ERROR: run directory not found: {run_dir}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Generating report for: {run_dir}")

    # Generate HTML report + data dictionary
    paths = generate_report(run_dir)
    typer.echo(f"Report:           {paths.report}")
    typer.echo(f"Data dictionary:  {paths.data_dictionary}")


    # Generate pipeline integrity report
    try:
        pi_path = generate_pipeline_integrity_report(run_dir)
        typer.echo(f"Pipeline integrity: {pi_path}")
    except Exception as exc:
        typer.echo(f"WARNING: pipeline integrity report failed: {exc}", err=True)

    typer.echo("Done.")


# ---------------------------------------------------------------------------
# walkforward
# ---------------------------------------------------------------------------


@app.command()
def walkforward(
    strategy: Annotated[Path, typer.Option(help="Path to strategy YAML config.")],
    n_folds: Annotated[int, typer.Option(help="Number of contiguous folds.")] = 10,
    gap: Annotated[int, typer.Option(help="Bars purged between train end and test start.")] = 100,
    embargo: Annotated[int, typer.Option(help="Bars embargoed after test end.")] = 50,
    out: Annotated[Optional[Path], typer.Option(help="Output root (default: runs/).")] = None,
    trial_group: Annotated[Optional[str], typer.Option(help="Trial group tag for deflated Sharpe.")] = None,
) -> None:
    """Run a purged walk-forward robustness test.

    Splits the full dataset into n_folds, purges gap bars between train and
    test, embargoes embargo bars after test, and reports per-fold metrics.

    Writes:
        runs/<strategy_id>/<ts>/walkforward.parquet
        runs/<strategy_id>/<ts>/walkforward_equity.parquet

    Example:
        uv run trading-research walkforward --strategy configs/strategies/zn_macd_pullback.yaml
    """
    import json
    import math
    from datetime import datetime, timezone

    import yaml

    from trading_research.backtest.walkforward import run_walkforward, write_walkforward_outputs
    from trading_research.eval.trials import record_trial

    if not strategy.is_file():
        typer.echo(f"ERROR: strategy file not found: {strategy}", err=True)
        raise typer.Exit(code=2)

    cfg_raw = yaml.safe_load(strategy.read_text(encoding="utf-8"))
    strategy_id = cfg_raw["strategy_id"]

    out_root = out or (Path(__file__).parents[3] / "runs")
    run_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d-%H-%M")
    run_dir = out_root / strategy_id / run_ts

    typer.echo(f"Walk-forward: {strategy_id}  folds={n_folds}  gap={gap}  embargo={embargo}")

    try:
        wf = run_walkforward(
            config_path=strategy,
            n_folds=n_folds,
            gap_bars=gap,
            embargo_bars=embargo,
            data_root=_DATA_ROOT,
            trial_group=trial_group,
        )
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1)

    wf_path, eq_path = write_walkforward_outputs(wf, run_dir)
    typer.echo(f"Walk-forward metrics:  {wf_path}")
    typer.echo(f"Walk-forward equity:   {eq_path}")

    # Print per-fold table.
    typer.echo("")
    typer.echo("Per-fold OOS metrics:")
    typer.echo(f"{'Fold':>5}  {'Test start':>12}  {'Bars':>6}  {'Trades':>7}  "
               f"{'WinRate':>8}  {'Sharpe':>8}  {'Calmar':>8}")
    for _, row in wf.per_fold_metrics.iterrows():
        wr = row.get("win_rate", float("nan"))
        wr_str = f"{wr:.1%}" if math.isfinite(wr) else "  N/A"
        sh = row.get("sharpe", float("nan"))
        sh_str = f"{sh:.2f}" if math.isfinite(sh) else "  N/A"
        ca = row.get("calmar", float("nan"))
        ca_str = f"{ca:.2f}" if math.isfinite(ca) else "  N/A"
        typer.echo(
            f"{row['fold']:>5}  {str(row['test_start'].date()):>12}  "
            f"{row['test_bars']:>6}  {row['trades']:>7}  "
            f"{wr_str:>8}  {sh_str:>8}  {ca_str:>8}"
        )

    # Aggregated OOS metrics.
    m = wf.aggregated_metrics
    if m:
        typer.echo("")
        typer.echo("Aggregated OOS metrics:")
        typer.echo(f"  Trades:      {m.get('total_trades', 0)}")
        sharpe_val = m.get("sharpe", float("nan"))
        typer.echo(f"  Sharpe:      {sharpe_val:.2f}" if math.isfinite(sharpe_val) else "  Sharpe:      N/A")
        calmar_val = m.get("calmar", float("nan"))
        typer.echo(f"  Calmar:      {calmar_val:.2f}" if math.isfinite(calmar_val) else "  Calmar:      N/A")

        # Record trial.
        record_trial(
            runs_root=out_root,
            strategy_id=strategy_id,
            config_path=strategy,
            sharpe=sharpe_val,
            trial_group=trial_group,
        )

    typer.echo("")
    typer.echo(f"Run output: {run_dir}")
    typer.echo("Done.")


# ---------------------------------------------------------------------------
# stationarity
# ---------------------------------------------------------------------------


@app.command()
def stationarity(
    symbol: Annotated[str, typer.Option(help="Instrument symbol (e.g. 6E, ZN).")],
    start: Annotated[Optional[str], typer.Option(help="Start date YYYY-MM-DD.")] = None,
    end: Annotated[Optional[str], typer.Option(help="End date YYYY-MM-DD.")] = None,
    timeframes: Annotated[str, typer.Option(help="Comma-separated timeframes to test.")] = "1m,5m,15m",
    out: Annotated[Optional[Path], typer.Option(help="Override runs/ root.")] = None,
) -> None:
    """Run the stationarity suite (ADF, Hurst, OU) on CLEAN 1m bars for SYMBOL.

    Writes parquet + JSON summary + markdown to runs/stationarity/<SYMBOL>/<YYYYMMDD-HHMM>/.

    Example:
        uv run trading-research stationarity --symbol ZN --start 2024-01-01 --end 2024-12-31
    """
    import glob as _glob
    from datetime import datetime, timezone

    import pandas as pd

    from trading_research.core.instruments import InstrumentRegistry
    from trading_research.stats.stationarity import run_stationarity_suite, write_report

    # --- Resolve instrument ---
    try:
        registry = InstrumentRegistry()
        instrument = registry.get(symbol)
    except KeyError as e:
        typer.echo(f"ERROR: unknown symbol — {e}", err=True)
        raise typer.Exit(code=2)

    # --- Find CLEAN 1m parquet ---
    clean_dir = _DATA_ROOT / "clean"
    patterns = [
        str(clean_dir / f"{symbol}_1m_backadjusted_*.parquet"),
        str(clean_dir / f"{symbol}_1m_unadjusted_*.parquet"),
    ]
    candidates: list[str] = []
    for pat in patterns:
        candidates.extend(_glob.glob(pat))

    if not candidates:
        typer.echo(
            f"ERROR: no CLEAN 1m parquet found for {symbol} in {clean_dir}",
            err=True,
        )
        raise typer.Exit(code=2)

    typer.echo(f"Loading CLEAN bars: {[Path(c).name for c in candidates]}")
    frames = [pd.read_parquet(p, engine="pyarrow") for p in sorted(candidates)]
    bars = pd.concat(frames, ignore_index=True)

    # Normalise timestamp column.
    bars["timestamp_utc"] = pd.to_datetime(bars["timestamp_utc"], utc=True)
    bars = bars.sort_values("timestamp_utc").reset_index(drop=True)

    if start:
        bars = bars[bars["timestamp_utc"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        bars = bars[bars["timestamp_utc"] <= pd.Timestamp(end, tz="UTC")]

    if bars.empty:
        typer.echo("ERROR: No bars in the specified date range.", err=True)
        raise typer.Exit(code=2)

    typer.echo(
        f"Bars: {len(bars):,}  "
        f"({bars['timestamp_utc'].iloc[0].date()} to {bars['timestamp_utc'].iloc[-1].date()})"
    )

    # --- Run suite ---
    tf_list = [t.strip() for t in timeframes.split(",") if t.strip()]
    typer.echo(f"Running stationarity suite: timeframes={tf_list}")

    report = run_stationarity_suite(instrument=instrument, bars=bars, timeframes=tf_list)

    # --- Write outputs ---
    runs_root = out or (Path(__file__).parents[3] / "runs")
    run_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M")
    output_dir = runs_root / "stationarity" / symbol / run_ts
    parquet_path, json_path, md_path = write_report(report, output_dir)

    typer.echo(f"\nOutputs written to {output_dir}:")
    typer.echo(f"  {parquet_path.name}")
    typer.echo(f"  {json_path.name}")
    typer.echo(f"  {md_path.name}")

    # --- Print markdown summary ---
    typer.echo("")
    typer.echo(md_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


@app.command()
def portfolio(
    run_ids: list[str] = typer.Argument(..., help="List of run IDs to include in the portfolio"),
    output_dir: Path = typer.Option(
        None, "--output-dir", "-o", help="Directory to save the portfolio report. Defaults to runs/portfolio/<timestamp>/"
    )
):
    """Generate a multi-strategy portfolio analytics report."""
    from trading_research.eval.portfolio_report import generate_portfolio_report
    import time
    
    if output_dir is None:
        run_ts = time.strftime("%Y-%m-%d-%H-%M-%S")
        output_dir = Path("runs/portfolio") / run_ts
        
    try:
        report_path = generate_portfolio_report(run_ids, output_dir)
        typer.secho(f"Success! Portfolio report generated at {report_path}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Failed to generate portfolio report: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    main()
