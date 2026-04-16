"""Example (always-flat) strategy.

Used only to verify the engine runs end-to-end without a real signal generator.
Returns all-zero signals so no trades are ever placed.

Every real strategy module must expose:
    generate_signals(df: pd.DataFrame) -> pd.DataFrame

The returned DataFrame must have the same index as *df* and include at minimum:
    signal          int8-like: +1 long, -1 short, 0 flat
    stop            float: stop price (NaN when signal == 0)
    target          float: target price (NaN when signal == 0)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Return an all-zero signal frame — no trades, no levels."""
    return pd.DataFrame(
        {
            "signal": np.zeros(len(df), dtype=np.int8),
            "stop": np.full(len(df), np.nan),
            "target": np.full(len(df), np.nan),
        },
        index=df.index,
    )
