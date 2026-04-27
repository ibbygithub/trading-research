"""Statistical analysis package for trading research.

Public API for the stationarity suite.
"""

from trading_research.stats.stationarity import (
    ADFResult,
    HurstResult,
    OUResult,
    StationarityReport,
    adf_test,
    hurst_exponent,
    ou_half_life,
    run_stationarity_suite,
)

__all__ = [
    "ADFResult",
    "HurstResult",
    "OUResult",
    "StationarityReport",
    "adf_test",
    "hurst_exponent",
    "ou_half_life",
    "run_stationarity_suite",
]
