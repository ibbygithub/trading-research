"""Stationarity suite: ADF, Hurst exponent, OU half-life.

Three independent tests that together characterise whether a series is
mean-reverting at a tradeable speed:

- ADF: formal hypothesis test for a unit root.
- Hurst exponent: long-range memory descriptor (DFA method).
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


def _interpret_ou(
    half_life: float,
    timeframe: str,
    instrument: Any | None = None,
) -> str:
    if math.isinf(half_life) or math.isnan(half_life):
        return "TRENDING" if half_life > 0 else "RANDOM_WALK"

    # Prefer per-instrument bounds from the Instrument registry (session 29).
    bounds: tuple[float, float] | None = None
    if instrument is not None and hasattr(instrument, "get_ou_bounds"):
        bounds = instrument.get_ou_bounds(timeframe)
    if bounds is None:
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
    instrument: Any | None = None,
) -> str:
    """Derive the per-series composite label per design doc §4.4.

    Session 27 change (Option A): ADF + OU half-life are the primary gates for
    TRADEABLE_MR.  Hurst is informational and still blocks when it says TRENDING
    (a contradiction with ADF stationarity), but Hurst RANDOM_WALK (H ≈ 0.5) no
    longer prevents TRADEABLE_MR classification.

    Rationale: DFA gives H ≈ 0.5 for any short-memory stationary AR(1) process,
    including positive-φ OU processes like VWAP spreads.  Requiring H < 0.45 as a
    gate would incorrectly block genuinely mean-reverting series.  ADF rejection of
    the unit root + tradeable OU half-life is sufficient evidence.
    """
    adf_pass = adf.p_value < _ADF_WEAK
    h = hurst.exponent
    hurst_trending = not math.isnan(h) and h > _HURST_RW_HIGH
    ou_interp = _interpret_ou(ou.half_life_bars, timeframe, instrument=instrument)

    if not adf_pass:
        return "NON_STATIONARY"

    # Hurst TRENDING contradicts ADF stationarity — flag the disagreement.
    if hurst_trending:
        return "INDETERMINATE"

    # ADF + OU are the primary gates.  Hurst RANDOM_WALK (H ≈ 0.5) is
    # expected for short-memory OU processes and does not block TRADEABLE_MR.
    if ou_interp == "TOO_FAST":
        return "TOO_FAST"
    if ou_interp == "TOO_SLOW":
        return "TOO_SLOW"
    if ou_interp == "TRADEABLE":
        return "TRADEABLE_MR"

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
# Hurst exponent — DFA (Detrended Fluctuation Analysis)
#
# Replaces the R/S estimator used in session 26. The R/S method classifies
# any AR(1) process with positive φ as TRENDING or RANDOM_WALK, even when
# the series is stationary and mean-reverting. A VWAP spread behaves as an
# OU process with positive φ at the bar level (price overshoots and takes
# several bars to return), so R/S systematically misclassified it.
#
# DFA measures how local fluctuations scale with window size after removing
# local polynomial trends. This makes it insensitive to φ sign: a stationary
# OU process — regardless of whether φ is positive or negative — produces
# H < 0.5, which is the correct discriminant for mean-reversion detection.
#
# Reference: Peng et al. (1994); Mantegna & Stanley (1999) ch. 4.
# ---------------------------------------------------------------------------


def _rs_hurst(
    arr: np.ndarray,
    min_window: int,
    max_window: int,
) -> HurstResult:
    """Rescaled-range (R/S) Hurst estimator — kept as private reference.

    Not exposed in the public API. Use dfa_hurst / hurst_exponent instead.
    Retained so test_dfa_vs_rs_comparison can call it directly to document
    the pre-session-27 behaviour on AR(1) φ=0.5.
    """
    n = len(arr)
    windows = [w for w in _HURST_WINDOWS if min_window <= w <= max_window]
    if len(windows) < 2:
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
            if len(seg) < 2:
                continue
            mean = np.mean(seg)
            deviations = np.cumsum(seg - mean)
            r = np.max(deviations) - np.min(deviations)
            s = np.std(seg, ddof=1)
            if s != 0.0:
                rs_values.append(r / s)
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

    slope, _, r_value, _, _ = linregress(log_ns, log_rs)
    h = float(slope)
    return HurstResult(
        exponent=h,
        n_windows=len(log_ns),
        r_squared=float(r_value ** 2),
        interpretation=_interpret_hurst(h),
    )


def dfa_hurst(
    series: pd.Series,
    min_window: int = 10,
    max_window: int | None = None,
    poly_order: int = 1,
) -> HurstResult:
    """Hurst exponent via Detrended Fluctuation Analysis (DFA).

    DFA correctly classifies OU processes with *positive* AR(1) coefficient as
    mean-reverting (H < 0.5), unlike R/S which misclassifies them as persistent.
    This matters for VWAP-spread series where consecutive bars overshoot before
    reverting — the spread has positive lag-1 autocorrelation even though it is
    stationary and mean-reverting.

    Algorithm (Peng et al. 1994):
    1. Mean-subtract and cumulatively sum the input series (integrate).
    2. For each window size w, split the integrated series into non-overlapping
       segments of length w.
    3. Fit a polynomial of degree poly_order to each segment and compute the
       RMS of residuals: the fluctuation function F(w).
    4. Average F(w) across segments for each w.
    5. OLS on log(mean_F) vs log(w). Slope = Hurst exponent.

    Parameters
    ----------
    series:
        Raw level or spread values (NOT pre-integrated). NaNs are dropped.
    min_window:
        Smallest segment size to use.
    max_window:
        Largest segment size. Defaults to len(series) // 2.
    poly_order:
        Polynomial degree for local detrending. 1 = linear (standard DFA-1).
    """
    arr = np.asarray(series.dropna(), dtype=float)
    n = len(arr)

    if n < _HURST_MIN_OBS:
        logger.warning("dfa_hurst: insufficient observations", n=n)
        return HurstResult(
            exponent=float("nan"),
            n_windows=0,
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    # Integrate: cumulative sum of mean-subtracted series (standard DFA step).
    integrated = np.cumsum(arr - np.mean(arr))

    effective_max = max_window if max_window is not None else n // 2
    windows = [w for w in _HURST_WINDOWS if min_window <= w <= effective_max]
    if len(windows) < 2:
        logger.warning("dfa_hurst: fewer than 2 valid windows", windows=windows)
        return HurstResult(
            exponent=float("nan"),
            n_windows=len(windows),
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    log_ws: list[float] = []
    log_fs: list[float] = []

    x_template = {w: np.arange(w, dtype=float) for w in windows}

    for w in windows:
        n_segments = n // w
        if n_segments < 1:
            continue
        f_sq_vals: list[float] = []
        x = x_template[w]
        vander = np.vander(x, N=poly_order + 1, increasing=True)
        for i in range(n_segments):
            seg = integrated[i * w : (i + 1) * w]
            coeffs, _, _, _ = np.linalg.lstsq(vander, seg, rcond=None)
            residuals = seg - vander @ coeffs
            f_sq_vals.append(float(np.mean(residuals ** 2)))
        if f_sq_vals:
            mean_f = math.sqrt(np.mean(f_sq_vals))
            if mean_f > 0.0:
                log_ws.append(math.log(w))
                log_fs.append(math.log(mean_f))

    if len(log_ws) < 2:
        return HurstResult(
            exponent=float("nan"),
            n_windows=len(log_ws),
            r_squared=float("nan"),
            interpretation="INSUFFICIENT_DATA",
        )

    from scipy.stats import linregress

    slope, _, r_value, _, _ = linregress(log_ws, log_fs)
    h = float(slope)
    return HurstResult(
        exponent=h,
        n_windows=len(log_ws),
        r_squared=float(r_value ** 2),
        interpretation=_interpret_hurst(h),
    )


def hurst_exponent(
    series: pd.Series,
    min_window: int = 10,
    max_window: int | None = None,
) -> HurstResult:
    """Hurst exponent via DFA (Detrended Fluctuation Analysis).

    DFA replaced R/S in session 27. R/S was misclassifying OU processes with
    positive AR(1) coefficient (e.g. VWAP spread) as TRENDING/RANDOM_WALK.
    DFA gives H < 0.5 for any stationary mean-reverting process regardless of
    the sign of φ, which is the correct discriminant for strategy selection.

    Parameters
    ----------
    series:
        Time-series values (raw level or spread). NaNs are dropped.
    min_window:
        Smallest segment size to consider.
    max_window:
        Largest segment size. Defaults to len(series) // 2.
    """
    return dfa_hurst(series, min_window=min_window, max_window=max_window)


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
            comp = _composite_classification(adf, hurst, ou, tf, instrument=instrument)
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
                "interpretation": _interpret_ou(ou.half_life_bars, tf, instrument=instrument),
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
