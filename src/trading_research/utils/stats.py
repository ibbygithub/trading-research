"""Shared statistical primitives used across eval, backtest, and replay.

Single source of truth for per-trade and per-period metric calculations.
All functions accept plain numpy arrays and return floats. Callers decide
the granularity (daily P&L, per-trade P&L, etc.).

PSR/DSR and higher-level portfolio metrics live in eval/stats.py;
this module contains only the low-level building blocks.
"""

from __future__ import annotations

import math

import numpy as np

_TRADING_DAYS = 252


def annualised_sharpe(pnl: np.ndarray, trading_days: int = _TRADING_DAYS) -> float:
    """Annualised Sharpe from a 1-D P&L array.

    Each element is one period. Pass daily P&L for calendar-day Sharpe;
    pass per-trade P&L to treat each trade as one period.
    """
    arr = np.asarray(pnl, dtype=float)
    if len(arr) < 2:
        return float("nan")
    mu = np.mean(arr)
    sigma = np.std(arr, ddof=1)
    if sigma == 0.0:
        return float("nan")
    return float(mu / sigma * math.sqrt(trading_days))


def annualised_sortino(pnl: np.ndarray, trading_days: int = _TRADING_DAYS) -> float:
    """Annualised Sortino (downside deviation only) from a 1-D P&L array."""
    arr = np.asarray(pnl, dtype=float)
    if len(arr) < 2:
        return float("nan")
    mu = np.mean(arr)
    downside = arr[arr < 0]
    if len(downside) < 2:
        return float("nan")
    sigma_d = np.std(downside, ddof=1)
    if sigma_d == 0.0:
        return float("nan")
    return float(mu / sigma_d * math.sqrt(trading_days))


def calmar(pnl: np.ndarray, span_days: int, trading_days: int = _TRADING_DAYS) -> float:
    """Calmar ratio: annualised_return / |max_drawdown| from a 1-D P&L array.

    span_days: calendar days spanned by the observations (used to annualise).
    Uses cumulative P&L as the equity curve; starting capital is zero-based
    (same convention as summary.py and bootstrap.py).
    """
    arr = np.asarray(pnl, dtype=float)
    if len(arr) == 0 or span_days <= 0:
        return float("nan")
    equity = np.cumsum(arr)
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max
    max_dd = float(np.min(drawdown))
    if max_dd == 0.0:
        return float("nan")
    annual_return = float(np.sum(arr)) / span_days * trading_days
    return annual_return / abs(max_dd)


def win_rate(pnl: np.ndarray) -> float:
    """Fraction of positive P&L observations."""
    arr = np.asarray(pnl, dtype=float)
    if len(arr) == 0:
        return float("nan")
    return float(np.sum(arr > 0) / len(arr))


def profit_factor(pnl: np.ndarray) -> float:
    """Gross wins / |gross losses|. Returns inf when there are no losses."""
    arr = np.asarray(pnl, dtype=float)
    gross_wins = float(np.sum(arr[arr > 0])) if np.any(arr > 0) else 0.0
    gross_losses = abs(float(np.sum(arr[arr <= 0]))) if np.any(arr <= 0) else 0.0
    return gross_wins / gross_losses if gross_losses > 0.0 else float("inf")
