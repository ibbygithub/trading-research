"""Tests for composite strategy ranking (eval.ranking).

Validates composite_score() and top_x_strategies() against
the formula documented in docs/design/composite-ranking.md.

Formula:
    score = log(PF) * (1 - DD) * (1 + log10(N / N_min))

where PF = profit_factor, DD = max_dd_pct, N = trade_count, N_min = min_trades.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from trading_research.eval.ranking import composite_score, top_x_strategies

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trial(pf: float, dd: float, n: int) -> SimpleNamespace:
    """Minimal trial stand-in with required attributes."""
    return SimpleNamespace(profit_factor=pf, max_dd_pct=dd, trade_count=n)


# ---------------------------------------------------------------------------
# composite_score unit tests
# ---------------------------------------------------------------------------


def test_high_pf_low_dd_high_trades_ranks_high() -> None:
    """Good strategy: high PF, low DD, many trades → large positive score."""
    score = composite_score(profit_factor=2.5, max_dd_pct=0.10, trade_count=500)
    assert score > 1.0, f"Expected score > 1.0 for strong strategy; got {score:.4f}"


def test_low_trades_excluded() -> None:
    """Trade count below min_trades → score is -inf (excluded from rankings)."""
    score = composite_score(
        profit_factor=3.0, max_dd_pct=0.05, trade_count=50, min_trades=100
    )
    assert score == float("-inf"), (
        f"Expected -inf for trade_count < min_trades; got {score}"
    )


def test_exactly_min_trades_not_excluded() -> None:
    """Exactly at the minimum trade count is included (not excluded)."""
    score = composite_score(
        profit_factor=1.5, max_dd_pct=0.20, trade_count=100, min_trades=100
    )
    assert math.isfinite(score), (
        f"trade_count == min_trades should be included; got {score}"
    )


def test_full_blowup_excluded() -> None:
    """max_dd_pct >= 1.0 (100% drawdown) → -inf."""
    score = composite_score(profit_factor=2.0, max_dd_pct=1.0, trade_count=200)
    assert score == float("-inf")

    score2 = composite_score(profit_factor=2.0, max_dd_pct=1.5, trade_count=200)
    assert score2 == float("-inf")


def test_score_decreases_with_higher_drawdown() -> None:
    """Higher drawdown → lower score, all else equal."""
    s_low_dd = composite_score(profit_factor=2.0, max_dd_pct=0.10, trade_count=300)
    s_high_dd = composite_score(profit_factor=2.0, max_dd_pct=0.40, trade_count=300)
    assert s_low_dd > s_high_dd, (
        f"Higher DD should lower score: {s_low_dd:.4f} vs {s_high_dd:.4f}"
    )


def test_score_increases_with_higher_pf() -> None:
    """Higher profit factor → higher score, all else equal."""
    s_low_pf = composite_score(profit_factor=1.2, max_dd_pct=0.15, trade_count=200)
    s_high_pf = composite_score(profit_factor=2.5, max_dd_pct=0.15, trade_count=200)
    assert s_high_pf > s_low_pf, (
        f"Higher PF should increase score: {s_high_pf:.4f} vs {s_low_pf:.4f}"
    )


def test_score_increases_with_more_trades() -> None:
    """More trades (above min_trades) → higher score, all else equal."""
    s_few = composite_score(profit_factor=1.8, max_dd_pct=0.20, trade_count=100)
    s_many = composite_score(profit_factor=1.8, max_dd_pct=0.20, trade_count=1000)
    assert s_many > s_few, (
        f"More trades should increase score: {s_many:.4f} vs {s_few:.4f}"
    )


def test_losing_strategy_negative_score() -> None:
    """PF < 1 (losing strategy) → negative score (log(PF) < 0)."""
    score = composite_score(profit_factor=0.8, max_dd_pct=0.20, trade_count=200)
    assert score < 0.0, f"PF < 1 should give negative score; got {score:.4f}"


def test_formula_calculation() -> None:
    """Spot-check a known calculation against the formula directly."""
    pf, dd, n, n_min = 1.5, 0.20, 400, 100
    expected = math.log(1.5) * (1 - 0.20) * (1 + math.log10(400 / 100))
    actual = composite_score(profit_factor=pf, max_dd_pct=dd, trade_count=n, min_trades=n_min)
    assert abs(actual - expected) < 1e-10, (
        f"Formula mismatch: expected {expected:.6f}, got {actual:.6f}"
    )


# ---------------------------------------------------------------------------
# top_x_strategies tests
# ---------------------------------------------------------------------------


def test_top_x_returns_sorted() -> None:
    """top_x_strategies output is sorted descending by composite score."""
    trials = [
        _trial(pf=1.2, dd=0.30, n=200),   # mediocre
        _trial(pf=3.0, dd=0.10, n=500),   # best
        _trial(pf=1.8, dd=0.20, n=300),   # mid
        _trial(pf=2.5, dd=0.15, n=400),   # second best
    ]
    result = top_x_strategies(trials, x=4, min_trades=100)
    assert len(result) == 4

    # Verify descending score order.
    scores = [
        composite_score(t.profit_factor, t.max_dd_pct, t.trade_count)
        for t in result
    ]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], (
            f"Not sorted: scores[{i}]={scores[i]:.4f} < scores[{i+1}]={scores[i+1]:.4f}"
        )


def test_top_x_excludes_low_trade_count() -> None:
    """Trials below min_trades are excluded from top_x results."""
    trials = [
        _trial(pf=5.0, dd=0.05, n=10),    # best PF but too few trades
        _trial(pf=1.5, dd=0.20, n=200),   # modest but enough trades
        _trial(pf=2.0, dd=0.15, n=300),
    ]
    result = top_x_strategies(trials, x=10, min_trades=100)
    # Only 2 of 3 trials have enough trades.
    assert len(result) == 2
    # The strategy with n=10 must not appear.
    trade_counts = [t.trade_count for t in result]
    assert 10 not in trade_counts, "Under-threshold trial should be excluded"


def test_top_x_respects_x_limit() -> None:
    """Returns at most x strategies even when more are available."""
    trials = [_trial(pf=1.5, dd=0.20, n=200 + i * 10) for i in range(20)]
    result = top_x_strategies(trials, x=5, min_trades=100)
    assert len(result) == 5


def test_top_x_fewer_than_x_available() -> None:
    """Returns fewer than x when fewer qualifying strategies exist."""
    trials = [
        _trial(pf=2.0, dd=0.15, n=200),
        _trial(pf=1.5, dd=0.25, n=50),   # excluded
    ]
    result = top_x_strategies(trials, x=10, min_trades=100)
    assert len(result) == 1


def test_top_x_empty_input() -> None:
    """Empty trial list returns empty list."""
    result = top_x_strategies([], x=10)
    assert result == []


def test_top_x_best_is_first() -> None:
    """The first element is the best-scoring strategy."""
    trials = [
        _trial(pf=1.2, dd=0.40, n=150),
        _trial(pf=2.8, dd=0.08, n=600),
        _trial(pf=1.9, dd=0.20, n=250),
    ]
    result = top_x_strategies(trials, x=3)
    # Best: pf=2.8, dd=0.08, n=600
    assert result[0].profit_factor == pytest.approx(2.8)
