"""Shared helpers for indicator tests."""

from __future__ import annotations

import pandas as pd
import pytest


def assert_no_lookahead(fn, df: pd.DataFrame, n_warmup: int = 50, **kwargs) -> None:
    """Verify an indicator has no look-ahead bias.

    Compute the indicator on the full ``df``, then on ``df[:n_warmup+1]``.
    The last value of the partial computation must equal the full series at
    position ``n_warmup``.  If they differ, the indicator is reading future data.

    Works for both Series and DataFrame indicators.
    """
    full = fn(df, **kwargs)
    partial = fn(df.iloc[: n_warmup + 1], **kwargs)

    if isinstance(full, pd.Series):
        full_val = full.iloc[n_warmup]
        part_val = partial.iloc[-1]
        if pd.isna(full_val) and pd.isna(part_val):
            return
        assert full_val == pytest.approx(part_val, rel=1e-6), (
            f"Look-ahead detected: full[{n_warmup}]={full_val}, partial[-1]={part_val}"
        )
    elif isinstance(full, pd.DataFrame):
        for col in full.columns:
            full_val = full[col].iloc[n_warmup]
            part_val = partial[col].iloc[-1]
            if pd.isna(full_val) and pd.isna(part_val):
                continue
            if pd.isna(full_val) or pd.isna(part_val):
                assert False, (
                    f"Look-ahead in col '{col}': full={full_val}, partial={part_val}"
                )
            assert float(full_val) == pytest.approx(float(part_val), rel=1e-5), (
                f"Look-ahead in col '{col}': full[{n_warmup}]={full_val}, "
                f"partial[-1]={part_val}"
            )


def make_ohlcv(
    n: int = 200,
    start: str = "2024-01-03 23:00:00+00:00",
    close_start: float = 110.0,
    close_step: float = 0.015625,
    volume: int = 500,
    buy_vol_frac: float = 0.5,
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame for indicator tests."""
    ts = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    closes = [close_start + i * close_step for i in range(n)]
    highs = [c + 0.015625 for c in closes]
    lows = [c - 0.015625 for c in closes]
    opens = closes[:]

    bvol = int(volume * buy_vol_frac)
    svol = volume - bvol

    return pd.DataFrame(
        {
            "timestamp_utc": ts,
            "timestamp_ny": ts.tz_convert("America/New_York"),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volume,
            "buy_volume": bvol,
            "sell_volume": svol,
            "up_ticks": 10,
            "down_ticks": 10,
            "total_ticks": 20,
        }
    )
