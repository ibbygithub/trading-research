"""Smoke test: the package is importable and version is set."""

import trading_research


def test_package_importable():
    assert trading_research.__version__ == "0.1.0"
