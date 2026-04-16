"""Fill model and TP/SL resolver for the backtest engine.

Fill model
----------
NEXT_BAR_OPEN (default): signal fires at bar T close; fill executes at
    bar T+1 open ± slippage.  This is the honest default — the strategy
    cannot have acted on T's close until T has closed.

SAME_BAR: fill at signal bar's close.  Only reachable with an explicit
    ``same_bar_justification`` in the strategy config.  The engine refuses
    to use SAME_BAR unless that field is non-empty.

TP/SL resolution
-----------------
``resolve_exit`` decides what happened inside a bar:
  - If only one level is inside the bar's range, that level hit.
  - If both are inside the range, the stop wins (pessimistic default).
  - If use_ofi=True and buy/sell volume data is present, the OFI ratio
    is used to infer which hit first.  If OFI data is missing, falls back
    to pessimistic with a logged warning.
"""

from __future__ import annotations

import math
from enum import Enum

import pandas as pd
import structlog

log = structlog.get_logger(__name__)


class FillModel(str, Enum):
    NEXT_BAR_OPEN = "next_bar_open"
    SAME_BAR = "same_bar"


def apply_fill(
    signal_bar: pd.Series,
    next_bar: pd.Series,
    model: FillModel,
    direction: int,
    slippage_ticks: int,
    tick_size: float,
) -> float:
    """Return the fill price for an entry or exit.

    Parameters
    ----------
    signal_bar:     The bar on which the signal fired (bar T).
    next_bar:       The following bar (bar T+1).  Unused for SAME_BAR.
    model:          NEXT_BAR_OPEN or SAME_BAR.
    direction:      +1 for long, -1 for short.
    slippage_ticks: Number of ticks of adverse slippage per side.
    tick_size:      Tick size in price units (e.g. 0.015625 for ZN).

    Returns
    -------
    Fill price (float).
    """
    slip = slippage_ticks * tick_size

    if model == FillModel.NEXT_BAR_OPEN:
        base = float(next_bar["open"])
    else:
        base = float(signal_bar["close"])

    # Long fills at a higher price (slippage against us); short at lower.
    return base + direction * slip


def resolve_exit(
    bar: pd.Series,
    direction: int,
    stop: float,
    target: float,
    use_ofi: bool = False,
) -> tuple[str, float]:
    """Determine what happened to an open position during *bar*.

    Parameters
    ----------
    bar:       The price bar being evaluated.
    direction: +1 long, -1 short.
    stop:      Stop price (NaN if not set).
    target:    Target price (NaN if not set).
    use_ofi:   When True, use buy_volume/sell_volume ratio to infer
               which level hit first when both are inside the bar range.

    Returns
    -------
    (exit_reason, exit_price) or ("open", bar.open) if neither triggered.
    """
    bar_high = float(bar["high"])
    bar_low = float(bar["low"])

    stop_nan = math.isnan(stop) if isinstance(stop, float) else stop is None
    target_nan = math.isnan(target) if isinstance(target, float) else target is None

    # When neither level is set, signal-driven exit: exit at open of this bar.
    if stop_nan and target_nan:
        return ("open", float(bar["open"]))

    # Determine if each level is inside this bar's range.
    if direction == 1:
        # Long: stop is below entry (triggered when low <= stop);
        #       target is above entry (triggered when high >= target).
        stop_hit = (not stop_nan) and bar_low <= stop
        target_hit = (not target_nan) and bar_high >= target
    else:
        # Short: stop is above entry (triggered when high >= stop);
        #        target is below entry (triggered when low <= target).
        stop_hit = (not stop_nan) and bar_high >= stop
        target_hit = (not target_nan) and bar_low <= target

    if stop_hit and target_hit:
        # Both inside range — this is the pessimistic resolution case.
        if use_ofi:
            result = _resolve_via_ofi(bar, direction, stop, target)
            if result is not None:
                return result
            # OFI data missing — fall back to pessimistic and warn.
            log.warning(
                "ofi_fallback_to_pessimistic",
                bar_ts=str(bar.name) if hasattr(bar, "name") else "unknown",
            )
        return ("stop", stop)

    if stop_hit:
        return ("stop", stop)

    if target_hit:
        return ("target", target)

    # Neither triggered — position carries to the next bar.
    return ("open", float("nan"))


def _resolve_via_ofi(
    bar: pd.Series,
    direction: int,
    stop: float,
    target: float,
) -> tuple[str, float] | None:
    """Use buy/sell volume ratio to infer which level hit first.

    Returns None if OFI data is unavailable.
    """
    buy_vol = bar.get("buy_volume") if hasattr(bar, "get") else None
    sell_vol = bar.get("sell_volume") if hasattr(bar, "get") else None

    # Treat zero or NaN as missing.
    try:
        bv = float(buy_vol)
        sv = float(sell_vol)
    except (TypeError, ValueError):
        return None

    if math.isnan(bv) or math.isnan(sv) or (bv + sv) == 0:
        return None

    # For a long position: if sell volume dominates (more selling),
    # the move was likely down first → stop hit first.
    # For a short position: if buy volume dominates, up first → stop hit first.
    ofi_ratio = (bv - sv) / (bv + sv)  # -1 = all selling, +1 = all buying

    if direction == 1:
        # Long: positive OFI (buying) → target hit first.
        if ofi_ratio > 0:
            return ("target", target)
        else:
            return ("stop", stop)
    else:
        # Short: negative OFI (selling) → target hit first.
        if ofi_ratio < 0:
            return ("target", target)
        else:
            return ("stop", stop)
