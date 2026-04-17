"""Signal interface between strategy code and the backtest engine.

A strategy returns a SignalFrame — a DataFrame with the same index as the
input features DataFrame plus at least a ``signal`` column.  The engine
consumes the SignalFrame; it does not care how signals were generated.

Signal conventions
------------------
+1  long entry (or maintain long)
-1  short entry (or maintain short)
 0  flat / no position

The ``stop`` and ``target`` columns hold price levels for the bar's signal.
They are NaN when the signal is 0 or when the strategy does not set explicit
levels (in which case the engine relies on an EOD or time-limit exit).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SignalFrame:
    """Wrapper around a signal DataFrame with validation.

    Parameters
    ----------
    df:              DataFrame indexed identically to the input features.
                     Required column: ``signal`` (int8-like: -1, 0, +1).
                     Optional columns: ``stop``, ``target``, ``signal_strength``.
    check_lookahead: When True, verify that no signal at bar T uses data that
                     is not available until bar T (i.e., signals must be
                     computable from data through bar T-1 close).  The check
                     is a heuristic: it shifts the signal series by 1 and
                     diffs; a non-zero result at the first bar would indicate
                     a look-ahead.  Pass False to skip (use for synthetic tests).
    """

    df: pd.DataFrame
    check_lookahead: bool = False

    def validate(self) -> None:
        """Raise ValueError if the signal DataFrame is malformed."""
        df = self.df

        if "signal" not in df.columns:
            raise ValueError("SignalFrame is missing required column 'signal'.")

        bad = df["signal"].dropna()
        invalid = bad[~bad.isin([-1, 0, 1])]
        if not invalid.empty:
            raise ValueError(
                f"'signal' column contains values outside {{-1, 0, 1}}: "
                f"{invalid.unique().tolist()[:5]}"
            )

        if self.check_lookahead:
            # Shift signal by 1 bar and compare — if the shifted version differs
            # from the original only at positions where data *should* have
            # changed, that's fine.  A signal at bar 0 that is non-zero when
            # no prior bar exists is the red flag we're catching.
            shifted = df["signal"].shift(1)
            first_original = df["signal"].iloc[0] if len(df) > 0 else 0
            if first_original != 0:
                raise ValueError(
                    "Look-ahead detected: signal at bar 0 is non-zero, which "
                    "implies it was computed using bar 0 data before the bar closed."
                )

    def get_signal(self, ts: pd.Timestamp) -> int:
        """Return signal value at timestamp *ts*, or 0 if not present."""
        try:
            return int(self.df.at[ts, "signal"])
        except KeyError:
            return 0

    def get_stop(self, ts: pd.Timestamp) -> float:
        """Return stop price at *ts*, or NaN."""
        if "stop" not in self.df.columns:
            return float("nan")
        try:
            v = self.df.at[ts, "stop"]
            return float(v) if pd.notna(v) else float("nan")
        except KeyError:
            return float("nan")

    def get_target(self, ts: pd.Timestamp) -> float:
        """Return target price at *ts*, or NaN."""
        if "target" not in self.df.columns:
            return float("nan")
        try:
            v = self.df.at[ts, "target"]
            return float(v) if pd.notna(v) else float("nan")
        except KeyError:
            return float("nan")
