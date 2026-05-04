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
    data_root: Path | None = None,
    trial_group: str | None = None,
    slippage_ticks: float | None = None,
    commission_rt_usd: float | None = None,
) -> WalkforwardResult:
    # 1. Parse config
    cfg_raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    strategy_id = cfg_raw["strategy_id"]
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    bt_cfg_raw = cfg_raw.get("backtest", {})
    feature_set = cfg_raw.get("feature_set", "base-v1")

    has_entry = "entry" in cfg_raw
    template_name = cfg_raw.get("template")
    signal_module_path = cfg_raw.get("signal_module")

    dispatch_count = sum([has_entry, bool(template_name), bool(signal_module_path)])
    if dispatch_count > 1:
        raise ValueError(
            f"Config {config_path} has more than one of 'entry', 'template', "
            "'signal_module'. Use exactly one."
        )
    if dispatch_count == 0:
        raise ValueError(
            f"Config {config_path} must have one of 'entry' (YAML template), "
            "'template' (registered template), or 'signal_module' (Python module)."
        )

    use_yaml_template = has_entry
    use_template = bool(template_name)

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
        slippage_ticks=slippage_ticks,
        commission_rt_usd=commission_rt_usd,
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
    if use_yaml_template:
        from trading_research.strategies.template import YAMLStrategy
        strategy = YAMLStrategy.from_config(cfg_raw)
        signals_df = strategy.generate_signals_df(bars)
        log.info(
            "walkforward.yaml_template_signals",
            strategy_id=strategy_id,
            n_signals=int((signals_df["signal"] != 0).sum()),
        )
    elif use_template:
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
        start_idx = 0 if k == 0 else k * (fold_size + total_buffer_per_fold) + embargo_bars

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


def run_rolling_walkforward(
    config_path: Path,
    train_months: int = 18,
    test_months: int = 6,
    embargo_bars: int = 576,
    data_root: Path | None = None,
    slippage_ticks: float | None = None,
    commission_rt_usd: float | None = None,
) -> WalkforwardResult:
    """True rolling-fit walk-forward for strategies with fitted filter parameters.

    Unlike ``run_walkforward`` (which runs signals on the entire dataset then
    splits), this function:

    1. Determines train/test fold boundaries (rolling windows).
    2. Per fold: calls ``strategy.fit_filters(train_features)`` to fit any
       regime filters on training data ONLY.
    3. Per fold: calls ``strategy.generate_signals(test_features, ...)`` to
       generate signals on the test window with the fitted filter.
    4. Per fold: runs the backtest engine on the test-window signals.
    5. Aggregates fold results as in ``run_walkforward``.

    This is the correct evaluation procedure when any strategy parameter
    (e.g. the volatility-regime ATR threshold) is fit on prior data.

    Parameters
    ----------
    config_path:
        YAML strategy config.  Must have a ``template:`` field.
    train_months:
        Length of the rolling training window in calendar months.
    test_months:
        Length of each test fold in calendar months.
    embargo_bars:
        Number of bars between the end of the training window and the
        start of the test window.  Prevents autocorrelation leakage.
    data_root:
        Root directory for data (default: ``Path("data")``).
    slippage_ticks, commission_rt_usd:
        Cost overrides; same semantics as ``run_walkforward``.
    """

    # Parse config
    cfg_raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    strategy_id = cfg_raw["strategy_id"]
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    bt_cfg_raw = cfg_raw.get("backtest", {})
    feature_set = cfg_raw.get("feature_set", "base-v1")
    template_name = cfg_raw.get("template")

    if not template_name:
        raise ValueError(
            f"run_rolling_walkforward requires a 'template:' field in {config_path}. "
            "Legacy signal_module configs are not supported."
        )

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
        slippage_ticks=slippage_ticks,
        commission_rt_usd=commission_rt_usd,
    )

    inst = load_instrument(symbol)

    # Load features
    from trading_research.replay.data import _find_parquet
    feat_dir = (data_root or Path("data")) / "features"
    feat_path = _find_parquet(
        feat_dir,
        f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet",
    )
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

    # Build instrument registry for strategy
    from trading_research.core.instruments import InstrumentRegistry
    from trading_research.core.templates import _GLOBAL_REGISTRY
    _ensure_template_imported(template_name)
    core_registry = InstrumentRegistry()
    core_inst = core_registry.get(symbol)
    knobs = cfg_raw.get("knobs", {})

    # Determine fold boundaries using calendar months (via pd.DateOffset)
    data_start = bars.index[0]
    data_end = bars.index[-1]

    # First test fold starts after the minimum training requirement
    fold_starts: list[pd.Timestamp] = []
    current = data_start + pd.DateOffset(months=train_months)
    while current + pd.DateOffset(months=test_months) <= data_end:
        fold_starts.append(current)
        current = current + pd.DateOffset(months=test_months)

    if not fold_starts:
        raise ValueError(
            f"Not enough data for rolling walk-forward. "
            f"Need >= {train_months + test_months} months; "
            f"data covers {data_start.date()} to {data_end.date()}."
        )

    log.info(
        "rolling_walkforward.start",
        template=template_name,
        train_months=train_months,
        test_months=test_months,
        embargo_bars=embargo_bars,
        n_folds=len(fold_starts),
    )

    all_trades: list[pd.DataFrame] = []
    fold_metrics: list[dict] = []

    for k, test_start in enumerate(fold_starts):
        # Rolling train window: always train_months before test_start
        train_start = test_start - pd.DateOffset(months=train_months)
        # Test window: test_months after test_start
        test_end = test_start + pd.DateOffset(months=test_months)

        train_bars = bars[(bars.index >= train_start) & (bars.index < test_start)]
        # Skip embargo_bars from the start of test window
        all_test_bars = bars[(bars.index >= test_start) & (bars.index < test_end)]
        if len(all_test_bars) <= embargo_bars:
            log.warning("rolling_walkforward.fold_too_small", fold=k + 1)
            continue
        test_bars = all_test_bars.iloc[embargo_bars:]

        if len(train_bars) < 100 or len(test_bars) < 10:
            log.warning(
                "rolling_walkforward.insufficient_bars",
                fold=k + 1,
                train_bars=len(train_bars),
                test_bars=len(test_bars),
            )
            continue

        # Fresh strategy instance per fold (ensures filter state is clean)
        strategy = _GLOBAL_REGISTRY.instantiate(template_name, knobs)

        # Fit regime filters on training window only
        if hasattr(strategy, "fit_filters"):
            strategy.fit_filters(train_bars)

        # Generate signals on test window
        signal_list = strategy.generate_signals(test_bars, test_bars, core_inst)
        signals_df = _signals_to_dataframe(signal_list, test_bars.index)

        sf = SignalFrame(signals_df)
        sf.validate()

        engine = BacktestEngine(bt_config, inst, strategy=strategy, core_instrument=core_inst)
        res = engine.run(test_bars, signals_df)

        sm = compute_summary(res)
        sm["fold"] = k + 1
        sm["test_start"] = test_bars.index[0]
        sm["test_end"] = test_bars.index[-1]
        sm["train_start"] = train_bars.index[0] if len(train_bars) > 0 else None
        sm["train_end"] = train_bars.index[-1] if len(train_bars) > 0 else None
        sm["test_bars"] = len(test_bars)
        sm["train_bars"] = len(train_bars)
        sm["trades"] = len(res.trades)

        # Capture fitted threshold if available (for reporting)
        if hasattr(strategy, "_filter_chain") and strategy._filter_chain is not None:
            thresholds = {}
            for f in strategy._filter_chain._filters:
                if hasattr(f, "fitted_threshold") and f.fitted_threshold is not None:
                    thresholds[f.name] = f.fitted_threshold
            sm["filter_thresholds"] = str(thresholds) if thresholds else None
        else:
            sm["filter_thresholds"] = None

        fold_metrics.append(sm)
        if not res.trades.empty:
            all_trades.append(res.trades)

        log.info(
            "rolling_walkforward.fold_done",
            fold=k + 1,
            test_start=str(test_bars.index[0].date()),
            test_end=str(test_bars.index[-1].date()),
            n_signals=len(signal_list),
            n_trades=len(res.trades),
            calmar=sm.get("calmar"),
        )

    pf_df = pd.DataFrame(fold_metrics)

    if all_trades:
        agg_trades = pd.concat(all_trades, ignore_index=True)
        agg_trades = agg_trades.sort_values("exit_ts")
        agg_eq = agg_trades.set_index("exit_ts")["net_pnl_usd"].cumsum()

        dummy_engine = BacktestEngine(bt_config, inst)
        agg_res = dummy_engine.run(bars.iloc[:1], signals_df.iloc[:1])
        agg_res.trades = agg_trades
        agg_res.equity_curve = agg_eq
        agg_metrics = compute_summary(agg_res)
    else:
        agg_trades = pd.DataFrame()
        agg_eq = pd.Series(dtype=float)
        agg_metrics = {}

    log.info(
        "rolling_walkforward.complete",
        n_folds=len(fold_metrics),
        total_trades=sum(m.get("trades", 0) for m in fold_metrics),
        agg_calmar=agg_metrics.get("calmar"),
    )

    return WalkforwardResult(pf_df, agg_metrics, agg_trades, agg_eq)


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
