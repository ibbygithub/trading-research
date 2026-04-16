"""Trials registry for honest deflated Sharpe computation.

Every backtest run records itself into ``runs/.trials.json`` with:
- timestamp
- strategy name
- config hash (SHA-256 of the YAML content)
- top-line Sharpe

When computing deflated Sharpe, the number of trials ``n_trials`` is
read from this registry, counted by trial group (strategy family).

This makes deflated Sharpe honest: if you've run 30 variants of a
strategy, the deflation reflects 30 actual tests rather than a
cosmetic n_trials=1.

Usage
-----
    from trading_research.eval.trials import record_trial, count_trials

    # After a backtest run:
    record_trial(
        runs_root=Path("runs"),
        strategy_id="zn-macd-pullback",
        config_path=Path("configs/strategies/zn_macd_pullback.yaml"),
        sharpe=1.4,
        trial_group="zn-macd",
    )

    # Before computing deflated Sharpe:
    n = count_trials(runs_root=Path("runs"), trial_group="zn-macd")
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


_REGISTRY_FILE = ".trials.json"


def record_trial(
    runs_root: Path,
    strategy_id: str,
    config_path: Path | None,
    sharpe: float,
    trial_group: str | None = None,
) -> None:
    """Record a backtest run in the trials registry.

    Parameters
    ----------
    runs_root:    Root of the runs/ directory.
    strategy_id:  Strategy identifier string.
    config_path:  Path to the strategy YAML config (for hashing).
    sharpe:       Observed Sharpe ratio for this run.
    trial_group:  Optional grouping tag (defaults to strategy_id).
    """
    runs_root = Path(runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    registry_path = runs_root / _REGISTRY_FILE

    config_hash = "unknown"
    if config_path and Path(config_path).is_file():
        content = Path(config_path).read_bytes()
        config_hash = hashlib.sha256(content).hexdigest()[:16]

    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "trial_group": trial_group or strategy_id,
        "config_hash": config_hash,
        "sharpe": sharpe if sharpe == sharpe else None,  # None for NaN
    }

    records = _load_registry(registry_path)
    records.append(entry)
    registry_path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def count_trials(
    runs_root: Path,
    trial_group: str | None = None,
    strategy_id: str | None = None,
) -> int:
    """Count how many trials have been recorded for a trial group.

    Parameters
    ----------
    runs_root:    Root of the runs/ directory.
    trial_group:  Count trials with this group tag.
    strategy_id:  Fallback: count trials with this strategy_id.
                  (Used when trial_group was not set at record time.)

    Returns
    -------
    Number of distinct trials recorded.  Returns 1 as a safe minimum
    (treat as single-trial test if registry is empty or missing).
    """
    registry_path = Path(runs_root) / _REGISTRY_FILE
    records = _load_registry(registry_path)

    if not records:
        return 1

    if trial_group:
        matches = [r for r in records if r.get("trial_group") == trial_group]
    elif strategy_id:
        matches = [r for r in records if r.get("strategy_id") == strategy_id]
    else:
        matches = records

    return max(1, len(matches))


def list_trials(runs_root: Path) -> list[dict]:
    """Return all trial records from the registry."""
    registry_path = Path(runs_root) / _REGISTRY_FILE
    return _load_registry(registry_path)


def _load_registry(path: Path) -> list[dict]:
    """Load the registry file, returning an empty list if missing or corrupt."""
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
