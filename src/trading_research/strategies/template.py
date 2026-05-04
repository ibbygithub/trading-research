"""YAML-defined strategy — entry/exit conditions without Python code.

A strategy is described entirely in YAML with an ``entry`` block:

    knobs:
      entry_atr_mult: 1.5
      adx_max: 22.0

    entry:
      long:
        all:
          - "close < vwap_session - entry_atr_mult * atr_14"
          - "adx_14 < adx_max"
      short:
        all:
          - "close > vwap_session + entry_atr_mult * atr_14"
          - "adx_14 < adx_max"
      time_window:
        start_utc: "12:00"
        end_utc: "17:00"

    exits:
      stop:
        long: "close - stop_atr_mult * atr_14"
        short: "close + stop_atr_mult * atr_14"
      target:
        long: "vwap_session"
        short: "vwap_session"

``YAMLStrategy.generate_signals_df(df)`` evaluates these conditions and
returns a DataFrame with columns ``signal``, ``stop``, ``target`` — the same
shape that Python-module strategies produce, so ``BacktestEngine.run()`` works
without modification.

Expression syntax
-----------------
Expressions are arithmetic/comparison formulas that may reference:

- Column names (e.g. ``close``, ``vwap_session``, ``atr_14``)
- Knob names (resolved from the ``knobs`` block)
- Numeric literals
- Arithmetic: ``+  -  *  /``
- Comparisons: ``<  >  <=  >=  ==  !=``
- Unary minus: ``-atr_14``
- Parentheses
- ``shift(col, n)`` — ``df[col].shift(n)`` (1-bar lookback etc.)

Only the above constructs are allowed. Arbitrary Python, imports, attribute
access, subscripts, and lambda are all rejected by the evaluator.
"""

from __future__ import annotations

import ast
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from trading_research.core.instruments import Instrument
    from trading_research.core.strategies import ExitDecision, PortfolioContext, Position, Signal

# ---------------------------------------------------------------------------
# Expression evaluator
# ---------------------------------------------------------------------------

_BINOP_OPS: dict[type, Any] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}

_CMP_OPS: dict[type, Any] = {
    ast.Lt: lambda a, b: a < b,
    ast.Gt: lambda a, b: a > b,
    ast.LtE: lambda a, b: a <= b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}


class ExprEvaluator:
    """Safe arithmetic/comparison expression evaluator over pandas Series.

    Resolves bare names from two sources (in order):
    1. ``df.columns`` — returns the full column as a ``pd.Series``
    2. ``knobs`` dict — returns the value as a Python scalar

    Raises ``ValueError`` for any unsupported syntax or unknown name.
    """

    def __init__(self, df: pd.DataFrame, knobs: dict[str, Any]) -> None:
        self._df = df
        self._knobs = knobs

    def eval(self, expr_str: str) -> pd.Series | float:
        """Parse *expr_str* and return a Series or scalar result."""
        try:
            tree = ast.parse(expr_str.strip(), mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid expression syntax {expr_str!r}: {exc}") from exc
        return self._node(tree.body)

    def _node(self, node: ast.expr) -> pd.Series | float:  # noqa: PLR0911
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError(
                    f"Only numeric constants allowed; got {type(node.value).__name__}: {node.value!r}"
                )
            return float(node.value)

        if isinstance(node, ast.Name):
            name = node.id
            if name in self._df.columns:
                return self._df[name].astype(float)
            if name in self._knobs:
                val = self._knobs[name]
                try:
                    return float(val)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Knob {name!r} value {val!r} cannot be used as a number"
                    ) from exc
            known_cols = list(self._df.columns)[:8]
            known_knobs = list(self._knobs)
            raise ValueError(
                f"Name {name!r} is not a column (first 8: {known_cols}) "
                f"or a knob ({known_knobs})"
            )

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -self._node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return self._node(node.operand)
            if isinstance(node.op, ast.Not):
                operand = self._node(node.operand)
                if isinstance(operand, pd.Series):
                    return ~operand.astype(bool)
                return not operand
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _BINOP_OPS:
                raise ValueError(
                    f"Unsupported binary operator {type(node.op).__name__}. "
                    "Allowed: + - * /"
                )
            left = self._node(node.left)
            right = self._node(node.right)
            return _BINOP_OPS[op_type](left, right)

        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ValueError(
                    "Chained comparisons (e.g. a < b < c) are not supported. "
                    "Split into separate conditions."
                )
            op_type = type(node.ops[0])
            if op_type not in _CMP_OPS:
                raise ValueError(
                    f"Unsupported comparison {type(node.ops[0]).__name__}. "
                    "Allowed: < > <= >= == !="
                )
            left = self._node(node.left)
            right = self._node(node.comparators[0])
            result = _CMP_OPS[op_type](left, right)
            if isinstance(result, pd.Series):
                return result.fillna(False)
            return result

        if isinstance(node, ast.BoolOp):
            values = [self._node(v) for v in node.values]
            if isinstance(node.op, ast.And):
                out = values[0]
                for v in values[1:]:
                    out = out & v
                return out
            if isinstance(node.op, ast.Or):
                out = values[0]
                for v in values[1:]:
                    out = out | v
                return out
            raise ValueError(f"Unsupported bool operator: {type(node.op).__name__}")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    "Only simple function calls supported (not method calls or lambdas)."
                )
            fname = node.func.id
            if fname == "shift":
                return self._call_shift(node)
            raise ValueError(
                f"Unknown function {fname!r}. Supported functions: shift(column, n)"
            )

        raise ValueError(
            f"Unsupported expression node {type(node).__name__}. "
            "Only arithmetic, comparisons, and shift() are allowed."
        )

    def _call_shift(self, node: ast.Call) -> pd.Series:
        """Evaluate ``shift(column, n)`` → ``df[column].shift(n)``."""
        if len(node.args) != 2:
            raise ValueError(
                "shift() requires exactly 2 arguments: shift(column_name, n)"
            )
        col_node = node.args[0]
        if not isinstance(col_node, ast.Name):
            raise ValueError(
                "First argument to shift() must be a bare column name, "
                f"got {type(col_node).__name__}"
            )
        col_name = col_node.id
        if col_name not in self._df.columns:
            raise ValueError(
                f"shift(): column {col_name!r} not found in DataFrame. "
                f"Available: {list(self._df.columns)[:8]}"
            )
        n_val = self._node(node.args[1])
        if isinstance(n_val, pd.Series):
            raise ValueError("shift() n argument must be a constant, not a column")
        return self._df[col_name].shift(int(n_val)).astype(float)


# ---------------------------------------------------------------------------
# YAMLStrategy
# ---------------------------------------------------------------------------


class YAMLStrategy:
    """Strategy defined entirely by YAML — no Python signal module required.

    The YAML config must contain an ``entry`` block. This distinguishes it
    from ``signal_module`` configs (Python module import) and ``template``
    configs (registered StrategyTemplate class).

    Dispatch detection (mutually exclusive):
        - ``entry:`` present  → this class
        - ``template:`` present → TemplateRegistry
        - ``signal_module:`` present → importlib module
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._knobs: dict[str, Any] = config.get("knobs", {})
        self._entry: dict = config["entry"]
        self._exits: dict = config.get("exits", {})
        self._id: str = config.get("strategy_id", "yaml-strategy")

    @classmethod
    def from_config(cls, config: dict) -> YAMLStrategy:
        """Construct from a parsed YAML dict.

        Raises ``ValueError`` if the ``entry`` block is missing.
        """
        if "entry" not in config:
            raise ValueError(
                "YAML strategy config must have an 'entry' block. "
                "For Python-module strategies use 'signal_module'; "
                "for registered templates use 'template'."
            )
        return cls(config)

    # ------------------------------------------------------------------
    # Strategy Protocol properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._id

    @property
    def template_name(self) -> str:
        return "yaml-template"

    @property
    def knobs(self) -> dict:
        return dict(self._knobs)

    # ------------------------------------------------------------------
    # Core signal generation
    # ------------------------------------------------------------------

    def generate_signals_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Evaluate entry/exit conditions and return the signal DataFrame.

        Returns a DataFrame with columns ``signal`` (int8), ``stop`` (float),
        and ``target`` (float), indexed identically to ``df``.

        This is the same shape produced by Python-module strategies, so it
        plugs directly into ``BacktestEngine.run(bars, signals_df)``.
        """
        if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
            raise ValueError("df.index must be a tz-aware DatetimeIndex.")

        ev = ExprEvaluator(df, self._knobs)
        n = len(df)

        # --- Entry masks per direction ---
        long_cfg = self._entry.get("long", {})
        short_cfg = self._entry.get("short", {})

        long_mask = self._eval_conditions(ev, long_cfg, n)
        short_mask = self._eval_conditions(ev, short_cfg, n)

        # Time window (optional) — applies to both directions
        tw = self._entry.get("time_window")
        if tw is not None:
            window_mask = _build_time_window_mask(df, tw)
            long_mask = long_mask & window_mask
            short_mask = short_mask & window_mask

        # Conflict resolution — if both directions fire on the same bar,
        # neither does (matches the Python-module convention).
        conflict = long_mask & short_mask
        long_mask = long_mask & ~conflict
        short_mask = short_mask & ~conflict

        # --- Exit level expressions ---
        stop_cfg = self._exits.get("stop", {})
        target_cfg = self._exits.get("target", {})

        long_stop = _eval_price_expr(ev, stop_cfg.get("long"), n)
        short_stop = _eval_price_expr(ev, stop_cfg.get("short"), n)
        long_target = _eval_price_expr(ev, target_cfg.get("long"), n)
        short_target = _eval_price_expr(ev, target_cfg.get("short"), n)

        # Suppress entries where stop is NaN (indicator warm-up period).
        valid_long = long_mask & np.isfinite(long_stop)
        valid_short = short_mask & np.isfinite(short_stop)

        # Assemble output arrays
        signal = np.zeros(n, dtype=np.int8)
        stop_arr = np.full(n, np.nan, dtype=float)
        target_arr = np.full(n, np.nan, dtype=float)

        signal[valid_long] = 1
        signal[valid_short] = -1
        stop_arr[valid_long] = long_stop[valid_long]
        stop_arr[valid_short] = short_stop[valid_short]
        target_arr[valid_long] = long_target[valid_long]
        target_arr[valid_short] = short_target[valid_short]

        return pd.DataFrame(
            {"signal": signal, "stop": stop_arr, "target": target_arr},
            index=df.index,
        )

    # ------------------------------------------------------------------
    # Strategy Protocol methods (engine compatibility)
    # ------------------------------------------------------------------

    def generate_signals(
        self,
        bars: pd.DataFrame,
        features: pd.DataFrame,
        instrument: Instrument,
    ) -> list[Signal]:
        """Protocol compliance — delegates to generate_signals_df."""
        from trading_research.core.strategies import Signal

        sdf = self.generate_signals_df(features)
        signals: list[Signal] = []
        for ts, row in sdf.iterrows():
            if int(row["signal"]) == 0:
                continue
            direction = "long" if int(row["signal"]) == 1 else "short"
            signals.append(Signal(
                timestamp=ts.to_pydatetime(),  # type: ignore[union-attr]
                direction=direction,
                strength=1.0,
                metadata={"stop": float(row["stop"]), "target": float(row["target"])},
            ))
        return signals

    def size_position(
        self,
        signal: Signal,
        context: PortfolioContext,
        instrument: Instrument,
    ) -> int:
        return 1

    def exit_rules(
        self,
        position: Position,
        current_bar: pd.Series,
        instrument: Instrument,
    ) -> ExitDecision:
        from trading_research.core.strategies import ExitDecision

        return ExitDecision(action="hold", reason="engine handles TP/SL/EOD")

    # ------------------------------------------------------------------
    # Condition evaluation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _eval_conditions(
        ev: ExprEvaluator,
        direction_cfg: dict,
        n: int,
    ) -> np.ndarray:
        """Evaluate direction conditions. Returns a bool ndarray.

        Composition:
        - ``all:`` — all conditions must be True (AND)
        - ``any:`` — at least one must be True (OR); ANDed with ``all``
        - Direction disabled when no conditions are specified.
        """
        if not direction_cfg:
            return np.zeros(n, dtype=bool)

        all_conditions: list[str] = direction_cfg.get("all", [])
        any_conditions: list[str] = direction_cfg.get("any", [])

        if not all_conditions and not any_conditions:
            return np.zeros(n, dtype=bool)

        mask = np.ones(n, dtype=bool)

        for cond in all_conditions:
            if not isinstance(cond, str):
                raise ValueError(
                    f"Each condition must be a string expression. "
                    f"Got {type(cond).__name__}: {cond!r}"
                )
            result = ev.eval(cond)
            if isinstance(result, pd.Series):
                mask = mask & result.fillna(False).to_numpy(dtype=bool)
            else:
                mask = mask & np.full(n, bool(result), dtype=bool)

        if any_conditions:
            any_mask = np.zeros(n, dtype=bool)
            for cond in any_conditions:
                if not isinstance(cond, str):
                    raise ValueError(
                        f"Each condition must be a string expression. "
                        f"Got {type(cond).__name__}: {cond!r}"
                    )
                result = ev.eval(cond)
                if isinstance(result, pd.Series):
                    any_mask = any_mask | result.fillna(False).to_numpy(dtype=bool)
                else:
                    any_mask = any_mask | np.full(n, bool(result), dtype=bool)
            mask = mask & any_mask

        return mask


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _build_time_window_mask(df: pd.DataFrame, tw: dict) -> np.ndarray:
    """Build boolean mask for bars within the UTC time window [start, end)."""
    start = _parse_hhmm(tw["start_utc"])
    end = _parse_hhmm(tw["end_utc"])
    bar_times = df.index.tz_convert("UTC").time
    return np.array([start <= t < end for t in bar_times], dtype=bool)


def _parse_hhmm(s: str) -> dt_time:
    parts = str(s).split(":")
    if len(parts) < 2:
        raise ValueError(f"Expected HH:MM, got {s!r}")
    return dt_time(int(parts[0]), int(parts[1]))


def _eval_price_expr(
    ev: ExprEvaluator, expr: str | None, n: int
) -> np.ndarray:
    """Evaluate a price-level expression (stop or target). Returns float ndarray."""
    if not expr:
        return np.full(n, np.nan, dtype=float)
    result = ev.eval(expr)
    if isinstance(result, pd.Series):
        return result.to_numpy(dtype=float, na_value=np.nan)
    return np.full(n, float(result), dtype=float)


def load_yaml_strategy(config: dict) -> YAMLStrategy:
    """Convenience wrapper: validate dispatch key and return a YAMLStrategy."""
    if "template" in config or "signal_module" in config:
        raise ValueError(
            "load_yaml_strategy() is for 'entry:' configs only. "
            "This config uses 'template' or 'signal_module'."
        )
    return YAMLStrategy.from_config(config)
