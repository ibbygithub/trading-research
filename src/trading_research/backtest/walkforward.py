"""Walk-forward backtest runner.

Supports two strategy instantiation paths:

1. **Template path** (new, session 29+): YAML config has ``template:`` field.
   Strategy is instantiated via ``TemplateRegistry``, signals come from
   ``strategy.generate_signals(bars, features, instrument)``.

2. **Legacy path**: YAML config has ``signal_module:`` field.  Strategy is a
   bare module with a ``generate_signals(bars, **params)`` function.
   Maintained for existing ZN configs; will be deprecated in sprint 38.

A config with both ``template:`` and ``signal_module:`` is rejected.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import structlog
import yaml

from trading_research.backtest.engine import BacktestConfig, BacktestEngine
from trading_research.backtest.fills import FillModel
from trading_research.backtest.signals import SignalFrame
from trading_research.core.strategies import Signal
from trading_research.data.instruments import load_instrument
from trading_research.eval.summary import compute_summary

log = structlog.get_logger(__name__)


@dataclass
class WalkforwardResult:
    per_fold_metrics: pd.DataFrame
    aggregated_metrics: dict
    aggregated_trades: pd.DataFrame
    aggregated_equity: pd.Series


def _signals_to_dataframe(signals: list[Signal], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Convert list[Signal] from a Strategy template to the engine's signal DataFrame."""
    signal_arr = np.zeros(len(index), dtype=np.int8)
    stop_arr = np.full(len(index), np.nan)
    target_arr = np.full(len(index), np.nan)

    ts_to_idx = {ts: i for i, ts in enumerate(index)}
    for sig in signals:
        ts = pd.Timestamp(sig.timestamp)
        if ts in ts_to_idx:
            i = ts_to_idx[ts]
            signal_arr[i] = 1 if sig.direction == "long" else -1
            if "stop" in sig.metadata:
                stop_arr[i] = sig.metadata["stop"]
            if "target" in sig.metadata:
                target_arr[i] = sig.metadata["target"]

    return pd.DataFrame(
        {"signal": signal_arr, "stop": stop_arr, "target": target_arr},
        index=index,
    )


def run_walkforward(
    config_path: Path,
    n_folds: int = 10,
    gap_bars: int = 100,
    embargo_bars: int = 50,
    data_root: Optional[Path] = None,
    trial_group: Optional[str] = None,
) -> WalkforwardResult:
    # 1. Parse config
    cfg_raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    strategy_id = cfg_raw["strategy_id"]
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    bt_cfg_raw = cfg_raw.get("backtest", {})
    feature_set = cfg_raw.get("feature_set", "base-v1")

    template_name = cfg_raw.get("template")
    signal_module_path = cfg_raw.get("signal_module")

    if template_name and signal_module_path:
        raise ValueError(
            f"Config {config_path} has both 'template' and 'signal_module'. "
            "Use one or the other."
        )
    if not template_name and not signal_module_path:
        raise ValueError(
            f"Config {config_path} must have either 'template' or 'signal_module'."
        )

    use_template = template_name is not None

    fill_model = FillModel(bt_cfg_raw.get("fill_model", "next_bar_open"))
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

    # 2. Load data
    from trading_research.replay.data import _find_parquet
    feat_dir = (data_root or Path("data")) / "features"
    feat_path = _find_parquet(feat_dir, f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet")
    bars = pd.read_parquet(feat_path, engine="pyarrow")
    bars = bars.set_index("timestamp_utc")
    bars.index = pd.DatetimeIndex(bars.index, tz="UTC")
    bars = bars.sort_index()

    start_date = bt_cfg_raw.get("start_date")
    end_date = bt_cfg_raw.get("end_date")
    if start_date:
        bars = bars[bars.index >= pd.Timestamp(start_date, tz="UTC")]
    if end_date:
        bars = bars[bars.index <= pd.Timestamp(end_date, tz="UTC")]

    # 3. Generate signals for the entire dataset
    if use_template:
        from trading_research.core.instruments import InstrumentRegistry
        from trading_research.core.templates import _GLOBAL_REGISTRY

        # Ensure the strategy module is imported so @register_template fires.
        _ensure_template_imported(template_name)

        knobs = cfg_raw.get("knobs", {})
        strategy = _GLOBAL_REGISTRY.instantiate(template_name, knobs)

        core_registry = InstrumentRegistry()
        core_inst = core_registry.get(symbol)

        signal_list = strategy.generate_signals(bars, bars, core_inst)
        signals_df = _signals_to_dataframe(signal_list, bars.index)
        log.info(
            "walkforward.template_signals",
            template=template_name,
            n_signals=len(signal_list),
        )
    else:
        mod = importlib.import_module(signal_module_path)
        signal_params = cfg_raw.get("signal_params", {})
        signals_df = mod.generate_signals(bars, **signal_params)

    sf = SignalFrame(signals_df)
    sf.validate()

    # 4. Split and run folds.
    #
    # Layout:
    #   [fold_0_test][gap_bars][embargo_bars][fold_1_test][gap_bars][embargo_bars]...
    #
    # gap_bars:    hard buffer between adjacent test folds; these bars are
    #              excluded from evaluation entirely to prevent boundary leakage.
    # embargo_bars: additional bars at the start of each test fold (after the gap)
    #              that are excluded from the fold's evaluation window. For
    #              rules-based strategies this is conservative; for ML-augmented
    #              strategies it prevents autocorrelation leakage from prior fold.
    #
    # For a rules-based strategy neither parameter changes what the engine
    # learns (there is no learning), but they ensure fold boundaries don't
    # overlap and that the reported per-fold metrics reflect only bars with
    # meaningful temporal separation from adjacent folds.

    total_buffer_per_fold = gap_bars + embargo_bars
    usable_bars = len(bars) - total_buffer_per_fold * (n_folds - 1)
    if usable_bars < n_folds * 10:
        raise ValueError(
            f"gap_bars={gap_bars} + embargo_bars={embargo_bars} consume too much of the "
            f"dataset ({len(bars)} bars, {n_folds} folds). Reduce gap/embargo or increase data."
        )
    fold_size = usable_bars // n_folds
    all_trades = []
    fold_metrics = []

    for k in range(n_folds):
        if k == 0:
            start_idx = 0
        else:
            start_idx = k * (fold_size + total_buffer_per_fold) + embargo_bars

        end_idx = start_idx + fold_size if k < n_folds - 1 else len(bars)
        end_idx = min(end_idx, len(bars))

        if start_idx >= end_idx:
            continue

        fold_bars = bars.iloc[start_idx:end_idx]

        engine = BacktestEngine(bt_config, inst)
        res = engine.run(fold_bars, signals_df)

        sm = compute_summary(res)
        sm["fold"] = k + 1
        sm["test_start"] = fold_bars.index[0]
        sm["test_bars"] = len(fold_bars)
        sm["trades"] = len(res.trades)

        fold_metrics.append(sm)
        if not res.trades.empty:
            all_trades.append(res.trades)

    pf_df = pd.DataFrame(fold_metrics)

    if all_trades:
        agg_trades = pd.concat(all_trades, ignore_index=True)
        agg_trades = agg_trades.sort_values("exit_ts")
        agg_eq = agg_trades.set_index("exit_ts")["net_pnl_usd"].cumsum()

        agg_res = BacktestEngine(bt_config, inst).run(bars.iloc[:1], signals_df.iloc[:1])
        agg_res.trades = agg_trades
        agg_res.equity_curve = agg_eq
        agg_metrics = compute_summary(agg_res)
    else:
        agg_trades = pd.DataFrame()
        agg_eq = pd.Series(dtype=float)
        agg_metrics = {}

    return WalkforwardResult(pf_df, agg_metrics, agg_trades, agg_eq)


def _ensure_template_imported(template_name: str) -> None:
    """Import the strategy module that registers the template, if needed."""
    from trading_research.core.templates import _GLOBAL_REGISTRY

    try:
        _GLOBAL_REGISTRY.get(template_name)
    except KeyError:
        # Convention: template "vwap-reversion-v1" lives in
        # trading_research.strategies.vwap_reversion_v1
        module_name = f"trading_research.strategies.{template_name.replace('-', '_')}"
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            raise KeyError(
                f"Template {template_name!r} not found in registry and could "
                f"not auto-import from {module_name!r}: {exc}"
            ) from exc


def write_walkforward_outputs(wf: WalkforwardResult, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    wf_path = out_dir / "walkforward.parquet"
    eq_path = out_dir / "walkforward_equity.parquet"

    wf.per_fold_metrics.to_parquet(wf_path, engine="pyarrow", index=False)

    if not wf.aggregated_equity.empty:
        eq_df = wf.aggregated_equity.reset_index()
        eq_df.columns = ["exit_ts", "equity_usd"]
        eq_df.to_parquet(eq_path, engine="pyarrow", index=False)
    else:
        pd.DataFrame(columns=["exit_ts", "equity_usd"]).to_parquet(eq_path, engine="pyarrow", index=False)

    return wf_path, eq_path
