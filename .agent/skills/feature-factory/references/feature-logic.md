# Feature Engineering & Indicator Protocol

This document defines the mathematical and technical standards for the `feature-factory`, incorporating the Lopez de Prado canon and Wilder's smoothing.

## 1. Technical Indicators (Causal)
Indicators must use recursive smoothing (Wilder) where applicable to match standard market physics.

| Indicator | Standard | Implementation Note |
| :--- | :--- | :--- |
| **EMA** | Span-based | Seed with SMA of first `span` bars. |
| **RSI** | Wilder's | `(prev * (n-1) + current) / n` recursive smoothing. |
| **ATR** | Wilder's | Max(H-L, \|H-Cp\|, \|L-Cp\|) with 14-period smoothing. |
| **Delta** | Order Flow | `buy_volume - sell_volume`. Must handle nulls. |

## 2. Advanced ML Features (Stationarity)
Use **Fractional Differentiation** to preserve memory while achieving stationarity.

```python
# Logic from src/trading_research/features/stationarity.py
def fractional_difference(series, d=0.4, threshold=0.01):
    # Scientist: Finds minimum differencing d to pass ADF test
    weights = compute_weights(d, threshold)
    return apply_weights(series, weights)
```

## 3. Labeling & Validation Logic
- **Triple Barrier Method**: Determines labels based on which barrier is hit first (Profit, Stop, or Time).

### Purge & Embargo
- **Purge**: Remove training samples whose labels overlap with the test set.
- **Embargo**: Remove samples immediately following a test set to prevent leakage from serial correlation.

## 4. Metadata & Store Schema
Every file in `data/features/` must have a `.metadata.json` including:

- `source_parquet_hash`: To ensure data provenance.
- `features`: List of names, functions, and YAML-loaded params.
- `as_of_rule`: `"Features at bar N use data through N-1"`.
- `passes_asof_test`: Boolean based on unit test results.

## 5. Statistical Diagnostics
Proactively run these tests during feature creation:

- **ADF (Augmented Dickey-Fuller)**: Test for stationarity.
- **Hurst Exponent**: `< 0.5` indicates mean-reverting regime.
- **Half-Life (OU)**: Determines appropriate holding period for labels.
