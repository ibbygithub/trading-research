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

### 2.2 Hurst Exponent — DFA (Detrended Fluctuation Analysis)

**Session 27 change:** R/S was replaced with DFA. See §8.2 and §8.3 for
the rationale and the composite classification change that accompanies it.

**Implementation:** Custom DFA-1 (first-order polynomial detrending).
Reference: Peng et al. (1994), "Mosaic organization of DNA nucleotides."

**Algorithm:**

1. Mean-subtract the input series and compute the cumulative sum (integrate).
2. For each window size `w` in `[8, 16, 32, 64, 128, 256, 512]` (or fewer
   if the series is shorter), split the integrated series into non-overlapping
   segments of length `w`.
3. For each segment, fit a polynomial of degree `poly_order` (default 1 =
   linear) and compute the RMS of residuals — the fluctuation function F(w).
4. Average F(w) across segments for each `w`.
5. Fit `log(mean_F)` vs `log(w)` by OLS. The slope is the Hurst exponent.

**Why DFA over R/S:** R/S applies rescaled-range analysis to the raw series.
For any AR(1) process with **positive φ**, R/S returns H > 0.5 — classifying
it as TRENDING or RANDOM_WALK. A VWAP spread behaves as an OU process with
positive φ at the bar level (price overshoots VWAP and takes several bars to
return), giving R/S H ≈ 0.65 even though the series is stationary. DFA does
not exhibit this defect for the TRENDING misclassification: for the same
series, DFA gives H ≈ 0.5 (RANDOM_WALK), which is less wrong and, with the
§4.4 composite fix, no longer blocks TRADEABLE_MR classification.

**Known limitation:** For **short-memory** stationary processes (AR(1) with
any φ, correlation length < 8 bars), DFA gives H ≈ 0.5 regardless of the
sign of φ. DFA cannot distinguish a mean-reverting AR(1) φ=0.5 from a random
walk at the window scales used. Strongly anti-persistent processes (φ < −0.5)
are correctly detected as mean-reverting (H < 0.45). See §4.4 and §8.3 for
how the composite classification handles this limitation.

**Range of window sizes:** starts at min_window (default 10) up to
`len(series) // 2`. If the series has fewer than 32 bars, return NaN and log
a warning; do not interpolate.

**The old R/S implementation** is retained as the private function
`_rs_hurst()` in `stationarity.py` for comparison and regression testing.
Do not expose it in the public API.

**Dependencies:** `numpy`, `scipy.stats.linregress`. No new packages.

**Output:** single float H ∈ (0, ∞) — though in practice H ∈ (0, 1.5) for
the series tested in this project.

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

### 8.2 Hurst reference check (updated session 27 — DFA replaces R/S)

**Previous (R/S, session 26):** "AR(1) φ=0.5 should return H < 0.5." This
claim was incorrect. R/S on AR(1) φ=0.5 gives H > 0.5 (TRENDING), which is
a methodological defect — not a test bug.

**Current (DFA, session 27):**

| Series | DFA expected H | Notes |
|---|---|---|
| White noise (i.i.d. returns) | ≈ 0.5 | |
| Random walk (level, I(1)) | ≈ 1.0 | |
| AR(1) φ=0.5 (slow OU) | ≈ 0.5 (RANDOM_WALK) | See §8.3 for composite handling |
| AR(1) φ=−0.7 (anti-persistent) | < 0.40 (MEAN_REVERTING) | |
| Cumsum + drift (trending) | > 0.55 (TRENDING) | |

**Known DFA limitation:** For any short-memory stationary AR(1) process
(|φ| < 1, correlation length < 8 bars), DFA gives H ≈ 0.5 regardless of φ
sign. This is theoretically correct: DFA cannot distinguish short-range mean
reversion from a random walk at the window scales used (8–512 bars), because
the integrated series is indistinguishable from a random walk at those scales.
Strongly anti-persistent processes (φ < −0.5) ARE correctly detected.

**Key improvement over R/S:** For AR(1) φ=0.5, R/S gave H ≈ 0.65 (TRENDING);
DFA gives H ≈ 0.5 (RANDOM_WALK). TRENDING was the harmful classification because
it blocked TRADEABLE_MR; RANDOM_WALK is benign with the session 27 composite fix.

Tolerance for reference checks: ±0.10. Finite-sample estimators of H are
noisy; demanding tighter tolerance would make the test brittle.

### 8.3 Composite classification — Hurst RANDOM_WALK for positive-φ OU (session 27)

This section documents the session 27 composite classification change (Option A).

**Problem:** AR(1) φ=0.5 (typical VWAP spread behaviour) gets H ≈ 0.5 from
DFA. Under the original composite logic, H ≈ 0.5 → RANDOM_WALK → blocks
TRADEABLE_MR even when ADF strongly rejects the unit root and OU half-life is
in the tradeable range.

**Fix:** `_composite_classification()` was updated so that ADF + OU half-life
are the **primary gates** for TRADEABLE_MR. Hurst RANDOM_WALK (H ∈ [0.45, 0.55])
no longer blocks TRADEABLE_MR. Hurst TRENDING (H > 0.55) still produces
INDETERMINATE — a genuine ADF/Hurst contradiction worth flagging.

**Rationale:** ADF rejection of the unit root is a formal hypothesis test
that the series is stationary. OU half-life confirms the reversion speed is
tradeable. Together, these are sufficient evidence for mean-reversion candidacy.
Hurst provides additional context but is not reliable enough for short-memory
processes to serve as a hard gate.

**Effect:** A VWAP spread with ADF p < 0.01, tradeable OU half-life, and DFA
H ≈ 0.5 is now correctly classified as TRADEABLE_MR. Previously it was
classified as INDETERMINATE or RANDOM_WALK and silently excluded from strategy
consideration.

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
