"""Dash-based visual replay cockpit for backtest forensics.

Usage via CLI:
    uv run trading-research replay --symbol ZN [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Exports:
    run_app  — convenience wrapper; loads data and opens browser
"""

from trading_research.replay.app import build_app

__all__ = ["build_app"]
