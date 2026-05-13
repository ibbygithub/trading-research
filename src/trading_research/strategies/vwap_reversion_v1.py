"""VWAP Reversion v1 — template-based intraday mean reversion.

Designed for 6E (Euro FX) but parameterised for any instrument with a
VWAP-spread feature set.  Entry when price deviates beyond
entry_threshold_atr × ATR from session VWAP during the configured entry
window.  Vol-targeting position sizing.  Exits via target band, stop,
max hold, or hard session flatten.

Session 29: first template-registered strategy in the project.
Session 31: regime filter layer added via ``regime_filters`` knob.
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from trading_research.core.strategies import (
    ExitDecision,
    PortfolioContext,
    Position,
    Signal,
)
from trading_research.core.templates import register_template
from trading_research.strategies.regime import RegimeFilterChain, build_filter

if TYPE_CHECKING:
    from trading_research.core.instruments import Instrument


class VWAPReversionV1Knobs(BaseModel):
    entry_threshold_atr: float = Field(2.2, ge=1.0, le=4.0)
    exit_target_atr: float = Field(0.3, ge=0.0, le=1.5)
    stop_loss_atr: float = Field(2.5, ge=1.0, le=5.0)
    max_hold_bars: int = Field(60, ge=1, le=240)
    entry_window_start_utc: time = time(12, 0)
    entry_window_end_utc: time = time(17, 0)
    entry_blackout_minutes_after_session_open: int = Field(60, ge=0, le=240)
    flatten_offset_minutes_before_settlement: int = Field(0, ge=0, le=60)
    blackout_minutes_before_release: int = Field(30, ge=0, le=120)
    feature_set: str = "base-v1"
    # Regime filter names to chain (AND-of-filters). Empty = no filter.
    # Supported: "volatility-regime"
    regime_filters: list[str] = Field(default_factory=list)
    # Knob passed through to VolatilityRegimeFilter when "volatility-regime"
    # is included in regime_filters.
    vol_percentile_threshold: float = Field(75.0, ge=50.0, le=95.0)
    # Mulligan scale-in knobs (session 32).
    # mulligan_n_atr: gate width — scale-in rejected if more than n_atr×ATR
    #   worse than original entry.  Sweep {0.3, 0.5, 1.0, 1.5} in session 33.
    # mulligan_target_atr: combined target as ATR multiples from avg entry.
    mulligan_enabled: bool = False
    mulligan_n_atr: float = Field(0.3, ge=0.0, le=5.0)
    mulligan_max_scale_ins: int = Field(1, ge=1, le=3)
    mulligan_target_atr: float = Field(0.3, ge=0.0, le=3.0)


@register_template(
    name="vwap-reversion-v1",
    human_description="Intraday VWAP mean reversion with extended hold window.",
    knobs_model=VWAPReversionV1Knobs,
    supported_instruments=["6E"],
    supported_timeframes=["5m", "15m"],
)
class VWAPReversionV1:
    def __init__(self, *, knobs: VWAPReversionV1Knobs, template_name: str) -> None:
        self._knobs = knobs
        self._template_name = template_name
        # Build regime filter chain from knobs. Filters must be fit before
        # generate_signals is called (see fit_filters()).
        if knobs.regime_filters:
            filter_kwargs: dict[str, object] = {}
            if "volatility-regime" in knobs.regime_filters:
                filter_kwargs["vol_percentile_threshold"] = knobs.vol_percentile_threshold
            self._filter_chain: RegimeFilterChain | None = RegimeFilterChain([
                build_filter(name, **filter_kwargs if name == "volatility-regime" else {})
                for name in knobs.regime_filters
            ])
        else:
            self._filter_chain = None

    @property
    def name(self) -> str:
        return f"{self._template_name}-instance"

    @property
    def template_name(self) -> str:
        return self._template_name

    @property
    def knobs(self) -> dict:
        return self._knobs.model_dump()

    def fit_filters(self, train_features: pd.DataFrame) -> None:
        """Fit regime filters on *train_features* (training window only).

        Must be called before ``generate_signals()`` when ``regime_filters``
        is non-empty.  In rolling walk-forward, call once per fold with the
        training window before evaluating the test window.

        No-op when no regime filters are configured.
        """
        if self._filter_chain is not None:
            self._filter_chain.fit(train_features)

    def generate_signals(
        self,
        bars: pd.DataFrame,
        features: pd.DataFrame,
        instrument: Instrument,
    ) -> list[Signal]:
        k = self._knobs
        required = ["close", "vwap_session", "atr_14"]
        missing = [c for c in required if c not in features.columns]
        if missing:
            raise KeyError(f"Missing required feature columns: {missing}")

        close = features["close"].to_numpy(dtype=float)
        vwap = features["vwap_session"].to_numpy(dtype=float)
        atr = features["atr_14"].to_numpy(dtype=float)

        vwap_spread = close - vwap
        spread_over_atr = np.where(atr > 0, vwap_spread / atr, 0.0)

        idx = features.index
        minutes_utc = idx.hour * 60 + idx.minute
        window_start = k.entry_window_start_utc.hour * 60 + k.entry_window_start_utc.minute
        window_end = k.entry_window_end_utc.hour * 60 + k.entry_window_end_utc.minute
        in_window = (minutes_utc >= window_start) & (minutes_utc < window_end)

        # Session-open blackout: suppress entries in the first N minutes after
        # the session opens.  For FX (session_open_et=18:00, blackout=60),
        # the blackout window is 18:00–19:00 ET.  Bars at 08:00 ET the next
        # morning are well past the blackout.
        session_open_et = instrument.session_open_et
        session_open_minutes = session_open_et.hour * 60 + session_open_et.minute
        idx_et = idx.tz_convert("America/New_York")
        minutes_et = idx_et.hour * 60 + idx_et.minute
        blackout_end = session_open_minutes + k.entry_blackout_minutes_after_session_open
        if blackout_end <= 24 * 60:
            in_blackout = (minutes_et >= session_open_minutes) & (minutes_et < blackout_end)
        else:
            blackout_end_wrapped = blackout_end - 24 * 60
            in_blackout = (minutes_et >= session_open_minutes) | (minutes_et < blackout_end_wrapped)
        past_blackout = ~in_blackout

        signals: list[Signal] = []
        n = len(features)

        for i in range(n):
            if not in_window[i] or not past_blackout[i]:
                continue
            if not np.isfinite(spread_over_atr[i]) or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            # Regime filter: short-circuit when any filter rejects this bar.
            if self._filter_chain is not None and not self._filter_chain.is_tradeable(features, i):
                continue

            ts = idx[i]
            z = spread_over_atr[i]

            if z < -k.entry_threshold_atr:
                stop_price = close[i] - k.stop_loss_atr * atr[i]
                target_price = vwap[i] + k.exit_target_atr * atr[i]
                signals.append(Signal(
                    timestamp=ts.to_pydatetime(),
                    direction="long",
                    strength=abs(z),
                    metadata={
                        "vwap_spread_z": float(z),
                        "stop": float(stop_price),
                        "target": float(target_price),
                    },
                ))
            elif z > k.entry_threshold_atr:
                stop_price = close[i] + k.stop_loss_atr * atr[i]
                target_price = vwap[i] - k.exit_target_atr * atr[i]
                signals.append(Signal(
                    timestamp=ts.to_pydatetime(),
                    direction="short",
                    strength=abs(z),
                    metadata={
                        "vwap_spread_z": float(z),
                        "stop": float(stop_price),
                        "target": float(target_price),
                    },
                ))

        return signals

    def size_position(
        self,
        signal: Signal,
        context: PortfolioContext,
        instrument: Instrument,
    ) -> int:
        equity = float(context.account_equity)
        if equity <= 0:
            return 0

        stop_price = signal.metadata.get("stop")
        target_price = signal.metadata.get("target")
        if stop_price is None or target_price is None:
            return 1

        risk_points = abs(target_price - stop_price)
        if risk_points <= 0:
            return 1

        tick_size = float(instrument.tick_size)
        tick_value = float(instrument.tick_value_usd)
        point_value = tick_value / tick_size

        estimated_entry = float(stop_price) + risk_points if signal.direction == "long" else float(stop_price) - risk_points
        stop_risk = abs(estimated_entry - float(stop_price)) * point_value
        if stop_risk <= 0:
            return 1

        target_risk_pct = 0.01
        max_contracts = int(equity * target_risk_pct / stop_risk)
        return max(max_contracts, 1)

    def exit_rules(
        self,
        position: Position,
        current_bar: pd.Series,
        instrument: Instrument,
    ) -> ExitDecision:
        if not self._knobs.mulligan_enabled:
            return ExitDecision(action="hold", reason="engine handles TP/SL/EOD")

        close = float(current_bar.get("close", float("nan")))
        vwap = float(current_bar.get("vwap_session", float("nan")))
        atr = float(current_bar.get("atr_14", float("nan")))

        if not (np.isfinite(close) and np.isfinite(vwap) and np.isfinite(atr) and atr > 0):
            return ExitDecision(action="hold", reason="engine handles TP/SL/EOD")

        z = (close - vwap) / atr
        k = self._knobs

        if position.direction == "long" and z < -k.entry_threshold_atr:
            return ExitDecision(action="scale_in", reason="second_vwap_deviation")
        if position.direction == "short" and z > k.entry_threshold_atr:
            return ExitDecision(action="scale_in", reason="second_vwap_deviation")

        return ExitDecision(action="hold", reason="engine handles TP/SL/EOD")
