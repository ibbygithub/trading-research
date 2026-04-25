"""Composite strategy ranking and multi-testing utilities for backtest reports.

Provides a single score that captures profit factor, drawdown, and trade count
in a way that:

1. Rewards high profit factor (log-compressed to avoid a single outlier dominating).
2. Penalises drawdown multiplicatively (a 50% drawdown halves the score).
3. Gives a small bonus for more trades (log10 scale — going from 100 to 1000
   trades roughly doubles the bonus, but the effect is modest).
4. Hard-floors strategies below a minimum trade count at -inf (excluded from
   rankings entirely).

Formula
-------
    score = log(PF) * (1 - DD) * (1 + log10(N / N_min))

where:
    PF     = profit_factor (clipped to ≥ 1e-6 to avoid log(0))
    DD     = max_dd_pct ∈ [0, 1)  (100% drawdown → -inf)
    N      = trade_count
    N_min  = min_trades threshold (default 100)

Rationale: a strategy with PF=1.5 (modest edge), DD=20% (tolerable), and
N=400 trades (solid sample) scores:
    log(1.5) * 0.80 * (1 + log10(4)) ≈ 0.405 * 0.80 * 1.602 ≈ 0.52

A strategy with PF=3.0 but only 60 trades (below N_min) scores -inf.

Design notes: docs/design/composite-ranking.md
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def composite_score(
    profit_factor: float,
    max_dd_pct: float,
    trade_count: int,
    min_trades: int = 100,
) -> float:
    """Compute composite ranking score for a single strategy.

    Parameters
    ----------
    profit_factor : float
        Gross profit / gross loss.  Values < 1 indicate a losing strategy.
    max_dd_pct : float
        Maximum drawdown as a fraction of peak equity in [0, 1).
        E.g. 0.20 = 20% drawdown.
    trade_count : int
        Total number of completed trades in the evaluation period.
    min_trades : int
        Minimum trade count for inclusion.  Strategies below this get -inf.

    Returns
    -------
    float
        Composite score.  Higher is better.  -inf means excluded.
    """
    if trade_count < min_trades:
        return float("-inf")

    if max_dd_pct >= 1.0:
        # Complete blowup.
        return float("-inf")

    # PF component: log-compressed, so PF=2 and PF=10 are not infinitely
    # different.  Clipped to avoid log(0) on degenerate strategies.
    pf_component = math.log(max(profit_factor, 1e-6))

    # DD penalty: multiplicative.  DD=0.20 → keep 80% of score.
    dd_penalty = 1.0 - min(max_dd_pct, 0.99)

    # Trade count bonus: modest log10 uplift above the minimum threshold.
    trade_bonus = 1.0 + math.log10(trade_count / min_trades)

    return pf_component * dd_penalty * trade_bonus


def top_x_strategies(
    trials: list[Any],
    x: int = 10,
    min_trades: int = 100,
) -> list[Any]:
    """Return the top X strategies ranked by composite score.

    Parameters
    ----------
    trials : list
        List of trial objects.  Each must expose:
            .profit_factor : float
            .max_dd_pct    : float  (drawdown as fraction, e.g. 0.20)
            .trade_count   : int
        Any trial without these attributes is skipped (logged to stderr).
    x : int
        Number of top strategies to return.
    min_trades : int
        Passed to composite_score; trials below this threshold score -inf.

    Returns
    -------
    list
        Top X trials sorted descending by composite score.  May be shorter
        than X if fewer than X trials meet the minimum trade threshold.
    """
    scored: list[tuple[float, Any]] = []
    for trial in trials:
        try:
            score = composite_score(
                profit_factor=float(trial.profit_factor),
                max_dd_pct=float(trial.max_dd_pct),
                trade_count=int(trial.trade_count),
                min_trades=min_trades,
            )
        except AttributeError as exc:
            # Skip trials missing required attributes.
            import sys
            print(  # noqa: T201 — structlog not available in this utility path
                f"top_x_strategies: skipping trial missing attribute: {exc}",
                file=sys.stderr,
            )
            continue
        if math.isfinite(score):
            scored.append((score, trial))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [trial for _, trial in scored[:x]]


# ---------------------------------------------------------------------------
# HTML rendering helpers (used by report.py)
# ---------------------------------------------------------------------------

_COMPOSITE_FORMULA_HTML = """
<div class="formula-box" style="background:#1e293b;border-left:4px solid #3b82f6;
     padding:1em 1.2em;margin:1em 0;border-radius:4px;font-family:monospace;">
  <strong style="color:#e2e8f0;">Composite score formula:</strong><br>
  <code style="color:#93c5fd;font-size:1.05em;">
    score = ln(PF) &times; (1 &minus; DD) &times; (1 + log<sub>10</sub>(N / N<sub>min</sub>))
  </code>
  <div style="margin-top:0.6em;color:#94a3b8;font-size:0.92em;">
    <strong>PF</strong> = profit factor &nbsp;|&nbsp;
    <strong>DD</strong> = max drawdown (fraction, e.g. 0.20 = 20%) &nbsp;|&nbsp;
    <strong>N</strong> = trade count &nbsp;|&nbsp;
    <strong>N<sub>min</sub></strong> = minimum trade threshold (default 100)<br>
    Strategies with N &lt; N<sub>min</sub> or DD &ge; 100% are excluded (score = &minus;&infin;).
  </div>
  <div style="margin-top:0.5em;color:#94a3b8;font-size:0.88em;">
    <em>Why this formula?</em> Log-compressing PF prevents one outlier from dominating.
    DD penalty is multiplicative — a 50% drawdown halves the score regardless of edge.
    The trade-count bonus is modest (log<sub>10</sub> scale) — tripling sample size from
    100 to 300 trades adds 0.48 to the multiplier, worth about one-third of the base score.
  </div>
</div>
"""


def render_composite_ranking_html(
    summaries: list[dict[str, Any]],
    x: int = 10,
    min_trades: int = 100,
) -> str:
    """Render a 'Top X by composite score' HTML table from a list of run summaries.

    Parameters
    ----------
    summaries : list[dict]
        List of dicts, each with at minimum:
            strategy_id, profit_factor, max_drawdown_pct, total_trades.
        These match the summary.json schema from generate_report().
    x : int
        How many strategies to show in the table.
    min_trades : int
        Minimum trade count for inclusion.

    Returns
    -------
    str
        Self-contained HTML fragment (no <html> or <body> tags).
    """
    from types import SimpleNamespace

    # Normalise drawdown: summary.json stores max_drawdown_pct as a negative
    # percentage (e.g. -20 means -20%).  Convert to a positive fraction in [0, 1).
    rows: list[SimpleNamespace] = []
    for s in summaries:
        pf = s.get("profit_factor") or 0.0
        dd_raw = s.get("max_drawdown_pct") or 0.0
        n = int(s.get("total_trades") or 0)
        label = s.get("strategy_id", "unknown")
        # dd_raw may be negative (loss) and possibly already a fraction or percent.
        # Treat magnitudes > 1 as percentage points; convert to fraction.
        dd_abs = abs(float(dd_raw))
        dd_frac = dd_abs / 100.0 if dd_abs > 1.0 else dd_abs

        obj = SimpleNamespace(
            profit_factor=float(pf),
            max_dd_pct=dd_frac,
            trade_count=n,
            strategy_id=label,
            _raw=s,
        )
        rows.append(obj)

    ranked = top_x_strategies(rows, x=x, min_trades=min_trades)

    if not ranked:
        return "<p style='color:#94a3b8;'>No strategies met the minimum trade threshold.</p>"

    header_style = "background:#334155;color:#e2e8f0;padding:0.5em 0.8em;text-align:right;"
    cell_style = "padding:0.45em 0.8em;text-align:right;color:#e2e8f0;"
    name_style = "padding:0.45em 0.8em;text-align:left;color:#93c5fd;"

    rows_html = []
    for rank, trial in enumerate(ranked, start=1):
        score = composite_score(trial.profit_factor, trial.max_dd_pct, trial.trade_count, min_trades)
        dd_pct = trial.max_dd_pct * 100.0
        rows_html.append(
            f"<tr>"
            f"<td style='{cell_style}'>{rank}</td>"
            f"<td style='{name_style}'>{trial.strategy_id}</td>"
            f"<td style='{cell_style}'>{trial.profit_factor:.3f}</td>"
            f"<td style='{cell_style}'>{dd_pct:.1f}%</td>"
            f"<td style='{cell_style}'>{trial.trade_count:,}</td>"
            f"<td style='{cell_style}'><strong>{score:.3f}</strong></td>"
            f"</tr>"
        )

    table = (
        f"<table style='width:100%;border-collapse:collapse;font-size:0.92em;'>"
        f"<thead><tr>"
        f"<th style='{header_style}'>Rank</th>"
        f"<th style='background:#334155;color:#e2e8f0;padding:0.5em 0.8em;text-align:left;'>Strategy</th>"
        f"<th style='{header_style}'>Profit Factor</th>"
        f"<th style='{header_style}'>Max DD</th>"
        f"<th style='{header_style}'>Trades</th>"
        f"<th style='{header_style}'>Score</th>"
        f"</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        f"</table>"
    )

    return (
        f"<section id='composite-ranking' style='margin:2em 0;'>"
        f"<h2 style='color:#e2e8f0;'>Top {x} Strategies — Composite Score</h2>"
        f"{_COMPOSITE_FORMULA_HTML}"
        f"{table}"
        f"</section>"
    )


def apply_bh_to_feature_table(
    feature_df: pd.DataFrame,
    p_col: str = "p_value",
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Add BH-adjusted p-values and significance flag to a feature importance table.

    Intended for any DataFrame that has a column of raw p-values from multiple
    feature significance tests (e.g. permutation importance p-values).

    Parameters
    ----------
    feature_df : pd.DataFrame
        DataFrame with at least one column of raw p-values.
    p_col : str
        Name of the raw p-value column.
    alpha : float
        FDR level for BH correction.

    Returns
    -------
    pd.DataFrame
        Copy of feature_df with two new columns:
            bh_adjusted_p  — BH-adjusted p-value.
            bh_significant — bool, True if the test is significant at the FDR level.
    """
    from trading_research.stats.multiple_testing import benjamini_hochberg

    df = feature_df.copy()
    if p_col not in df.columns:
        raise KeyError(f"Column '{p_col}' not found in feature_df")

    p_arr = df[p_col].to_numpy(dtype=float)
    result = benjamini_hochberg(p_arr, alpha=alpha)
    df["bh_adjusted_p"] = result.adjusted_p_values
    df["bh_significant"] = result.significant
    return df
