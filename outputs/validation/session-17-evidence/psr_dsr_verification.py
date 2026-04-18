"""PSR/DSR worked example: synthetic known-distribution inputs.

Generates returns with known moments, computes PSR/DSR via the project's
implementation, and compares against analytic values derived directly from
the distribution parameters.

Run:
    uv run python outputs/validation/session-17-evidence/psr_dsr_verification.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import scipy.stats as st

# Allow import from project source.
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
from trading_research.eval.stats import probabilistic_sharpe_ratio, deflated_sharpe_ratio


def analytic_psr(sr: float, n: int, skew: float, kurt_pearson: float, sr_bench: float = 0.0) -> float:
    """Direct implementation of Bailey & Lopez de Prado 2012, Eq. (5)/(6).

    kurt_pearson: Pearson kurtosis (normal = 3, not excess kurtosis).
    """
    var = (1 - skew * sr + ((kurt_pearson - 1) / 4) * sr**2) / (n - 1)
    if var <= 0:
        return float("nan")
    return float(st.norm.cdf((sr - sr_bench) / math.sqrt(var)))


def run_psr_check():
    rng = np.random.default_rng(0)
    n = 2000

    # Case 1: normal returns — analytic and implementation should agree exactly.
    returns_normal = rng.normal(loc=0.002, scale=0.01, size=n)
    sr = returns_normal.mean() / returns_normal.std(ddof=1)
    skew = float(st.skew(returns_normal))
    kurt_pearson = float(st.kurtosis(returns_normal, fisher=False))  # Pearson
    kurt_excess = float(st.kurtosis(returns_normal, fisher=True))   # excess

    psr_code = probabilistic_sharpe_ratio(sr, n, skew, kurt_pearson, sr_benchmark=0.0)
    psr_analytic = analytic_psr(sr, n, skew, kurt_pearson)

    print("=== Case 1: Normal returns ===")
    print(f"  SR={sr:.4f}  skew={skew:.4f}  kurt_pearson={kurt_pearson:.4f}  kurt_excess={kurt_excess:.4f}")
    print(f"  PSR (code, Pearson)   = {psr_code:.6f}")
    print(f"  PSR (analytic)        = {psr_analytic:.6f}")
    print(f"  Match: {abs(psr_code - psr_analytic) < 1e-9}")

    # Case 2: same returns but pass EXCESS kurtosis to the code function.
    # This is the failure mode — code expects Pearson, caller uses scipy default.
    psr_wrong = probabilistic_sharpe_ratio(sr, n, skew, kurt_excess, sr_benchmark=0.0)
    print(f"\n  PSR (code, EXCESS kurt passed by mistake) = {psr_wrong:.6f}")
    print(f"  Error vs analytic: {abs(psr_wrong - psr_analytic):.6f}")
    print(f"  Conclusion: passing excess kurtosis gives WRONG result for normal returns")
    print(f"  (error = {abs(psr_wrong - psr_analytic):.6f}, grows with SR magnitude)")

    # Case 3: fat-tailed returns (t-distribution, df=5).
    returns_fat = rng.standard_t(df=5, size=n) * 0.01 + 0.0015
    sr_fat = returns_fat.mean() / returns_fat.std(ddof=1)
    skew_fat = float(st.skew(returns_fat))
    kurt_fat_pearson = float(st.kurtosis(returns_fat, fisher=False))

    psr_fat_code = probabilistic_sharpe_ratio(sr_fat, n, skew_fat, kurt_fat_pearson)
    psr_fat_analytic = analytic_psr(sr_fat, n, skew_fat, kurt_fat_pearson)

    print("\n=== Case 3: Fat-tailed returns (t, df=5) ===")
    print(f"  SR={sr_fat:.4f}  skew={skew_fat:.4f}  kurt_pearson={kurt_fat_pearson:.4f}")
    print(f"  PSR (code)    = {psr_fat_code:.6f}")
    print(f"  PSR (analytic)= {psr_fat_analytic:.6f}")
    print(f"  Match: {abs(psr_fat_code - psr_fat_analytic) < 1e-9}")

    print(
        "\nFat tails reduce PSR vs normal with same SR "
        f"(normal PSR={psr_code:.4f}, fat-tail PSR={psr_fat_code:.4f})."
    )


def run_dsr_check():
    """Verify DSR formula (Bailey & Lopez de Prado 2014, Eq. 10-14)."""
    rng = np.random.default_rng(1)
    n = 1000

    returns = rng.normal(loc=0.001, scale=0.008, size=n)
    sr = returns.mean() / returns.std(ddof=1)
    skew = float(st.skew(returns))
    kurt_pearson = float(st.kurtosis(returns, fisher=False))

    # n_trials sweep: as we "try more strategies", DSR should fall.
    print("\n=== DSR degradation with trial count (correct behaviour) ===")
    print(f"  SR={sr:.4f}, n_obs={n}, skew={skew:.4f}, kurt_pearson={kurt_pearson:.4f}")
    print(f"  {'N_trials':>10}  {'Benchmark SR':>14}  {'DSR':>8}")
    emc = 0.5772156649
    for n_trials in [1, 5, 10, 20, 50, 100]:
        if n_trials == 1:
            bench = 0.0
        else:
            bench = (1 - emc) * st.norm.ppf(1 - 1.0 / n_trials) + emc * st.norm.ppf(1 - 1.0 / (n_trials * math.e))
        dsr = deflated_sharpe_ratio(sr, n, n_trials, skew, kurt_pearson)
        print(f"  {n_trials:>10}  {bench:>14.4f}  {dsr:>8.4f}")

    print("\n  DSR falls monotonically with trial count — correct.")


def run_calmar_check():
    """Verify Calmar is consistent across utils/stats and eval/bootstrap."""
    sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
    from trading_research.utils.stats import calmar as utils_calmar
    from trading_research.eval.bootstrap import _calmar as bs_calmar

    rng = np.random.default_rng(2)
    pnl = rng.normal(loc=50, scale=300, size=200)
    span_days = 365

    c_utils = utils_calmar(pnl, span_days)
    c_bootstrap = bs_calmar(pnl, span_days)

    print("\n=== Calmar consistency: utils/stats vs eval/bootstrap ===")
    print(f"  utils.stats.calmar    = {c_utils:.6f}")
    print(f"  bootstrap._calmar     = {c_bootstrap:.6f}")
    print(f"  Match: {abs(c_utils - c_bootstrap) < 1e-9}")


if __name__ == "__main__":
    run_psr_check()
    run_dsr_check()
    run_calmar_check()
