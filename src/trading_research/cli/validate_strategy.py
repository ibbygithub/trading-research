"""``trading-research validate-strategy`` — lint-time validator for strategy YAML.

Loads the YAML, resolves the features parquet for the configured
``symbol``/``timeframe``/``feature_set``, builds a 100-bar synthetic DataFrame
with the parquet's column schema, evaluates the strategy's entry/exit
expressions on it, and reports any errors before a real backtest runs.

Specification: Chapter 13.4 of the operator's manual.

Exit codes:
    0 — strategy is syntactically valid; expressions resolved cleanly.
    1 — one or more validation errors found.
    2 — YAML not parseable, features parquet not found, or unknown symbol.
"""

from __future__ import annotations

import glob as _glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer

_PROJECT_ROOT = Path(__file__).parents[3]
_DATA_ROOT = _PROJECT_ROOT / "data"
_REGIMES_DIR = _PROJECT_ROOT / "configs" / "regimes"


@dataclass
class ValidationResult:
    """Result of a validate-strategy run, structured for both text and exit-code paths."""

    config_path: Path
    dispatch: str = ""
    symbol: str = ""
    timeframe: str = ""
    feature_set: str = ""
    features_path: Path | None = None
    columns: list[str] = field(default_factory=list)
    knobs: dict[str, object] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    long_signal_rate_pct: float | None = None
    short_signal_rate_pct: float | None = None
    cross_key_ok: bool = True


def _find_features_parquet(
    data_root: Path, symbol: str, timeframe: str, feature_set: str
) -> Path | None:
    pattern = str(
        data_root
        / "features"
        / f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet"
    )
    matches = sorted(_glob.glob(pattern))
    if not matches:
        return None
    return Path(matches[-1])


def _read_columns(parquet_path: Path) -> list[str]:
    """Read the parquet schema without loading row data."""
    import pyarrow.parquet as pq

    schema = pq.read_schema(parquet_path)
    return list(schema.names)


def _build_synthetic_bars(columns: list[str], n: int = 100):
    """Construct an n-bar DataFrame with the given columns, tz-aware index, plausible values.

    Numeric columns get an increasing-with-noise series; non-numeric columns get NaN.
    The index is a tz-aware UTC DatetimeIndex; timestamp_utc / timestamp_ny columns
    are skipped (the index carries the time).
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed=0)
    idx = pd.date_range("2026-01-02 14:30", periods=n, freq="1min", tz="UTC")

    data: dict[str, object] = {}
    for col in columns:
        if col in {"timestamp_utc", "timestamp_ny"}:
            continue
        base = 100.0 + rng.standard_normal(n).cumsum() * 0.1
        data[col] = base
    return pd.DataFrame(data, index=idx)


def _detect_dispatch(cfg: dict) -> str:
    has_entry = "entry" in cfg
    template_name = cfg.get("template")
    signal_module = cfg.get("signal_module")
    n = sum([has_entry, bool(template_name), bool(signal_module)])
    if n == 0:
        return "none"
    if n > 1:
        return "conflict"
    if has_entry:
        return "yaml-template"
    if template_name:
        return f"registered-template:{template_name}"
    return f"signal-module:{signal_module}"


def _cross_key_check(cfg: dict, result: ValidationResult) -> None:
    """Enforce Chapter 13.2 cross-key constraints."""
    dispatch_count = sum([
        "entry" in cfg,
        bool(cfg.get("template")),
        bool(cfg.get("signal_module")),
    ])
    if dispatch_count == 0:
        result.errors.append(
            "config must have one of 'entry', 'template', or 'signal_module' "
            "(Chapter 9.4: three dispatch paths)."
        )
        result.cross_key_ok = False
    elif dispatch_count > 1:
        result.errors.append(
            "config may have only one of 'entry', 'template', or 'signal_module'."
        )
        result.cross_key_ok = False

    bt = cfg.get("backtest", {})
    if bt.get("fill_model") == "same_bar" and not bt.get("same_bar_justification"):
        result.warnings.append(
            "fill_model: same_bar requires a non-empty same_bar_justification "
            "(Chapter 14.2)."
        )

    for key in ("regime_filter", "regime_filters"):
        if key in cfg and "entry" not in cfg:
            result.warnings.append(
                f"{key!r} has no effect without an 'entry' block."
            )


def _evaluate_yaml_strategy(
    cfg: dict,
    columns: list[str],
    result: ValidationResult,
) -> None:
    """Construct YAMLStrategy and evaluate on synthetic bars; capture errors into result."""
    from trading_research.strategies.template import YAMLStrategy

    try:
        strategy = YAMLStrategy.from_config(cfg, regimes_dir=_REGIMES_DIR)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        result.errors.append(f"YAMLStrategy.from_config: {exc}")
        return

    result.knobs = dict(strategy.knobs)

    bars = _build_synthetic_bars(columns)
    try:
        signals = strategy.generate_signals_df(bars)
    except (ValueError, KeyError, TypeError) as exc:
        result.errors.append(f"signal generation: {exc}")
        return

    sig = signals["signal"].to_numpy() if "signal" in signals.columns else None
    if sig is not None and len(sig) > 0:
        result.long_signal_rate_pct = float((sig == 1).sum()) / len(sig) * 100.0
        result.short_signal_rate_pct = float((sig == -1).sum()) / len(sig) * 100.0
        if result.long_signal_rate_pct == 0 and result.short_signal_rate_pct == 0:
            result.warnings.append(
                "synthetic signal rate is 0%/0% — conditions may be too strict "
                "(or the synthetic data does not exercise them)."
            )
        elif (
            result.long_signal_rate_pct > 80
            or result.short_signal_rate_pct > 80
        ):
            result.warnings.append(
                "synthetic signal rate exceeds 80% on one side — conditions may "
                "be trivially always-true."
            )


def validate_strategy(
    config_path: Path,
    data_root: Path | None = None,
) -> ValidationResult:
    """Run the full validation pipeline and return a structured result.

    Public function suitable for programmatic use; the CLI command is a thin
    wrapper around this.
    """
    import yaml

    result = ValidationResult(config_path=config_path)

    if not config_path.is_file():
        result.errors.append(f"file not found: {config_path}")
        return result

    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        result.errors.append(f"YAML parse error: {exc}")
        return result

    if not isinstance(cfg, dict):
        result.errors.append("top-level YAML must be a mapping.")
        return result

    result.dispatch = _detect_dispatch(cfg)
    result.symbol = cfg.get("symbol", "")
    result.timeframe = cfg.get("timeframe", "5m")
    result.feature_set = cfg.get("feature_set", "base-v1")

    if not result.symbol:
        result.errors.append("config must declare 'symbol'.")

    _cross_key_check(cfg, result)

    if not result.cross_key_ok or not result.symbol:
        return result

    root = data_root or _DATA_ROOT
    features_path = _find_features_parquet(
        root, result.symbol, result.timeframe, result.feature_set
    )
    if features_path is None:
        result.errors.append(
            f"features parquet not found: "
            f"data/features/{result.symbol}_backadjusted_"
            f"{result.timeframe}_features_{result.feature_set}_*.parquet"
        )
        return result
    result.features_path = features_path
    result.columns = _read_columns(features_path)

    if result.dispatch == "yaml-template":
        _evaluate_yaml_strategy(cfg, result.columns, result)
    elif result.dispatch.startswith("registered-template:"):
        result.warnings.append(
            "registered-template dispatch: validate-strategy currently lints "
            "YAML-template configs only. Run the backtest on a short date "
            "window to surface template-specific errors."
        )
    elif result.dispatch.startswith("signal-module:"):
        result.warnings.append(
            "signal-module dispatch (legacy Python path): validate-strategy "
            "does not import the module. Run the backtest on a short date "
            "window to surface module-specific errors."
        )

    return result


def _print_text_report(result: ValidationResult, verbose: bool) -> None:
    typer.echo(f"Validating: {result.config_path}")
    typer.echo(f"  Dispatch:    {result.dispatch}")
    typer.echo(
        f"  Symbol:      {result.symbol} / {result.timeframe} / {result.feature_set}"
    )

    if result.features_path is not None:
        typer.echo(f"  Feature set: {result.features_path.name} [OK]")
        if verbose:
            typer.echo(f"  Columns ({len(result.columns)}):")
            for c in result.columns:
                typer.echo(f"    - {c}")
    else:
        typer.echo("  Feature set: (not resolved)")

    if result.knobs and verbose:
        typer.echo("  Knobs:")
        for k, v in result.knobs.items():
            typer.echo(f"    {k} = {v}")

    if result.long_signal_rate_pct is not None:
        typer.echo(
            f"  Synthetic signal rate: long={result.long_signal_rate_pct:.0f}%, "
            f"short={result.short_signal_rate_pct:.0f}% on 100-bar test"
        )

    if result.warnings:
        typer.echo("")
        for w in result.warnings:
            typer.echo(f"  WARNING: {w}")

    if result.errors:
        typer.echo("")
        for e in result.errors:
            typer.echo(f"  ERROR: {e}", err=True)
        typer.echo("")
        typer.echo(
            f"  {len(result.errors)} error(s) found. Fix before running backtest.",
            err=True,
        )
    else:
        typer.echo("")
        if result.warnings:
            typer.echo("  No errors. (Warnings noted above.)")
        else:
            typer.echo("  No errors.")


def validate_strategy_command(
    config_path: Annotated[Path, typer.Argument(help="Path to strategy YAML config.")],
    verbose: Annotated[
        bool, typer.Option("--verbose", help="Print column list and resolved knobs.")
    ] = False,
    data_root: Annotated[
        Path | None, typer.Option(help="Override data/ root.")
    ] = None,
) -> None:
    """Lint a strategy YAML: cross-key check + expression resolution on synthetic bars.

    Exit codes: 0 = clean, 1 = errors, 2 = unresolved (YAML or features missing).
    """
    result = validate_strategy(config_path, data_root=data_root)
    _print_text_report(result, verbose=verbose)

    if result.errors:
        unresolved_markers = (
            "file not found",
            "YAML parse error",
            "features parquet not found",
            "top-level YAML must be a mapping",
        )
        if any(any(m in e for m in unresolved_markers) for e in result.errors):
            raise typer.Exit(code=2)
        raise typer.Exit(code=1)
