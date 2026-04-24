"""Stationarity suite: ADF, Hurst exponent, OU half-life.

Three independent tests that together characterise whether a series is
mean-reverting at a tradeable speed:

- ADF: formal hypothesis test for a unit root.
- Hurst exponent: long-range memory descriptor (R/S method).
- OU half-life: implied reversion speed via Ornstein-Uhlenbeck OLS fit.

Design spec: docs/design/stationarity-suite.md
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Thresholds — from design doc §4. Do NOT change without justification.
# ---------------------------------------------------------------------------

_ADF_STRONG = 0.01
_ADF_WEAK = 0.05

_HURST_MR_STRONG = 0.40
_HURST_MR_WEAK = 0.45
_HURST_RW_LOW = 0.45
_HURST_RW_HIGH = 0.55
_HURST_TREND_WEAK = 0.60

# OU tradeable half-life ranges (bars) by timeframe — design doc §4.3.
_OU_TRADEABLE: dict[str, tuple[float, float]] = {
    "1m": (5.0, 60.0),
    "5m": (3.0, 24.0),
    "15m": (2.0, 8.0),
}
_OU_MIN_OBS = 10
_HURST_MIN_OBS = 32

# Window sizes for Hurst R/S analysis — design doc §2.2.
_HURST_WINDOWS = [8, 16, 32, 64, 128, 256, 512]


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ADFResult:
    statistic: float
    p_value: float
    lags_used: int
    n_observations: int
    critical_values: dict[str, float]
    is_stationary: bool
    interpretation: str


@dataclass
class HurstResult:
    exponent: float
    n_windows: int
    r_squared: float
    interpretation: str


@dataclass
class OUResult:
    half_life_bars: float
    beta: float
    r_squared: float
    interpretation: str


@dataclass
class StationarityReport:
    instrument: str
    run_ts: datetime
    code_version: str
    data_version: str
    results: pd.DataFrame
    composite: dict[str, str]

    def to_summary_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable summary (metadata + composite only)."""
        return {
            "instrument": self.instrument,
            "run_ts": self.run_ts.isoformat(),
            "code_version": self.code_version,
            "data_version": self.data_version,
            "series": self.composite,
        }

    def to_summary_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_summary_dict(), indent=indent)

    @classmethod
    def from_summary_dict(
        cls,
        d: dict[str, Any],
        results: pd.DataFrame,
    ) -> StationarityReport:
        return cls(
            instrument=d["instrument"],
            run_ts=datetime.fromisoformat(d["run_ts"]),
            code_version=d["code_version"],
            data_version=d["data_version"],
            results=results,
            composite=d["series"],
        )


# ---------------------------------------------------------------------------
# Interpretation helpers
# ---------------------------------------------------------------------------


def _interpret_adf(p_value: float) -> str:
    if p_value < _ADF_STRONG:
        return "STATIONARY (strong)"
    if p_value < _ADF_WEAK:
        return "STATIONARY (weak)"
    return "NON_STATIONARY"


def _interpret_hurst(h: float) -> str:
    if math.isnan(h):
        return "INSUFFICIENT_DATA"
    if h < _HURST_MR_STRONG:
        return "MEAN_REVERTING (strong)"
    if h < _HURST_MR_WEAK:
        return "MEAN_REVERTING (weak)"
    if h <= _HURST_RW_HIGH:
        return "RANDOM_WALK"
    if h < _HURST_TREND_WEAK:
        return "TRENDING (weak)"
    return "TRENDING (strong)"


def _interpret_ou(half_life: float, timeframe: str) -> str:
    if math.isinf(half_life) or math.isnan(half_life):
        return "TRENDING" if half_life > 0 else "RANDOM_WALK"
    bounds = _OU_TRADEABLE.get(timeframe)
    if bounds is None:
        return "UNKNOWN_TIMEFRAME"
    lo, hi = bounds
    if half_life < lo:
        return "TOO_FAST"
    if half_life > hi:
        return "TOO_SLOW"
    return "TRADEABLE"


def _composite_classification(
    adf: ADFResult,
    hurst: HurstResult,
    ou: OUResult,
    timeframe: str,
) -> str:
    """Derive the per-series composite label per design doc §4.4."""
    adf_pass = adf.p_value < _ADF_WEAK
    h = hurst.exponent
    hurst_mr = not math.isnan(h) and h < _HURST_MR_WEAK
    hurst_trending = not math.isnan(h) and h > _HURST_RW_HIGH
    hurst_rw = not math.isnan(h) and _HURST_RW_LOW <= h <= _HURST_RW_HIGH
    ou_interp = _interpret_ou(ou.half_life_bars, timeframe)

    if not adf_pass:
        return "NON_STATIONARY"
    if hurst_trending:
        return "TRENDING"
    if hurst_rw:
        return "RANDOM_WALK"
    if hurst_mr:
        if ou_interp == "TOO_FAST":
            return "TOO_FAST"
        if ou_interp == "TOO_SLOW":
            return "TOO_SLOW"
        if ou_interp == "TRADEABLE":
            return "TRADEABLE_MR"
        return "INDETERMINATE"
    return "INDETERMINATE"


# ---------------------------------------------------------------------------
# ADF
# ---------------------------------------------------------------------------


def adf_test(
    series: pd.Series,
    maxlag: int | None = None,
    regression: str = "c",
) -> ADFResult:
    """Augmented Dickey-Fuller test wrapper.

    Parameters
    ----------
    series:
        Time-series values. NaNs are dropped before testing.
    maxlag:
        Maximum lag to consider. None → AIC selection.
    regression:
        'c' for constant (returns/spreads), 'ct' for constant+trend (levels).
    """
    from statsmodels.tsa.stattools import adfuller

    clean = series.dropna()
    if len(clean) < 20:
        raise ValueError(f"ADF requires at least 20 observations; got {len(clean)}")

    autolag = "AIC" if maxlag is None else None
    result = adfuller(clean, maxlag=maxlag, autolag=autolag, regression=regression)

    stat, pval, lags_used, n_obs, crit_vals = (
        result[0], result[1], result[2], result[3], result[4],
    )
    return ADFResult(
        statistic=float(stat),
        p_value=float(pval),
        lags_used=int(lags_used),
        n_observations=int(n_obs),
        critical_values={k: float(v) for k, v in crit_vals.items()},
        is_stationary=bool(pval < _ADF_WEAK),
        interpretation=_interpret_adf(float(pval)),
    )


# ---------------------------------------------------------------------------
# Hurst exponent — rescaled-range (R/S) method
# ---------------------------------------------------------------------------


def _rs_for_window(segment: np.ndarray) -> float:
    """R/S statistic for a single segment."""
    if len(segment) < 2:
        return float("nan")
    mean = np.mean(segment)
    deviations = np.cumsum(segment - mean)
    r = np.max(deviations) - np.min(deviations)
    s = np.std(segment, ddof=1)
    if s == 0.0:
        return float("nan")
    return r / s


def hurst_exponent(
    series: pd.Series,
    min_window: int = 10,
    max_window: int | None = None,
) -> HurstResult:
    """Hurst exponent via rescaled-range (R/S) analysis.

    Parameters
    ----------
    series:
        Time-series values. NaNs are dropped.
    min_window:
        Smallest segment size to consider.
    max_window:
        Largest segment size. Defaults to len(series) // 2.
    """
    arr = np.asarray(series.dropna(), dtype=float)
    n = len(arr)

    if n < _HURST_MIN_OBS:
        logger.warning("hurst_exponent: insufficient observations", n=n)
        return HurstResult(
            exponent=float("nan"),
            n_windows=0,
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    effective_max = max_window if max_window is not None else n // 2
    windows = [w for w in _HURST_WINDOWS if min_window <= w <= effective_max]
    if len(windows) < 2:
        logger.warning("hurst_exponent: fewer than 2 valid windows", windows=windows)
        return HurstResult(
            exponent=float("nan"),
            n_windows=len(windows),
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    log_ns: list[float] = []
    log_rs: list[float] = []

    for w in windows:
        n_segments = n // w
        if n_segments < 1:
            continue
        rs_values = []
        for i in range(n_segments):
            seg = arr[i * w : (i + 1) * w]
            rs = _rs_for_window(seg)
            if not math.isnan(rs):
                rs_values.append(rs)
        if rs_values:
            log_ns.append(math.log(w))
            log_rs.append(math.log(np.mean(rs_values)))

    if len(log_ns) < 2:
        return HurstResult(
            exponent=float("nan"),
            n_windows=len(log_ns),
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    from scipy.stats import linregress

    slope, intercept, r_value, _, _ = linregress(log_ns, log_rs)
    r_sq = float(r_value ** 2)
    h = float(slope)

    return HurstResult(
        exponent=h,
        n_windows=len(log_ns),
        r_squared=r_sq,
        interpretation=_interpret_hurst(h),
    )


# ---------------------------------------------------------------------------
# OU half-life — Ornstein-Uhlenbeck OLS fit
# ---------------------------------------------------------------------------


def ou_half_life(series: pd.Series) -> OUResult:
    """Ornstein-Uhlenbeck half-life via OLS regression of Δy on y_{t-1}.

    Fits Δy_t = α + β * y_{t-1} + ε_t.  Half-life = ln(2) / (−β).
    β must be negative for mean reversion.
    """
    arr = np.asarray(series.dropna(), dtype=float)

    if len(arr) < _OU_MIN_OBS:
        logger.warning("ou_half_life: insufficient observations", n=len(arr))
        return OUResult(
            half_life_bars=float("nan"),
            beta=float("nan"),
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    y = arr[:-1]
    delta_y = arr[1:] - arr[:-1]

    # OLS: delta_y = alpha + beta * y  →  design matrix [1, y]
    design = np.column_stack([np.ones(len(y)), y])
    coeffs, _, rank, _ = np.linalg.lstsq(design, delta_y, rcond=None)
    beta = float(coeffs[1])

    # Compute R².
    y_hat = design @ coeffs
    ss_res = float(np.sum((delta_y - y_hat) ** 2))
    ss_tot = float(np.sum((delta_y - np.mean(delta_y)) ** 2))
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    # Classify and compute half-life.
    if abs(beta) < 1e-10:
        return OUResult(
            half_life_bars=float("inf"),
            beta=beta,
            r_squared=r_sq,
            interpretation="RANDOM_WALK",
        )
    if beta >= 0:
        return OUResult(
            half_life_bars=float("inf"),
            beta=beta,
            r_squared=r_sq,
            interpretation="TRENDING",
        )

    hl = math.log(2.0) / (-beta)
    return OUResult(
        half_life_bars=hl,
        beta=beta,
        r_squared=r_sq,
        interpretation="MEAN_REVERTING",
    )


# ---------------------------------------------------------------------------
# Series construction helpers
# ---------------------------------------------------------------------------


def _session_vwap(bars: pd.DataFrame) -> pd.Series:
    """Session VWAP reset on gaps > 60 minutes. Returns Series aligned to bars index."""
    ts = pd.to_datetime(bars["timestamp_utc"], utc=True)
    close = bars["close"].astype(float)
    volume = pd.to_numeric(bars.get("volume", pd.Series(1.0, index=bars.index)), errors="coerce").fillna(1.0)

    gap_min = ts.diff().dt.total_seconds().div(60).fillna(0.0)
    session_id = (gap_min > 60).cumsum()

    cum_vol = volume.groupby(session_id).cumsum()
    cum_tp_vol = (close * volume).groupby(session_id).cumsum()
    return cum_tp_vol / cum_vol.replace(0.0, float("nan"))


def _resample_close(bars: pd.DataFrame, freq: str) -> pd.Series:
    """Resample close to a higher timeframe, dropping gaps."""
    ts = pd.to_datetime(bars["timestamp_utc"], utc=True)
    close = pd.Series(bars["close"].astype(float).values, index=ts)
    return close.resample(freq, closed="left", label="left").last().dropna()


def _resample_vwap_spread(bars: pd.DataFrame, freq: str) -> pd.Series:
    """close − session_VWAP resampled to freq."""
    ts = pd.to_datetime(bars["timestamp_utc"], utc=True)
    vwap = pd.Series(_session_vwap(bars).values, index=ts)
    close = pd.Series(bars["close"].astype(float).values, index=ts)

    close_r = close.resample(freq, closed="left", label="left").last()
    vwap_r = vwap.resample(freq, closed="left", label="left").last()
    return (close_r - vwap_r).dropna()


# Maps timeframe label → (pandas resample freq, ADF regression type)
_TIMEFRAME_FREQ: dict[str, tuple[str, str]] = {
    "1m": ("1min", "c"),
    "5m": ("5min", "c"),
    "15m": ("15min", "c"),
}


def _build_series_for_timeframe(
    bars_1m: pd.DataFrame,
    timeframe: str,
) -> dict[str, tuple[pd.Series, str]]:
    """Return dict of series_name → (series, adf_regression) for a timeframe.

    Constructs only the series defined in design doc §3.
    """
    freq, default_reg = _TIMEFRAME_FREQ.get(timeframe, ("1min", "c"))
    series_map: dict[str, tuple[pd.Series, str]] = {}

    if timeframe == "1m":
        close = _resample_close(bars_1m, freq)
        log_close = np.log(close)
        series_map["log_returns_1m"] = (log_close.diff().dropna(), "c")
        series_map["log_price_level"] = (log_close.dropna(), "ct")

    elif timeframe == "5m":
        close = _resample_close(bars_1m, freq)
        series_map["log_returns_5m"] = (np.log(close).diff().dropna(), "c")
        series_map["vwap_spread_5m"] = (_resample_vwap_spread(bars_1m, freq), "c")

    elif timeframe == "15m":
        close = _resample_close(bars_1m, freq)
        series_map["log_returns_15m"] = (np.log(close).diff().dropna(), "c")
        series_map["vwap_spread_15m"] = (_resample_vwap_spread(bars_1m, freq), "c")

    return series_map


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_stationarity_suite(
    instrument: Any,
    bars: pd.DataFrame,
    timeframes: list[str],
) -> StationarityReport:
    """Run ADF, Hurst, and OU on all series for the given timeframes.

    Parameters
    ----------
    instrument:
        Instrument object (must have .symbol attribute).
    bars:
        1-minute OHLCV bars with timestamp_utc column (tz-aware UTC).
    timeframes:
        List of timeframe labels to test, e.g. ["1m", "5m", "15m"].
    """
    symbol = instrument.symbol if hasattr(instrument, "symbol") else str(instrument)
    now_utc = datetime.now(UTC)
    code_version = _git_sha()
    data_version = _data_hash(bars)

    rows: list[dict[str, Any]] = []
    composite: dict[str, str] = {}

    for tf in timeframes:
        series_map = _build_series_for_timeframe(bars, tf)
        for series_name, (s, adf_reg) in series_map.items():
            logger.info(
                "stationarity_suite.testing",
                instrument=symbol,
                timeframe=tf,
                series=series_name,
                n=len(s),
            )
            try:
                adf = adf_test(s, regression=adf_reg)
            except ValueError as exc:
                logger.warning("adf_test skipped", series=series_name, reason=str(exc))
                continue

            hurst = hurst_exponent(s)
            ou = ou_half_life(s)
            comp = _composite_classification(adf, hurst, ou, tf)
            composite[series_name] = comp

            # ADF row
            rows.append({
                "instrument": symbol,
                "timeframe": tf,
                "series_name": series_name,
                "test_name": "adf",
                "statistic": adf.statistic,
                "p_value": adf.p_value,
                "n_lags": adf.lags_used,
                "n_obs": adf.n_observations,
                "interpretation": adf.interpretation,
                "composite": comp,
                "run_ts": now_utc,
                "code_version": code_version,
                "data_version": data_version,
            })
            # Hurst row
            rows.append({
                "instrument": symbol,
                "timeframe": tf,
                "series_name": series_name,
                "test_name": "hurst",
                "statistic": hurst.exponent,
                "p_value": float("nan"),
                "n_lags": float("nan"),
                "n_obs": len(s),
                "interpretation": hurst.interpretation,
                "composite": comp,
                "run_ts": now_utc,
                "code_version": code_version,
                "data_version": data_version,
            })
            # OU row
            rows.append({
                "instrument": symbol,
                "timeframe": tf,
                "series_name": series_name,
                "test_name": "ou_halflife",
                "statistic": ou.half_life_bars,
                "p_value": float("nan"),
                "n_lags": float("nan"),
                "n_obs": len(s),
                "interpretation": _interpret_ou(ou.half_life_bars, tf),
                "composite": comp,
                "run_ts": now_utc,
                "code_version": code_version,
                "data_version": data_version,
            })

    results_df = pd.DataFrame(rows) if rows else pd.DataFrame()

    return StationarityReport(
        instrument=symbol,
        run_ts=now_utc,
        code_version=code_version,
        data_version=data_version,
        results=results_df,
        composite=composite,
    )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def write_report(
    report: StationarityReport,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Write parquet results, JSON summary, and markdown to output_dir.

    Returns (parquet_path, json_path, markdown_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = output_dir / "results.parquet"
    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"

    if not report.results.empty:
        report.results.to_parquet(parquet_path, engine="pyarrow", index=False)

    json_path.write_text(report.to_summary_json(), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    return parquet_path, json_path, md_path


def _render_markdown(report: StationarityReport) -> str:
    lines = [
        f"# Stationarity Report — {report.instrument}",
        "",
        f"**Run:** {report.run_ts.strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Code version:** {report.code_version}  ",
        f"**Data version:** {report.data_version}  ",
        "",
        "## Composite Classifications",
        "",
        "| Series | Classification |",
        "|---|---|",
    ]
    for series_name, label in sorted(report.composite.items()):
        lines.append(f"| `{series_name}` | {label} |")

    if not report.results.empty:
        lines += [
            "",
            "## Detailed Results",
            "",
            "| Series | Timeframe | Test | Statistic | p-value | Interpretation |",
            "|---|---|---|---|---|---|",
        ]
        for _, row in report.results.iterrows():
            pv = f"{row['p_value']:.4f}" if not (isinstance(row["p_value"], float) and math.isnan(row["p_value"])) else "—"
            stat = f"{row['statistic']:.4f}" if not (isinstance(row["statistic"], float) and math.isnan(row["statistic"])) else "—"
            lines.append(
                f"| `{row['series_name']}` | {row['timeframe']} | {row['test_name']} "
                f"| {stat} | {pv} | {row['interpretation']} |"
            )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _git_sha() -> str:
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        sha = result.stdout.strip()
        return sha if sha else "unknown"
    except Exception:
        return "unknown"


def _data_hash(bars: pd.DataFrame) -> str:
    """Fast hash of the bars DataFrame for provenance tracking."""
    try:
        import hashlib

        return hashlib.md5(  # noqa: S324 — non-security hash for provenance
            pd.util.hash_pandas_object(bars, index=True).values.tobytes()
        ).hexdigest()[:8]
    except Exception:
        return "unknown"
