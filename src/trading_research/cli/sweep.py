"""Parameter sweep runner — core logic, separated from CLI for testability.

The CLI ``sweep`` command delegates to ``run_sweep()``.  Tests can supply a
``runner`` callable to avoid real backtest I/O.

Typical usage:
    from trading_research.cli.sweep import expand_params, run_sweep

    combos = expand_params(["entry_atr_mult=1.0,1.5,2.0", "adx_max=18,22,25"])
    # combos = [
    #   {"entry_atr_mult": 1.0, "adx_max": 18.0},
    #   {"entry_atr_mult": 1.0, "adx_max": 22.0},
    #   ...  (9 total)
    # ]
"""

from __future__ import annotations

import importlib
import json
import math
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Parameter expansion
# ---------------------------------------------------------------------------


def _coerce_value(raw: str) -> Any:
    """Parse a single parameter value string.

    Tries YAML parsing first (handles int, float, bool, null).
    Falls back to the raw string if YAML parsing fails.
    """
    try:
        parsed = yaml.safe_load(raw.strip())
        # yaml.safe_load("") returns None — fall back to the raw string.
        if parsed is None and raw.strip():
            return raw.strip()
        return parsed
    except Exception:
        return raw.strip()


def expand_params(param_specs: list[str]) -> list[dict[str, Any]]:
    """Generate cartesian product of parameter values from spec strings.

    Each spec has the form ``key=v1,v2,v3`` where values are YAML-parsed
    (so ``1.5`` → float, ``22`` → int, ``true`` → bool).

    Args:
        param_specs: List of strings like ``["entry_atr_mult=1.0,1.5,2.0", "adx_max=18,22"]``.

    Returns:
        List of dicts, each representing one parameter combination.

    Raises:
        ValueError: If any spec string is malformed.

    Examples:
        >>> expand_params(["a=1,2", "b=x,y"])
        [{"a": 1, "b": "x"}, {"a": 1, "b": "y"}, {"a": 2, "b": "x"}, {"a": 2, "b": "y"}]
    """
    if not param_specs:
        return [{}]

    parsed: dict[str, list[Any]] = {}
    for spec in param_specs:
        if "=" not in spec:
            raise ValueError(
                f"Invalid param spec '{spec}': expected 'key=v1,v2,...' format."
            )
        key, _, values_str = spec.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"Empty key in param spec '{spec}'.")
        values = [_coerce_value(v) for v in values_str.split(",") if v.strip()]
        if not values:
            raise ValueError(f"No values in param spec '{spec}'.")
        parsed[key] = values

    keys = list(parsed.keys())
    value_lists = [parsed[k] for k in keys]
    return [dict(zip(keys, combo, strict=True)) for combo in product(*value_lists)]


# ---------------------------------------------------------------------------
# Single-variant runner (real implementation)
# ---------------------------------------------------------------------------


def _real_runner(
    config_path: Path,
    signal_params_override: dict[str, Any],
    runs_root: Path,
    sweep_id: str,
    data_root: Path,
) -> dict:
    """Run one backtest variant and return a summary dict.

    This is the real implementation used by the CLI.  Tests inject their own
    callable via the ``runner`` parameter of ``run_sweep()``.

    Supports three dispatch paths (same as the ``backtest`` CLI command):
    - YAML template  — config has an ``entry:`` block; overrides go into ``knobs``.
    - Registered template — config has a ``template:`` key.
    - Python module  — config has a ``signal_module:`` key; overrides go into ``signal_params``.
    """
    import pandas as pd

    from trading_research.backtest.engine import BacktestConfig, BacktestEngine
    from trading_research.backtest.fills import FillModel
    from trading_research.backtest.signals import SignalFrame
    from trading_research.data.instruments import load_instrument
    from trading_research.eval.summary import compute_summary
    from trading_research.replay.data import DataNotFoundError, _find_parquet

    cfg_raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    strategy_id = cfg_raw["strategy_id"]
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    bt_cfg_raw = cfg_raw.get("backtest", {})

    has_entry = "entry" in cfg_raw
    template_name = cfg_raw.get("template")
    signal_module_path = cfg_raw.get("signal_module")

    dispatch_count = sum([has_entry, bool(template_name), bool(signal_module_path)])
    if dispatch_count == 0:
        raise ValueError(
            f"Config {config_path.name} must have one of 'entry', 'template', or 'signal_module'."
        )
    if dispatch_count > 1:
        raise ValueError(
            f"Config {config_path.name} may have only one of 'entry', 'template', or 'signal_module'."
        )

    fill_model_str = bt_cfg_raw.get("fill_model", "next_bar_open")
    fill_model = FillModel(fill_model_str)

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

    inst = load_instrument(symbol)

    feat_dir = data_root / "features"
    try:
        feat_path = _find_parquet(
            feat_dir,
            f"{symbol}_backadjusted_{timeframe}_features_*_*.parquet",
        )
    except DataNotFoundError as e:
        raise FileNotFoundError(
            f"No features parquet found for {symbol} {timeframe}: {e}"
        ) from e

    bars = pd.read_parquet(feat_path, engine="pyarrow")
    bars = bars.set_index("timestamp_utc")
    bars.index = pd.DatetimeIndex(bars.index, tz="UTC")
    bars = bars.sort_index()

    strategy_obj = None

    if has_entry:
        # YAML template: overrides patch into knobs before constructing strategy.
        from trading_research.strategies.template import YAMLStrategy

        merged_cfg = dict(cfg_raw)
        base_knobs = dict(cfg_raw.get("knobs", {}))
        merged_cfg["knobs"] = {**base_knobs, **signal_params_override}
        strategy_obj = YAMLStrategy.from_config(merged_cfg)
        signals_df = strategy_obj.generate_signals_df(bars)

    elif template_name:
        import contextlib
        import importlib as _il

        from trading_research.backtest.walkforward import _signals_to_dataframe
        from trading_research.core.instruments import InstrumentRegistry
        from trading_research.core.templates import _GLOBAL_REGISTRY

        template_module = cfg_raw.get("template_module")
        if template_module:
            try:
                _il.import_module(template_module)
            except ImportError as exc:
                raise ImportError(
                    f"Cannot import template_module '{template_module}': {exc}"
                ) from exc
        else:
            for _m in ["trading_research.strategies.vwap_reversion_v1"]:
                with contextlib.suppress(ImportError):
                    _il.import_module(_m)

        base_knobs = dict(cfg_raw.get("knobs", {}))
        merged_knobs = {**base_knobs, **signal_params_override}
        strategy_obj = _GLOBAL_REGISTRY.instantiate(template_name, merged_knobs)
        core_inst = InstrumentRegistry().get(symbol)
        raw_signals = strategy_obj.generate_signals(bars, bars, core_inst)
        signals_df = _signals_to_dataframe(raw_signals, bars.index)

    else:
        # Legacy Python signal_module path.
        mod = importlib.import_module(signal_module_path)
        base_params = cfg_raw.get("signal_params", {})
        merged_params = {**base_params, **signal_params_override}
        if merged_params:
            signals_df = mod.generate_signals(bars, **merged_params)
        else:
            signals_df = mod.generate_signals(bars)

    sf = SignalFrame(signals_df)
    sf.validate()

    engine = BacktestEngine(bt_config, inst, strategy=strategy_obj)
    result = engine.run(bars, signals_df)

    summary = compute_summary(result)

    # Write run artifacts.
    run_ts = datetime.now(tz=UTC).strftime("%Y-%m-%d-%H-%M")
    # Include sweep ID in the directory name for traceability.
    run_dir = runs_root / strategy_id / f"{run_ts}-sw{sweep_id[:6]}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result.trades.to_parquet(run_dir / "trades.parquet", engine="pyarrow", index=False)
    eq_df = result.equity_curve.reset_index()
    eq_df.columns = ["exit_ts", "equity_usd"]
    eq_df.to_parquet(run_dir / "equity_curve.parquet", engine="pyarrow", index=False)

    summary_out = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in summary.items()}
    summary_out["signal_params_override"] = signal_params_override
    summary_out["sweep_id"] = sweep_id
    (run_dir / "summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")

    return {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "signal_params_override": signal_params_override,
        "run_dir": run_dir,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Public sweep entrypoint
# ---------------------------------------------------------------------------


def run_sweep(
    config_path: Path,
    param_specs: list[str],
    runs_root: Path,
    data_root: Path,
    runner: Callable[..., dict] | None = None,
) -> list[dict]:
    """Run a parameter sweep and record all variants as exploration trials.

    Args:
        config_path: Path to the base strategy YAML.
        param_specs:  List of ``key=v1,v2,...`` strings.
        runs_root:    Directory for run artifacts and .trials.json.
        data_root:    Root of the data/ directory tree.
        runner:       Optional callable that replaces the real backtest runner.
                      Signature: ``runner(config_path, signal_params_override,
                      runs_root, sweep_id, data_root) -> dict``.
                      Used by tests to avoid real I/O.

    Returns:
        List of result dicts, one per combination (successful runs only).
    """
    from trading_research.eval.trials import record_trial

    combos = expand_params(param_specs)
    sweep_id = uuid.uuid4().hex[:8]
    actual_runner = runner if runner is not None else _real_runner

    results: list[dict] = []
    n = len(combos)
    logger.info(
        "sweep: starting",
        sweep_id=sweep_id,
        n_variants=n,
        config=str(config_path),
    )

    for i, combo in enumerate(combos, 1):
        logger.info("sweep: variant", index=i, total=n, params=combo)
        try:
            result = actual_runner(
                config_path,
                combo,
                runs_root,
                sweep_id,
                data_root,
            )
        except Exception as exc:
            logger.error(
                "sweep: variant failed",
                index=i,
                params=combo,
                error=str(exc),
            )
            continue

        summary = result.get("summary", {})
        sharpe = summary.get("sharpe", float("nan"))
        calmar = summary.get("calmar")
        max_dd = summary.get("max_drawdown_usd")
        win_rate = summary.get("win_rate")
        total_trades = summary.get("total_trades")
        strategy_id = result.get("strategy_id", "unknown")
        symbol = result.get("symbol")
        timeframe = result.get("timeframe")

        record_trial(
            runs_root=runs_root,
            strategy_id=strategy_id,
            config_path=config_path,
            sharpe=sharpe if sharpe is not None and not (isinstance(sharpe, float) and math.isnan(sharpe)) else float("nan"),
            trial_group=strategy_id,
            mode="exploration",
            parent_sweep_id=sweep_id,
            calmar=calmar if calmar is not None and not (isinstance(calmar, float) and math.isnan(calmar)) else None,
            max_drawdown_usd=max_dd if max_dd is not None and not (isinstance(max_dd, float) and math.isnan(max_dd)) else None,
            win_rate=win_rate if win_rate is not None and not (isinstance(win_rate, float) and math.isnan(win_rate)) else None,
            total_trades=total_trades if total_trades is not None else None,
            instrument=symbol,
            timeframe=timeframe,
        )

        result["sweep_id"] = sweep_id
        results.append(result)

    logger.info(
        "sweep: complete",
        sweep_id=sweep_id,
        successful=len(results),
        failed=n - len(results),
    )
    return results
