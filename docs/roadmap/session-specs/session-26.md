# Session 26 — Stationarity Suite Implementation

**Agent fit:** either (Gemini-eligible with statistical validation tests)
**Estimated effort:** L (4h+)
**Depends on:** 24 (design doc), 25 (pipeline refactor)
**Unblocks:** 28, 29

## Goal

Implement the stationarity suite (ADF, Hurst exponent, OU half-life) per the design doc at `docs/design/stationarity-suite.md`, validated against canonical reference implementations, callable via a CLI command, producing a structured report.

## Context

Session 24 produced the design doc. This session implements against it. No design decisions should be made here — if the spec is ambiguous, stop and ask the data scientist (don't guess at thresholds or test parameters).

## In scope

Create under `src/trading_research/stats/`:

- `__init__.py`
- `stationarity.py`:
  - `adf_test(series: pd.Series, maxlag: int | None = None) -> ADFResult` — wraps `statsmodels.tsa.stattools.adfuller`, returns structured result.
  - `hurst_exponent(series: pd.Series, min_window: int = 10, max_window: int | None = None) -> HurstResult` — rescaled-range method, returns exponent and confidence.
  - `ou_half_life(series: pd.Series) -> OUResult` — fits Ornstein-Uhlenbeck via least-squares regression, returns half-life in bars and R² of the fit.
  - `StationarityReport` — dataclass holding results across multiple series and tests.
  - `run_stationarity_suite(instrument: Instrument, bars: pd.DataFrame, timeframes: list[str]) -> StationarityReport` — orchestrator that runs all three tests on all specified series per the design doc.

Create CLI entry point:

- Add subcommand to existing CLI: `uv run trading-research stationarity --symbol 6E --start 2020-01-01 --end 2024-12-31` — runs the suite, writes a JSON report to `outputs/stationarity/{symbol}_{timestamp}.json` and a human-readable markdown summary alongside.

Create tests under `tests/stats/`:

- `test_stationarity_adf.py`:
  - `test_adf_stationary_series` — ADF on a known stationary series (white noise) rejects null.
  - `test_adf_non_stationary_series` — ADF on random walk fails to reject.
  - `test_adf_matches_statsmodels` — our wrapper produces same p-value as direct `adfuller` call (within floating point).
- `test_stationarity_hurst.py`:
  - `test_hurst_brownian_motion` — random walk has Hurst ≈ 0.5.
  - `test_hurst_trending_series` — cumulative sum of positive drift has Hurst > 0.55.
  - `test_hurst_mean_reverting_series` — OU-simulated series has Hurst < 0.45.
- `test_stationarity_ou.py`:
  - `test_ou_half_life_synthetic` — synthetic OU process with known half-life; fitted half-life within 20% of true value.
  - `test_ou_fit_quality` — high R² for OU process, low R² for random walk.
- `test_stationarity_suite_integration.py`:
  - `test_suite_runs_on_synthetic_bars` — generate synthetic OHLCV, run suite, get structured report with expected keys.
  - `test_report_serialization_round_trip` — report → JSON → report is identical.

## Out of scope

- Do NOT run the suite on real 6E or ZN data — that's session 28.
- Do NOT integrate stationarity results into the backtest HTML report — that's F1 or later.
- Do NOT add new statistical tests beyond the three specified in the design doc.
- Do NOT modify the design doc — if something is wrong with it, stop and escalate to session 24.

## Acceptance tests

- [ ] `uv run pytest tests/stats/ -v` — all tests pass.
- [ ] `uv run pytest` — full suite passes.
- [ ] `uv run trading-research stationarity --help` — subcommand is registered and shows help.
- [ ] Each statistical test has a validation against its canonical reference or a known-answer synthetic test.
- [ ] `ruff check src/trading_research/stats/ tests/stats/` passes.

## Definition of done

- [ ] Implementation matches design doc field-by-field.
- [ ] Reference-implementation comparison tests pass (ADF matches statsmodels to 6 decimals).
- [ ] Synthetic series tests pass with reasonable tolerances.
- [ ] Work log at `outputs/work-log/YYYY-MM-DD-session-26.md` includes the exact ADF / Hurst / OU values produced on the canonical test series, for reproducibility.
- [ ] Committed on feature branch `session-26-stationarity-suite`.

## Persona review

- **Data scientist: required.** Reviews that implementations match the design doc and pass canonical-reference tests. This is statistically sensitive code; data scientist signs off before merge. Expect push-back if any test doesn't have a clear reference.
- **Architect: optional.** Reviews module structure and the stats package's coupling to the rest of the codebase.
- **Mentor: optional.**

## Design notes

### ADF wrapper

```python
@dataclass
class ADFResult:
    statistic: float
    p_value: float
    lags_used: int
    n_observations: int
    critical_values: dict[str, float]
    is_stationary: bool  # True if p_value < 0.05
    interpretation: str  # human-readable sentence

def adf_test(series: pd.Series, maxlag: int | None = None) -> ADFResult:
    from statsmodels.tsa.stattools import adfuller
    result = adfuller(series.dropna(), maxlag=maxlag, autolag="AIC" if maxlag is None else None)
    return ADFResult(
        statistic=result[0],
        p_value=result[1],
        lags_used=result[2],
        n_observations=result[3],
        critical_values=result[4],
        is_stationary=result[1] < 0.05,
        interpretation=_interpret_adf(result[1]),
    )
```

### Hurst via rescaled range

Implementation is straightforward; use the well-known R/S analysis method. Log–log regression of rescaled range vs window size, slope is the Hurst exponent. Do not pull in the `hurst` PyPI package unless validation shows a local implementation is insufficient — the architect's "dependencies that aren't worth their weight" rule applies.

### OU half-life

Fit an AR(1) model to the series:
```
Δx_t = -θ (x_t - μ) + ε_t
```
Half-life = ln(2) / θ. Standard implementation via linear regression on `(x_t, Δx_t)` pairs. Half-life in bars; caller converts to time units using bar timeframe.

### Output report format

One JSON per instrument per run, at `outputs/stationarity/{symbol}_{YYYYMMDD-HHMMSS}.json`:

```json
{
  "instrument": "6E",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "code_version": "<git sha>",
  "results": [
    {
      "series_name": "returns_5m",
      "timeframe": "5m",
      "adf": {"statistic": -4.2, "p_value": 0.0006, "is_stationary": true, ...},
      "hurst": {"exponent": 0.48, "interpretation": "slight mean reversion", ...},
      "ou_half_life": {"bars": 23, "hours": 1.9, "r_squared": 0.12, ...}
    },
    ...
  ]
}
```

Also write a markdown summary at the same base path for human reading.

### Performance

ADF and Hurst on 5-minute bars over 5 years is ~500k rows per series × several series × several timeframes. Each test is ~seconds; full suite is minutes, not hours. Do not optimize prematurely.

## Risks

- **Local Hurst implementation wrong.** Mitigation: `test_hurst_brownian_motion` must pass with 0.48 ≤ H ≤ 0.52 on a long random walk. If it fails, fix before proceeding.
- **OU fit unstable on trending series.** Mitigation: report R² alongside half-life; low R² means don't trust the half-life.
- **Series has too few observations.** Mitigation: every test has a minimum-observations check; raises clear error rather than returning garbage.

## Reference

- `docs/design/stationarity-suite.md` — the design doc. This spec must match.
- `statsmodels.tsa.stattools.adfuller` — ADF reference.
- Hurst, H.E. (1951) — original R/S method.
- Lopez de Prado, *Advances in Financial Machine Learning*, ch. 17.
- Session 24 spec for integration context.

## Success signal

```
uv run trading-research stationarity --symbol ZN --start 2024-01-01 --end 2024-12-31
```

Produces a JSON + markdown report in `outputs/stationarity/`. The report has ADF, Hurst, and OU results for at least three series. ADF p-value matches a direct statsmodels call within floating-point tolerance.
