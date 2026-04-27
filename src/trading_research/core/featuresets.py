"""Versioned, hash-addressable feature set registry.

A FeatureSet is an immutable specification of which indicators, VWAP flavors,
and HTF projections are computed when building a FEATURES parquet.  Its
``compute_hash()`` method produces a stable 16-char hex digest that changes
whenever the spec changes *or* when the code version changes — ensuring that
feature parquets built from different code are never silently treated as
equivalent.

Backing store: ``configs/featuresets/<name>-<version>.yaml``
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_FEATURESETS_DIR = (
    Path(__file__).resolve().parents[3] / "configs" / "featuresets"
)


@dataclass
class FeatureSpec:
    """Single indicator or projection entry within a FeatureSet."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)


class FeatureSet(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    version: str
    features: list[FeatureSpec]
    code_version: str

    def compute_hash(self) -> str:
        """Stable 16-char hex digest of (name, version, sorted features, code_version).

        Invariant: reordering the features list does not change the hash because
        the list is sorted by feature name before serialization.  Changing any
        param, adding/removing a feature, or changing code_version does change it.
        """
        sorted_features = sorted(self.features, key=lambda f: f.name)
        payload = {
            "name": self.name,
            "version": self.version,
            "features": [
                {"name": f.name, "params": f.params} for f in sorted_features
            ],
            "code_version": self.code_version,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        # digest_size=8 → 16 hex chars; blake2b is fast and collision-resistant.
        return hashlib.blake2b(canonical.encode(), digest_size=8).hexdigest()


class FeatureSetRegistry:
    """Lazy-loading registry backed by ``configs/featuresets/``."""

    def __init__(self, featuresets_dir: Path | None = None) -> None:
        self._dir = featuresets_dir or DEFAULT_FEATURESETS_DIR
        self._cache: dict[tuple[str, str], FeatureSet] | None = None

    def _load(self) -> dict[tuple[str, str], FeatureSet]:
        if self._cache is None:
            if not self._dir.is_dir():
                raise FileNotFoundError(
                    f"featuresets directory not found at {self._dir}"
                )
            code_version = _get_code_version()
            self._cache = {}
            for yaml_path in sorted(self._dir.glob("*.yaml")):
                raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                tag: str = raw["tag"]
                name, version = _split_tag(tag)
                features = _parse_feature_specs(raw)
                fs = FeatureSet(
                    name=name,
                    version=version,
                    features=features,
                    code_version=code_version,
                )
                self._cache[(name, version)] = fs
        return self._cache

    def get(self, name: str, version: str) -> FeatureSet:
        """Return the FeatureSet for (name, version), e.g. ('base', 'v1')."""
        registry = self._load()
        key = (name, version)
        try:
            return registry[key]
        except KeyError as exc:
            known = ", ".join(f"{n}-{v}" for n, v in sorted(registry)) or "(none)"
            raise KeyError(
                f"Unknown feature set {name!r} {version!r}. Known: {known}"
            ) from exc

    def list(self) -> list[FeatureSet]:
        """Return all registered feature sets."""
        return list(self._load().values())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _split_tag(tag: str) -> tuple[str, str]:
    """Split 'base-v1' → ('base', 'v1'), 'vwap-reversion-v2' → ('vwap-reversion', 'v2')."""
    # Find the last '-v<digits>' suffix.
    import re

    m = re.search(r"-v(\d+)$", tag)
    if m:
        version = f"v{m.group(1)}"
        name = tag[: m.start()]
        return name, version
    # Fallback: treat everything as the name, version unknown.
    return tag, "unknown"


def _get_code_version() -> str:
    """Return the current git short SHA, or 'unknown' if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _parse_feature_specs(raw: dict[str, Any]) -> list[FeatureSpec]:
    """Flatten indicators / vwap / htf_projections into a FeatureSpec list."""
    specs: list[FeatureSpec] = []

    for entry in raw.get("indicators", []):
        entry = dict(entry)
        name = entry.pop("name")
        specs.append(FeatureSpec(name=name, params=entry))

    for entry in raw.get("vwap", []):
        entry = dict(entry)
        name = entry.pop("name")
        specs.append(FeatureSpec(name=name, params=entry))

    for proj in raw.get("htf_projections", []):
        source_tf: str = proj["source_tf"]
        for col in proj.get("columns", []):
            col = dict(col)
            name = col.pop("name")
            col["source_tf"] = source_tf
            specs.append(FeatureSpec(name=name, params=col))

    return specs
