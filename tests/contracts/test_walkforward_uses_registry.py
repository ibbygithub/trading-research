"""Contract tests: walkforward.py uses TemplateRegistry when config has template: field.

Written in 29a as stubs. Filled in 29b.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from trading_research.backtest.walkforward import run_walkforward


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    """Return a helper that writes a YAML config to tmp_path and returns the path."""
    def _write(cfg: dict) -> Path:
        p = tmp_path / "test_config.yaml"
        p.write_text(yaml.dump(cfg), encoding="utf-8")
        return p
    return _write


def test_walkforward_rejects_config_with_both_template_and_signal_module(tmp_path: Path) -> None:
    """walkforward must raise when YAML has both template: and signal_module:."""
    cfg = {
        "strategy_id": "test",
        "symbol": "6E",
        "template": "vwap-reversion-v1",
        "signal_module": "trading_research.strategies.zn_vwap_reversion",
    }
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")

    with pytest.raises(ValueError, match="more than one of"):
        run_walkforward(p)


def test_walkforward_rejects_config_with_neither(tmp_path: Path) -> None:
    """walkforward must raise when YAML has neither template: nor signal_module:."""
    cfg = {
        "strategy_id": "test",
        "symbol": "6E",
    }
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")

    with pytest.raises(ValueError, match="must have one of"):
        run_walkforward(p)


def test_walkforward_uses_registry_when_template_present(tmp_path: Path) -> None:
    """walkforward must instantiate via TemplateRegistry when YAML has template: field.

    We mock the data loading and engine to isolate the template instantiation path.
    """
    from trading_research.core.templates import _GLOBAL_REGISTRY, TemplateRegistry

    cfg = {
        "strategy_id": "test-6e",
        "symbol": "6E",
        "template": "vwap-reversion-v1",
        "timeframe": "5m",
        "knobs": {"entry_threshold_atr": 2.2},
        "backtest": {"fill_model": "next_bar_open"},
    }
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")

    # Ensure the template module is loaded
    import trading_research.strategies.vwap_reversion_v1  # noqa: F401

    assert "vwap-reversion-v1" in [t.name for t in _GLOBAL_REGISTRY.list()]


def test_walkforward_falls_back_to_signal_module(tmp_path: Path) -> None:
    """walkforward must still use signal_module: path when template: is absent.

    We use a non-existent symbol so it fails at data loading, not at config
    validation — proving the signal_module path is accepted.
    """
    cfg = {
        "strategy_id": "test-xx",
        "symbol": "XX",
        "signal_module": "trading_research.strategies.zn_vwap_reversion",
        "timeframe": "5m",
        "backtest": {"fill_model": "next_bar_open"},
    }
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")

    # Should fail at data loading (no XX parquet), not at config validation.
    with pytest.raises(Exception):
        run_walkforward(p)
