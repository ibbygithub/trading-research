"""Trial leaderboard — filter, sort, and render trial registry entries.

Usage (programmatic):
    from trading_research.eval.leaderboard import build_leaderboard, generate_html

    rows = build_leaderboard(
        registry_path=Path("runs/.trials.json"),
        filters=["mode=exploration", "instrument=6A"],
        sort_key="calmar",
    )
    html = generate_html(rows, sort_key="calmar", filters=["mode=exploration"])

Column availability:
    New fields (mode, calmar, instrument, timeframe, ...) are populated for
    trials written by the ``sweep`` command (session 35+).  Older trials show
    None / NaN for those columns — displayed as "N/A" in the table.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import structlog

from trading_research.eval.trials import Trial, load_trials

logger = structlog.get_logger(__name__)

# Columns shown in the leaderboard table, in display order.
_COLUMNS: list[tuple[str, str]] = [
    ("timestamp", "Timestamp"),
    ("strategy_id", "Strategy"),
    ("instrument", "Instrument"),
    ("timeframe", "Timeframe"),
    ("calmar", "Calmar"),
    ("sharpe", "Sharpe"),
    ("max_drawdown_usd", "Max DD (USD)"),
    ("win_rate", "Win Rate"),
    ("total_trades", "Trades"),
    ("mode", "Mode"),
    ("parent_sweep_id", "Sweep ID"),
]

# Fields that are numeric and sortable.
_NUMERIC_FIELDS = {"calmar", "sharpe", "max_drawdown_usd", "win_rate", "total_trades"}

# Fields that support equality filtering.
_FILTERABLE_FIELDS = {
    "mode", "instrument", "timeframe", "strategy_id", "trial_group",
    "code_version", "parent_sweep_id",
}


def _trial_value(trial: Trial, field: str) -> Any:
    """Return the value of a trial field, or None if the field doesn't exist."""
    return getattr(trial, field, None)


def _parse_filter(spec: str) -> tuple[str, str]:
    """Parse 'key=value' into (key, value). Raises ValueError on bad format."""
    if "=" not in spec:
        raise ValueError(
            f"Invalid filter spec '{spec}': expected 'key=value' format. "
            "Example: --filter mode=exploration"
        )
    key, _, value = spec.partition("=")
    return key.strip(), value.strip()


def _matches_filter(trial: Trial, key: str, value: str) -> bool:
    """Return True if trial[key] == value (string comparison)."""
    actual = _trial_value(trial, key)
    if actual is None:
        return False
    return str(actual) == value


def build_leaderboard(
    registry_path: Path | None = None,
    filters: list[str] | None = None,
    sort_key: str = "calmar",
    ascending: bool = False,
) -> list[Trial]:
    """Load, filter, and sort trials from the registry.

    Args:
        registry_path: Path to .trials.json.  Defaults to runs/.trials.json.
        filters: List of 'key=value' strings.  All filters must match (AND logic).
        sort_key: Trial field to sort by.  Numeric NaN/None sorts last.
        ascending: Sort direction (default: descending — best first).

    Returns:
        Filtered, sorted list of Trial objects.
    """
    if registry_path is None:
        registry_path = Path(__file__).resolve().parents[3] / "runs" / ".trials.json"

    trials = load_trials(registry_path)

    # Apply filters.
    if filters:
        for spec in filters:
            try:
                key, value = _parse_filter(spec)
            except ValueError as exc:
                logger.warning("leaderboard: skipping bad filter", error=str(exc))
                continue
            trials = [t for t in trials if _matches_filter(t, key, value)]

    # Sort: numeric fields treat None/NaN as worst (sort to end).
    def _sort_key(t: Trial) -> tuple[int, float]:
        val = _trial_value(t, sort_key)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            # Push missing values to end regardless of direction.
            return (1, 0.0)
        try:
            numeric = float(val)
        except (TypeError, ValueError):
            return (1, 0.0)
        # Ascending: lower is better (flag 0, use value).
        # Descending: higher is better (flag 0, negate value so sort asc puts best first).
        return (0, numeric if ascending else -numeric)

    trials.sort(key=_sort_key)

    return trials


def format_table(trials: list[Trial], sort_key: str = "calmar") -> str:
    """Return a plain-text table of trials."""
    if not trials:
        return "  No trials found.\n"

    def _fmt(val: Any, field: str) -> str:
        if val is None:
            return "N/A"
        if isinstance(val, float):
            if math.isnan(val):
                return "N/A"
            if field == "win_rate":
                return f"{val:.1%}"
            if field == "max_drawdown_usd":
                return f"{val:,.0f}"
            return f"{val:.3f}"
        if isinstance(val, int):
            return str(val)
        s = str(val)
        # Truncate long strings in the table.
        return s[:24] if len(s) > 24 else s

    col_keys = [k for k, _ in _COLUMNS]
    col_headers = [h for _, h in _COLUMNS]

    # Compute column widths.
    widths = [len(h) for h in col_headers]
    rows_data: list[list[str]] = []
    for t in trials:
        row = [_fmt(_trial_value(t, k), k) for k in col_keys]
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
        rows_data.append(row)

    sep = "  ".join("-" * w for w in widths)
    header = "  ".join(h.ljust(widths[i]) for i, h in enumerate(col_headers))

    lines = [header, sep]
    for row in rows_data:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))

    return "\n".join(lines)


def generate_html(
    trials: list[Trial],
    sort_key: str = "calmar",
    filters: list[str] | None = None,
    title: str = "Trial Leaderboard",
) -> str:
    """Return a self-contained HTML leaderboard page."""
    filter_desc = ", ".join(filters) if filters else "none"
    n = len(trials)

    def _fmt_cell(val: Any, field: str) -> str:
        if val is None:
            return "<td class='na'>N/A</td>"
        if isinstance(val, float):
            if math.isnan(val):
                return "<td class='na'>N/A</td>"
            if field == "win_rate":
                return f"<td>{val:.1%}</td>"
            if field == "max_drawdown_usd":
                return f"<td>{val:,.0f}</td>"
            # Colour Calmar and Sharpe.
            colour = ""
            if field in ("calmar", "sharpe"):
                colour = " class='pos'" if val > 0 else " class='neg'"
            return f"<td{colour}>{val:.3f}</td>"
        if isinstance(val, int):
            return f"<td>{val}</td>"
        s = str(val)
        return f"<td>{s}</td>"

    header_cells = "".join(f"<th>{h}</th>" for _, h in _COLUMNS)
    body_rows: list[str] = []
    for t in trials:
        cells = "".join(
            _fmt_cell(_trial_value(t, k), k) for k, _ in _COLUMNS
        )
        body_rows.append(f"    <tr>{cells}</tr>")
    body = "\n".join(body_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: monospace; font-size: 13px; margin: 20px; background: #1a1a1a; color: #ddd; }}
  h1 {{ color: #eee; font-size: 18px; }}
  p.meta {{ color: #888; font-size: 12px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #333; color: #aaa; text-align: left; padding: 6px 10px;
        border-bottom: 2px solid #555; white-space: nowrap; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid #2a2a2a; white-space: nowrap; }}
  tr:hover {{ background: #222; }}
  .na {{ color: #555; }}
  .pos {{ color: #5c5; }}
  .neg {{ color: #c55; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Rows: {n} &nbsp;|&nbsp; Sort: {sort_key} &nbsp;|&nbsp; Filters: {filter_desc}</p>
<table>
  <thead><tr>{header_cells}</tr></thead>
  <tbody>
{body}
  </tbody>
</table>
</body>
</html>
"""
