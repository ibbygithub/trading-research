# Gemini Validation Playbook
Version: 1.0
Date: 2026-04-26
Owner: Data Scientist + Architect personas
Applies to: Every Gemini sub-sprint that ships statistical or numerical code.

## Why this exists

Gemini 3.1 (Antigravity) has shipped good work on sessions 11–13 and 25–28.
It has also produced confidently-wrong code in cases where its self-validation
loop only checked internal consistency. The trading-research project cannot
afford that — wrong p-values silently shape strategy decisions.

This playbook codifies the **canonical-method parity** pattern. Use it for
every public method Gemini ships.

## The pattern

For every public function that implements a statistical or numerical method
with a canonical reference implementation:

1. **Spec author writes a parity test** before Gemini sees the spec.
2. The test:
   - Generates input data with a fixed seed.
   - Runs *our* implementation.
   - Runs the *canonical* implementation.
   - Asserts the two outputs match within explicit numerical tolerance.
3. Gemini fills in *our* implementation against this failing test.
4. The test ships in the repo — it is part of the regression suite.

```python
# Standard pattern — every Gemini-shipped method gets one of these.
import numpy as np
from <canonical_library> import <canonical_function>
from <our_module> import <our_function>

def test_<our_function>_matches_canonical():
    rng = np.random.default_rng(SEED)
    inputs = rng.<distribution>(size=N)

    ours = our_function(inputs, **kwargs)
    canonical = canonical_function(inputs, **kwargs)

    np.testing.assert_allclose(
        ours, canonical,
        rtol=RELATIVE_TOLERANCE,
        atol=ABSOLUTE_TOLERANCE,
    )
```

The seed, distribution, N, tolerances, and kwargs are all written *by the
spec author*. Gemini cannot relax any of them without escalating.

---

## Worked examples

### Example A — Benjamini-Hochberg (already shipped, retroactive validation)

`src/trading_research/stats/multiple_testing.py` claims parity with
`scipy.stats.false_discovery_control`. The parity test we want:

```python
# tests/stats/test_bh_canonical_parity.py
import numpy as np
from scipy.stats import false_discovery_control
from trading_research.stats.multiple_testing import benjamini_hochberg

SEED = 20260426
N_TESTS = 1000

def test_bh_adjusted_pvalues_match_scipy():
    rng = np.random.default_rng(SEED)
    p = rng.uniform(0, 1, size=N_TESTS)

    ours = benjamini_hochberg(p, alpha=0.05)
    scipy_adjusted = false_discovery_control(p, method="bh")

    np.testing.assert_allclose(
        ours.adjusted_p_values, scipy_adjusted,
        rtol=1e-10, atol=1e-12,
        err_msg="BH-adjusted p-values diverge from scipy reference"
    )

def test_bh_significant_mask_matches_scipy_at_alpha():
    rng = np.random.default_rng(SEED + 1)
    p = rng.uniform(0, 1, size=N_TESTS)
    alpha = 0.05

    ours = benjamini_hochberg(p, alpha=alpha)
    scipy_adjusted = false_discovery_control(p, method="bh")
    expected_significant = scipy_adjusted <= alpha

    np.testing.assert_array_equal(
        ours.significant, expected_significant,
        err_msg="Significance mask diverges from scipy"
    )

def test_bh_edge_all_zeros():
    p = np.zeros(50)
    ours = benjamini_hochberg(p, alpha=0.05)
    assert ours.n_significant == 50

def test_bh_edge_all_ones():
    p = np.ones(50)
    ours = benjamini_hochberg(p, alpha=0.05)
    assert ours.n_significant == 0
```

Tolerances: `rtol=1e-10, atol=1e-12`. Two methods implementing the same
algorithm in float64 should agree to near machine precision; loosening past
1e-9 means something else is happening.

### Example B — ADF (statsmodels parity)

```python
# tests/stats/test_adf_canonical_parity.py
import numpy as np
from statsmodels.tsa.stattools import adfuller
from trading_research.stats.stationarity import adf_test  # our wrapper

SEED = 20260426
N = 5000

def test_adf_stationary_series_matches_statsmodels():
    """OU-like stationary series — both should reject the unit root."""
    rng = np.random.default_rng(SEED)
    x = np.zeros(N)
    for i in range(1, N):
        x[i] = 0.7 * x[i-1] + rng.normal()

    our_result = adf_test(x, maxlag=20, regression="c")
    sm_stat, sm_pvalue, sm_lags, sm_nobs, sm_crit, _ = adfuller(
        x, maxlag=20, regression="c", autolag=None
    )

    np.testing.assert_allclose(our_result.statistic, sm_stat, rtol=1e-9)
    np.testing.assert_allclose(our_result.p_value, sm_pvalue, rtol=1e-7)
    assert our_result.lags_used == sm_lags
    assert our_result.n_observations == sm_nobs

def test_adf_random_walk_matches_statsmodels():
    """Random walk — both should fail to reject the unit root."""
    rng = np.random.default_rng(SEED + 1)
    x = np.cumsum(rng.normal(size=N))

    our_result = adf_test(x, maxlag=20, regression="c")
    sm_stat, sm_pvalue, *_ = adfuller(x, maxlag=20, regression="c", autolag=None)

    np.testing.assert_allclose(our_result.statistic, sm_stat, rtol=1e-9)
    np.testing.assert_allclose(our_result.p_value, sm_pvalue, rtol=1e-7)
```

Note: `autolag=None` (fixed lag) is required for parity. `autolag="AIC"`
selects different lag counts under tiny numerical perturbations and breaks
parity. The project uses fixed lag anyway (per session 28 work log). The
test enforces this contract.

### Example C — OU half-life (OLS parity)

```python
# tests/stats/test_ou_half_life_canonical_parity.py
import numpy as np
import statsmodels.api as sm
from trading_research.stats.stationarity import ou_half_life

SEED = 20260426
N = 5000

def test_ou_half_life_matches_ols_fit():
    """OU process with known beta. Our half-life must match sm.OLS-derived value."""
    rng = np.random.default_rng(SEED)
    true_beta = 0.85  # 1 - mean reversion speed
    x = np.zeros(N)
    for i in range(1, N):
        x[i] = true_beta * x[i-1] + rng.normal()

    our_hl = ou_half_life(x)

    # Canonical: regress dx_t on x_{t-1}; beta = exp(-kappa*dt)
    dx = np.diff(x)
    x_lag = x[:-1]
    X = sm.add_constant(x_lag)
    fit = sm.OLS(dx, X).fit()
    canonical_beta = fit.params[1]
    canonical_hl = -np.log(2) / canonical_beta if canonical_beta < 0 else np.inf

    np.testing.assert_allclose(our_hl.half_life_bars, canonical_hl, rtol=1e-9)
```

If `our_hl` uses a different OLS specification (e.g., different lag scheme),
the test fails — and that is correct, because the project's documented OU
specification needs to match the canonical reference.

### Example D — OHLCV resampling (pandas parity)

For sprint B1 (timeframe catalog):

```python
# tests/data/test_resample_canonical_parity.py
import numpy as np
import pandas as pd
from trading_research.data.resampling import resample_ohlcv

SEED = 20260426

def test_5m_to_15m_matches_pandas_resample():
    rng = np.random.default_rng(SEED)
    n = 1000
    idx = pd.date_range("2024-01-02 09:30", periods=n, freq="5min", tz="UTC")
    bars = pd.DataFrame({
        "open":  rng.uniform(100, 101, n),
        "high":  rng.uniform(101, 102, n),
        "low":   rng.uniform( 99, 100, n),
        "close": rng.uniform(100, 101, n),
        "volume": rng.integers(1, 1000, n),
    }, index=idx)
    # Ensure high/low invariants
    bars["high"] = bars[["open","high","low","close"]].max(axis=1)
    bars["low"]  = bars[["open","high","low","close"]].min(axis=1)

    ours = resample_ohlcv(bars, "15min")
    canonical = bars.resample("15min", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()

    pd.testing.assert_frame_equal(
        ours[canonical.columns], canonical,
        check_exact=False, atol=1e-12, rtol=1e-12,
    )
```

`label="left"` and `closed="left"` are the project's convention (timestamp
labels the *start* of the bar). The test enforces this; if Gemini ships a
right-labeled resampler, the test fails loudly.

### Example E — Bootstrap CI (no canonical, use simulation)

When no canonical library exists (e.g., a custom Calmar bootstrap), the
parity test becomes a simulation:

```python
def test_calmar_bootstrap_recovers_known_distribution():
    """Generate trades from a known returns distribution; bootstrap CI must
    cover the analytical Calmar with ≈95% rate over many synthetic samples."""
    SEED = 20260426
    rng = np.random.default_rng(SEED)
    true_calmar = 1.5  # constructed from the input distribution

    n_repeats = 200
    coverage = 0
    for _ in range(n_repeats):
        sample = generate_synthetic_trades(rng, true_calmar=true_calmar, n=500)
        lo, hi = bootstrap_calmar_ci(sample, alpha=0.05, n_bootstrap=2000)
        if lo <= true_calmar <= hi:
            coverage += 1

    coverage_rate = coverage / n_repeats
    assert 0.90 <= coverage_rate <= 1.0, (
        f"Bootstrap 95% CI covers true Calmar at {coverage_rate:.2%} "
        f"(expected ~95%). Likely off-by-one in resampling or biased estimator."
    )
```

This is the harder pattern; it asserts a *property* (coverage rate) rather
than a value. Use only when no canonical reference exists. The spec author
must justify why.

---

## Tolerance reference

| Method class | rtol | atol | Why |
|---|---|---|---|
| Float arithmetic on identical algorithms | 1e-10 | 1e-12 | Near-machine precision |
| Statistical tests via different optimisers | 1e-7 | 1e-9 | Numerical optimiser differences |
| Iterative methods (e.g., MLE fits) | 1e-5 | 1e-7 | Convergence tolerance |
| Bootstrap / Monte Carlo | n/a | property-based | Coverage rate, not value |

If a Gemini sprint asks for looser tolerance, escalate. Loose tolerance
is where wrong code hides.

---

## What Gemini is allowed to do without escalating

- Implement the function body that satisfies the failing tests.
- Add private helper functions internal to the module.
- Refactor existing code that the spec explicitly authorises.
- Improve docstrings (without changing API).

## What Gemini must escalate

- "The canonical library returns a different shape — should I reshape?" → escalate.
- "The tolerance fails by 2× — can I loosen rtol?" → escalate.
- "There's no canonical reference for this case." → escalate; spec author
  must add a property-based test or mark the function not-Gemini-eligible.
- "The spec is missing X." → escalate; do not extrapolate.
- "An existing test conflicts with the new test." → escalate; do not silently
  change the existing test.

Escalation is cheap. Gemini-extrapolation is what produces the bugs we cannot
afford.

---

## Deployment

This playbook is referenced by every Gemini sprint spec. The spec includes:

```
## Validation
This sub-sprint follows the Gemini Validation Playbook.
- Canonical reference: <library>.<function>
- Parity test fixture: <test file path> (pre-written by spec author)
- Tolerance: rtol=<value>, atol=<value>
- Escalation contact: spec author of this sub-sprint
```

If a sprint spec lacks this section, the sub-sprint is not Gemini-eligible.
Run on Sonnet instead.
