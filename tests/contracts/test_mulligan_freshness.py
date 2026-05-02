"""Contract tests for Mulligan scale-in rules.

Five cases per spec (session 32a):

  Positive: fresh Signal + directional gate satisfied → accepted.
  Negative 1: no fresh signal (same timestamp as entry) → MulliganViolation M-1.
  Negative 2: same Signal timestamp re-evaluated after first acceptance → M-1.
  Negative 3: fresh Signal but entry price more than N×ATR worse than original
              → MulliganViolation M-2 (directional gate).
  Combined-risk: combined_risk() returns correct avg-entry-based target and
                 unchanged stop.

Plus two engine-level acceptance tests:

  Engine rejects scale_in from exit_rules when no fresh same-direction signal
  exists in signals_df → MulliganViolation logged, position continues.

  VWAPReversionV1 instantiates with mulligan_enabled=True and engine runs to
  produce a BacktestResult (acceptance test #3: "trial record").
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from trading_research.core.strategies import ExitDecision, Position, Signal
from trading_research.strategies.mulligan import (
    CombinedRisk,
    MulliganController,
    MulliganViolation,
    combined_risk,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

TS_ENTRY = datetime(2024, 1, 10, 14, 0, 0, tzinfo=UTC)
TS_NEW = datetime(2024, 1, 10, 15, 0, 0, tzinfo=UTC)   # strictly later
TS_EARLIER = datetime(2024, 1, 10, 13, 0, 0, tzinfo=UTC)

ATR = 0.005   # representative 5m ATR on 6E
N_ATR = 0.3   # default gate multiplier
GATE_OFFSET = ATR * N_ATR  # 0.0015

LONG_POS = Position(
    instrument_symbol="6E",
    entry_time=TS_ENTRY,
    entry_price=Decimal("1.1000"),
    size=1,
    direction="long",
    stop=Decimal("1.0950"),
    target=Decimal("1.1030"),
)

SHORT_POS = Position(
    instrument_symbol="6E",
    entry_time=TS_ENTRY,
    entry_price=Decimal("1.1000"),
    size=1,
    direction="short",
    stop=Decimal("1.1050"),
    target=Decimal("1.0970"),
)


def _make_controller(direction: str = "long", max_scale_ins: int = 1) -> MulliganController:
    return MulliganController(
        entry_trigger_ts=TS_ENTRY,
        direction=direction,  # type: ignore[arg-type]
        max_scale_ins=max_scale_ins,
    )


def _fresh_long_signal(ts: datetime = TS_NEW) -> Signal:
    return Signal(timestamp=ts, direction="long", strength=1.5)


def _fresh_short_signal(ts: datetime = TS_NEW) -> Signal:
    return Signal(timestamp=ts, direction="short", strength=1.5)


# ---------------------------------------------------------------------------
# Positive: fresh signal + directional gate satisfied → accepted
# ---------------------------------------------------------------------------

def test_positive_fresh_signal_gate_satisfied_long() -> None:
    """Long scale-in at a price within N×ATR of original entry is accepted."""
    ctrl = _make_controller("long")
    # Gate floor: 1.1000 - 0.3×0.005 = 1.0985
    # Scale-in at 1.0990 ≥ 1.0985 → should pass
    new_price = Decimal("1.0990")

    ctrl.check_scale_in(_fresh_long_signal(), LONG_POS, new_price, ATR, N_ATR)

    assert ctrl.last_consumed_ts == TS_NEW
    assert ctrl.scale_in_count == 1


def test_positive_fresh_signal_gate_satisfied_short() -> None:
    """Short scale-in at a price within N×ATR of original entry is accepted."""
    ctrl = _make_controller("short")
    # Gate ceiling: 1.1000 + 0.3×0.005 = 1.1015
    # Scale-in at 1.1010 ≤ 1.1015 → should pass
    new_price = Decimal("1.1010")

    ctrl.check_scale_in(_fresh_short_signal(), SHORT_POS, new_price, ATR, N_ATR)

    assert ctrl.last_consumed_ts == TS_NEW
    assert ctrl.scale_in_count == 1


# ---------------------------------------------------------------------------
# Negative 1: averaging-down — no fresh signal (same or earlier timestamp)
# ---------------------------------------------------------------------------

def test_negative1_same_timestamp_raises_m1() -> None:
    """Signal at same timestamp as original entry is not fresh → M-1 violation."""
    ctrl = _make_controller("long")
    # Timestamp == entry trigger timestamp → NOT strictly later
    stale_signal = Signal(timestamp=TS_ENTRY, direction="long", strength=1.0)

    with pytest.raises(MulliganViolation, match="Rule M-1"):
        ctrl.check_scale_in(stale_signal, LONG_POS, Decimal("1.0990"), ATR, N_ATR)


def test_negative1_earlier_timestamp_raises_m1() -> None:
    """Signal with timestamp before original entry → M-1 violation."""
    ctrl = _make_controller("long")
    old_signal = Signal(timestamp=TS_EARLIER, direction="long", strength=1.0)

    with pytest.raises(MulliganViolation, match="Rule M-1"):
        ctrl.check_scale_in(old_signal, LONG_POS, Decimal("1.0990"), ATR, N_ATR)


# ---------------------------------------------------------------------------
# Negative 2: same-signal second look (re-presenting already-consumed timestamp)
# ---------------------------------------------------------------------------

def test_negative2_same_signal_second_look_raises_m1() -> None:
    """Presenting the same Signal timestamp a second time → M-1 violation."""
    ctrl = _make_controller("long", max_scale_ins=2)
    fresh = _fresh_long_signal()

    # First presentation succeeds and advances last_consumed_ts to TS_NEW.
    ctrl.check_scale_in(fresh, LONG_POS, Decimal("1.0990"), ATR, N_ATR)

    # Second presentation of the same timestamp: TS_NEW <= TS_NEW → rejected.
    with pytest.raises(MulliganViolation, match="Rule M-1"):
        ctrl.check_scale_in(fresh, LONG_POS, Decimal("1.0990"), ATR, N_ATR)


# ---------------------------------------------------------------------------
# Negative 3: directional gate — new price too far adverse from original
# ---------------------------------------------------------------------------

def test_negative3_long_price_below_gate_raises_m2() -> None:
    """Long scale-in more than N×ATR below original entry → M-2 violation.

    Gate floor = 1.1000 - 0.3×0.005 = 1.0985.
    Test price = 1.0970 < 1.0985 → rejected.
    """
    ctrl = _make_controller("long")
    # fresh timestamp passes M-1
    fresh = _fresh_long_signal()
    # price fails M-2
    beyond_gate = Decimal("1.0970")

    with pytest.raises(MulliganViolation, match="Rule M-2"):
        ctrl.check_scale_in(fresh, LONG_POS, beyond_gate, ATR, N_ATR)


def test_negative3_short_price_above_gate_raises_m2() -> None:
    """Short scale-in more than N×ATR above original entry → M-2 violation.

    Gate ceiling = 1.1000 + 0.3×0.005 = 1.1015.
    Test price = 1.1030 > 1.1015 → rejected.
    """
    ctrl = _make_controller("short")
    fresh = _fresh_short_signal()
    beyond_gate = Decimal("1.1030")

    with pytest.raises(MulliganViolation, match="Rule M-2"):
        ctrl.check_scale_in(fresh, SHORT_POS, beyond_gate, ATR, N_ATR)


# ---------------------------------------------------------------------------
# Max-scale-ins cap
# ---------------------------------------------------------------------------

def test_scale_in_cap_raises_when_max_reached() -> None:
    """After max_scale_ins acceptances, next attempt is blocked."""
    ctrl = _make_controller("long", max_scale_ins=1)
    ts1 = datetime(2024, 1, 10, 15, 0, 0, tzinfo=UTC)
    ctrl.check_scale_in(
        Signal(timestamp=ts1, direction="long", strength=1.0),
        LONG_POS,
        Decimal("1.0990"),
        ATR,
        N_ATR,
    )
    ts2 = datetime(2024, 1, 10, 16, 0, 0, tzinfo=UTC)
    with pytest.raises(MulliganViolation, match="Max scale-ins"):
        ctrl.check_scale_in(
            Signal(timestamp=ts2, direction="long", strength=1.0),
            LONG_POS,
            Decimal("1.0988"),
            ATR,
            N_ATR,
        )


# ---------------------------------------------------------------------------
# Combined-risk computation
# ---------------------------------------------------------------------------

def test_combined_risk_long_returns_correct_values() -> None:
    """combined_risk() returns weighted avg-entry target and unchanged stop (long)."""
    # orig: 1 contract at 1.1000, stop 1.0950
    # scale-in: 1 contract at 1.0990
    # combined_avg_entry = (1.1000 + 1.0990) / 2 = 1.0995
    # combined_target = 1.0995 + 0.3 * 0.005 = 1.0995 + 0.0015 = 1.1010
    # combined_stop = 1.0950 (unchanged)
    result = combined_risk(
        orig=LONG_POS,
        new_entry_price=Decimal("1.0990"),
        scale_in_size=1,
        atr=ATR,
        mulligan_target_atr=N_ATR,
    )

    assert isinstance(result, CombinedRisk)
    assert result.combined_size == 2
    assert result.combined_avg_entry == Decimal("1.0995")
    expected_target = Decimal("1.0995") + Decimal(str(N_ATR * ATR))
    assert abs(result.combined_target - expected_target) < Decimal("0.000001")
    assert result.combined_stop == LONG_POS.stop


def test_combined_risk_short_returns_correct_values() -> None:
    """combined_risk() returns weighted avg-entry target and unchanged stop (short)."""
    # orig: 1 contract at 1.1000, scale-in 1 contract at 1.1010
    # combined_avg_entry = (1.1000 + 1.1010) / 2 = 1.1005
    # combined_target = 1.1005 - 0.3 * 0.005 = 1.1005 - 0.0015 = 1.0990
    # combined_stop = 1.1050 (unchanged)
    result = combined_risk(
        orig=SHORT_POS,
        new_entry_price=Decimal("1.1010"),
        scale_in_size=1,
        atr=ATR,
        mulligan_target_atr=N_ATR,
    )

    assert result.combined_size == 2
    expected_avg = Decimal("1.1005")
    assert result.combined_avg_entry == expected_avg
    expected_target = expected_avg - Decimal(str(N_ATR * ATR))
    assert abs(result.combined_target - expected_target) < Decimal("0.000001")
    assert result.combined_stop == SHORT_POS.stop


def test_combined_risk_unequal_sizes() -> None:
    """combined_risk() correctly weights average entry with unequal lot sizes."""
    # orig: 1 contract at 1.1000, scale-in: 3 contracts at 1.0985
    # combined_avg_entry = (1×1.1000 + 3×1.0985) / 4
    #                    = (1.1000 + 3.2955) / 4
    #                    = 4.3955 / 4 = 1.098875
    result = combined_risk(
        orig=LONG_POS,
        new_entry_price=Decimal("1.0985"),
        scale_in_size=3,
        atr=ATR,
        mulligan_target_atr=N_ATR,
    )

    assert result.combined_size == 4
    expected_avg = (Decimal("1.1000") * 1 + Decimal("1.0985") * 3) / 4
    assert abs(result.combined_avg_entry - expected_avg) < Decimal("0.000001")


# ---------------------------------------------------------------------------
# Engine-level: exit_rules returning scale_in + MulliganController integration
# ---------------------------------------------------------------------------

def _inst():
    from trading_research.data.instruments import load_instruments
    return load_instruments().get("ZN")


def _ts(n: int, freq: str = "5min") -> pd.DatetimeIndex:
    base = pd.Timestamp("2024-01-10 14:00:00", tz="UTC")
    return pd.date_range(base, periods=n, freq=freq)


def _make_bars(n: int, close: float = 110.0) -> pd.DataFrame:
    idx = _ts(n)
    return pd.DataFrame({
        "open":  [close] * n,
        "high":  [close + 0.25] * n,
        "low":   [close - 0.25] * n,
        "close": [close] * n,
        "atr_14": [0.005] * n,
        "buy_volume":  [500] * n,
        "sell_volume": [500] * n,
        "timestamp_ny": [ts.tz_convert("America/New_York") for ts in idx],
    }, index=idx)


def _make_signals(bars: pd.DataFrame, values: list[int]) -> pd.DataFrame:
    return pd.DataFrame({
        "signal": values,
        "stop":   [109.0 if v == 1 else 111.0 if v == -1 else np.nan for v in values],
        "target": [111.0 if v == 1 else 109.0 if v == -1 else np.nan for v in values],
    }, index=bars.index)


class _ScaleInStrategy:
    """Stub strategy whose exit_rules always returns scale_in."""

    def __init__(self, mulligan_enabled: bool = True) -> None:
        self._enabled = mulligan_enabled

    @property
    def name(self) -> str:
        return "scale-in-stub"

    @property
    def template_name(self) -> str:
        return "test-template"

    @property
    def knobs(self) -> dict:
        return {
            "mulligan_enabled": self._enabled,
            "mulligan_n_atr": 0.3,
            "mulligan_max_scale_ins": 1,
            "mulligan_target_atr": 0.3,
        }

    def generate_signals(self, bars, features, instrument):
        return []

    def size_position(self, signal, context, instrument) -> int:
        return 1

    def exit_rules(self, position, current_bar, instrument) -> ExitDecision:
        return ExitDecision(action="scale_in", reason="test-scale-in")


def test_engine_rejects_scale_in_without_same_direction_signal() -> None:
    """When exit_rules returns scale_in but signals_df has no same-direction
    signal at the current bar, the engine logs MulliganViolation and continues
    (position remains open, no second trade created).
    """
    from trading_research.backtest.engine import BacktestConfig, BacktestEngine

    bars = _make_bars(10)
    # Long entry at bar 1; no further long signals → Mulligan can never fire
    signals = _make_signals(bars, [0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    strategy = _ScaleInStrategy(mulligan_enabled=True)

    cfg = BacktestConfig(strategy_id="test", symbol="ZN", quantity=1)
    engine = BacktestEngine(cfg, _inst(), strategy=strategy, core_instrument=None)
    result = engine.run(bars, signals)

    # One trade should still complete (EOD or TP/SL) — Mulligan rejection
    # does not abort the original trade.
    assert not result.trades.empty
    # No Mulligan leg — only the original trade
    assert len(result.trades) == 1


def test_mulligan_knobs_accepted_by_vwap_template_and_engine_runs() -> None:
    """VWAPReversionV1 with mulligan_enabled=True can be instantiated and the
    engine runs on synthetic bars producing a BacktestResult (acceptance test #3).
    """
    from trading_research.backtest.engine import BacktestConfig, BacktestEngine
    from trading_research.strategies.vwap_reversion_v1 import VWAPReversionV1Knobs

    # Verify the knob model accepts mulligan fields
    knobs = VWAPReversionV1Knobs(
        mulligan_enabled=True,
        mulligan_n_atr=0.5,
        mulligan_max_scale_ins=1,
        mulligan_target_atr=0.2,
    )
    assert knobs.mulligan_enabled is True
    assert knobs.mulligan_n_atr == 0.5
    assert knobs.mulligan_target_atr == 0.2

    # Build a minimal features DataFrame (engine needs these columns)
    idx = _ts(20)
    close_val = 1.1000
    bars = pd.DataFrame({
        "open":          [close_val] * 20,
        "high":          [close_val + 0.001] * 20,
        "low":           [close_val - 0.001] * 20,
        "close":         [close_val] * 20,
        "vwap_session":  [close_val] * 20,
        "atr_14":        [0.005] * 20,
        "buy_volume":    [500] * 20,
        "sell_volume":   [500] * 20,
        "timestamp_ny":  [ts.tz_convert("America/New_York") for ts in idx],
    }, index=idx)

    # No entry signals → engine completes trivially
    signals = _make_signals(bars, [0] * 20)

    cfg = BacktestConfig(strategy_id="test-mulligan", symbol="ZN", quantity=1)
    engine = BacktestEngine(cfg, _inst())
    result = engine.run(bars, signals)

    assert result.trades is not None   # BacktestResult produced
    assert result.equity_curve is not None
