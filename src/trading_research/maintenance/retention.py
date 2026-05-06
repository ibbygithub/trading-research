"""Retention policy model for storage cleanup.

Loads ``configs/retention.yaml`` when present; falls back to the documented
defaults from Chapter 56.5 §56.5.4 when the file is absent or when individual
keys are missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _parse_duration(value: str) -> int:
    """Parse a duration string like ``90d``, ``6m``, ``730d`` into days."""
    m = re.fullmatch(r"(\d+)\s*([dDmMyY])", value.strip())
    if not m:
        raise ValueError(f"Invalid duration string: {value!r}. Use e.g. '90d', '6m', '2y'.")
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit == "d":
        return n
    if unit == "m":
        return n * 30
    if unit == "y":
        return n * 365
    raise ValueError(f"Unknown duration unit: {unit!r}")


@dataclass
class RunsPolicy:
    keep_last_per_strategy: int = 10
    archive_older_than_days: int = 90
    archive_dir: str = "outputs/archive/runs/"


@dataclass
class CanonicalPolicy:
    keep_latest_per_tuple: bool = True
    archive_dir: str = "outputs/archive/clean/"


@dataclass
class FeaturesPolicy:
    keep_latest_per_tuple: bool = True
    retire_tags: list[str] = field(default_factory=list)


@dataclass
class TrialsPolicy:
    keep_modes: list[str] = field(default_factory=lambda: ["validation"])
    compact_after_days: int = 180
    delete_after_days: int = 730
    archive_path: str = "outputs/archive/trials/"


@dataclass
class RetentionPolicy:
    runs: RunsPolicy = field(default_factory=RunsPolicy)
    canonical: CanonicalPolicy = field(default_factory=CanonicalPolicy)
    features: FeaturesPolicy = field(default_factory=FeaturesPolicy)
    trials: TrialsPolicy = field(default_factory=TrialsPolicy)


def _build_runs(raw: dict[str, Any]) -> RunsPolicy:
    p = RunsPolicy()
    if "keep_last_per_strategy" in raw:
        p.keep_last_per_strategy = int(raw["keep_last_per_strategy"])
    if "archive_older_than" in raw:
        p.archive_older_than_days = _parse_duration(raw["archive_older_than"])
    if "archive_dir" in raw:
        p.archive_dir = str(raw["archive_dir"])
    return p


def _build_canonical(raw: dict[str, Any]) -> CanonicalPolicy:
    p = CanonicalPolicy()
    if "keep_latest_per_tuple" in raw:
        p.keep_latest_per_tuple = bool(raw["keep_latest_per_tuple"])
    if "archive_dir" in raw:
        p.archive_dir = str(raw["archive_dir"])
    return p


def _build_features(raw: dict[str, Any]) -> FeaturesPolicy:
    p = FeaturesPolicy()
    if "keep_latest_per_tuple" in raw:
        p.keep_latest_per_tuple = bool(raw["keep_latest_per_tuple"])
    if "retire_tags" in raw:
        p.retire_tags = list(raw["retire_tags"]) if raw["retire_tags"] else []
    return p


def _build_trials(raw: dict[str, Any]) -> TrialsPolicy:
    p = TrialsPolicy()
    if "keep_modes" in raw:
        p.keep_modes = list(raw["keep_modes"])
    if "compact_after" in raw:
        p.compact_after_days = _parse_duration(raw["compact_after"])
    if "delete_after" in raw:
        p.delete_after_days = _parse_duration(raw["delete_after"])
    if "archive_path" in raw:
        p.archive_path = str(raw["archive_path"])
    return p


def load_retention_policy(
    project_root: Path | None = None,
) -> RetentionPolicy:
    """Load the retention policy from ``configs/retention.yaml``.

    Falls back to documented defaults when the file is absent or when
    individual keys are missing.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parents[3]

    config_path = project_root / "configs" / "retention.yaml"
    if not config_path.exists():
        return RetentionPolicy()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    return RetentionPolicy(
        runs=_build_runs(raw.get("runs", {})),
        canonical=_build_canonical(raw.get("clean", {})),
        features=_build_features(raw.get("features", {})),
        trials=_build_trials(raw.get("trials", {})),
    )
