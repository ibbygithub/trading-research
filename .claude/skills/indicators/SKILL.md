---
name: indicators
description: Use when implementing, computing, or modifying technical indicators (moving averages, MACD, RSI, Bollinger Bands, ATR, etc.), order-flow indicators (delta, cumulative delta, divergence, absorption), or mean-reversion-specific tools (Hurst exponent, half-life, z-scores, cointegration). Invoke when adding a new indicator to the project, when debugging unexpected indicator values, when computing indicators for a new dataset, or when designing strategies that depend on specific indicator implementations. This skill defines the canonical indicator implementations, their as-of correctness contracts, and how indicator values are stored and consumed downstream.
---

# Indicators

This skill owns the math and the implementations of indicators in the project. Its job is to make sure that every indicator is computed correctly, computed once, computed identically every time, and — most importantly — computed in a way that doesn't leak future information into past values.

The principle: **an indicator value at bar N must be computable using only data through bar N.** This is the as-of rule, and it's the difference between a strategy that works in backtest and one that works in production. Every indicator in this skill is implemented to satisfy this rule, and every indicator implementation has a unit test that explicitly verifies it.

The second principle: **indicators are infrastructure, not strategy.** An indicator is a number computed from bars. A strategy is a decision computed from indicators. Keeping these separate means the same indicator can serve multiple strategies, and bugs in indicator code get fixed once instead of being copy-pasted into every strategy that uses them.

## What this skill covers

- Trend indicators: SMA, EMA, MACD, ADX
- Mean reversion indicators: RSI, Bollinger Bands, Bollinger %B, z-score
- Volatility indicators: ATR, true range, realized volatility, Parkinson estimator
- Statistical tools: Hurst exponent, half-life of mean reversion (Ornstein-Uhlenbeck), Augmented Dickey-Fuller test
- Order flow indicators: bar delta, cumulative session delta, delta divergence, absorption
- Multi-instrument tools: rolling correlation, cointegration tests (Engle-Granger), spread z-score
- The as-of correctness contract and how to test for it
- The indicator output schema and how indicators are stored

## What this skill does NOT cover

- Strategy logic that uses indicators (see `backtesting`)
- Charting indicator values (see `charting`)
- Feature engineering for ML (see `feature-engineering`)
- The bar data the indicators are computed from (see `data-management`)

## The as-of correctness contract

Every indicator function in this project has the following contract:

> **Given a series of bars `[b_1, b_2, ..., b_N]`, the indicator value at position N is computed using only the bars at positions 1 through N. The value at position N MUST NOT depend on bars at positions N+1 or later.**

This is enforced two ways:

1. **By construction.** Indicator implementations are written to be causal — they only look backward. No `pd.Series.rolling(center=True)`, no `scipy.signal.savgol_filter` without explicit edge handling, no anything that uses future data even slightly.

2. **By test.** Every indicator has a unit test that verifies as-of correctness by computing the indicator on `bars[:N]` and comparing the last value to the value at position N when computed on the full series. They must be identical. This test is mandatory; an indicator without it doesn't get merged.

```python
# tests/test_indicators/test_asof_correctness.py
import pytest
from trading_research.indicators import ema, rsi, bollinger_bands, atr

@pytest.mark.parametrize("indicator_func,kwargs", [
    (ema, {"span": 20}),
    (rsi, {"period": 14}),
    (bollinger_bands, {"period": 20, "n_std": 2}),
    (atr, {"period": 14}),
    # ... every indicator goes here
])
def test_asof_correctness(indicator_func, kwargs, sample_bars):
    """Verify the indicator at position N matches when computed on bars[:N+1]."""
    full_result = indicator_func(sample_bars, **kwargs)

    # Test at multiple positions to catch off-by-one bugs
    for n in [50, 100, 200, 500]:
        partial_bars = sample_bars[:n + 1]
        partial_result = indicator_func(partial_bars, **kwargs)

        # The last value of partial_result must equal the n-th value of full_result
        if isinstance(full_result, dict):  # multi-output indicators like Bollinger
            for key in full_result:
                assert full_result[key][n] == partial_result[key][-1], \
                    f"As-of violation in {indicator_func.__name__}.{key} at position {n}"
        else:
            assert full_result[n] == partial_result[-1], \
                f"As-of violation in {indicator_func.__name__} at position {n}"
```

This test catches the most insidious bugs in technical analysis code: indicators that compute correctly in vectorized form but accidentally use future information through some operation the author didn't think about. If a new indicator passes this test, it's safe to use in backtests. If it fails, the implementation is wrong and gets rewritten before any strategy can use it.

## The indicator output schema

Indicators are computed from a bar dataset and produce a column (or columns) that align 1:1 with the input bars. The standard pattern:

```python
def ema(bars: pl.DataFrame, span: int, column: str = "close") -> pl.Series:
    """Exponential moving average of a column over `span` bars.

    Returns a polars Series of the same length as `bars`. The first
    `span - 1` values may be NaN depending on the warmup convention.
    """
```

For multi-output indicators (Bollinger Bands returns upper, middle, lower; MACD returns macd, signal, histogram), the function returns a polars DataFrame with named columns:

```python
def bollinger_bands(
    bars: pl.DataFrame,
    period: int = 20,
    n_std: float = 2.0,
    column: str = "close",
) -> pl.DataFrame:
    """Bollinger Bands. Returns DataFrame with columns: upper, middle, lower, pct_b."""
```

**Storage:** indicator values are not stored on disk by default. They're computed on demand from the clean bar data. The `data/features/` directory exists for cases where indicator computation is expensive enough to be worth caching, but most indicators are fast enough that recomputation is fine.

When indicators ARE cached to features, the file naming convention is:

```
data/features/ZN_1m_2020-01-01_2024-12-31_indicators.parquet
```

This file contains all the columns from the corresponding clean parquet plus the indicator columns. The indicator set is documented in a sibling JSON metadata file:

```json
{
  "source_parquet": "data/clean/ZN_1m_2020-01-01_2024-12-31.parquet",
  "indicators_added": [
    {"name": "ema_20", "function": "ema", "params": {"span": 20}},
    {"name": "ema_50", "function": "ema", "params": {"span": 50}},
    {"name": "rsi_14", "function": "rsi", "params": {"period": 14}},
    {"name": "bb_upper_20_2", "function": "bollinger_bands", "params": {"period": 20, "n_std": 2}, "output": "upper"},
    {"name": "bb_lower_20_2", "function": "bollinger_bands", "params": {"period": 20, "n_std": 2}, "output": "lower"}
  ],
  "computation_timestamp_utc": "2025-01-15T15:22:33Z"
}
```

This metadata is critical for reproducibility. Two months from now, "what indicators were on this dataset" should be answerable from the metadata file, not from inspecting the parquet schema.

## Trend indicators

**SMA (Simple Moving Average).** Vanilla. Mean of the last `period` bars. NaN for the first `period - 1` positions.

**EMA (Exponential Moving Average).** The standard formula `EMA[i] = alpha * close[i] + (1 - alpha) * EMA[i-1]` where `alpha = 2 / (span + 1)`. The first value is initialized to the close of the first bar (or to the SMA of the first `span` bars, depending on the convention). The default in this project is **the SMA of the first span bars** as the seed value, because it produces less startup distortion than seeding from the first bar alone.

**MACD (Moving Average Convergence Divergence).** Standard: 12-period EMA minus 26-period EMA, with a 9-period EMA of that difference as the signal line. The histogram is `macd - signal`. Returns three series.

**ADX (Average Directional Index).** Wilder's directional movement index. Used to measure trend strength independently of direction. Less commonly used in mean-reversion strategies, but included because it's the standard tool for the question "is this market trending or ranging right now?" — which is exactly the question a mean-reversion strategy should ask before taking a trade.

```python
# src/trading_research/indicators/trend.py
import polars as pl
import numpy as np

def sma(bars: pl.DataFrame, period: int, column: str = "close") -> pl.Series:
    """Simple moving average."""
    return bars[column].rolling_mean(window_size=period)

def ema(bars: pl.DataFrame, span: int, column: str = "close") -> pl.Series:
    """Exponential moving average, seeded with SMA of first `span` bars."""
    alpha = 2.0 / (span + 1.0)
    values = bars[column].to_numpy()
    result = np.full(len(values), np.nan)

    if len(values) < span:
        return pl.Series(result)

    # Seed with SMA of first `span` bars
    result[span - 1] = np.mean(values[:span])

    # Recursive EMA
    for i in range(span, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]

    return pl.Series(result)

def macd(
    bars: pl.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pl.DataFrame:
    """MACD. Returns DataFrame with columns: macd, signal, histogram."""
    ema_fast = ema(bars, fast, column)
    ema_slow = ema(bars, slow, column)
    macd_line = ema_fast - ema_slow
    signal_line = ema(pl.DataFrame({"close": macd_line}), signal)
    histogram = macd_line - signal_line
    return pl.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    })
```

## Mean reversion indicators

**RSI (Relative Strength Index).** Wilder's formulation. The standard 14-period RSI. The Wilder smoothing is the recursive `(prev * (n-1) + current) / n` form, NOT the simple moving average. This matters because the SMA-based RSI gives different values from the Wilder RSI, and most charting platforms use Wilder.

**Bollinger Bands.** SMA of close ± N standard deviations of close, computed over the same window. The default is 20-period, 2 standard deviations. **%B** is the position of price within the bands: `(close - lower) / (upper - lower)`. %B is often more useful than the bands themselves for systematic strategies because it's a single number bounded mostly to [0, 1].

**Z-score.** Rolling z-score of a column: `(value - rolling_mean) / rolling_std`. Used as a generic mean-reversion signal. Z-scores beyond ±2 are commonly treated as extension; beyond ±3 as extreme.

```python
# src/trading_research/indicators/reversion.py
import polars as pl
import numpy as np

def rsi(bars: pl.DataFrame, period: int = 14, column: str = "close") -> pl.Series:
    """Wilder's RSI. NaN for the first `period` values."""
    closes = bars[column].to_numpy()
    deltas = np.diff(closes, prepend=np.nan)

    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Wilder smoothing: first value is SMA, then recursive
    avg_gain = np.full(len(closes), np.nan)
    avg_loss = np.full(len(closes), np.nan)

    if len(closes) < period + 1:
        return pl.Series(np.full(len(closes), np.nan))

    avg_gain[period] = np.mean(gains[1:period + 1])
    avg_loss[period] = np.mean(losses[1:period + 1])

    for i in range(period + 1, len(closes)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    rs = avg_gain / np.where(avg_loss == 0, np.nan, avg_loss)
    rsi_values = 100 - (100 / (1 + rs))
    return pl.Series(rsi_values)

def bollinger_bands(
    bars: pl.DataFrame,
    period: int = 20,
    n_std: float = 2.0,
    column: str = "close",
) -> pl.DataFrame:
    """Bollinger Bands. Returns upper, middle, lower, pct_b."""
    middle = bars[column].rolling_mean(window_size=period)
    std = bars[column].rolling_std(window_size=period)
    upper = middle + n_std * std
    lower = middle - n_std * std
    pct_b = (bars[column] - lower) / (upper - lower)
    return pl.DataFrame({
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "pct_b": pct_b,
    })

def rolling_zscore(
    bars: pl.DataFrame,
    period: int = 20,
    column: str = "close",
) -> pl.Series:
    """Rolling z-score: (value - rolling_mean) / rolling_std."""
    mean = bars[column].rolling_mean(window_size=period)
    std = bars[column].rolling_std(window_size=period)
    return (bars[column] - mean) / std
```

## Volatility indicators

**True Range.** `max(high - low, abs(high - prev_close), abs(low - prev_close))`. The base of ATR.

**ATR (Average True Range).** Wilder smoothing of true range. The default period is 14. ATR in the bar's price units; for tick-denominated strategies, divide by `tick_size` to get ATR in ticks.

**Realized volatility.** Standard deviation of log returns over a rolling window, annualized. Used for vol-targeting position sizing in `risk-management`.

**Parkinson estimator.** A volatility estimator based on the high-low range that's more efficient than close-to-close volatility. Useful for short windows where close-to-close has high noise.

## Statistical tools for mean reversion

These are the tools the data scientist persona will reach for when validating that a series is actually mean-reverting before a strategy is built on top of it.

**Hurst exponent.** A number between 0 and 1 that characterizes the long-range dependence of a time series. H = 0.5 means the series is a random walk (no mean reversion, no trend). H < 0.5 means the series is mean-reverting (the lower, the more strongly). H > 0.5 means the series is trending. For pairs trading and mean reversion in general, you want to see H well below 0.5 in the spread or the price you're trading.

**Half-life of mean reversion.** Fit an Ornstein-Uhlenbeck process to the series and extract the half-life — the expected time for a deviation from the mean to decay by half. A 5-bar half-life means a strategy with a 20-bar holding period is fine; a 50-bar half-life means a 5-bar holding period is too short. The half-life directly informs strategy timeframe selection.

**Augmented Dickey-Fuller test (ADF).** Statistical test for stationarity. The null hypothesis is "this series has a unit root" (non-stationary, trending). Rejecting the null at a low p-value means the series is stationary (mean-reverting). For pairs trading: ADF on the spread is the standard test for cointegration.

**Engle-Granger cointegration test.** For two series, fit a linear regression of one on the other, then ADF the residuals. If the residuals are stationary, the two series are cointegrated and pairs trading is mathematically justified. If not, the relationship between them is non-stationary and trading the spread is gambling.

```python
# src/trading_research/indicators/statistics.py
import numpy as np
from statsmodels.tsa.stattools import adfuller
from statsmodels.regression.linear_model import OLS
import polars as pl

def hurst_exponent(series: pl.Series, max_lag: int = 100) -> float:
    """Estimate the Hurst exponent using the rescaled range method.

    Returns a float in (0, 1):
        H ≈ 0.5: random walk
        H < 0.5: mean-reverting (lower = stronger)
        H > 0.5: trending (higher = stronger)
    """
    values = series.drop_nulls().to_numpy()
    if len(values) < max_lag * 2:
        return float("nan")

    lags = range(2, max_lag)
    tau = [np.std(np.subtract(values[lag:], values[:-lag])) for lag in lags]
    # Linear fit of log(tau) vs log(lag)
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] * 2.0

def half_life(series: pl.Series) -> float:
    """Estimate the half-life of mean reversion via OLS on the OU process.

    Returns the number of bars expected for a deviation from the mean
    to decay by half. NaN if the series is not mean-reverting.
    """
    values = series.drop_nulls().to_numpy()
    if len(values) < 30:
        return float("nan")

    # Δp_t = α + β * p_{t-1} + ε
    lagged = values[:-1]
    delta = np.diff(values)
    X = np.column_stack([np.ones(len(lagged)), lagged])
    beta = OLS(delta, X).fit().params[1]

    if beta >= 0:
        return float("nan")  # not mean-reverting
    return -np.log(2) / beta

def adf_test(series: pl.Series) -> dict:
    """Augmented Dickey-Fuller test for stationarity.

    Returns dict with statistic, p_value, critical_values, and is_stationary
    (True if p < 0.05).
    """
    values = series.drop_nulls().to_numpy()
    result = adfuller(values, autolag="AIC")
    return {
        "statistic": result[0],
        "p_value": result[1],
        "critical_values": result[4],
        "is_stationary": result[1] < 0.05,
    }
```

## Order flow indicators

These require buy_volume and sell_volume from the bar data. They return NaN when those fields are null.

**Bar delta.** `buy_volume - sell_volume` per bar. Positive delta means the bar saw more aggressive buying; negative means more aggressive selling.

**Cumulative session delta.** Running sum of bar delta within each session. Resets at session boundaries. Often plotted alongside price; divergences between price and cumulative delta are a classic order-flow signal.

**Delta divergence.** A higher-order signal that fires when price makes a new high (low) but cumulative delta does not, suggesting the move is not supported by aggressive flow. Implementation requires defining "new high" with a lookback window.

**Absorption.** Bars where volume is high but price movement is small, suggesting the bar absorbed selling (or buying) pressure without moving. Computed as `volume / abs(close - open)` or `volume / (high - low)`. High absorption at extremes is a reversal signal.

```python
# src/trading_research/indicators/orderflow.py
import polars as pl
import numpy as np

def bar_delta(bars: pl.DataFrame) -> pl.Series:
    """Buy volume minus sell volume per bar. NaN if order flow is unavailable."""
    if "buy_volume" not in bars.columns or "sell_volume" not in bars.columns:
        return pl.Series(np.full(len(bars), np.nan))
    return bars["buy_volume"] - bars["sell_volume"]

def cumulative_session_delta(bars: pl.DataFrame) -> pl.Series:
    """Cumulative delta within each session. Resets at session_id boundaries."""
    delta = bar_delta(bars)
    if delta.is_null().all():
        return delta

    # Cumulative sum within each session_id group
    df = bars.with_columns(delta=delta)
    return (
        df.with_columns(cum_delta=pl.col("delta").cum_sum().over("session_id"))
        .get_column("cum_delta")
    )
```

## Multi-instrument tools

**Rolling correlation.** Standard rolling Pearson correlation between two return series. Used to monitor pair stability.

**Cointegration test (Engle-Granger).** Fit a linear regression of one price on the other, ADF the residuals.

**Spread z-score.** For a pair with hedge ratio β, the spread is `price_A - β * price_B`. The rolling z-score of the spread is the entry signal for pairs trading.

These are documented here but the full multi-instrument workflow lives in the strategy code, since pairs trading is more complex than just running these tools.

## Standing rules this skill enforces

1. **Every indicator passes the as-of correctness test.** No exceptions.
2. **Indicators are pure functions of their inputs.** No global state, no caching at the indicator level.
3. **NaN handling is explicit.** Every indicator documents how it handles the warmup period (typically returns NaN for the first N bars).
4. **No proprietary or undocumented indicators in the project.** If an indicator is in this skill, its math is documented and standard. If you want to invent a new indicator, fine, but it goes through the same documentation, implementation, and testing process.
5. **Indicators don't make trading decisions.** They produce numbers. Strategies make decisions. Mixing the two in one function is a bug.
6. **Indicators that depend on order flow handle missing data gracefully.** A bar with null buy_volume returns NaN for the indicator, not zero, not an exception.
7. **Indicator metadata is stored alongside any cached features file.** Reproducibility requires knowing exactly what was computed with what parameters.

## When to invoke this skill

Load this skill when the task involves:

- Implementing a new indicator
- Debugging an indicator that's producing wrong values
- Writing or modifying the indicator caching to `data/features/`
- Choosing indicators for a new strategy
- Verifying as-of correctness on existing indicator code
- Computing statistical tests (Hurst, half-life, ADF) on a series

Don't load this skill for:

- Strategy logic that uses indicators (the strategy lives in the strategies module; this skill is for the indicators it imports)
- Charting indicator values (use `charting`)
- Feature engineering for ML (use `feature-engineering` — there's overlap, but feature engineering is about creating ML inputs from indicators, not about the indicators themselves)

## Open questions for build time

1. **Whether to use a third-party TA library (TA-Lib, pandas-ta) or implement from scratch.** Lean implement-from-scratch for the core indicators because (a) it forces understanding of the math, (b) it avoids the as-of correctness uncertainty in third-party code, (c) the implementations are short. TA-Lib is acceptable if a specific indicator is too complex to reimplement and the as-of correctness can be verified.
2. **Numba/Cython for hot-path indicators.** Polars is fast enough for almost everything. If a specific indicator becomes a bottleneck in walk-forward backtests, optimize then, not now.
3. **Whether the indicator metadata file should also include the source parquet's checksum** so that "indicator file is fresh" can be detected by hash rather than mtime. Probably yes for production; defer for now.
