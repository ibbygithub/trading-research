"""Walk-forward robustness runner.

For session 11, the fixture strategy is rule-based with fixed parameters,
so "training" is a no-op.  The walk-forward is purely a subperiod
robustness test: split the full dataset into n_folds contiguous windows,
purge gap_bars between train and test, embargo embargo_bars after test,
run the strategy on each test fold, aggregate the results.

When parameter-tuning strategies arrive (session 12+), the fit() hook
on the signal module will be called with train data before inference
on test data.

Usage (CLI)
-----------
    uv run trading-research walkforward --strategy configs/strategies/zn_macd_pullback.yaml

Usage (Python)
--------------
    from trading_research.backtest.walkforward import run_walkforward
    summary = run_walkforward("configs/strategies/zn_macd_pullback.yaml")
"""

from __future__ import annotations

import importlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog

from trading_research.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from trading_research.backtest.fills import FillModel
from trading_research.backtest.signals import SignalFrame
from trading_research.eval.summary import compute_summary

log = structlog.get_logger(__name__)


@dataclass
class FoldResult:
    """Results from a single walk-forward fold."""

    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_bars: int
    test_bars: int
    result: BacktestResult
    metrics: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metrics = compute_summary(self.result)


@dataclass
class WalkForwardSummary:
    """Aggregated walk-forward results."""

    folds: list[FoldResult]
    per_fold_metrics: pd.DataFrame       # one row per fold
    oos_equity: pd.Series                # concatenated OOS equity curve
    oos_trades: pd.DataFrame             # all OOS trades in order
    aggregated_metrics: dict             # metrics on the full OOS trade log


def run_walkforward(
    config_path: str | Path,
    n_folds: int = 10,
    gap_bars: int = 100,
    embargo_bars: int = 50,
    data_root: Path | None = None,
    trial_group: str | None = None,
) -> WalkForwardSummary:
    """Run a purged walk-forward over the full dataset.

    Parameters
    ----------
    config_path:    Path to strategy YAML config.
    n_folds:        Number of contiguous folds.
    gap_bars:       Bars purged between train end and test start.
    embargo_bars:   Bars embargoed after test end before next train.
    data_root:      Override the default data/ directory.
    trial_group:    Optional trial group tag for the trials registry.

    Returns
    -------
    WalkForwardSummary with per-fold results and aggregated OOS metrics.
    """
    import yaml
    from trading_research.data.instruments import load_instrument

    config_path = Path(config_path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Strategy config not found: {config_path}")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    strategy_id = cfg["strategy_id"]
    symbol = cfg["symbol"]
    timeframe = cfg.get("timeframe", "5m")
    signal_module_path = cfg["signal_module"]
    bt_cfg_raw = cfg.get("backtest", {})
    signal_params = cfg.get("signal_params", {})
    feature_set = cfg.get("feature_set", "base-v1")

    _data_root = data_root or (Path(__file__).parents[3] / "data")

    # --- Load features ---
    from trading_research.replay.data import DataNotFoundError, _find_parquet

    feat_dir = _data_root / "features"
    feat_path = _find_parquet(
        feat_dir,
        f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet",
    )
    log.info("walkforward.loading_features", path=str(feat_path))
    bars = pd.read_parquet(feat_path, engine="pyarrow")
    bars = bars.set_index("timestamp_utc")
    bars.index = pd.DatetimeIndex(bars.index, tz="UTC")
    bars = bars.sort_index()

    # --- Load instrument ---
    inst = load_instrument(symbol)

    # --- Load signal module ---
    try:
        mod = importlib.import_module(signal_module_path)
    except ImportError as e:
        raise ImportError(f"Cannot import signal_module '{signal_module_path}': {e}") from e

    # --- Build backtest config ---
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

    # --- Split dataset into folds ---
    n_bars = len(bars)
    fold_size = n_bars // n_folds

    if fold_size < gap_bars + embargo_bars + 20:
        raise ValueError(
            f"Fold size ({fold_size} bars) too small for gap={gap_bars} "
            f"and embargo={embargo_bars}. Reduce n_folds or gap/embargo."
        )

    fold_results: list[FoldResult] = []

    for fold_k in range(1, n_folds):
        # Train: folds 0..k-1
        train_end_bar = fold_k * fold_size - 1
        test_start_bar = train_end_bar + 1 + gap_bars
        test_end_bar = (fold_k + 1) * fold_size - 1 - embargo_bars
        test_end_bar = min(test_end_bar, n_bars - 1)

        if test_start_bar >= test_end_bar:
            log.warning("walkforward.fold_skipped", fold=fold_k,
                        reason="test window too small after gap/embargo")
            continue

        train_bars_df = bars.iloc[: train_end_bar + 1]
        test_bars_df = bars.iloc[test_start_bar : test_end_bar + 1]

        log.info(
            "walkforward.fold",
            fold=fold_k,
            train_bars=len(train_bars_df),
            test_bars=len(test_bars_df),
            test_start=str(test_bars_df.index[0].date()),
            test_end=str(test_bars_df.index[-1].date()),
        )

        # For rule-based strategies, training is a no-op.
        # If the module exposes `fit(bars, **params)`, call it on train data.
        if hasattr(mod, "fit") and len(train_bars_df) > 0:
            mod.fit(train_bars_df, **signal_params)

        # Generate signals on test fold.
        if signal_params:
            signals_df = mod.generate_signals(test_bars_df, **signal_params)
        else:
            signals_df = mod.generate_signals(test_bars_df)

        sf = SignalFrame(signals_df)
        sf.validate()

        engine = BacktestEngine(bt_config, inst)
        result = engine.run(test_bars_df, signals_df)

        fold_result = FoldResult(
            fold=fold_k,
            train_start=bars.index[0],
            train_end=train_bars_df.index[-1] if len(train_bars_df) > 0 else bars.index[0],
            test_start=test_bars_df.index[0],
            test_end=test_bars_df.index[-1],
            train_bars=len(train_bars_df),
            test_bars=len(test_bars_df),
            result=result,
        )
        fold_results.append(fold_result)

    if not fold_results:
        raise ValueError("No folds completed — check n_folds, gap_bars, embargo_bars settings.")

    # --- Aggregate OOS results ---
    oos_trades_list = [f.result.trades for f in fold_results if not f.result.trades.empty]
    if oos_trades_list:
        oos_trades = pd.concat(oos_trades_list, ignore_index=True)
        oos_trades = oos_trades.sort_values("entry_ts").reset_index(drop=True)
    else:
        oos_trades = pd.DataFrame()

    # Build OOS equity curve from concatenated trades.
    if not oos_trades.empty:
        oos_equity = oos_trades["net_pnl_usd"].cumsum()
        oos_equity.index = pd.to_datetime(oos_trades["exit_ts"])
    else:
        oos_equity = pd.Series(dtype=float)

    # Aggregate metrics on the full OOS trade log.
    if not oos_trades.empty:
        from trading_research.backtest.engine import BacktestResult
        oos_result = BacktestResult(
            trades=oos_trades,
            equity_curve=oos_equity,
            config=bt_config,
            symbol_meta={},
        )
        aggregated_metrics = compute_summary(oos_result)
    else:
        aggregated_metrics = {}

    # --- Per-fold metrics table ---
    rows = []
    for f in fold_results:
        m = f.metrics
        rows.append({
            "fold": f.fold,
            "test_start": f.test_start,
            "test_end": f.test_end,
            "test_bars": f.test_bars,
            "trades": m.get("total_trades", 0),
            "win_rate": m.get("win_rate", float("nan")),
            "calmar": m.get("calmar", float("nan")),
            "sharpe": m.get("sharpe", float("nan")),
            "expectancy_usd": m.get("expectancy_usd", float("nan")),
            "max_dd_usd": m.get("max_drawdown_usd", float("nan")),
            "profit_factor": m.get("profit_factor", float("nan")),
        })
    per_fold_metrics = pd.DataFrame(rows)

    summary = WalkForwardSummary(
        folds=fold_results,
        per_fold_metrics=per_fold_metrics,
        oos_equity=oos_equity,
        oos_trades=oos_trades,
        aggregated_metrics=aggregated_metrics,
    )

    log.info(
        "walkforward.complete",
        n_folds=len(fold_results),
        oos_trades=len(oos_trades),
    )
    return summary


def write_walkforward_outputs(
    wf: WalkForwardSummary,
    run_dir: Path,
) -> tuple[Path, Path]:
    """Write walk-forward results to run_dir.

    Parameters
    ----------
    wf:      WalkForwardSummary from run_walkforward().
    run_dir: Target directory (e.g. runs/<strategy_id>/<ts>/).

    Returns
    -------
    (walkforward_parquet, walkforward_equity_parquet)
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    wf_path = run_dir / "walkforward.parquet"
    wf_equity_path = run_dir / "walkforward_equity.parquet"

    wf.per_fold_metrics.to_parquet(wf_path, engine="pyarrow", index=False)

    if not wf.oos_equity.empty:
        eq_df = wf.oos_equity.reset_index()
        eq_df.columns = ["exit_ts", "equity_usd"]
        eq_df.to_parquet(wf_equity_path, engine="pyarrow", index=False)
    else:
        pd.DataFrame(columns=["exit_ts", "equity_usd"]).to_parquet(
            wf_equity_path, engine="pyarrow", index=False
        )

    return wf_path, wf_equity_path
