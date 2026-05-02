"""VolatilityRegimeFilter — gates entries during high-ATR regimes.

Market-structure justification (Path A, pre-committed in regime-filter-spec.md)
--------------------------------------------------------------------------------
When intraday ATR on 6E is in the top quartile of its training-window
distribution, directional event flows dominate OU mean-reversion dynamics.
This is the statistical correlate of the Hurst = 1.24 finding from sprint 30:
high-vol bars are where spread momentum is strongest and where reversion
entries are most likely to be pushed further before turning.

Real FX desks routinely suspend mean-reversion books during high-vol regimes.
The 75th-percentile (top-quartile) gate is a standard risk-management
partition, not a data-mined threshold.

Walk-forward usage
------------------
In rolling-fit walk-forward, call ``fit(train_features)`` ONCE per fold
(training window only), then use ``is_tradeable(test_features, idx)`` for
every bar in the test window.  The fitted ATR threshold reflects the training
period's vol distribution, not the test period's.

For non-walk-forward backtests the caller must call ``fit(features)`` before
signal generation.  The filter raises ``RuntimeError`` if ``is_tradeable()``
is called without a prior ``fit()``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_research.strategies.regime import register_filter


@register_filter("volatility-regime")
class VolatilityRegimeFilter:
    """Gate entries when realised ATR exceeds the P<threshold> of the training window.

    Parameters
    ----------
    vol_percentile_threshold:
        Structural threshold level.  Default 75 = top-quartile gate.
        Range [50, 95]; values outside this range are rejected at construction.
        This is a configuration knob — it should NOT be swept across values to
        maximise backtest metrics.  The pre-committed structural default is 75.
    atr_column:
        Name of the ATR column in the features DataFrame.  Default ``atr_14``.
    """

    def __init__(
        self,
        *,
        vol_percentile_threshold: float = 75.0,
        atr_column: str = "atr_14",
    ) -> None:
        if not (50.0 <= vol_percentile_threshold <= 95.0):
            raise ValueError(
                f"vol_percentile_threshold must be in [50, 95]; got {vol_percentile_threshold}"
            )
        self._percentile = vol_percentile_threshold
        self._atr_column = atr_column
        self._threshold: float | None = None

    @property
    def name(self) -> str:
        return f"volatility-regime(p{int(self._percentile)})"

    @property
    def is_fitted(self) -> bool:
        """True after ``fit()`` has been called at least once."""
        return self._threshold is not None

    @property
    def fitted_threshold(self) -> float | None:
        """The ATR threshold value computed by the last ``fit()`` call."""
        return self._threshold

    def fit(self, features: pd.DataFrame) -> None:
        """Compute the ATR threshold from *features* (training window).

        Stores ``P<vol_percentile_threshold>(atr_column)`` for use by
        ``is_tradeable()``.  Calling ``fit()`` again resets the threshold.

        Raises
        ------
        KeyError
            If ``atr_column`` is not present in *features*.
        ValueError
            If the ATR column is entirely NaN or empty.
        """
        if self._atr_column not in features.columns:
            raise KeyError(
                f"ATR column {self._atr_column!r} not found in features. "
                f"Available columns: {list(features.columns)}"
            )
        values = features[self._atr_column].dropna().to_numpy(dtype=float)
        if len(values) == 0:
            raise ValueError(
                f"fit() received an empty ATR series for column {self._atr_column!r}."
            )
        self._threshold = float(np.percentile(values, self._percentile))

    def is_tradeable(self, features: pd.DataFrame, idx: int) -> bool:
        """Return True if the bar at *idx* is in a low-vol (tradeable) regime.

        A bar is tradeable when ``atr_column[idx] <= fitted_threshold``.
        Bars with non-finite or non-positive ATR are treated as untradeable
        (conservative default — if we can't measure vol, we don't trade).

        Raises
        ------
        RuntimeError
            If called before ``fit()``.
        """
        if self._threshold is None:
            raise RuntimeError(
                f"{self.name}: fit() must be called before is_tradeable(). "
                "Pass training-window features to fit() first."
            )
        if self._atr_column not in features.columns:
            raise KeyError(
                f"ATR column {self._atr_column!r} not found in features."
            )
        atr_val = features[self._atr_column].iloc[idx]
        if not np.isfinite(atr_val) or atr_val <= 0:
            return False
        return float(atr_val) <= self._threshold
