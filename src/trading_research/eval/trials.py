"""Trial registry — per-run tracking with cohort versioning for honest DSR.

Registry format (JSON):
    {
        "trials": [ <Trial dict>, ... ]
    }

Each Trial carries a ``code_version`` (git short SHA at time of record) and a
``cohort_label`` (defaults to code_version) so that Deflated Sharpe Ratio is
only computed within trials produced by the same engine version.

Cross-cohort DSR is intentionally disabled: comparing DSR across engine
versions is apples-to-oranges because the underlying backtest procedure
changed.  Callers that need cross-cohort data should group by cohort first.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog

from trading_research.eval.stats import deflated_sharpe_ratio

logger = structlog.get_logger(__name__)

MIN_TRIALS_FOR_DSR = 2

# Assumed defaults when per-trial statistical moments are missing.
# These assume normal returns with one year of daily observations.
_DEFAULT_N_OBS = 252
_DEFAULT_SKEWNESS = 0.0
_DEFAULT_KURTOSIS_PEARSON = 3.0  # Pearson kurtosis, normal distribution


@dataclass
class Trial:
    """A single recorded backtest trial."""

    timestamp: str
    strategy_id: str
    config_hash: str
    sharpe: float
    trial_group: str
    code_version: str
    featureset_hash: str | None
    cohort_label: str
    # Statistical moments — populated by record_trial when available.
    # When None, compute_dsr() falls back to conservative defaults.
    n_obs: int | None = None
    skewness: float | None = None
    kurtosis_pearson: float | None = None
    # Session-35 fields: exploration/validation tagging and sweep grouping.
    mode: str = "validation"
    parent_sweep_id: str | None = None
    # Performance metrics stored at record time for leaderboard use.
    calmar: float | None = None
    max_drawdown_usd: float | None = None
    win_rate: float | None = None
    total_trades: int | None = None
    instrument: str | None = None
    timeframe: str | None = None
    # Bootstrap CI bounds (90%) — populated when available.
    sharpe_ci_lo: float | None = None
    sharpe_ci_hi: float | None = None
    calmar_ci_lo: float | None = None
    calmar_ci_hi: float | None = None


def _get_code_version() -> str:
    """Return the current git short SHA, or 'unknown' if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _registry_path(runs_root: Path) -> Path:
    return runs_root / ".trials.json"


def _load_raw(path: Path) -> list[dict]:
    """Read the JSON registry and return the trials list.

    Handles both the legacy flat-list format and the current dict format.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("trials", [])
    return []


def _write_registry(path: Path, trials: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"trials": trials}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _dict_to_trial(d: dict) -> Trial:
    return Trial(
        timestamp=d.get("timestamp", ""),
        strategy_id=d.get("strategy_id", ""),
        config_hash=d.get("config_hash", ""),
        sharpe=float(d.get("sharpe", math.nan)),
        trial_group=d.get("trial_group", d.get("strategy_id", "")),
        code_version=d.get("code_version", "unknown"),
        featureset_hash=d.get("featureset_hash"),
        cohort_label=d.get("cohort_label", d.get("code_version", "unknown")),
        n_obs=d.get("n_obs"),
        skewness=d.get("skewness"),
        kurtosis_pearson=d.get("kurtosis_pearson"),
        # Session-35 fields — default to "validation"/None for backwards compat.
        mode=d.get("mode", "validation"),
        parent_sweep_id=d.get("parent_sweep_id"),
        calmar=d.get("calmar"),
        max_drawdown_usd=d.get("max_drawdown_usd"),
        win_rate=d.get("win_rate"),
        total_trades=d.get("total_trades"),
        instrument=d.get("instrument"),
        timeframe=d.get("timeframe"),
        sharpe_ci_lo=d.get("sharpe_ci_lo"),
        sharpe_ci_hi=d.get("sharpe_ci_hi"),
        calmar_ci_lo=d.get("calmar_ci_lo"),
        calmar_ci_hi=d.get("calmar_ci_hi"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_trials_file(runs_root: Path) -> Path:
    return _registry_path(runs_root)


def load_trials(path: Path | None = None) -> list[Trial]:
    """Load all trials from the registry.

    Args:
        path: Path to the .trials.json file.  Defaults to ``runs/.trials.json``
              relative to the project root (two levels above this file's
              ``src/`` directory).
    """
    if path is None:
        path = Path(__file__).resolve().parents[3] / "runs" / ".trials.json"
    raw = _load_raw(path)
    return [_dict_to_trial(d) for d in raw]


def record_trial(
    runs_root: Path,
    strategy_id: str,
    config_path: Path,
    sharpe: float,
    trial_group: str | None = None,
    featureset_hash: str | None = None,
    cohort_label: str | None = None,
    n_obs: int | None = None,
    skewness: float | None = None,
    kurtosis_pearson: float | None = None,
    mode: str = "validation",
    parent_sweep_id: str | None = None,
    calmar: float | None = None,
    max_drawdown_usd: float | None = None,
    win_rate: float | None = None,
    total_trades: int | None = None,
    instrument: str | None = None,
    timeframe: str | None = None,
    sharpe_ci_lo: float | None = None,
    sharpe_ci_hi: float | None = None,
    calmar_ci_lo: float | None = None,
    calmar_ci_hi: float | None = None,
) -> None:
    """Append a trial entry to the registry.

    New entries always carry the current git SHA as ``code_version`` and
    default ``cohort_label`` to that SHA.
    """
    tf = _registry_path(runs_root)
    raw = _load_raw(tf)

    config_hash = ""
    if config_path.exists():
        config_hash = hashlib.md5(config_path.read_bytes()).hexdigest()

    code_version = _get_code_version()
    entry: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "strategy_id": strategy_id,
        "config_hash": config_hash,
        "sharpe": float(sharpe) if sharpe is not None else math.nan,
        "trial_group": trial_group or strategy_id,
        "code_version": code_version,
        "featureset_hash": featureset_hash,
        "cohort_label": cohort_label or code_version,
        "mode": mode,
    }
    if n_obs is not None:
        entry["n_obs"] = n_obs
    if skewness is not None:
        entry["skewness"] = skewness
    if kurtosis_pearson is not None:
        entry["kurtosis_pearson"] = kurtosis_pearson
    if parent_sweep_id is not None:
        entry["parent_sweep_id"] = parent_sweep_id
    if calmar is not None:
        entry["calmar"] = float(calmar)
    if max_drawdown_usd is not None:
        entry["max_drawdown_usd"] = float(max_drawdown_usd)
    if win_rate is not None:
        entry["win_rate"] = float(win_rate)
    if total_trades is not None:
        entry["total_trades"] = int(total_trades)
    if instrument is not None:
        entry["instrument"] = instrument
    if timeframe is not None:
        entry["timeframe"] = timeframe
    if sharpe_ci_lo is not None and math.isfinite(sharpe_ci_lo):
        entry["sharpe_ci_lo"] = float(sharpe_ci_lo)
    if sharpe_ci_hi is not None and math.isfinite(sharpe_ci_hi):
        entry["sharpe_ci_hi"] = float(sharpe_ci_hi)
    if calmar_ci_lo is not None and math.isfinite(calmar_ci_lo):
        entry["calmar_ci_lo"] = float(calmar_ci_lo)
    if calmar_ci_hi is not None and math.isfinite(calmar_ci_hi):
        entry["calmar_ci_hi"] = float(calmar_ci_hi)

    raw.append(entry)
    _write_registry(tf, raw)


def count_trials(runs_root: Path, strategy_id: str) -> int:
    """Return the number of trials for a strategy_id or trial_group."""
    tf = _registry_path(runs_root)
    raw = _load_raw(tf)
    cnt = sum(
        1
        for t in raw
        if t.get("strategy_id") == strategy_id or t.get("trial_group") == strategy_id
    )
    return cnt if cnt > 0 else 1


def migrate_trials(path: Path, backup: bool = True) -> None:
    """Migrate existing registry entries to the versioned schema.

    Specifically:
    - Converts the legacy flat-list format to ``{"trials": [...]}``.
    - Tags every entry that lacks ``code_version`` with ``"pre-hardening"``.
    - Tags every entry that lacks ``cohort_label`` with ``"pre-hardening"``.
    - Sets ``featureset_hash`` to None for entries that lack it.

    Idempotent: running twice produces the same output.
    """
    if not path.exists():
        logger.warning("migrate_trials: registry not found, nothing to migrate", path=str(path))
        return

    original_text = path.read_text(encoding="utf-8")

    if backup:
        backup_path = path.with_suffix(".json.backup")
        backup_path.write_text(original_text, encoding="utf-8")
        logger.info("migrate_trials: backup written", backup=str(backup_path))

    raw = _load_raw(path)
    for trial in raw:
        trial.setdefault("code_version", "pre-hardening")
        trial.setdefault("cohort_label", "pre-hardening")
        trial.setdefault("featureset_hash", None)
        # Session-35 migration: tag all existing trials as validation by default.
        trial.setdefault("mode", "validation")
        trial.setdefault("parent_sweep_id", None)

    _write_registry(path, raw)
    logger.info("migrate_trials: complete", n_trials=len(raw), path=str(path))


def compute_dsr(
    trials: list[Trial],
    cohort: str | None = None,
) -> float | None:
    """Compute Deflated Sharpe Ratio for a single cohort.

    Cross-cohort DSR is disabled.  Callers must supply a ``cohort`` label.
    If ``cohort`` is None, returns None and logs a warning.

    If the cohort has fewer than MIN_TRIALS_FOR_DSR entries, returns None.

    Statistical moments (n_obs, skewness, kurtosis_pearson) that are missing
    from trial entries fall back to conservative defaults: n_obs=252,
    skewness=0, kurtosis_pearson=3 (normal distribution).  A warning is
    logged when defaults are used so callers know the result is approximate.
    """
    if cohort is None:
        logger.warning(
            "compute_dsr called without cohort label; use per-cohort DSR. Returning None."
        )
        return None

    filtered = [t for t in trials if t.cohort_label == cohort]
    if len(filtered) < MIN_TRIALS_FOR_DSR:
        logger.warning(
            "compute_dsr: insufficient trials in cohort",
            cohort=cohort,
            n=len(filtered),
            minimum=MIN_TRIALS_FOR_DSR,
        )
        return None

    # Select the best (highest) sharpe as the candidate.
    finite_trials = [t for t in filtered if not math.isnan(t.sharpe)]
    if not finite_trials:
        logger.warning("compute_dsr: all sharpe values are NaN in cohort", cohort=cohort)
        return None

    best = max(finite_trials, key=lambda t: t.sharpe)

    n_obs = best.n_obs if best.n_obs is not None else _DEFAULT_N_OBS
    skewness = best.skewness if best.skewness is not None else _DEFAULT_SKEWNESS
    kurtosis_pearson = (
        best.kurtosis_pearson
        if best.kurtosis_pearson is not None
        else _DEFAULT_KURTOSIS_PEARSON
    )

    if best.n_obs is None or best.skewness is None or best.kurtosis_pearson is None:
        logger.warning(
            "compute_dsr: using default statistical moments for cohort; "
            "populate n_obs/skewness/kurtosis_pearson in record_trial for accurate DSR",
            cohort=cohort,
        )

    return deflated_sharpe_ratio(
        sharpe=best.sharpe,
        n_obs=n_obs,
        n_trials=len(filtered),
        skewness=skewness,
        kurtosis_pearson=kurtosis_pearson,
    )
