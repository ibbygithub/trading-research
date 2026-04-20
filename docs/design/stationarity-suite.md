# Stationarity Suite — Design Specification

**Status:** Design complete. Implementation target: Session 26.
**Author:** Data Scientist persona, Session 24.
**Implements against:** Session 24 spec, roadmap sessions-23-50.md Track A.

---

## 1. Purpose

Mean-reversion strategies rest on a statistical assumption: the series being
traded (price, spread, indicator) is stationary — it has a stable mean to which
it reverts. If that assumption is violated, the strategy is fishing in a
trending or noisy market where there is no natural reversion level.

This suite provides three independent tests that, taken together, give a
multi-angle view of the series' behaviour:

- **ADF** (Augmented Dickey-Fuller): formal hypothesis test for a unit root.
  Rejection of the null means the series is likely stationary. Sensitive to
  the choice of lag and the time window.

- **Hurst exponent**: a data-descriptor (not a hypothesis test) that
  characterizes long-range memory. H < 0.5 = mean-reverting; H = 0.5 =
  random walk; H > 0.5 = trending/persistent. Insensitive to distributional
  assumptions; does not require a p-value correction.

- **OU half-life**: fits an Ornstein-Uhlenbeck mean-reversion process by
  OLS and reads the implied reversion speed. Even if a series is stationary
  by ADF, it may revert so slowly (e.g., half-life of 300 bars on a 1-minute
  chart) that no practical strategy can exploit it. Half-life converts
  "mean-reverting in principle" to "mean-reverting at a tradeable speed".

The three tests are required to agree before a series is marked `TRADEABLE`
for mean reversion. Agreement means the series passes each individual test's
threshold. Disagreement is informative — a series that fails ADF but shows
H < 0.45 may have a non-linear reversion structure that warrants further
investigation.

**Primary use-case:** 6E (EUR/USD futures) pipeline ahead of session 29's
strategy-class decision. Secondary: the same suite runs on any new instrument
as part of `stationarity --symbol <SYMBOL>`.

---

## 2. Tests

### 2.1 ADF — Augmented Dickey-Fuller

**Implementation:** `statsmodels.tsa.stattools.adfuller`

**Null hypothesis:** the series has a unit root (is non-stationary / random
walk or trend-stationary).

**Lag selection:** `autolag='AIC'` (Akaike Information Criterion). This is
the statsmodels default and is preferred over fixed-lag because the optimal
lag varies across instruments and timeframes. AIC lag selection is documented
to perform well in finite samples relative to BIC for ADF (Ng & Perron, 2001).

**Regression type:** `regression='c'` (constant only, no trend). The
instruments in scope (6E, 6A, 6C) are tested on *returns* and *VWAP-spread
series* (see §3), not on log-price levels. Returns are not expected to have a
deterministic trend; including one would over-reject the null. For log-price
levels, use `regression='ct'` (constant + trend).

**Output per call:** `(adf_statistic, p_value, n_lags_used, n_obs, critical_values_dict)`.
The suite records `adf_statistic`, `p_value`, and `n_lags_used`.

**Reference implementation check:** Confirm the suite's ADF p-values match
`statsmodels.tsa.stattools.adfuller` on a standard test series (e.g., AR(1)
with φ = 0.9) to within floating-point tolerance. This check is a required
unit test in session 26.

### 2.2 Hurst Exponent — Rescaled-Range Method

**Implementation:** Custom, using the R/S (rescaled range) estimator. The
`hurst` PyPI package is an option but is poorly maintained and may be
unavailable in future Python versions. Implement locally. The rescaled-range
method is described in Hurst (1951) and summarized in Lo (1991).

**Algorithm:**

1. For each sub-window size `n` in `[8, 16, 32, 64, 128, 256, 512]` (or fewer
   if the series is shorter), split the series into non-overlapping segments of
   length `n`.
2. For each segment, compute `R/S` = (max cumulative deviation − min cumulative
   deviation) / standard deviation.
3. Average `R/S` across segments for each `n`.
4. Fit `log(mean_RS)` vs `log(n)` by OLS. The slope is the Hurst exponent.

**Range of window sizes:** starts at 8 (minimum meaningful segment) up to
`len(series) // 2` (to have at least 2 segments). If the series has fewer than
32 bars, return NaN and log a warning; do not interpolate.

**Dependencies:** `numpy`, `scipy.stats.linregress` (already in the
environment). No new packages.

**Output:** single float H ∈ (0, 1).

### 2.3 OU Half-Life — Ornstein-Uhlenbeck OLS Fit

**Implementation:** Least-squares regression of `Δy_t` on `y_{t-1}`.

```
Δy_t = α + β * y_{t-1} + ε_t
```

The OU reversion speed is `−β` (must be negative for mean reversion). The
**half-life** is `ln(2) / −β` bars.

**Implementation steps:**

1. Compute first differences: `delta_y = y[1:] - y[:-1]`.
2. Regress `delta_y` on `y[:-1]` and a constant using `numpy.linalg.lstsq`
   or `scipy.stats.linregress`.
3. Extract `β` (the slope). If `β ≥ 0`, the series is not mean-reverting
   under OU; return `half_life = inf`.
4. Compute `half_life = log(2) / (-β)` in units of bars.

**Failure modes to handle explicitly:**
- `β ≥ 0`: return `half_life = float('inf')`, interpretation = `TRENDING`.
- `β ≈ 0` (|β| < 1e-10): return `half_life = float('inf')`, interpretation = `RANDOM_WALK`.
- Series too short (< 10 observations): return NaN.

**Dependencies:** `numpy` only.

---

## 3. Input Series

The suite tests the following series for each instrument. These cover the
inputs that mean-reversion strategies most commonly use.

| Series Name | Construction | Timeframes | Regression type |
|---|---|---|---|
| `log_returns_1m` | `log(close).diff()` on 1m bars | 1m | `c` |
| `log_returns_5m` | `log(close).diff()` on resampled 5m bars | 5m | `c` |
| `log_returns_15m` | `log(close).diff()` on resampled 15m bars | 15m | `c` |
| `vwap_spread_5m` | `close − VWAP` on 5m bars | 5m | `c` |
| `vwap_spread_15m` | `close − VWAP` on 15m bars | 15m | `c` |
| `log_price_level` | `log(close)` on 1m bars | 1m | `ct` |

**Notes:**

- `log_price_level` is included to confirm that price levels are
  non-stationary (expected result: ADF fails to reject). This is a sanity
  check, not a trading signal.
- Returns are differenced; no further preprocessing (no z-scoring).
- VWAP here means session VWAP, reset at the start of each RTH session.
  The VWAP indicator already in `src/trading_research/indicators/vwap.py`
  is the reference implementation.
- Instrument list for session 28 (initial run): 6E. Extend to 6A, 6C in
  session 43 when pairs work begins.

---

## 4. Thresholds

All thresholds are cited from primary sources. Changes require explicit
justification in the commit message; this is not a free parameter.

### 4.1 ADF

| p-value | Interpretation |
|---|---|
| p < 0.01 | STATIONARY (strong) |
| 0.01 ≤ p < 0.05 | STATIONARY (weak) — passes threshold, note in report |
| p ≥ 0.05 | NON-STATIONARY — fails threshold |

Source: standard significance levels; 5% is the conventional threshold in
econometrics for ADF. The strong/weak split at 1% is an addition for
practitioner clarity — a weak-stationary series warrants more caution.

### 4.2 Hurst Exponent

| H value | Interpretation |
|---|---|
| H < 0.40 | MEAN-REVERTING (strong) |
| 0.40 ≤ H < 0.45 | MEAN-REVERTING (weak) — passes threshold |
| 0.45 ≤ H ≤ 0.55 | RANDOM WALK — fails threshold |
| 0.55 < H < 0.60 | TRENDING (weak) — fails threshold |
| H ≥ 0.60 | TRENDING (strong) |

Source: Peters (1994), "Fractal Market Analysis". The 0.45/0.55 band around
0.5 is deliberately wide. An H estimate from a finite sample has sampling
error; calling H = 0.47 "mean-reverting" would be over-confident. The flat
zone around 0.5 is the correct response to estimation uncertainty.

**Note from the mentor:** "A Hurst of 0.55 is not meaningfully trending on a
practical timescale. Don't trade it as a trend-follower. Treat the 0.45–0.55
band as 'strategy class is indeterminate, run more analysis.'"

### 4.3 OU Half-Life

Half-life thresholds depend on the timeframe. A 30-bar half-life means
something different on 1-minute bars vs 15-minute bars.

| Timeframe | Min half-life (practical) | Max half-life (practical) | Interpretation |
|---|---|---|---|
| 1m | 5 bars (5 min) | 60 bars (1 hour) | TRADEABLE for intraday |
| 5m | 3 bars (15 min) | 24 bars (2 hours) | TRADEABLE for intraday |
| 15m | 2 bars (30 min) | 8 bars (2 hours) | TRADEABLE for intraday |

If `half_life < min`: reversion is too fast — strategy would need sub-bar
fills, interpretation = `TOO_FAST`.

If `half_life > max`: reversion is too slow — a strategy with a 4-hour
position limit cannot wait for a 6-hour reversion, interpretation = `TOO_SLOW`.

If `half_life` is within range: interpretation = `TRADEABLE`.

Source: half-life thresholds are derived from Ibby's operating constraints
(intraday, flat by EOD, 4-hour maximum hold). Lopez de Prado (2018), ch. 17
gives the OU framework; the specific bound values are project-specific.

### 4.4 Composite Classification

A series is classified `TRADEABLE_MR` (mean-reversion candidate) only if ALL
of the following hold:

1. ADF p-value < 0.05 (weak or strong stationary)
2. Hurst H < 0.45 (weak or strong mean-reverting)
3. OU half-life within the tradeable range for the series' timeframe

Any other combination yields one of:
- `NON_STATIONARY` — ADF fails to reject
- `RANDOM_WALK` — ADF passes, Hurst in [0.45, 0.55]
- `TRENDING` — Hurst > 0.55
- `TOO_FAST` or `TOO_SLOW` — stationary + mean-reverting but OU half-life out of range
- `INDETERMINATE` — tests disagree in a way not covered above (e.g., ADF
  rejects but Hurst > 0.55)

The `INDETERMINATE` case is not an error; it is an honest answer. Log it and
surface it in the report. It is the data scientist's job to explain it; the
mentor's job to decide whether to trade it anyway.

---

## 5. Output Format

The suite produces a **pandas DataFrame** with one row per (instrument, timeframe, series_name, test_name) combination.

**Schema:**

| Column | Type | Notes |
|---|---|---|
| `instrument` | str | e.g., `"6E"` |
| `timeframe` | str | e.g., `"5m"` |
| `series_name` | str | e.g., `"vwap_spread_5m"` |
| `test_name` | str | `"adf"` / `"hurst"` / `"ou_halflife"` |
| `statistic` | float | ADF t-stat, Hurst H, or half-life in bars |
| `p_value` | float | ADF p-value; NaN for Hurst and OU (they are not hypothesis tests) |
| `n_lags` | int | ADF lags used; NaN for Hurst and OU |
| `n_obs` | int | Number of observations in the series tested |
| `interpretation` | str | One of the classification labels in §4 |
| `composite` | str | Per-series composite classification (populated only on last row per series grouping, or as a separate summary frame) |
| `run_ts` | datetime (UTC) | When the test was run |
| `code_version` | str | Git short SHA |
| `data_version` | str | Hash of the CLEAN parquet manifest (from `data.manifest`) |

**Persistence:** The DataFrame is written to
`runs/stationarity/<SYMBOL>/<YYYYMMDD-HHMM>.parquet` on completion. A JSON
summary (the composite classifications only) is written to the same directory
as `summary.json`.

The JSON summary format:
```json
{
  "instrument": "6E",
  "run_ts": "2026-04-28T14:00:00+00:00",
  "code_version": "abc1234",
  "data_version": "ff2a9b3c",
  "series": {
    "vwap_spread_5m": "TRADEABLE_MR",
    "log_returns_5m": "RANDOM_WALK",
    "log_price_level": "NON_STATIONARY"
  }
}
```

---

## 6. Integration with the Features Layer

The stationarity suite is **not** run on every feature build. It is expensive
(multiple ADF calls per series, each O(n²) in the worst case) and the results
change slowly — a series that was stationary last month is still stationary
this month unless the regime changed.

**Trigger mechanism:** A dedicated CLI command:

```
uv run python -m trading_research.stationarity --symbol 6E [--start 2020-01-01] [--end 2024-12-31]
```

This command:
1. Loads the CLEAN parquet for the symbol via the pipeline manifest.
2. Computes or resamples to the required timeframes (1m, 5m, 15m).
3. Runs all tests on all series.
4. Writes the output parquet and JSON summary to `runs/stationarity/`.
5. Prints a human-readable table to stdout.

The command is implemented in `src/trading_research/stationarity/__init__.py`
and `src/trading_research/stationarity/__main__.py` (new module, session 26).

**FEATURES layer linkage:** The stationarity summary JSON path is recorded in
the FEATURES layer manifest for the instrument as `stationarity_report`. This
is metadata only — it is not recomputed as part of the features build.

---

## 7. Consumers

**Session 29 — strategy class decision:**

The strategy selection logic in session 29 reads the JSON summary for 6E and
uses the composite classification to pick:

- `TRADEABLE_MR` on `vwap_spread_5m` or `vwap_spread_15m` → proceed with
  mean-reversion template on VWAP spread.
- `RANDOM_WALK` on spreads but `TRADEABLE_MR` on returns → reconsider;
  possibly breakout or momentum.
- `TRENDING` → momentum template is preferred.
- `INDETERMINATE` → session 29 escalates to mentor + data scientist review
  before choosing a strategy class.

The session 29 spec will include a reference to this document and the JSON
summary file path.

**Track C strategy backtests:**

Every backtest result in the trial registry should record the stationarity
composite for the primary series used by the strategy. This is stored as
`featureset_hash` (linking to the feature-set version) — session 29 adds the
stationarity composite as an additional field if needed.

---

## 8. Validation

The implementation in session 26 must include the following validation tests:

### 8.1 ADF reference check

Generate a known-stationary AR(1) series with φ = 0.5 (strongly stationary)
and a known unit-root series with φ = 1.0. Confirm:

- AR(1) φ=0.5: `adfuller(series, autolag='AIC')[1]` < 0.05 (p-value).
- RW φ=1.0: `adfuller(series, autolag='AIC')[1]` > 0.05.

The suite's wrapper must produce the same p-values as calling `adfuller`
directly. This ensures the wrapper adds no transformation errors.

Synthetic series length: 500 observations. Random seed: 42.

### 8.2 Hurst reference check

A geometric random walk (φ=1 AR(1)) should return H ≈ 0.5. An AR(1) with
φ=0.5 should return H < 0.5. An AR(1) with φ=0.95 (near unit root) should
return H close to but below 0.5 (persistent but not truly trending — the
distinguisher). A simple linear trend should return H > 0.5.

Tolerance for reference checks: ±0.10 of the known theoretical value.
Finite-sample estimators of H are noisy; demanding tighter tolerance would
make the test brittle.

### 8.3 OU half-life reference check

Generate an OU process analytically: `y_t = φ * y_{t-1} + ε_t` with φ = 0.9.
Theoretical half-life = `ln(2) / ln(1/φ)` bars. Confirm the suite's estimate
is within ±10% of this value for a series of 500 observations.

### 8.4 Round-trip test

Run the full suite on the synthetic AR(1) φ=0.5 series, write the parquet and
JSON summary, reload both, confirm no data loss. Confirms the persistence layer
and schema are correct.

### 8.5 Composite classification correctness

Construct synthetic series that hit each classification:
- `TRADEABLE_MR`: AR(1) φ=0.5, vwap-like spread, 500 bars (5m timeframe →
  half-life within bounds).
- `NON_STATIONARY`: random walk.
- `TRENDING`: geometric random walk with drift.
- `TOO_SLOW`: AR(1) φ=0.999 (near unit root, half-life > 1000 bars).

Confirm the composite label matches the expected classification for each.

---

## Dependencies Required for Session 26

| Package | Purpose | Status |
|---|---|---|
| `statsmodels` | `adfuller` reference implementation | Check pyproject.toml |
| `numpy` | Hurst / OU implementation, array ops | Already installed |
| `scipy` | `linregress` for OU fit (optional — `numpy.linalg.lstsq` works) | Already installed |
| `pandas` | Output DataFrame | Already installed |
| `pyarrow` | Parquet write/read | Already installed |

Before session 26 begins, confirm `statsmodels` is in `pyproject.toml`.
If not, add it with `uv add statsmodels` and update `uv.lock`.

---

## Observed Debt (Out of Scope for This Session)

- The ADF result depends heavily on the observation window. A series can be
  stationary in one regime and non-stationary in another. A rolling-window
  ADF is not in scope but would be a meaningful enhancement after session 26.

- The Hurst estimator has meaningful finite-sample bias for short series
  (< 128 observations). A bias correction (Lo, 1991) is not in scope but
  should be on the backlog.

- The OU fit assumes a linear drift-diffusion process. Non-linear reversion
  (e.g., threshold reversion) is not captured. Out of scope for this suite.
