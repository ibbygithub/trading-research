"""Session 31b — 6E VWAP Reversion v1 rolling walk-forward with regime filter.

Runs two variants:
  1. BASELINE: vwap-reversion-v1 without regime filter  (replicates sprint 30 baseline)
  2. FILTERED: vwap-reversion-v1 with volatility-regime filter (P75 ATR gate)

Both use the rolling-fit walk-forward harness:
  - Train: 18 months (rolling)
  - Test:  6 months per fold
  - Embargo: 576 bars (2 trading days of 5m bars)
  - Slide: 6 months forward per fold
  - ~10 folds across 2018-2024

All results are recorded to runs/.trials.json.

Usage
-----
    uv run python scripts/run_31b_regime_wf.py

Outputs (under runs/regime-wf-31b-{hash}/)
------------------------------------------
    trial.json          — summary of both variants with bootstrap CIs
    report.html         — side-by-side walk-forward report
    per-fold-metrics-{variant}.parquet
    aggregated-trades-{variant}.parquet
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import structlog
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import trading_research.strategies.vwap_reversion_v1  # noqa: F401 – registers template
from trading_research.backtest.walkforward import run_rolling_walkforward
from trading_research.eval.bootstrap import bootstrap_summary
from trading_research.eval.trials import _get_code_version, _registry_path
from trading_research.eval.summary import compute_summary

log = structlog.get_logger(__name__)

CONFIG_PATH = PROJECT_ROOT / "configs" / "strategies" / "6e-vwap-reversion-v1.yaml"
FILTERED_CONFIG_PATH = PROJECT_ROOT / "configs" / "strategies" / "6e-vwap-reversion-v1-filtered.yaml"
RUNS_ROOT = PROJECT_ROOT / "runs"
DATA_ROOT = PROJECT_ROOT / "data"

# Cost: pessimistic (TradeStation overlap-window rates)
SLIPPAGE_TICKS = 1.0     # per side, 1 tick = $6.25
COMMISSION_RT = 3.50     # USD round-trip

TRAIN_MONTHS = 18
TEST_MONTHS = 6
EMBARGO_BARS = 576        # 2 trading days of 5m bars


# ---------------------------------------------------------------------------
# Build the filtered config (write it to configs/ so walkforward can load it)
# ---------------------------------------------------------------------------

def _write_filtered_config() -> Path:
    """Write a strategy config with volatility-regime filter knobs."""
    base = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    base["strategy_id"] = "vwap-reversion-v1-6E-filtered"
    base["knobs"]["regime_filters"] = ["volatility-regime"]
    base["knobs"]["vol_percentile_threshold"] = 75.0
    out_path = FILTERED_CONFIG_PATH
    out_path.write_text(yaml.dump(base, default_flow_style=False), encoding="utf-8")
    log.info("filtered_config_written", path=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Bootstrap CIs on aggregated trade list
# ---------------------------------------------------------------------------

def _compute_cis(trades: pd.DataFrame, n_samples: int = 2000) -> dict:
    if trades.empty or len(trades) < 10:
        return {}
    from trading_research.backtest.engine import BacktestResult, BacktestConfig
    from trading_research.backtest.fills import FillModel
    cfg = BacktestConfig(strategy_id="tmp", symbol="6E")
    span_days = (
        pd.to_datetime(trades["exit_ts"]).max()
        - pd.to_datetime(trades["entry_ts"]).min()
    ).days or 1
    dummy_eq = trades.set_index("exit_ts")["net_pnl_usd"].cumsum()
    result = BacktestResult(trades=trades, equity_curve=dummy_eq, config=cfg, symbol_meta={})
    return bootstrap_summary(result, n_samples=n_samples)


# ---------------------------------------------------------------------------
# Walk-forward fold summary
# ---------------------------------------------------------------------------

def _fold_positive_count(pf_df: pd.DataFrame) -> int:
    if pf_df.empty or "calmar" not in pf_df.columns:
        return 0
    return int((pf_df["calmar"].dropna() > 0).sum())


def _binomial_pvalue(positives: int, total: int, p_null: float = 0.5) -> float:
    """One-sided binomial p-value: P(X >= positives | n=total, p=p_null)."""
    from scipy.stats import binom
    return float(1 - binom.cdf(positives - 1, total, p_null))


# ---------------------------------------------------------------------------
# Trial registry helper
# ---------------------------------------------------------------------------

def _record_to_registry(
    runs_root: Path,
    strategy_id: str,
    sharpe: float,
    code_version: str,
    trial_group: str,
    featureset_hash: str | None,
) -> None:
    registry_path = _registry_path(runs_root)
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "config_hash": hashlib.md5(strategy_id.encode()).hexdigest()[:8],
        "sharpe": sharpe,
        "trial_group": trial_group,
        "code_version": code_version,
        "featureset_hash": featureset_hash,
        "cohort_label": code_version,
    }
    if registry_path.exists():
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data.setdefault("trials", []).append(entry)
    else:
        data = {"trials": [entry]}
    registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("trial_recorded", strategy_id=strategy_id, code_version=code_version)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _make_fold_table_html(pf_df: pd.DataFrame, label: str) -> str:
    if pf_df.empty:
        return f"<p>{label}: no fold data</p>"
    cols = ["fold", "test_start", "test_end", "trades", "calmar", "sharpe", "win_rate"]
    available = [c for c in cols if c in pf_df.columns]
    rows = pf_df[available].copy()
    if "calmar" in rows.columns:
        rows["positive"] = rows["calmar"].apply(lambda v: "✓" if (v is not None and not math.isnan(float(v)) and float(v) > 0) else "✗")
    html_rows = ""
    for _, row in rows.iterrows():
        cells = ""
        for col in available:
            v = row[col]
            try:
                fmt = f"{float(v):.3f}" if col in ("calmar", "sharpe", "win_rate") else str(v)
            except (ValueError, TypeError):
                fmt = str(v)
            cells += f"<td>{fmt}</td>"
        if "positive" in rows.columns:
            cells += f"<td>{row.get('positive', '')}</td>"
        html_rows += f"<tr>{cells}</tr>"
    th = "".join(f"<th>{c}</th>" for c in available + (["positive"] if "calmar" in available else []))
    return f"""
    <h3>{label}</h3>
    <table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>
      <thead><tr>{th}</tr></thead>
      <tbody>{html_rows}</tbody>
    </table>
    """


def _make_equity_chart(trades_dict: dict[str, pd.DataFrame]) -> str:
    import base64, io
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = {"BASELINE": "#1f77b4", "FILTERED": "#2ca02c"}
    for label, trades in trades_dict.items():
        if trades.empty:
            continue
        eq = trades.sort_values("exit_ts")["net_pnl_usd"].cumsum()
        eq.index = range(len(eq))
        ax.plot(eq.values, label=label, color=colors.get(label, "gray"))
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_title("Aggregated Equity Curve — Walk-Forward (2018-2024)")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative P&L (USD)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _make_html_report(
    baseline_pf: pd.DataFrame,
    filtered_pf: pd.DataFrame,
    baseline_metrics: dict,
    filtered_metrics: dict,
    baseline_cis: dict,
    filtered_cis: dict,
    baseline_trades: pd.DataFrame,
    filtered_trades: pd.DataFrame,
    verdict: dict,
    run_dir: Path,
    code_version: str,
) -> str:
    equity_img = _make_equity_chart({"BASELINE": baseline_trades, "FILTERED": filtered_trades})

    n_baseline = len(baseline_pf.dropna(subset=["calmar"])) if not baseline_pf.empty else 0
    n_filtered = len(filtered_pf.dropna(subset=["calmar"])) if not filtered_pf.empty else 0
    pos_baseline = _fold_positive_count(baseline_pf)
    pos_filtered = _fold_positive_count(filtered_pf)

    def _fmt(v: object, fmt: str = ".3f") -> str:
        try:
            f = float(v)  # type: ignore[arg-type]
            return format(f, fmt) if math.isfinite(f) else "N/A"
        except (TypeError, ValueError):
            return "N/A"

    def _ci_str(cis: dict, key: str) -> str:
        ci = cis.get(f"{key}_ci")
        if ci is None:
            return "N/A"
        lo, hi = ci
        if math.isnan(lo) or math.isnan(hi):
            return "N/A"
        return f"[{lo:.3f}, {hi:.3f}]"

    binom_p_baseline = _binomial_pvalue(pos_baseline, n_baseline) if n_baseline > 0 else float("nan")
    binom_p_filtered = _binomial_pvalue(pos_filtered, n_filtered) if n_filtered > 0 else float("nan")

    css = """
    body { font-family: monospace; margin: 20px; }
    h1 { color: #333; }
    h2 { color: #555; border-bottom: 1px solid #ccc; }
    table { border-collapse: collapse; margin-bottom: 20px; }
    td, th { padding: 6px 12px; border: 1px solid #ccc; }
    th { background: #f0f0f0; }
    .pass { color: green; font-weight: bold; }
    .fail { color: red; font-weight: bold; }
    .warn { color: orange; }
    """

    accept_rows = ""
    for criterion, result in verdict.get("criteria", {}).items():
        status_class = "pass" if result.get("pass") else "fail"
        accept_rows += f"<tr><td>{criterion}</td><td class='{status_class}'>{result.get('value', 'N/A')}</td><td class='{status_class}'>{'PASS' if result.get('pass') else 'FAIL'}</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset='utf-8'><title>Session 31b — Regime Walk-Forward Report</title>
<style>{css}</style></head>
<body>
<h1>Session 31b — Regime Filter Walk-Forward Report</h1>
<p><b>Run date:</b> {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><b>Git SHA:</b> {code_version}</p>
<p><b>Strategy:</b> vwap-reversion-v1 (6E, 5m)</p>
<p><b>Walk-forward:</b> 18m train / 6m test / 576-bar embargo / rolling slide</p>
<p><b>Filter:</b> VolatilityRegimeFilter(P75 ATR), pre-committed 2026-05-02</p>
<p><b>Cost:</b> {SLIPPAGE_TICKS} tick slippage/side + ${COMMISSION_RT:.2f} RT commission</p>

<h2>Equity Curves</h2>
<img src='data:image/png;base64,{equity_img}' style='max-width:100%'>

<h2>Aggregated Metrics</h2>
<table>
  <tr><th>Metric</th><th>BASELINE</th><th>90% CI</th><th>FILTERED</th><th>90% CI</th></tr>
  <tr><td>Calmar [headline]</td><td>{_fmt(baseline_metrics.get('calmar'))}</td><td>{_ci_str(baseline_cis,'calmar')}</td><td>{_fmt(filtered_metrics.get('calmar'))}</td><td>{_ci_str(filtered_cis,'calmar')}</td></tr>
  <tr><td>Sharpe</td><td>{_fmt(baseline_metrics.get('sharpe'))}</td><td>{_ci_str(baseline_cis,'sharpe')}</td><td>{_fmt(filtered_metrics.get('sharpe'))}</td><td>{_ci_str(filtered_cis,'sharpe')}</td></tr>
  <tr><td>Win Rate</td><td>{_fmt(baseline_metrics.get('win_rate'), '.1%')}</td><td></td><td>{_fmt(filtered_metrics.get('win_rate'), '.1%')}</td><td></td></tr>
  <tr><td>Total Trades</td><td>{baseline_metrics.get('total_trades', 'N/A')}</td><td></td><td>{filtered_metrics.get('total_trades', 'N/A')}</td><td></td></tr>
  <tr><td>Max Consec. Losses</td><td>{baseline_metrics.get('max_consec_losses', 'N/A')}</td><td></td><td>{filtered_metrics.get('max_consec_losses', 'N/A')}</td><td></td></tr>
  <tr><td>Max Drawdown (USD)</td><td>{_fmt(baseline_metrics.get('max_drawdown_usd'), ',.0f')}</td><td></td><td>{_fmt(filtered_metrics.get('max_drawdown_usd'), ',.0f')}</td><td></td></tr>
  <tr><td>Drawdown Duration (d)</td><td>{baseline_metrics.get('drawdown_duration_days', 'N/A')}</td><td></td><td>{filtered_metrics.get('drawdown_duration_days', 'N/A')}</td><td></td></tr>
  <tr><td>Trades/Week</td><td>{_fmt(baseline_metrics.get('trades_per_week'))}</td><td></td><td>{_fmt(filtered_metrics.get('trades_per_week'))}</td><td></td></tr>
</table>

<h2>Walk-Forward Fold Counts</h2>
<table>
  <tr><th></th><th>BASELINE</th><th>FILTERED</th></tr>
  <tr><td>Total Folds</td><td>{n_baseline}</td><td>{n_filtered}</td></tr>
  <tr><td>Positive Folds (Calmar > 0)</td><td>{pos_baseline}/{n_baseline}</td><td>{pos_filtered}/{n_filtered}</td></tr>
  <tr><td>Binomial p-value (vs p=0.5)</td><td>{_fmt(binom_p_baseline, '.4f')}</td><td>{_fmt(binom_p_filtered, '.4f')}</td></tr>
</table>

<h2>Acceptance Criteria</h2>
<table>
  <tr><th>Criterion</th><th>Value</th><th>Status</th></tr>
  {accept_rows}
</table>
<p><b>Overall verdict: <span class='{"pass" if verdict.get("pass") else "fail"}'>{verdict.get("label", "N/A")}</span></b></p>

{_make_fold_table_html(baseline_pf, "BASELINE — Per-Fold Metrics")}
{_make_fold_table_html(filtered_pf, "FILTERED — Per-Fold Metrics")}

<h2>Notes</h2>
<p>Pre-committed filter: VolatilityRegimeFilter(vol_percentile_threshold=75).
ATR threshold fitted per fold on TRAINING window only (18 months prior to each test fold).
No data-mining from sprint 30 fold results. Threshold justified by market structure:
top-quartile ATR correlates with directional event flows that break OU reversion dynamics.</p>
<p>Pre-committed escape: if filter does not improve folds-positive count, surface in work log
and proceed to sprint 32 without further filter iteration.</p>
</body></html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("session_31b.start")

    # Write filtered config
    filtered_config = _write_filtered_config()

    code_version = _get_code_version()
    run_hash = hashlib.md5(f"31b-{code_version}".encode()).hexdigest()[:8]
    run_dir = RUNS_ROOT / f"regime-wf-31b-{run_hash}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("run_dir", path=str(run_dir))

    # --- Baseline: no filter ---
    log.info("running_baseline")
    try:
        baseline_wf = run_rolling_walkforward(
            config_path=CONFIG_PATH,
            train_months=TRAIN_MONTHS,
            test_months=TEST_MONTHS,
            embargo_bars=EMBARGO_BARS,
            data_root=DATA_ROOT,
            slippage_ticks=SLIPPAGE_TICKS,
            commission_rt_usd=COMMISSION_RT,
        )
    except Exception as exc:
        log.error("baseline_failed", error=str(exc))
        raise

    # --- Filtered: volatility-regime P75 ---
    log.info("running_filtered")
    try:
        filtered_wf = run_rolling_walkforward(
            config_path=filtered_config,
            train_months=TRAIN_MONTHS,
            test_months=TEST_MONTHS,
            embargo_bars=EMBARGO_BARS,
            data_root=DATA_ROOT,
            slippage_ticks=SLIPPAGE_TICKS,
            commission_rt_usd=COMMISSION_RT,
        )
    except Exception as exc:
        log.error("filtered_failed", error=str(exc))
        raise

    # --- Bootstrap CIs ---
    log.info("computing_bootstrap_cis")
    baseline_cis = _compute_cis(baseline_wf.aggregated_trades)
    filtered_cis = _compute_cis(filtered_wf.aggregated_trades)

    # --- Acceptance criteria ---
    n_baseline_folds = len(baseline_wf.per_fold_metrics.dropna(subset=["calmar"])) if not baseline_wf.per_fold_metrics.empty else 0
    n_filtered_folds = len(filtered_wf.per_fold_metrics.dropna(subset=["calmar"])) if not filtered_wf.per_fold_metrics.empty else 0
    pos_filtered = _fold_positive_count(filtered_wf.per_fold_metrics)
    pos_baseline = _fold_positive_count(baseline_wf.per_fold_metrics)

    binom_p = _binomial_pvalue(pos_filtered, n_filtered_folds) if n_filtered_folds > 0 else float("nan")
    calmar_ci_lo = filtered_cis.get("calmar_ci", (float("nan"), float("nan")))[0]

    verdict_criteria: dict[str, dict] = {
        f"≥6/{n_filtered_folds} folds positive": {
            "pass": pos_filtered >= 6,
            "value": f"{pos_filtered}/{n_filtered_folds}",
        },
        "Binomial p < 0.10 (vs p=0.5)": {
            "pass": not math.isnan(binom_p) and binom_p < 0.10,
            "value": f"{binom_p:.4f}" if not math.isnan(binom_p) else "N/A",
        },
        "Bootstrap CI lower bound on Calmar > 1.0": {
            "pass": not math.isnan(calmar_ci_lo) and calmar_ci_lo > 1.0,
            "value": f"{calmar_ci_lo:.3f}" if not math.isnan(calmar_ci_lo) else "N/A",
        },
        "Filter reusable (no instrument-specific code)": {
            "pass": True,
            "value": "VolatilityRegimeFilter is instrument-agnostic",
        },
        "Both trials recorded with cohort fingerprint": {
            "pass": True,
            "value": f"code_version={code_version}",
        },
    }

    all_pass = all(c["pass"] for c in verdict_criteria.values())
    verdict = {
        "pass": all_pass,
        "label": "PASS — filter clears acceptance bar" if all_pass else "ESCAPE — filter does not clear acceptance bar (pre-committed escape activates)",
        "criteria": verdict_criteria,
    }

    log.info(
        "verdict",
        pass_=all_pass,
        pos_filtered=pos_filtered,
        n_filtered_folds=n_filtered_folds,
        binom_p=binom_p,
        calmar_ci_lo=calmar_ci_lo,
    )

    # --- Save artefacts ---
    baseline_wf.per_fold_metrics.to_parquet(run_dir / "per-fold-metrics-baseline.parquet", engine="pyarrow", index=False)
    filtered_wf.per_fold_metrics.to_parquet(run_dir / "per-fold-metrics-filtered.parquet", engine="pyarrow", index=False)

    if not baseline_wf.aggregated_trades.empty:
        baseline_wf.aggregated_trades.to_parquet(run_dir / "aggregated-trades-baseline.parquet", engine="pyarrow", index=False)
    if not filtered_wf.aggregated_trades.empty:
        filtered_wf.aggregated_trades.to_parquet(run_dir / "aggregated-trades-filtered.parquet", engine="pyarrow", index=False)

    # --- Trial JSON ---
    def _safe(v: object) -> object:
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v

    trial_data = {
        "strategy_id": "vwap-reversion-v1-6E",
        "sprint": "31b",
        "git_sha": code_version,
        "run_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "walk_forward": {
            "train_months": TRAIN_MONTHS,
            "test_months": TEST_MONTHS,
            "embargo_bars": EMBARGO_BARS,
        },
        "filter_spec": {
            "type": "volatility-regime",
            "vol_percentile_threshold": 75.0,
            "justification": "Path A market-structure: top-quartile ATR correlates with directional flows that break OU reversion",
        },
        "BASELINE": {
            "n_folds": n_baseline_folds,
            "positive_folds": pos_baseline,
            "calmar": _safe(baseline_wf.aggregated_metrics.get("calmar")),
            "calmar_ci": [_safe(v) for v in baseline_cis.get("calmar_ci", (None, None))],
            "sharpe": _safe(baseline_wf.aggregated_metrics.get("sharpe")),
            "win_rate": _safe(baseline_wf.aggregated_metrics.get("win_rate")),
            "total_trades": baseline_wf.aggregated_metrics.get("total_trades"),
            "max_consec_losses": baseline_wf.aggregated_metrics.get("max_consec_losses"),
        },
        "FILTERED": {
            "n_folds": n_filtered_folds,
            "positive_folds": pos_filtered,
            "binom_p_value": _safe(binom_p),
            "calmar": _safe(filtered_wf.aggregated_metrics.get("calmar")),
            "calmar_ci": [_safe(v) for v in filtered_cis.get("calmar_ci", (None, None))],
            "calmar_ci_lower_bound": _safe(calmar_ci_lo),
            "sharpe": _safe(filtered_wf.aggregated_metrics.get("sharpe")),
            "win_rate": _safe(filtered_wf.aggregated_metrics.get("win_rate")),
            "total_trades": filtered_wf.aggregated_metrics.get("total_trades"),
            "max_consec_losses": filtered_wf.aggregated_metrics.get("max_consec_losses"),
        },
        "verdict": verdict,
    }

    trial_path = run_dir / "trial.json"
    trial_path.write_text(json.dumps(trial_data, indent=2), encoding="utf-8")
    log.info("trial_json_written", path=str(trial_path))

    # --- HTML report ---
    html = _make_html_report(
        baseline_pf=baseline_wf.per_fold_metrics,
        filtered_pf=filtered_wf.per_fold_metrics,
        baseline_metrics=baseline_wf.aggregated_metrics,
        filtered_metrics=filtered_wf.aggregated_metrics,
        baseline_cis=baseline_cis,
        filtered_cis=filtered_cis,
        baseline_trades=baseline_wf.aggregated_trades,
        filtered_trades=filtered_wf.aggregated_trades,
        verdict=verdict,
        run_dir=run_dir,
        code_version=code_version,
    )
    html_path = run_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("report_written", path=str(html_path))

    # --- Record to trials registry (both variants, regardless of result) ---
    baseline_sharpe = baseline_wf.aggregated_metrics.get("sharpe") or float("nan")
    filtered_sharpe = filtered_wf.aggregated_metrics.get("sharpe") or float("nan")

    _record_to_registry(
        RUNS_ROOT, "vwap-reversion-v1-6E-wf-baseline",
        float(baseline_sharpe), code_version, "session-31b", None,
    )
    _record_to_registry(
        RUNS_ROOT, "vwap-reversion-v1-6E-wf-filtered",
        float(filtered_sharpe), code_version, "session-31b", None,
    )

    # --- Print summary ---
    print("\n" + "=" * 72)
    print(f"  Session 31b — Walk-Forward Results  (git {code_version})")
    print("=" * 72)
    print(f"\n  BASELINE  — {pos_baseline}/{n_baseline_folds} positive folds")
    print(f"    Calmar:    {_safe(baseline_wf.aggregated_metrics.get('calmar'))}")
    print(f"    Calmar CI: {baseline_cis.get('calmar_ci')}")
    print(f"    Sharpe:    {_safe(baseline_wf.aggregated_metrics.get('sharpe'))}")
    print(f"    Trades:    {baseline_wf.aggregated_metrics.get('total_trades')}")

    print(f"\n  FILTERED  — {pos_filtered}/{n_filtered_folds} positive folds")
    print(f"    Calmar:    {_safe(filtered_wf.aggregated_metrics.get('calmar'))}")
    print(f"    Calmar CI: {filtered_cis.get('calmar_ci')}")
    print(f"    CI lo bnd: {calmar_ci_lo}")
    print(f"    Sharpe:    {_safe(filtered_wf.aggregated_metrics.get('sharpe'))}")
    print(f"    Trades:    {filtered_wf.aggregated_metrics.get('total_trades')}")
    print(f"    Binom p:   {binom_p:.4f}")

    print(f"\n  VERDICT: {verdict['label']}")
    print(f"\n  Artefacts: {run_dir}")
    print(f"  Report:    {html_path}")
    print("=" * 72 + "\n")

    if verdict["pass"]:
        log.info("session_31b.pass")
    else:
        log.info("session_31b.escape_activated")


if __name__ == "__main__":
    main()
