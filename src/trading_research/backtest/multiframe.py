"""Look-ahead-safe higher-timeframe feature join.

When a YAML strategy references columns from a higher timeframe (e.g. 60m EMA
as a bias filter for a 5m entry strategy), the higher-TF data must be joined
without leaking future information into the primary bars.

Design
------
Bar timestamps represent the bar **open** time.  A 60m bar with timestamp
12:00 UTC covers 12:00–13:00 and its indicator values (e.g. EMA computed at
bar close) are only final at 13:00.  A 5m bar at 12:05 must NOT see that 60m
bar — the bar is still open at that point.

Prevention: shift the HTF DataFrame by 1 bar before joining.  After the shift:
  - The 60m entry at 13:00 carries the data that was at 12:00 (the bar that
    opened at 12:00 and closed at 13:00).
  - A merge_asof backward join then assigns this value to all 5m bars in the
    range [13:00, 14:00), i.e. bars that fall within the *next* 60m period.

This matches the "shift-then-forward-fill" pattern already used in the
htf_projections layer of the feature pipeline (base-v1.yaml).

Public API
----------
``join_htf(primary, htf, prefix)`` — the sole public function.

Column naming
-------------
All HTF columns are prefixed with ``{prefix}_``.  Metadata columns
(``timestamp_ny``, ``trade_date``) are excluded from the join.  The joined
columns are available to ExprEvaluator expressions in the strategy YAML —
no code changes required.

Example in a strategy YAML::

    higher_timeframes:
      - 60m

    entry:
      long:
        all:
          - "close < vwap_session - entry_atr_mult * atr_14"
          - "60m_ema_20 > 60m_ema_50"     # HTF bias: uptrend only
"""

from __future__ import annotations

import pandas as pd
import structlog

log = structlog.get_logger(__name__)

# Columns that are never useful as HTF features on the primary index.
_SKIP_COLS: frozenset[str] = frozenset({"timestamp_ny", "trade_date"})


def safe_prefix(timeframe: str) -> str:
    """Return a valid Python-identifier prefix for *timeframe*.

    Column names must be valid Python identifiers so ``ExprEvaluator`` can
    parse them from expressions.  A timeframe like ``"60m"`` starts with a
    digit and is therefore not a valid identifier.  This function prepends
    ``"tf"`` when needed::

        safe_prefix("60m")   → "tf60m"
        safe_prefix("240m")  → "tf240m"
        safe_prefix("1D")    → "tf1D"
        safe_prefix("daily") → "daily"    (already valid — unchanged)

    Strategy YAML files should use the output of this function when
    referencing HTF columns in expressions::

        - "tf60m_ema_20 > tf60m_ema_50"   # 60m EMA bias
    """
    if timeframe and timeframe[0].isdigit():
        return f"tf{timeframe}"
    return timeframe


def join_htf(
    primary: pd.DataFrame,
    htf: pd.DataFrame,
    prefix: str,
) -> pd.DataFrame:
    """Join higher-timeframe features onto *primary* with look-ahead prevention.

    Parameters
    ----------
    primary:
        Primary-timeframe features DataFrame.  Index must be a tz-aware
        ``DatetimeIndex`` (UTC), named ``timestamp_utc`` or unnamed.
    htf:
        Higher-timeframe features DataFrame.  Same index convention.
        Must have more bars per unit time than *primary* (60m onto 5m, etc.).
    prefix:
        Column-name prefix for all joined HTF columns.  Convention: use the
        timeframe string, e.g. ``"60m"`` or ``"1D"``.

    Returns
    -------
    pd.DataFrame
        Copy of *primary* with additional columns ``{prefix}_{col}`` for every
        HTF column not in ``_SKIP_COLS``.  Rows with no available HTF bar yet
        (i.e. bars before the first HTF bar) will have ``NaN`` in the new
        columns — these are warm-up bars and should be treated as untradeable
        (``ExprEvaluator`` comparisons return ``False`` on ``NaN`` series).

    Raises
    ------
    ValueError
        If *primary* or *htf* does not have a tz-aware ``DatetimeIndex``.
    """
    _validate_index(primary, "primary")
    _validate_index(htf, "htf")

    # Filter out metadata columns that have no meaning on the primary index.
    data_cols = [c for c in htf.columns if c not in _SKIP_COLS]
    htf_data = htf[data_cols]

    # Shift HTF by 1 bar: bar at T now carries data that was at T-1 (the
    # prior completed bar).  After this shift the value at timestamp T is
    # safe to project onto any primary bar whose timestamp >= T.
    htf_shifted = htf_data.shift(1)

    # Prefix columns.
    htf_shifted = htf_shifted.add_prefix(f"{prefix}_")

    # merge_asof (backward) fills each primary bar with the most recent HTF
    # row whose timestamp is <= the primary bar's timestamp.
    primary_reset = primary.reset_index()    # timestamp_utc → column
    htf_reset = htf_shifted.reset_index()   # timestamp_utc → column

    key_col = primary_reset.columns[0]  # preserves actual index name

    merged = pd.merge_asof(
        primary_reset.sort_values(key_col),
        htf_reset.sort_values(key_col),
        on=key_col,
        direction="backward",
    )

    result = merged.set_index(key_col)
    result.index = pd.DatetimeIndex(result.index, tz="UTC")
    result.index.name = key_col

    htf_col_count = len(htf_shifted.columns)
    log.debug(
        "multiframe.join_htf",
        prefix=prefix,
        primary_bars=len(primary),
        htf_bars=len(htf),
        columns_added=htf_col_count,
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_index(df: pd.DataFrame, label: str) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            f"{label} DataFrame must have a DatetimeIndex; "
            f"got {type(df.index).__name__}"
        )
    if df.index.tz is None:
        raise ValueError(
            f"{label} DataFrame index must be tz-aware (UTC expected); "
            "found naive DatetimeIndex."
        )
