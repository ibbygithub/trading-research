"""Parity test: OU half-life against statsmodels OLS canonical reference.

Validates that our ou_half_life implementation produces results numerically
identical to statsmodels.api.OLS for the Ornstein-Uhlenbeck regression
Δy_t = α + β * y_{t-1} + ε_t, where half_life = ln(2) / (-β).

Spec: session 29d, gemini-validation-playbook Example C.
Tolerance: rtol=1e-9, atol=1e-12.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import statsmodels.api as sm

from trading_research.stats.stationarity import ou_half_life

SEED = 20260426
N = 5000


@pytest.fixture()
def ou_series() -> np.ndarray:
    """Generate a synthetic OU process for parity testing."""
    rng = np.random.default_rng(SEED)
    mu = 0.0
    theta = 0.05
    sigma = 0.3
    x = np.zeros(N)
    x[0] = rng.normal(0, 1)
    for i in range(1, N):
        x[i] = x[i - 1] + theta * (mu - x[i - 1]) + sigma * rng.normal()
    return x


def _canonical_ou_halflife(series: np.ndarray) -> tuple[float, float, float]:
    """Compute OU half-life using statsmodels OLS as canonical reference."""
    y = series[:-1]
    delta_y = series[1:] - series[:-1]
    X = sm.add_constant(y)
    model = sm.OLS(delta_y, X).fit()
    beta = model.params[1]
    r_squared = model.rsquared
    if beta >= 0 or abs(beta) < 1e-10:
        return float("inf"), beta, r_squared
    half_life = math.log(2) / (-beta)
    return half_life, beta, r_squared


def test_ou_halflife_matches_statsmodels(ou_series: np.ndarray) -> None:
    """Our ou_half_life must match statsmodels OLS to tight numerical tolerance."""
    import pandas as pd

    our_result = ou_half_life(pd.Series(ou_series))
    canon_hl, canon_beta, canon_r2 = _canonical_ou_halflife(ou_series)

    np.testing.assert_allclose(
        our_result.half_life_bars,
        canon_hl,
        rtol=1e-9,
        atol=1e-12,
        err_msg="OU half-life diverges from statsmodels canonical",
    )

    np.testing.assert_allclose(
        our_result.beta,
        canon_beta,
        rtol=1e-9,
        atol=1e-12,
        err_msg="OU beta diverges from statsmodels canonical",
    )

    np.testing.assert_allclose(
        our_result.r_squared,
        canon_r2,
        rtol=1e-9,
        atol=1e-12,
        err_msg="OU R² diverges from statsmodels canonical",
    )


def test_ou_halflife_positive_for_mean_reverting(ou_series: np.ndarray) -> None:
    """Synthetic OU with positive theta must produce positive half-life."""
    import pandas as pd

    result = ou_half_life(pd.Series(ou_series))
    assert result.half_life_bars > 0
    assert result.beta < 0
    assert result.interpretation == "MEAN_REVERTING"
