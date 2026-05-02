"""Backtest simulation engine.

Design principles
-----------------
- Walk forward bar-by-bar (iterate, not vectorize).  Clarity over speed at
  this stage — the simulation must be auditable.
- Next-bar-open fills by default.  SAME_BAR requires an explicit justification
  string in BacktestConfig.
- Pessimistic TP/SL resolution (stop wins when both are inside a bar's range).
- EOD flat: close all open positions at the last bar of each session.
- MAE/MFE tracked from fill bar to exit bar inclusive.

Usage
-----
    cfg = BacktestConfig(strategy_id="my-strat", symbol="6E")
    result = BacktestEngine(cfg, instrument_spec).run(bars_df, signals_df)
    result.trades          # pd.DataFrame conforming to TRADE_SCHEMA
    result.equity_curve    # pd.Series of cumulative net_pnl_usd
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import time

import pandas as pd
import structlog

from trading_research.backtest.fills import FillModel, apply_fill, resolve_exit
from trading_research.core.strategies import PortfolioContext, Signal, Strategy
from trading_research.data.instruments import InstrumentSpec
from trading_research.data.schema import TRADE_SCHEMA, Trade

log = structlog.get_logger(__name__)


@dataclass
class BacktestConfig:
    strategy_id: str
    symbol: str
    fill_model: FillModel = FillModel.NEXT_BAR_OPEN
    # Required (non-empty) when fill_model is SAME_BAR — documents the reason.
    same_bar_justification: str = ""
    max_holding_bars: int | None = None
    eod_flat: bool = True
    use_ofi_resolution: bool = False
    quantity: int = 1

    def __post_init__(self) -> None:
        if self.fill_model == FillModel.SAME_BAR and not self.same_bar_justification.strip():
            raise ValueError(
                "same_bar_justification must be non-empty when fill_model is SAME_BAR. "
                "Document why same-bar fills are appropriate for this strategy."
            )
        if self.quantity < 1:
            raise ValueError("quantity must be >= 1.")


@dataclass
class BacktestResult:
    trades: pd.DataFrame        # conforms to TRADE_SCHEMA
    equity_curve: pd.Series     # cumulative net_pnl_usd indexed by exit_ts (UTC)
    config: BacktestConfig
    symbol_meta: dict           # raw dict from instruments.yaml


class BacktestEngine:
    """Run a strategy signal DataFrame through the bar data and produce a trade log."""

    def __init__(
        self,
        config: BacktestConfig,
        instrument: InstrumentSpec,
        strategy: Strategy | None = None,
        core_instrument: object | None = None,
    ) -> None:
        self._cfg = config
        self._inst = instrument
        self._strategy = strategy
        self._core_instrument = core_instrument

        bd = instrument.backtest_defaults
        self._slippage_ticks = bd.slippage_ticks
        self._commission_per_side = bd.commission_usd
        self._tick_size = instrument.tick_size
        self._tick_value = instrument.tick_value_usd
        self._point_value = instrument.point_value_usd

        # Parse session close time for EOD flat.
        rth_close: time = instrument.session.rth.close

        # Use a sentinel (None) when eod_flat is disabled so comparisons skip.
        self._session_close: time | None = rth_close if config.eod_flat else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        bars: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> BacktestResult:
        """Simulate the strategy.

        Parameters
        ----------
        bars:    Feature DataFrame.  Must have columns: open, high, low, close,
                 and optionally buy_volume, sell_volume.  Index must be a
                 tz-aware UTC DatetimeIndex.
        signals: Signal DataFrame with same index.  Must have a ``signal``
                 column.  Optional: ``stop``, ``target``.

        Returns
        -------
        BacktestResult with completed trades and equity curve.
        """
        cfg = self._cfg
        completed: list[dict] = []

        # Position state
        in_position = False
        direction: int = 0
        entry_trigger_ts: pd.Timestamp | None = None
        entry_ts: pd.Timestamp | None = None
        entry_price: float = 0.0
        stop: float = float("nan")
        target: float = float("nan")
        bars_held: int = 0
        mae_low: float = float("inf")   # track worst adverse low from entry
        mfe_high: float = float("-inf") # track best favourable high from entry
        position_qty: int = cfg.quantity  # per-trade quantity

        bar_list = list(bars.itertuples())
        n = len(bar_list)

        for i, bar in enumerate(bar_list):
            ts = bar.Index
            bar_s = bars.iloc[i]  # Series for helper functions

            # ----------------------------------------------------------
            # 1. If in a position: check for exit conditions.
            # ----------------------------------------------------------
            if in_position:
                bars_held += 1

                # Track MAE/MFE (use full bar range regardless of exit).
                mae_low = min(mae_low, float(bar.low))
                mfe_high = max(mfe_high, float(bar.high))

                # Check EOD flat: is this bar at or past session close?
                eod_triggered = self._is_eod(bar_s)

                # Check time limit.
                time_limit_triggered = (
                    cfg.max_holding_bars is not None
                    and bars_held >= cfg.max_holding_bars
                )

                if eod_triggered or time_limit_triggered:
                    exit_reason = "eod" if eod_triggered else "time_limit"
                    exit_trigger_ts = ts
                    exit_ts = ts
                    exit_price = self._exit_fill(bar_s, direction)
                    trade = self._close_trade(
                        direction, entry_trigger_ts, entry_ts, entry_price,
                        exit_trigger_ts, exit_ts, exit_price, exit_reason,
                        stop, target, mae_low, mfe_high,
                        qty=position_qty,
                    )
                    completed.append(trade)
                    in_position = False
                    continue

                # Check TP/SL.
                exit_reason, resolved_price = resolve_exit(
                    bar_s, direction, stop, target,
                    use_ofi=cfg.use_ofi_resolution,
                )

                if exit_reason in ("stop", "target"):
                    # Exit triggered inside this bar.
                    exit_trigger_ts = ts
                    exit_ts = ts
                    exit_price = resolved_price
                    trade = self._close_trade(
                        direction, entry_trigger_ts, entry_ts, entry_price,
                        exit_trigger_ts, exit_ts, exit_price, exit_reason,
                        stop, target, mae_low, mfe_high,
                        qty=position_qty,
                    )
                    completed.append(trade)
                    in_position = False
                    continue

                # Check signal reversal / exit signal.
                sig = int(signals.at[ts, "signal"]) if ts in signals.index else 0
                if sig != 0 and sig != direction:
                    # Opposing signal — exit this position.
                    exit_trigger_ts = ts
                    next_bar_s = bars.iloc[i + 1] if i + 1 < n else bar_s
                    exit_ts = next_bar_s.name
                    exit_price = self._entry_fill(bar_s, next_bar_s, direction * -1)
                    # Correction: use fill against current direction.
                    exit_price = apply_fill(
                        bar_s, next_bar_s, cfg.fill_model, -direction,
                        self._slippage_ticks, self._tick_size,
                    )
                    trade = self._close_trade(
                        direction, entry_trigger_ts, entry_ts, entry_price,
                        exit_trigger_ts, exit_ts, exit_price, "signal",
                        stop, target, mae_low, mfe_high,
                        qty=position_qty,
                    )
                    completed.append(trade)
                    in_position = False
                    # Fall through: we may immediately enter a new position
                    # on the same signal in the block below.

            # ----------------------------------------------------------
            # 2. If not in a position: check for entry signal.
            # ----------------------------------------------------------
            if not in_position:
                sig = int(signals.at[ts, "signal"]) if ts in signals.index else 0
                if sig != 0:
                    entry_direction = sig
                    entry_trigger_ts = ts

                    # Entry fills on next bar (NEXT_BAR_OPEN default).
                    if i + 1 >= n:
                        # No next bar — discard this signal.
                        continue

                    next_bar_s = bars.iloc[i + 1]
                    fill_price = apply_fill(
                        bar_s, next_bar_s, cfg.fill_model, entry_direction,
                        self._slippage_ticks, self._tick_size,
                    )
                    entry_ts = next_bar_s.name
                    entry_price = fill_price
                    direction = entry_direction
                    stop = self._get_level(signals, ts, "stop")

                    # Guard: NaN stop means this is an exit-only signal
                    # (e.g. MACD zero-cross close). Skip entry — do not open
                    # a new position without a defined risk level.
                    if math.isnan(stop):
                        continue

                    target = self._get_level(signals, ts, "target")

                    # Size the position via Strategy.size_position if available.
                    if self._strategy is not None:
                        from decimal import Decimal
                        sig_obj = Signal(
                            timestamp=ts.to_pydatetime(),
                            direction="long" if entry_direction == 1 else "short",
                            strength=float(signals.at[ts, "signal_strength"])
                                if "signal_strength" in signals.columns
                                else 1.0,
                            metadata={
                                "stop": stop,
                                "target": target,
                            },
                        )
                        ctx = PortfolioContext(
                            open_positions=[],
                            account_equity=Decimal("25000"),
                            daily_pnl=Decimal("0"),
                        )
                        position_qty = self._strategy.size_position(
                            sig_obj, ctx, self._core_instrument,
                        )
                        if position_qty == 0:
                            log.info(
                                "engine.trade_suppressed",
                                reason="size_position returned 0",
                                ts=str(ts),
                            )
                            continue
                    else:
                        position_qty = cfg.quantity

                    bars_held = 0
                    mae_low = fill_price
                    mfe_high = fill_price
                    in_position = True

        # ----------------------------------------------------------
        # 3. Force-close any still-open position at end of data.
        # ----------------------------------------------------------
        if in_position:
            last_bar_s = bars.iloc[-1]
            exit_price = float(last_bar_s["close"])
            trade = self._close_trade(
                direction, entry_trigger_ts, entry_ts, entry_price,
                bars.index[-1], bars.index[-1], exit_price, "eod",
                stop, target, mae_low, mfe_high,
                qty=position_qty,
            )
            completed.append(trade)

        trades_df = self._to_dataframe(completed)
        equity_curve = self._build_equity_curve(trades_df)

        return BacktestResult(
            trades=trades_df,
            equity_curve=equity_curve,
            config=cfg,
            symbol_meta={
                "symbol": self._inst.root_symbol,
                "tick_size": self._inst.tick_size,
                "tick_value_usd": self._inst.tick_value_usd,
                "point_value_usd": self._inst.point_value_usd,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_eod(self, bar: pd.Series) -> bool:
        """True if this bar is at or past the RTH session close."""
        if self._session_close is None:
            return False
        # Use timestamp_ny if present, otherwise convert index.
        if "timestamp_ny" in bar.index:
            ts_ny = bar["timestamp_ny"]
        else:
            idx = bar.name
            if hasattr(idx, "tz_convert"):
                ts_ny = idx.tz_convert("America/New_York")
            else:
                ts_ny = pd.Timestamp(idx).tz_localize("UTC").tz_convert("America/New_York")
        bar_time = ts_ny.time() if hasattr(ts_ny, "time") else ts_ny
        return bar_time >= self._session_close

    def _entry_fill(
        self, signal_bar: pd.Series, next_bar: pd.Series, direction: int
    ) -> float:
        return apply_fill(
            signal_bar, next_bar, self._cfg.fill_model, direction,
            self._slippage_ticks, self._tick_size,
        )

    def _exit_fill(self, bar: pd.Series, direction: int) -> float:
        """EOD / time-limit exit fills at the current bar's close."""
        slip = self._slippage_ticks * self._tick_size
        # Exit is adverse: long exits lower, short exits higher.
        return float(bar["close"]) - direction * slip

    @staticmethod
    def _get_level(signals: pd.DataFrame, ts: pd.Timestamp, col: str) -> float:
        if col not in signals.columns:
            return float("nan")
        try:
            v = signals.at[ts, col]
            return float(v) if pd.notna(v) else float("nan")
        except KeyError:
            return float("nan")

    def _close_trade(
        self,
        direction: int,
        entry_trigger_ts: pd.Timestamp,
        entry_ts: pd.Timestamp,
        entry_price: float,
        exit_trigger_ts: pd.Timestamp,
        exit_ts: pd.Timestamp,
        exit_price: float,
        exit_reason: str,
        initial_stop: float,
        initial_target: float,
        mae_low: float,
        mfe_high: float,
        qty: int | None = None,
    ) -> dict:
        cfg = self._cfg
        qty = qty if qty is not None else cfg.quantity

        pnl_points = direction * (exit_price - entry_price)
        pnl_usd = pnl_points * self._point_value * qty

        slip_usd = self._slippage_ticks * self._tick_value * 2 * qty
        comm_usd = self._commission_per_side * 2 * qty
        net_pnl_usd = pnl_usd - slip_usd - comm_usd

        # MAE/MFE in points relative to entry.
        if direction == 1:
            mae_points = direction * (mae_low - entry_price)   # negative = adverse
            mfe_points = direction * (mfe_high - entry_price)  # positive = favourable
        else:
            mae_points = direction * (mfe_high - entry_price)  # short: high is adverse
            mfe_points = direction * (mae_low - entry_price)   # short: low is favourable

        return {
            "trade_id": str(uuid.uuid4()),
            "strategy_id": cfg.strategy_id,
            "symbol": cfg.symbol,
            "direction": "long" if direction == 1 else "short",
            "quantity": qty,
            "entry_trigger_ts": entry_trigger_ts,
            "entry_ts": entry_ts,
            "entry_price": entry_price,
            "exit_trigger_ts": exit_trigger_ts,
            "exit_ts": exit_ts,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "initial_stop": None if (isinstance(initial_stop, float) and math.isnan(initial_stop)) else initial_stop,
            "initial_target": None if (isinstance(initial_target, float) and math.isnan(initial_target)) else initial_target,
            "pnl_points": pnl_points,
            "pnl_usd": pnl_usd,
            "slippage_usd": slip_usd,
            "commission_usd": comm_usd,
            "net_pnl_usd": net_pnl_usd,
            "mae_points": mae_points,
            "mfe_points": mfe_points,
        }

    @staticmethod
    def _to_dataframe(records: list[dict]) -> pd.DataFrame:
        if not records:
            import pyarrow as pa
            from trading_research.data.schema import TRADE_SCHEMA
            return TRADE_SCHEMA.empty_table().to_pandas()  # type: ignore[attr-defined]

        df = pd.DataFrame(records)
        for col in ("entry_trigger_ts", "entry_ts", "exit_trigger_ts", "exit_ts"):
            df[col] = pd.to_datetime(df[col], utc=True)
        return df

    @staticmethod
    def _build_equity_curve(trades_df: pd.DataFrame) -> pd.Series:
        if trades_df.empty:
            return pd.Series(dtype=float, name="equity_usd")
        curve = trades_df.set_index("exit_ts")["net_pnl_usd"].sort_index().cumsum()
        curve.name = "equity_usd"
        return curve
