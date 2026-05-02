"""Contract tests: strategy template and instance naming conventions.

Written in 29a as stubs. Filled in immediately (naming is pure validation).
"""

from __future__ import annotations

import hashlib
import re

import pytest
import yaml


def _config_hash_short(knobs: dict) -> str:
    """Compute the 6-char blake2b hash of canonical YAML-dumped knobs."""
    canonical = yaml.dump(knobs, sort_keys=True, default_flow_style=False)
    return hashlib.blake2b(canonical.encode()).hexdigest()[:6]


_TEMPLATE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-v\d+$")
_INSTANCE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-v\d+-[A-Z0-9]+-[0-9a-f]{6}$")


class TestTemplateNaming:
    """Template names must follow <strategy-class>-v<N> in kebab-case."""

    @pytest.mark.parametrize("name", [
        "vwap-reversion-v1",
        "macd-pullback-v1",
        "zn-vwap-reversion-v0",
        "pairs-spread-v2",
    ])
    def test_valid_template_names(self, name: str) -> None:
        assert _TEMPLATE_PATTERN.match(name), f"{name!r} should match template pattern"

    @pytest.mark.parametrize("name", [
        "VWAP-Reversion-v1",
        "vwap_reversion_v1",
        "vwap-reversion",
        "v1-vwap-reversion",
        "vwap-reversion-v",
    ])
    def test_invalid_template_names(self, name: str) -> None:
        assert not _TEMPLATE_PATTERN.match(name), f"{name!r} should NOT match template pattern"


class TestInstanceNaming:
    """Instance names must follow <template>-<INSTRUMENT>-<hash6>."""

    def test_valid_instance_name(self) -> None:
        knobs = {"entry_threshold_atr": 2.2, "stop_loss_atr": 2.5}
        h = _config_hash_short(knobs)
        instance_name = f"vwap-reversion-v1-6E-{h}"
        assert _INSTANCE_PATTERN.match(instance_name)

    def test_hash_is_deterministic(self) -> None:
        knobs = {"a": 1.0, "b": "hello"}
        h1 = _config_hash_short(knobs)
        h2 = _config_hash_short(knobs)
        assert h1 == h2
        assert len(h1) == 6

    def test_different_knobs_different_hash(self) -> None:
        h1 = _config_hash_short({"threshold": 2.0})
        h2 = _config_hash_short({"threshold": 2.5})
        assert h1 != h2
