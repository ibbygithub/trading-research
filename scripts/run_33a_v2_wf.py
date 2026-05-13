"""Session 33a — 6E VWAP Reversion v2 rolling walk-forward + gate data.

v2 = vwap-reversion-v1 + VolatilityRegimeFilter(P75 ATR) + Mulligan scale-in.

Runs two cost variants:
  Realistic   (sprint 30 run #4 equiv.): 2.0-tick overlap slippage, $4.20/RT
  Pessimistic (sprint 30 run #6 equiv.): 3.0-tick overlap slippage, $4.20/RT

Rolling-fit walk-forward: 18m train / 6m test / 576-bar embargo / ~10 folds.
Bootstrap: n=2000, seed=20260427.
Cohort DSR: n_trials=12 (8 v1-cost-sweep + 2 session-31b + 2 v2-this-run).

Usage
-----
    uv run python scripts/run_33a_v2_wf.py

Outputs (runs/vwap-reversion-v1-6E-v2-{hash}/)
------------------------------------------------
    trial.json              — v1 vs v2 side-by-side + gate criterion inputs
    report.html             — full report including fold table, stationarity, costs
    per-fold-metrics-realistic.parquet
    per-fold-metrics-pessimistic.parquet
    aggregated-trades-realistic.parquet
    aggregated-trades-pessimistic.parquet
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import structlog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import trading_research.strategies.vwap_reversion_v1  # noqa: F401, E402
from trading_research.backtest.walkforward import run_rolling_walkforward  # noqa: E402
from trading_research.eval.bootstrap import bootstrap_summary  # noqa: E402
from trading_research.eval.stats import deflated_sharpe_ratio  # noqa: E402
from trading_research.eval.trials import _get_code_version, _registry_path  # noqa: E402

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Config / constants
# ---------------------------------------------------------------------------

V2_CONFIG = PROJECT_ROOT / "configs" / "strategies" / "6e-vwap-reversion-v1-v2.yaml"
V1_TRIAL_JSON = PROJECT_ROOT / "runs" / "vwap-reversion-v1-6E-55f3e1e3" / "trial.json"
RUNS_ROOT = PROJECT_ROOT / "runs"
DATA_ROOT = PROJECT_ROOT / "data"

REALISTIC_SLIPPAGE = 2.0    # overlap window ticks — matches sprint 30 run #4
PESSIMISTIC_SLIPPAGE = 3.0  # overlap window ticks — matches sprint 30 run #6
COMMISSION_RT = 4.20

TRAIN_MONTHS = 18
TEST_MONTHS = 6
EMBARGO_BARS = 576          # 2 trading days × 288 bars/day at 5m

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260427

# Cohort composition for DSR (per spec):
#   8 v1-cost-sweep (sprint 30) + 2 session-31b (baseline + filtered) + 2 v2 (this run)
COHORT_N_TRIALS = 12


# ---------------------------------------------------------------------------
# Helpers — stationarity per fold
# ---------------------------------------------------------------------------

def _stationarity_for_fold(fold_bars: pd.DataFrame, core_inst: object) -> str:
    """Run composite stationarity classification on vwap_spread for a fold."""
    from trading_research.stats.stationarity import (
        adf_test,
        hurst_exponent,
        ou_half_life,
        _composite_classification,
    )
    series = None
    for col in ("vwap_spread", "vwap_diff", "vwap_spread_5m"):
        if col in fold_bars.columns:
            series = fold_bars[col].dropna()
            break
    if series is None and "close" in fold_bars.columns and "vwap_session" in fold_bars.columns:
        series = (fold_bars["close"] - fold_bars["vwap_session"]).dropna()

    if series is None or len(series) < 30:
        return "INSUFFICIENT_DATA"

    try:
        adf_r = adf_test(series, regression="c")
        hurst_r = hurst_exponent(series)
        ou_r = ou_half_life(series)
        return _composite_classification(adf_r, hurst_r, ou_r, "5m", instrument=core_inst)
    except Exception as exc:
        log.warning("stationarity_fold_failed", exc=str(exc))
        return "ERROR"


def _add_stationarity_to_folds(
    pf_df: pd.DataFrame,
    all_bars: pd.DataFrame,
    core_inst: object,
) -> pd.DataFrame:
    """Add stationarity_class column to per-fold metrics DataFrame."""
    if pf_df.empty or "test_start" not in pf_df.columns or "test_end" not in pf_df.columns:
        return pf_df
    classes = []
    for _, row in pf_df.iterrows():
        ts = pd.Timestamp(row["test_start"])
        te = pd.Timestamp(row["test_end"])
        fold_bars = all_bars[(all_bars.index >= ts) & (all_bars.index <= te)]
        classes.append(_stationarity_for_fold(fold_bars, core_inst))
    pf_df = pf_df.copy()
    pf_df["stationarity_class"] = classes
    return pf_df


# ---------------------------------------------------------------------------
# Helpers — bootstrap CIs
# ---------------------------------------------------------------------------

def _compute_cis(trades: pd.DataFrame) -> dict:
    if trades.empty or len(trades) < 10:
        return {}
    from trading_research.backtest.engine import BacktestConfig, BacktestResult
    cfg = BacktestConfig(strategy_id="tmp", symbol="6E")
    dummy_eq = trades.sort_values("exit_ts").set_index("exit_ts")["net_pnl_usd"].cumsum()
    result = BacktestResult(trades=trades, equity_curve=dummy_eq, config=cfg, symbol_meta={})
    return bootstrap_summary(result, n_samples=BOOTSTRAP_N, seed=BOOTSTRAP_SEED)


# ---------------------------------------------------------------------------
# Helpers — max-consecutive-losses bootstrap (G4)
# ---------------------------------------------------------------------------

def _bootstrap_max_consec_losses(trades: pd.DataFrame, n_samples: int = 2000, seed: int = BOOTSTRAP_SEED) -> dict:
    """Bootstrap distribution of max consecutive losses. Returns p50, p95."""
    if trades.empty or len(trades) < 10:
        return {"p50": float("nan"), "p95": float("nan")}
    wins = (trades["net_pnl_usd"].values >= 0).astype(int)
    rng = np.random.default_rng(seed)
    mcls = []
    for _ in range(n_samples):
        sample = rng.choice(wins, size=len(wins), replace=True)
        # Max consecutive losses = max run of 0s
        mcl = 0
        cur = 0
        for w in sample:
            if w == 0:
                cur += 1
                mcl = max(mcl, cur)
            else:
                cur = 0
        mcls.append(mcl)
    arr = np.array(mcls, dtype=float)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
    }


# ---------------------------------------------------------------------------
# Helpers — DSR
# ---------------------------------------------------------------------------

def _compute_cohort_dsr(trades: pd.DataFrame, n_trials: int) -> float:
    """Compute Deflated Sharpe Ratio over the full cohort."""
    if trades.empty or len(trades) < 10:
        return float("nan")
    import scipy.stats as st
    pnl = trades["net_pnl_usd"].values
    n_obs = len(pnl)
    sharpe = float(pnl.mean() / pnl.std(ddof=1) * np.sqrt(252)) if pnl.std(ddof=1) > 0 else float("nan")
    skew = float(st.skew(pnl))
    kurt = float(st.kurtosis(pnl, fisher=False))  # Pearson kurtosis
    return deflated_sharpe_ratio(sharpe, n_obs, n_trials, skew, kurt)


# ---------------------------------------------------------------------------
# Helpers — fold positive count / binomial p-value
# ---------------------------------------------------------------------------

def _fold_positive_count(pf_df: pd.DataFrame) -> int:
    if pf_df.empty or "calmar" not in pf_df.columns:
        return 0
    return int((pf_df["calmar"].dropna() > 0).sum())


def _binomial_pvalue(positives: int, total: int, p_null: float = 0.5) -> float:
    from scipy.stats import binom
    if total == 0:
        return float("nan")
    return float(1 - binom.cdf(positives - 1, total, p_null))


# ---------------------------------------------------------------------------
# Helpers — trial registry
# ---------------------------------------------------------------------------

def _record_to_registry(
    strategy_id: str,
    sharpe: float,
    code_version: str,
    trial_group: str,
    featureset_hash: str | None,
) -> None:
    registry_path = _registry_path(RUNS_ROOT)
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "config_hash": hashlib.md5(strategy_id.encode()).hexdigest()[:8],
        "sharpe": sharpe if math.isfinite(sharpe) else None,
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
# Helpers — featureset hash
# ---------------------------------------------------------------------------

def _featureset_hash() -> str | None:
    feat_dir = DATA_ROOT / "features"
    manifests = list(feat_dir.glob("6E_backadjusted_5m_features_base-v1_*.manifest.json"))
    if not manifests:
        return None
    m = json.loads(manifests[0].read_text(encoding="utf-8"))
    return m.get("hash") or m.get("featureset_hash")


# ---------------------------------------------------------------------------
# Helpers — aggregated metrics from trades
# ---------------------------------------------------------------------------

def _agg_metrics_from_trades(trades: pd.DataFrame) -> dict:
    """Compute summary metrics from a trade DataFrame."""
    if trades.empty:
        return {}
    from trading_research.backtest.engine import BacktestConfig, BacktestResult
    from trading_research.eval.summary import compute_summary
    cfg = BacktestConfig(strategy_id="tmp", symbol="6E")
    dummy_eq = trades.sort_values("exit_ts").set_index("exit_ts")["net_pnl_usd"].cumsum()
    result = BacktestResult(trades=trades, equity_curve=dummy_eq, config=cfg, symbol_meta={})
    return compute_summary(result)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _equity_chart_b64(trades_dict: dict) -> str:
    import base64
    import io
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = {"v1 (realistic)": "#999999", "v2 realistic": "#1f77b4", "v2 pessimistic": "#d62728"}
    for label, trades in trades_dict.items():
        if trades is None or (hasattr(trades, "empty") and trades.empty):
            continue
        eq = trades.sort_values("exit_ts")["net_pnl_usd"].cumsum()
        eq.index = range(len(eq))
        ax.plot(eq.values, label=label, color=colors.get(label, "gray"), linewidth=1.5)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Aggregated Equity Curves — Session 33 Walk-Forward (2018–2024)")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative P&L (USD)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


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


def _fold_table_html(pf_df: pd.DataFrame, label: str) -> str:
    if pf_df.empty:
        return f"<p>{label}: no fold data</p>"
    cols = ["fold", "test_start", "test_end", "trades", "calmar", "sharpe", "win_rate", "stationarity_class"]
    available = [c for c in cols if c in pf_df.columns]
    rows_html = ""
    for _, row in pf_df[available].iterrows():
        cells = ""
        for col in available:
            v = row[col]
            try:
                if col in ("calmar", "sharpe", "win_rate"):
                    fmt = f"{float(v):.3f}"
                elif col == "stationarity_class":
                    fmt = str(v)
                else:
                    fmt = str(v)
            except (ValueError, TypeError):
                fmt = str(v)
            bg = ""
            if col == "calmar":
                try:
                    bg = " style='background:#d4f4d4'" if float(v) > 0 else " style='background:#f4d4d4'"
                except (TypeError, ValueError):
                    pass
            cells += f"<td{bg}>{fmt}</td>"
        rows_html += f"<tr>{cells}</tr>"
    th = "".join(f"<th>{c}</th>" for c in available)
    return f"""
    <h3>{label}</h3>
    <table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>
      <thead><tr>{th}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>"""


def _side_by_side_html(v1: dict, v2: dict, v2_cis: dict) -> str:
    """v1 vs v2 comparison table per spec (strict improvement test)."""
    rows = []
    metrics = [
        ("calmar", "Calmar", ".3f"),
        ("sharpe", "Sharpe", ".3f"),
        ("win_rate", "Win Rate", ".1%"),
        ("max_consec_losses", "Max Consec. Losses", ".0f"),
        ("trades_per_week", "Trades/Week", ".2f"),
        ("max_drawdown_usd", "Max Drawdown (USD)", ",.0f"),
    ]
    for key, label, fmt in metrics:
        v1_val = v1.get(key)
        v2_val = v2.get(key)
        v1_ci = v1.get(f"{key}_ci")
        v2_ci = v2_cis.get(f"{key}_ci")

        v1_str = _fmt(v1_val, fmt) if v1_val is not None else "N/A"
        v1_ci_str = f"[{v1_ci[0]:{fmt}}, {v1_ci[1]:{fmt}}]" if v1_ci else "N/A"
        v2_str = _fmt(v2_val, fmt) if v2_val is not None else "N/A"
        v2_ci_str = (
            f"[{v2_ci[0]:{fmt}}, {v2_ci[1]:{fmt}}]"
            if v2_ci and not any(math.isnan(x) for x in v2_ci)
            else "N/A"
        )

        # Δ = v2 − v1
        delta_str = "N/A"
        improved_str = "N/A"
        try:
            delta = float(v2_val) - float(v1_val)
            delta_str = _fmt(delta, fmt)
            # "Significant" = v2 CI lower bound > v1 point estimate (strict per spec)
            if v2_ci and not any(math.isnan(x) for x in v2_ci):
                improved_str = "YES" if v2_ci[0] > float(v1_val) else "no"
            else:
                improved_str = "CI unavailable"
        except (TypeError, ValueError):
            pass

        row_style = " style='background:#ffffd4'" if improved_str == "YES" else ""
        rows.append(
            f"<tr{row_style}><td>{label}</td>"
            f"<td>{v1_str}</td><td>{v1_ci_str}</td>"
            f"<td>{v2_str}</td><td>{v2_ci_str}</td>"
            f"<td>{delta_str}</td><td>{improved_str}</td></tr>"
        )

    return f"""
    <h2>Side-by-Side: v1 (sprint 30 run #4 realistic) vs v2 (realistic)</h2>
    <p><em>Strict improvement: "YES" only if v2 CI lower bound &gt; v1 point estimate.</em></p>
    <table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>
      <thead><tr>
        <th>Metric</th>
        <th>v1 value</th><th>v1 CI</th>
        <th>v2 value</th><th>v2 95% CI</th>
        <th>&Delta; (v2&minus;v1)</th><th>Improved?</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>"""


def _make_report(
    v2_real_pf: pd.DataFrame,
    v2_pess_pf: pd.DataFrame,
    v2_real_metrics: dict,
    v2_pess_metrics: dict,
    v2_real_cis: dict,
    v2_pess_cis: dict,
    v2_real_mcl: dict,
    v1_ref: dict,
    v2_real_trades: pd.DataFrame,
    v2_pess_trades: pd.DataFrame,
    dsr: float,
    code_version: str,
    run_dir: Path,
) -> str:
    n_real = len(v2_real_pf.dropna(subset=["calmar"])) if not v2_real_pf.empty else 0
    n_pess = len(v2_pess_pf.dropna(subset=["calmar"])) if not v2_pess_pf.empty else 0
    pos_real = _fold_positive_count(v2_real_pf)
    pos_pess = _fold_positive_count(v2_pess_pf)
    binom_p = _binomial_pvalue(pos_real, n_real) if n_real > 0 else float("nan")

    # Stationarity consistency check (G5)
    stat_classes = []
    if "stationarity_class" in v2_real_pf.columns:
        stat_classes = v2_real_pf["stationarity_class"].dropna().tolist()
    unique_classes = list(set(stat_classes))
    stat_consistent = len(unique_classes) <= 1 and bool(unique_classes)
    stat_label = ", ".join(unique_classes) if unique_classes else "N/A"

    equity_img = _equity_chart_b64({
        "v2 realistic": v2_real_trades,
        "v2 pessimistic": v2_pess_trades,
    })

    css = """
    body { font-family: monospace; margin: 24px; background: #fafafa; }
    h1 { color: #222; } h2 { color: #444; border-bottom: 1px solid #ccc; }
    table { border-collapse: collapse; margin-bottom: 20px; }
    td, th { padding: 5px 10px; border: 1px solid #ccc; }
    th { background: #f0f0f0; font-weight: bold; }
    .pass { color: #1a7a1a; font-weight: bold; }
    .fail { color: #c00; font-weight: bold; }
    .warn { color: #a56000; }
    """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset='utf-8'>
<title>Session 33a — v2 Walk-Forward Report</title>
<style>{css}</style></head>
<body>
<h1>Session 33a — vwap-reversion-v1 v2 Walk-Forward Report</h1>
<p><b>Run date:</b> {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><b>Git SHA:</b> {code_version}</p>
<p><b>Strategy:</b> vwap-reversion-v1 + VolatilityRegimeFilter(P75) + Mulligan scale-in</p>
<p><b>Walk-forward:</b> {TRAIN_MONTHS}m train / {TEST_MONTHS}m test / {EMBARGO_BARS}-bar embargo / rolling</p>
<p><b>Bootstrap:</b> n={BOOTSTRAP_N}, seed={BOOTSTRAP_SEED}</p>
<p><b>Cohort DSR n_trials:</b> {COHORT_N_TRIALS}</p>

<h2>Equity Curves</h2>
<img src='data:image/png;base64,{equity_img}' style='max-width:100%'>

<h2>v2 Aggregated Metrics — Realistic (2.0 tick, $4.20/RT)</h2>
<table>
  <tr><th>Metric</th><th>Value</th><th>95% CI</th></tr>
  <tr><td>Calmar [headline]</td><td>{_fmt(v2_real_metrics.get('calmar'))}</td><td>{_ci_str(v2_real_cis,'calmar')}</td></tr>
  <tr><td>Sharpe</td><td>{_fmt(v2_real_metrics.get('sharpe'))}</td><td>{_ci_str(v2_real_cis,'sharpe')}</td></tr>
  <tr><td>Win Rate</td><td>{_fmt(v2_real_metrics.get('win_rate'),'.1%')}</td><td></td></tr>
  <tr><td>Total Trades</td><td>{v2_real_metrics.get('total_trades','N/A')}</td><td></td></tr>
  <tr><td>Trades/Week</td><td>{_fmt(v2_real_metrics.get('trades_per_week'))}</td><td></td></tr>
  <tr><td>Max Consec. Losses (point)</td><td>{v2_real_metrics.get('max_consec_losses','N/A')}</td><td></td></tr>
  <tr><td>Max Consec. Losses (boot p50)</td><td>{_fmt(v2_real_mcl.get('p50'),'.0f')}</td><td></td></tr>
  <tr><td>Max Consec. Losses (boot p95)</td><td>{_fmt(v2_real_mcl.get('p95'),'.0f')}</td><td></td></tr>
  <tr><td>Max Drawdown (USD)</td><td>{_fmt(v2_real_metrics.get('max_drawdown_usd'),',.0f')}</td><td></td></tr>
  <tr><td>Drawdown Duration (days)</td><td>{v2_real_metrics.get('drawdown_duration_days','N/A')}</td><td></td></tr>
</table>

<h2>v2 Fold Counts — Realistic</h2>
<table>
  <tr><th>Total Folds</th><td>{n_real}</td></tr>
  <tr><th>Positive Folds (Calmar &gt; 0)</th><td>{pos_real}/{n_real}</td></tr>
  <tr><th>Binomial p-value (vs p=0.5)</th><td>{_fmt(binom_p,'.4f')}</td></tr>
</table>

<h2>Stationarity (G5) — Realistic, per fold</h2>
<p>Unique classifications: <b>{stat_label}</b> —
{'<span class="pass">CONSISTENT</span>' if stat_consistent else '<span class="fail">INCONSISTENT — possible regime-fitting</span>'}</p>

<h2>Cohort DSR (G3)</h2>
<p>DSR (n_trials={COHORT_N_TRIALS}): <b>{_fmt(dsr,'.4f')}</b></p>
<p><em>DSR CI: not separately bootstrapped here; point estimate is the gate input.
DSR &gt; 0.95 required for G3 PASS.</em></p>

<h2>Pessimistic Cost (2.0-tick/3.0-tick, $4.20/RT) — Sprint 30 run #6 equiv.</h2>
<table>
  <tr><th>Metric</th><th>Pessimistic</th><th>95% CI</th></tr>
  <tr><td>Calmar</td><td>{_fmt(v2_pess_metrics.get('calmar'))}</td><td>{_ci_str(v2_pess_cis,'calmar')}</td></tr>
  <tr><td>Sharpe</td><td>{_fmt(v2_pess_metrics.get('sharpe'))}</td><td>{_ci_str(v2_pess_cis,'sharpe')}</td></tr>
  <tr><td>Folds positive</td><td>{pos_pess}/{n_pess}</td><td></td></tr>
  <tr><td>Total trades</td><td>{v2_pess_metrics.get('total_trades','N/A')}</td><td></td></tr>
</table>

{_side_by_side_html(
    {"calmar": v1_ref.get("calmar"), "calmar_ci": v1_ref.get("calmar_ci"),
     "sharpe": v1_ref.get("sharpe"), "sharpe_ci": v1_ref.get("sharpe_ci"),
     "win_rate": v1_ref.get("win_rate"),
     "max_consec_losses": v1_ref.get("max_consec_losses"),
     "trades_per_week": v1_ref.get("trades_per_week"),
     "max_drawdown_usd": v1_ref.get("max_drawdown_usd")},
    v2_real_metrics,
    v2_real_cis,
)}

{_fold_table_html(v2_real_pf, "Realistic — Per-Fold Metrics")}
{_fold_table_html(v2_pess_pf, "Pessimistic — Per-Fold Metrics")}

<h2>Notes</h2>
<p>v2 adds VolatilityRegimeFilter(P75 ATR, pre-committed sprint 31a) + Mulligan scale-in
(exit_rules emits scale_in on second VWAP deviation; engine validates M-1/M-2/M-3).
v1 reference = sprint 30 run #4 realistic (s1.0-o2.0-c4.20, contiguous-segmentation,
code version 2e87e7e). Mixed evaluation methodology noted; G7 addressed in gate review.</p>
</body></html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("session_33a.start")

    code_version = _get_code_version()
    run_hash = hashlib.md5(f"33a-v2-{code_version}".encode()).hexdigest()[:8]
    run_dir = RUNS_ROOT / f"vwap-reversion-v1-6E-v2-{run_hash}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("run_dir", path=str(run_dir))

    feat_hash = _featureset_hash()
    log.info("featureset_hash", hash_=feat_hash)

    # Load full bars for stationarity slicing
    from trading_research.replay.data import _find_parquet
    feat_dir = DATA_ROOT / "features"
    feat_path = _find_parquet(feat_dir, "6E_backadjusted_5m_features_base-v1_*.parquet")
    all_bars = pd.read_parquet(feat_path, engine="pyarrow")
    all_bars = all_bars.set_index("timestamp_utc")
    all_bars.index = pd.DatetimeIndex(all_bars.index, tz="UTC")
    all_bars = all_bars.sort_index()
    all_bars = all_bars[
        (all_bars.index >= pd.Timestamp("2018-01-01", tz="UTC"))
        & (all_bars.index <= pd.Timestamp("2024-12-31", tz="UTC"))
    ]
    log.info("bars_loaded", n=len(all_bars))

    # Core instrument for stationarity
    from trading_research.core.instruments import InstrumentRegistry
    core_registry = InstrumentRegistry()
    core_inst = core_registry.get("6E")

    # --- Realistic walk-forward ---
    log.info("running_v2_realistic", slippage=REALISTIC_SLIPPAGE)
    wf_real = run_rolling_walkforward(
        config_path=V2_CONFIG,
        train_months=TRAIN_MONTHS,
        test_months=TEST_MONTHS,
        embargo_bars=EMBARGO_BARS,
        data_root=DATA_ROOT,
        slippage_ticks=REALISTIC_SLIPPAGE,
        commission_rt_usd=COMMISSION_RT,
    )

    # --- Pessimistic walk-forward ---
    log.info("running_v2_pessimistic", slippage=PESSIMISTIC_SLIPPAGE)
    wf_pess = run_rolling_walkforward(
        config_path=V2_CONFIG,
        train_months=TRAIN_MONTHS,
        test_months=TEST_MONTHS,
        embargo_bars=EMBARGO_BARS,
        data_root=DATA_ROOT,
        slippage_ticks=PESSIMISTIC_SLIPPAGE,
        commission_rt_usd=COMMISSION_RT,
    )

    # --- Per-fold stationarity ---
    log.info("computing_stationarity")
    pf_real = _add_stationarity_to_folds(wf_real.per_fold_metrics, all_bars, core_inst)
    pf_pess = _add_stationarity_to_folds(wf_pess.per_fold_metrics, all_bars, core_inst)

    # --- Aggregated metrics ---
    v2_real_metrics = _agg_metrics_from_trades(wf_real.aggregated_trades)
    v2_pess_metrics = _agg_metrics_from_trades(wf_pess.aggregated_trades)
    # Merge wf.aggregated_metrics (has more fields like total_trades, trades_per_week)
    v2_real_metrics.update(wf_real.aggregated_metrics)
    v2_pess_metrics.update(wf_pess.aggregated_metrics)

    # --- Bootstrap CIs ---
    log.info("computing_bootstrap_cis")
    v2_real_cis = _compute_cis(wf_real.aggregated_trades)
    v2_pess_cis = _compute_cis(wf_pess.aggregated_trades)

    # --- Max-consecutive-losses bootstrap ---
    log.info("bootstrapping_max_consec_losses")
    v2_real_mcl = _bootstrap_max_consec_losses(wf_real.aggregated_trades)

    # --- Cohort DSR ---
    log.info("computing_dsr", n_trials=COHORT_N_TRIALS)
    dsr = _compute_cohort_dsr(wf_real.aggregated_trades, COHORT_N_TRIALS)
    log.info("dsr_result", dsr=dsr)

    # --- Load v1 reference (sprint 30 run #4) ---
    v1_ref: dict = {}
    if V1_TRIAL_JSON.exists():
        v1_data = json.loads(V1_TRIAL_JSON.read_text(encoding="utf-8"))
        # run #4 (0-indexed) = s1.0-o2.0-c4.20
        for v in v1_data.get("variants", []):
            if v.get("label") == "s1.0-o2.0-c4.20":
                v1_ref = v
                break
    log.info("v1_ref_loaded", label=v1_ref.get("label", "NOT FOUND"))

    # --- Save artifacts ---
    pf_real.to_parquet(run_dir / "per-fold-metrics-realistic.parquet", engine="pyarrow", index=False)
    pf_pess.to_parquet(run_dir / "per-fold-metrics-pessimistic.parquet", engine="pyarrow", index=False)
    if not wf_real.aggregated_trades.empty:
        wf_real.aggregated_trades.to_parquet(run_dir / "aggregated-trades-realistic.parquet", engine="pyarrow", index=False)
    if not wf_pess.aggregated_trades.empty:
        wf_pess.aggregated_trades.to_parquet(run_dir / "aggregated-trades-pessimistic.parquet", engine="pyarrow", index=False)

    # --- Fold count + stationarity summary ---
    n_real = len(pf_real.dropna(subset=["calmar"])) if not pf_real.empty else 0
    n_pess = len(pf_pess.dropna(subset=["calmar"])) if not pf_pess.empty else 0
    pos_real = _fold_positive_count(pf_real)
    pos_pess = _fold_positive_count(pf_pess)
    binom_p = _binomial_pvalue(pos_real, n_real) if n_real > 0 else float("nan")

    stat_classes = pf_real["stationarity_class"].tolist() if "stationarity_class" in pf_real.columns else []
    unique_stat = list(set(stat_classes))
    stat_consistent = len(unique_stat) <= 1 and bool(unique_stat)

    calmar_real = wf_real.aggregated_metrics.get("calmar", float("nan"))
    calmar_pess = wf_pess.aggregated_metrics.get("calmar", float("nan"))

    def _safe(v: object) -> object:
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v

    # --- Trial JSON ---
    trial_data = {
        "strategy_id": "vwap-reversion-v1-6E-v2",
        "sprint": "33a",
        "git_sha": code_version,
        "run_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "walk_forward": {
            "train_months": TRAIN_MONTHS,
            "test_months": TEST_MONTHS,
            "embargo_bars": EMBARGO_BARS,
        },
        "v2_spec": {
            "regime_filter": "VolatilityRegimeFilter(P75 ATR)",
            "mulligan": "scale_in on second VWAP deviation (M-1/M-2/M-3)",
        },
        "v1_reference": {
            "sprint": "30",
            "label": v1_ref.get("label", "s1.0-o2.0-c4.20"),
            "calmar": _safe(v1_ref.get("calmar")),
            "calmar_ci": [_safe(x) for x in v1_ref.get("calmar_ci", [None, None])],
            "sharpe": _safe(v1_ref.get("sharpe")),
        },
        "v2_realistic": {
            "slippage_ticks": REALISTIC_SLIPPAGE,
            "commission_rt": COMMISSION_RT,
            "n_folds": n_real,
            "positive_folds": pos_real,
            "binom_p_value": _safe(binom_p),
            "calmar": _safe(calmar_real),
            "calmar_ci": [_safe(x) for x in v2_real_cis.get("calmar_ci", [None, None])],
            "sharpe": _safe(wf_real.aggregated_metrics.get("sharpe")),
            "sharpe_ci": [_safe(x) for x in v2_real_cis.get("sharpe_ci", [None, None])],
            "win_rate": _safe(wf_real.aggregated_metrics.get("win_rate")),
            "total_trades": wf_real.aggregated_metrics.get("total_trades"),
            "max_consec_losses_point": wf_real.aggregated_metrics.get("max_consec_losses"),
            "max_consec_losses_p95": _safe(v2_real_mcl.get("p95")),
            "max_drawdown_usd": _safe(wf_real.aggregated_metrics.get("max_drawdown_usd")),
            "drawdown_duration_days": wf_real.aggregated_metrics.get("drawdown_duration_days"),
            "trades_per_week": _safe(wf_real.aggregated_metrics.get("trades_per_week")),
        },
        "v2_pessimistic": {
            "slippage_ticks": PESSIMISTIC_SLIPPAGE,
            "commission_rt": COMMISSION_RT,
            "n_folds": n_pess,
            "positive_folds": pos_pess,
            "calmar": _safe(calmar_pess),
            "calmar_ci": [_safe(x) for x in v2_pess_cis.get("calmar_ci", [None, None])],
            "sharpe": _safe(wf_pess.aggregated_metrics.get("sharpe")),
            "total_trades": wf_pess.aggregated_metrics.get("total_trades"),
        },
        "cohort_dsr": {
            "n_trials": COHORT_N_TRIALS,
            "dsr": _safe(dsr),
        },
        "stationarity_g5": {
            "per_fold_classes": stat_classes,
            "unique_classes": unique_stat,
            "consistent": stat_consistent,
        },
        "featureset_hash": feat_hash,
        "code_version": code_version,
    }

    trial_path = run_dir / "trial.json"
    trial_path.write_text(json.dumps(trial_data, indent=2), encoding="utf-8")
    log.info("trial_json_written", path=str(trial_path))

    # --- HTML report ---
    html = _make_report(
        v2_real_pf=pf_real,
        v2_pess_pf=pf_pess,
        v2_real_metrics=wf_real.aggregated_metrics,
        v2_pess_metrics=wf_pess.aggregated_metrics,
        v2_real_cis=v2_real_cis,
        v2_pess_cis=v2_pess_cis,
        v2_real_mcl=v2_real_mcl,
        v1_ref=v1_ref,
        v2_real_trades=wf_real.aggregated_trades,
        v2_pess_trades=wf_pess.aggregated_trades,
        dsr=dsr,
        code_version=code_version,
        run_dir=run_dir,
    )
    html_path = run_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("report_written", path=str(html_path))

    # --- Record trials ---
    real_sharpe = wf_real.aggregated_metrics.get("sharpe") or float("nan")
    pess_sharpe = wf_pess.aggregated_metrics.get("sharpe") or float("nan")
    _record_to_registry("vwap-reversion-v1-6E-v2-realistic", float(real_sharpe), code_version, "session-33a", feat_hash)
    _record_to_registry("vwap-reversion-v1-6E-v2-pessimistic", float(pess_sharpe), code_version, "session-33a", feat_hash)

    # --- Console summary ---
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  Session 33a — v2 Walk-Forward Results  (git {code_version})")
    print(sep)
    print("\n  REALISTIC  (2.0 tick, $4.20/RT)")
    print(f"    Folds positive: {pos_real}/{n_real}   binom_p={binom_p:.4f}")
    print(f"    Calmar:         {_safe(calmar_real)}")
    print(f"    Calmar CI 95%:  {v2_real_cis.get('calmar_ci')}")
    print(f"    Sharpe:         {_safe(wf_real.aggregated_metrics.get('sharpe'))}")
    print(f"    Trades:         {wf_real.aggregated_metrics.get('total_trades')}")
    print(f"    Max CL (point): {wf_real.aggregated_metrics.get('max_consec_losses')}")
    print(f"    Max CL (p95):   {v2_real_mcl.get('p95')}")
    print(f"    Stationarity:   {stat_classes}")
    print("\n  PESSIMISTIC (3.0 tick, $4.20/RT)")
    print(f"    Folds positive: {pos_pess}/{n_pess}")
    print(f"    Calmar:         {_safe(calmar_pess)}")
    print(f"    Sharpe:         {_safe(wf_pess.aggregated_metrics.get('sharpe'))}")
    print(f"\n  COHORT DSR  n_trials={COHORT_N_TRIALS}: {_safe(dsr)}")
    print("\n  V1 reference (sprint 30 #4):")
    print(f"    Calmar: {v1_ref.get('calmar')}   CI: {v1_ref.get('calmar_ci')}")
    print(f"\n  Artifacts: {run_dir}")
    print(f"  Report:    {html_path}")
    print(f"{sep}\n")

    return trial_data


if __name__ == "__main__":
    main()
