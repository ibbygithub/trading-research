"""Session 30a — 6E VWAP Reversion v1 cost-sensitivity sweep.

Runs 8 cost variants against the 6E strategy, records all trials to the
registry, and writes a self-contained HTML report plus Parquet artefacts.

Usage
-----
    uv run python scripts/run_30a_cost_sweep.py

Outputs (all under runs/vwap-reversion-v1-6E-{hash}/)
-----------------------------------------------------
    trial.json                — standalone summary of all 8 variants
    report.html               — single-page cost-sensitivity report
    per-fold-metrics.parquet  — per-fold metrics for all 8 variants
    aggregated-trades.parquet — all trades for all 8 variants
    equity-curves/{label}.parquet

Also updates runs/.trials.json (the persistent registry).
"""

from __future__ import annotations

import base64
import hashlib
import io
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
import scipy.stats
import structlog
import yaml

# ---------------------------------------------------------------------------
# Project root + path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

CONFIG_PATH = PROJECT_ROOT / "configs" / "strategies" / "6e-vwap-reversion-v1.yaml"
RUNS_ROOT = PROJECT_ROOT / "runs"

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Cost matrix — 8 variants
# ---------------------------------------------------------------------------
# For each run, slippage_overlap_ticks is used as the effective per-side
# slippage because all entries happen inside the 12:00–17:00 UTC overlap
# window. This is the conservative/realistic assumption.

COST_VARIANTS = [
    {"label": "s0.5-o0.5-c4.20",  "slippage_quiet": 0.5, "slippage_overlap": 0.5, "commission_rt": 4.20},
    {"label": "s0.5-o1.0-c4.20",  "slippage_quiet": 0.5, "slippage_overlap": 1.0, "commission_rt": 4.20},
    {"label": "s1.0-o1.0-c4.20",  "slippage_quiet": 1.0, "slippage_overlap": 1.0, "commission_rt": 4.20},
    {"label": "s1.0-o2.0-c4.20",  "slippage_quiet": 1.0, "slippage_overlap": 2.0, "commission_rt": 4.20},
    {"label": "s2.0-o2.0-c4.20",  "slippage_quiet": 2.0, "slippage_overlap": 2.0, "commission_rt": 4.20},
    {"label": "s2.0-o3.0-c4.20",  "slippage_quiet": 2.0, "slippage_overlap": 3.0, "commission_rt": 4.20},
    {"label": "s3.0-o3.0-c4.20",  "slippage_quiet": 3.0, "slippage_overlap": 3.0, "commission_rt": 4.20},
    {"label": "s0.5-o0.5-c0.00",  "slippage_quiet": 0.5, "slippage_overlap": 0.5, "commission_rt": 0.00},
]

# Walkforward parameters (fixed for all 8 runs)
N_FOLDS = 4
EMBARGO_BARS = 576    # 2 trading days × 288 bars/day at 5m
GAP_BARS = 0
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260426


def _git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _run_hash(variants: list[dict]) -> str:
    serialised = yaml.dump(variants, sort_keys=True)
    return hashlib.blake2b(serialised.encode(), digest_size=4).hexdigest()


def _featureset_hash() -> str | None:
    feat_dir = PROJECT_ROOT / "data" / "features"
    manifests = list(feat_dir.glob("6E_backadjusted_5m_features_base-v1_*.manifest.json"))
    if not manifests:
        log.warning("No featureset manifest found; featureset_hash will be None")
        return None
    m = json.loads(manifests[0].read_text(encoding="utf-8"))
    return m.get("hash") or m.get("featureset_hash")


def _stationarity_for_fold(fold_bars: pd.DataFrame, core_inst: object) -> dict:
    """Run ADF, OU, Hurst on the vwap_spread series for a fold slice."""
    from trading_research.stats.stationarity import (
        adf_test,
        hurst_exponent,
        ou_half_life,
        _composite_classification,
    )

    # Prefer a pre-computed spread column; fall back to computing close - vwap_session.
    series = None
    for candidate in ("vwap_spread", "vwap_diff", "vwap_spread_5m"):
        if candidate in fold_bars.columns:
            series = fold_bars[candidate].dropna()
            break

    if series is None and "close" in fold_bars.columns and "vwap_session" in fold_bars.columns:
        series = (fold_bars["close"] - fold_bars["vwap_session"]).dropna()

    if series is None or len(series) == 0:
        log.warning("stationarity: cannot compute spread, skipping")
        return {
            "adf_pval": float("nan"),
            "ou_halflife_bars": float("nan"),
            "hurst": float("nan"),
            "stationarity_class": "UNKNOWN",
        }
    if len(series) < 30:
        return {
            "adf_pval": float("nan"),
            "ou_halflife_bars": float("nan"),
            "hurst": float("nan"),
            "stationarity_class": "INSUFFICIENT_DATA",
        }

    try:
        adf_r = adf_test(series, regression="c")
    except Exception as exc:
        log.warning("adf_test failed", exc=str(exc))
        adf_r = None

    hurst_r = hurst_exponent(series)
    ou_r = ou_half_life(series)

    if adf_r is None:
        return {
            "adf_pval": float("nan"),
            "ou_halflife_bars": ou_r.half_life_bars,
            "hurst": hurst_r.exponent,
            "stationarity_class": "ADF_FAILED",
        }

    comp = _composite_classification(adf_r, hurst_r, ou_r, "5m", instrument=core_inst)
    return {
        "adf_pval": adf_r.p_value,
        "ou_halflife_bars": ou_r.half_life_bars,
        "hurst": hurst_r.exponent,
        "stationarity_class": comp,
    }


def _run_variant(
    variant: dict,
    bars: pd.DataFrame,
    core_inst: object,
    git_sha: str,
    featureset_hash: str | None,
) -> dict:
    """Run a single cost variant — returns a dict of all results."""
    from trading_research.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
    from trading_research.backtest.fills import FillModel
    from trading_research.backtest.walkforward import (
        _ensure_template_imported,
        _signals_to_dataframe,
    )
    from trading_research.data.instruments import load_instrument
    from trading_research.eval.bootstrap import bootstrap_summary
    from trading_research.eval.summary import compute_summary
    from trading_research.eval.trials import record_trial

    label = variant["label"]
    slippage = variant["slippage_overlap"]
    commission_rt = variant["commission_rt"]

    log.info("run_variant.start", label=label, slippage=slippage, commission_rt=commission_rt)

    cfg_raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    bt_cfg_raw = cfg_raw.get("backtest", {})
    template_name = cfg_raw["template"]
    knobs = cfg_raw.get("knobs", {})

    fill_model = FillModel(bt_cfg_raw.get("fill_model", "next_bar_open"))
    bt_config = BacktestConfig(
        strategy_id=f"vwap-reversion-v1-6E-{label}",
        symbol=symbol,
        fill_model=fill_model,
        max_holding_bars=bt_cfg_raw.get("max_holding_bars"),
        eod_flat=bt_cfg_raw.get("eod_flat", True),
        use_ofi_resolution=bt_cfg_raw.get("use_ofi_resolution", False),
        quantity=bt_cfg_raw.get("quantity", 1),
        slippage_ticks=slippage,
        commission_rt_usd=commission_rt,
    )

    inst = load_instrument(symbol)

    _ensure_template_imported(template_name)
    from trading_research.core.templates import _GLOBAL_REGISTRY
    strategy = _GLOBAL_REGISTRY.instantiate(template_name, knobs)

    signal_list = strategy.generate_signals(bars, bars, core_inst)
    signals_df = _signals_to_dataframe(signal_list, bars.index)

    log.info("run_variant.signals_generated", label=label, n_signals=len(signal_list))

    # Fold layout (same as run_walkforward)
    total_buffer = GAP_BARS + EMBARGO_BARS
    usable_bars = len(bars) - total_buffer * (N_FOLDS - 1)
    fold_size = usable_bars // N_FOLDS

    all_fold_metrics = []
    all_trades = []
    fold_bars_list = []

    for k in range(N_FOLDS):
        start_idx = k * (fold_size + total_buffer) + EMBARGO_BARS if k > 0 else 0
        end_idx = start_idx + fold_size if k < N_FOLDS - 1 else len(bars)
        end_idx = min(end_idx, len(bars))
        if start_idx >= end_idx:
            continue

        fold_bars = bars.iloc[start_idx:end_idx]
        fold_bars_list.append(fold_bars)

        engine = BacktestEngine(bt_config, inst)
        res = engine.run(fold_bars, signals_df)

        sm = compute_summary(res)
        sm["fold"] = k + 1
        sm["test_start"] = fold_bars.index[0]
        sm["test_bars"] = len(fold_bars)
        sm["trades"] = len(res.trades)
        sm["cost_label"] = label

        # Per-fold stationarity
        stat = _stationarity_for_fold(fold_bars, core_inst)
        sm.update(stat)

        all_fold_metrics.append(sm)
        if not res.trades.empty:
            all_trades.append(res.trades)

    pf_df = pd.DataFrame(all_fold_metrics)

    if all_trades:
        agg_trades = pd.concat(all_trades, ignore_index=True)
        agg_trades = agg_trades.sort_values("exit_ts").reset_index(drop=True)
        agg_trades["cost_label"] = label
        agg_eq = agg_trades.set_index("exit_ts")["net_pnl_usd"].cumsum()

        # Build a minimal BacktestResult for bootstrap
        agg_res = BacktestResult(
            trades=agg_trades,
            equity_curve=agg_eq,
            config=bt_config,
            symbol_meta={},
        )
        agg_metrics = compute_summary(agg_res)
        cis = bootstrap_summary(agg_res, n_samples=BOOTSTRAP_N, seed=BOOTSTRAP_SEED)

        trade_returns = agg_trades["net_pnl_usd"].values.astype(float)
        skew_val = float(scipy.stats.skew(trade_returns)) if len(trade_returns) > 2 else float("nan")
        kurt_val = float(scipy.stats.kurtosis(trade_returns, fisher=False)) if len(trade_returns) > 2 else float("nan")
        n_obs = len(agg_trades)
    else:
        agg_trades = pd.DataFrame()
        agg_eq = pd.Series(dtype=float)
        agg_metrics = {}
        cis = {}
        trade_returns = np.array([])
        skew_val = float("nan")
        kurt_val = float("nan")
        n_obs = 0

    # Record trial
    record_trial(
        runs_root=RUNS_ROOT,
        strategy_id=f"vwap-reversion-v1-6E-{label}",
        config_path=CONFIG_PATH,
        sharpe=agg_metrics.get("sharpe", float("nan")),
        trial_group="v1-cost-sweep",
        featureset_hash=featureset_hash,
        cohort_label=git_sha,
        n_obs=n_obs if n_obs > 0 else None,
        skewness=skew_val if math.isfinite(skew_val) else None,
        kurtosis_pearson=kurt_val if math.isfinite(kurt_val) else None,
    )

    log.info(
        "run_variant.done",
        label=label,
        n_trades=n_obs,
        sharpe=agg_metrics.get("sharpe"),
        calmar=agg_metrics.get("calmar"),
    )

    return {
        "label": label,
        "variant": variant,
        "pf_df": pf_df,
        "agg_trades": agg_trades,
        "agg_eq": agg_eq,
        "agg_metrics": agg_metrics,
        "cis": cis,
        "skew": skew_val,
        "kurt": kurt_val,
        "n_obs": n_obs,
        "fold_bars_list": fold_bars_list,
    }


def _equity_curve_png_b64(results_list: list[dict], label: str) -> str:
    """Return base64-encoded PNG of fold equity curves for one cost variant."""
    target = next((r for r in results_list if r["label"] == label), None)
    if target is None or target["agg_trades"].empty:
        return ""

    colours = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63"]
    fig, ax = plt.subplots(figsize=(8, 3), dpi=80)

    fold_bars_list = target["fold_bars_list"]
    agg_trades = target["agg_trades"]

    for k, fold_bars in enumerate(fold_bars_list):
        fold_start = fold_bars.index[0]
        fold_end = fold_bars.index[-1]
        fold_trades = agg_trades[
            (agg_trades["exit_ts"] >= fold_start) & (agg_trades["exit_ts"] <= fold_end)
        ]
        if fold_trades.empty:
            continue
        eq = fold_trades.set_index("exit_ts")["net_pnl_usd"].cumsum()
        eq = eq - eq.iloc[0]  # normalise to start at 0
        ax.plot(eq.index, eq.values, color=colours[k % len(colours)],
                label=f"Fold {k + 1}", linewidth=1.2)

    ax.axhline(0, color="#999", linewidth=0.5, linestyle="--")
    ax.set_title(f"Fold equity curves — {label}", fontsize=9)
    ax.set_xlabel("Date", fontsize=7)
    ax.set_ylabel("Cumulative P&L (USD)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.legend(fontsize=6)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _fmt(v: object, fmt: str = ".2f") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    if isinstance(v, float):
        return f"{v:{fmt}}"
    return str(v)


def _fmt_ci(ci: tuple | None, fmt: str = ".2f") -> str:
    if ci is None:
        return "N/A"
    lo, hi = ci
    if math.isnan(lo) or math.isnan(hi):
        return "N/A"
    return f"[{lo:{fmt}}, {hi:{fmt}}]"


def _build_html_report(
    results_list: list[dict],
    git_sha: str,
    dsr: float | None,
    run_date: str,
) -> str:
    cfg_raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    bt_cfg = cfg_raw.get("backtest", {})
    start_date = bt_cfg.get("start_date", "—")
    end_date = bt_cfg.get("end_date", "—")

    # --- Stationarity regime flip detection ---
    stationarity_by_fold: list[dict] = []
    all_classes: list[str] = []
    for res in results_list[:1]:  # use first variant; stationarity is data-driven, cost-independent
        for _, row in res["pf_df"].iterrows():
            cls = row.get("stationarity_class", "UNKNOWN")
            stationarity_by_fold.append({
                "fold": int(row["fold"]),
                "adf_pval": row.get("adf_pval"),
                "ou_halflife_bars": row.get("ou_halflife_bars"),
                "hurst": row.get("hurst"),
                "stationarity_class": cls,
            })
            all_classes.append(str(cls))

    majority_class = max(set(all_classes), key=all_classes.count) if all_classes else "UNKNOWN"
    regime_flip = len(set(all_classes) - {"UNKNOWN", "INSUFFICIENT_DATA", "ADF_FAILED"}) > 1

    # --- Bootstrap narrative ---
    run5 = next((r for r in results_list if r["label"] == "s2.0-o2.0-c4.20"), None)
    ci_narrative = ""
    if run5:
        calmar_ci = run5["cis"].get("calmar_ci", (float("nan"), float("nan")))
        sharpe_ci = run5["cis"].get("sharpe_ci", (float("nan"), float("nan")))
        ci_lo, ci_hi = calmar_ci
        calmar_pt = run5["agg_metrics"].get("calmar", float("nan"))
        sharpe_pt = run5["agg_metrics"].get("sharpe", float("nan"))
        if not math.isnan(ci_lo):
            ci_positive = ci_lo > 0
            ci_narrative = (
                f"For the most realistic cost configuration (Run 5: s2.0-o2.0-c4.20), "
                f"the point-estimate Calmar is {_fmt(calmar_pt)} with 90% CI {_fmt_ci(calmar_ci)}. "
                f"{'The lower bound is positive — the strategy shows edge even at the pessimistic end of the CI.' if ci_positive else 'The lower bound includes zero or is negative — the evidence of edge is not conclusive at this cost level.'} "
                f"Sharpe point estimate {_fmt(sharpe_pt)} with 90% CI {_fmt_ci(sharpe_ci)}. "
                f"CI widths reflect a moderate sample size; additional folds or years of data would tighten them."
            )
        else:
            ci_narrative = "Bootstrap CI could not be computed (insufficient trades)."

    # --- HTML ---
    rows_html = ""
    for r in results_list:
        m = r["agg_metrics"]
        cis = r["cis"]
        calmar = m.get("calmar", float("nan"))
        sharpe = m.get("sharpe", float("nan"))
        calmar_ci = cis.get("calmar_ci", (float("nan"), float("nan")))
        sharpe_ci = cis.get("sharpe_ci", (float("nan"), float("nan")))
        win_rate = m.get("win_rate", float("nan"))
        trades_pw = m.get("trades_per_week", float("nan"))
        dd_dur = m.get("drawdown_duration_days", float("nan"))
        max_cl = m.get("max_consec_losses", 0)

        dsr_cell = _fmt(dsr) if dsr is not None else "N/A"

        calmar_str = f"{_fmt(calmar)} {_fmt_ci(calmar_ci)}"
        sharpe_str = f"{_fmt(sharpe)} {_fmt_ci(sharpe_ci)}"
        wr_str = f"{win_rate:.1%}" if not math.isnan(win_rate) else "N/A"

        flag_row = "background:#fff3cd;" if r["label"] == "s0.5-o0.5-c0.00" else ""

        rows_html += f"""
        <tr style="{flag_row}">
          <td style="font-family:monospace">{r['label']}</td>
          <td>{calmar_str}</td>
          <td>{sharpe_str}</td>
          <td>{dsr_cell}</td>
          <td>{wr_str}</td>
          <td>{_fmt(trades_pw)}</td>
          <td>{_fmt(dd_dur, '.0f')} d</td>
          <td>{max_cl}</td>
        </tr>"""

    # Stationarity table
    stat_rows = ""
    for row in stationarity_by_fold:
        flip = row["stationarity_class"] != majority_class
        flag = "⚠️ " if flip else ""
        colour = "color:red;font-weight:bold" if flip else ""
        stat_rows += f"""
        <tr>
          <td>Fold {row['fold']}</td>
          <td>{_fmt(row.get('adf_pval'), '.4f')}</td>
          <td>{_fmt(row.get('ou_halflife_bars'), '.1f')}</td>
          <td>{_fmt(row.get('hurst'), '.3f')}</td>
          <td style="{colour}">{flag}{row['stationarity_class']}</td>
        </tr>"""

    if not stationarity_by_fold:
        stat_rows = "<tr><td colspan='5'>No stationarity data available</td></tr>"

    regime_banner = ""
    if regime_flip:
        regime_banner = """
        <div style="background:#f8d7da;border:1px solid #f5c2c7;padding:8px 12px;
                    margin:12px 0;border-radius:4px;color:#842029">
          <strong>⚠️ Stationarity regime flip detected.</strong>
          Not all folds share the same stationarity classification.
          This suggests the mean-reversion property of the VWAP spread is not stable
          across the full test window. Regime filtering in Sprint 31 is the natural
          response.
        </div>"""

    # Equity curve images (one per variant)
    eq_imgs = ""
    for r in results_list:
        b64 = _equity_curve_png_b64(results_list, r["label"])
        if b64:
            eq_imgs += f"""
            <div style="margin:8px 0">
              <img src="data:image/png;base64,{b64}"
                   style="max-width:100%;border:1px solid #ddd" />
            </div>"""
        else:
            eq_imgs += f"<p><em>{r['label']}: no trades</em></p>"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>6E VWAP Reversion v1 — Cost Sensitivity Report</title>
<style>
  body {{ font-family: sans-serif; font-size: 13px; margin: 24px; color: #333; }}
  h1 {{ font-size: 18px; margin-bottom: 4px; }}
  h2 {{ font-size: 14px; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 8px; text-align: left; vertical-align: top; }}
  th {{ background: #f0f0f0; font-weight: 600; font-size: 12px; }}
  td {{ font-size: 12px; }}
  .meta {{ color: #666; font-size: 11px; margin-bottom: 16px; }}
  .narrative {{ background: #f8f9fa; border-left: 3px solid #0d6efd;
               padding: 8px 12px; margin: 8px 0; font-size: 12px; }}
</style>
</head>
<body>

<h1>6E VWAP Reversion v1 — Cost Sensitivity Report</h1>
<div class="meta">
  <strong>Strategy:</strong> vwap-reversion-v1-6E &nbsp;|&nbsp;
  <strong>Run date:</strong> {run_date} &nbsp;|&nbsp;
  <strong>Git SHA:</strong> {git_sha} &nbsp;|&nbsp;
  <strong>Data window:</strong> {start_date} – {end_date} &nbsp;|&nbsp;
  <strong>Folds:</strong> {N_FOLDS} &nbsp;|&nbsp;
  <strong>Embargo:</strong> {EMBARGO_BARS} bars
</div>

<h2>1. Cost Sensitivity Table</h2>
<p style="font-size:11px;color:#666">
  Calmar and Sharpe: point estimate + 90% bootstrap CI [p5, p95].
  DSR computed within cohort {git_sha} (n_trials=8).
  Run #8 (c0.00) is the theoretical ceiling; runs #5–7 are the realistic floor.
</p>
<table>
  <tr>
    <th>Label</th>
    <th>Calmar (point + 90% CI)</th>
    <th>Sharpe (point + 90% CI)</th>
    <th>DSR (n=8)</th>
    <th>Win Rate</th>
    <th>Trades/Wk</th>
    <th>Max DD Dur.</th>
    <th>Max Consec Losses</th>
  </tr>
  {rows_html}
</table>

<h2>2. Per-Fold Stationarity</h2>
<p style="font-size:11px;color:#666">
  Computed on vwap_spread column of 5m feature data for each fold.
  Majority class: <strong>{majority_class}</strong>.
</p>
{regime_banner}
<table>
  <tr>
    <th>Fold</th>
    <th>ADF p-value</th>
    <th>OU Half-Life (bars)</th>
    <th>Hurst</th>
    <th>Stationarity Class</th>
  </tr>
  {stat_rows}
</table>

<h2>3. Per-Fold Equity Curves</h2>
<p style="font-size:11px;color:#666">
  Each panel shows 4-fold equity curves normalised to start at 0. Colours: F1=blue, F2=orange, F3=green, F4=pink.
</p>
{eq_imgs}

<h2>4. Bootstrap CI Narrative</h2>
<div class="narrative">{ci_narrative}</div>

</body>
</html>"""

    return html


def main() -> None:
    git_sha = _git_sha()
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    feat_hash = _featureset_hash()

    log.info("sweep.start", git_sha=git_sha, n_variants=len(COST_VARIANTS))

    # Load data once, shared across all variants
    from trading_research.core.instruments import InstrumentRegistry
    from trading_research.replay.data import _find_parquet

    cfg_raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    symbol = cfg_raw["symbol"]
    timeframe = cfg_raw.get("timeframe", "5m")
    feature_set = cfg_raw.get("feature_set", "base-v1")
    bt_cfg_raw = cfg_raw.get("backtest", {})
    start_date = bt_cfg_raw.get("start_date")
    end_date = bt_cfg_raw.get("end_date")

    feat_dir = PROJECT_ROOT / "data" / "features"
    feat_path = _find_parquet(
        feat_dir,
        f"{symbol}_backadjusted_{timeframe}_features_{feature_set}_*.parquet",
    )
    bars = pd.read_parquet(feat_path, engine="pyarrow")
    bars = bars.set_index("timestamp_utc")
    bars.index = pd.DatetimeIndex(bars.index, tz="UTC")
    bars = bars.sort_index()
    if start_date:
        bars = bars[bars.index >= pd.Timestamp(start_date, tz="UTC")]
    if end_date:
        bars = bars[bars.index <= pd.Timestamp(end_date, tz="UTC")]

    log.info("data.loaded", n_bars=len(bars), start=str(bars.index[0]), end=str(bars.index[-1]))

    core_inst = InstrumentRegistry().get(symbol)

    # Run all 8 variants
    results_list = []
    for variant in COST_VARIANTS:
        res = _run_variant(variant, bars, core_inst, git_sha, feat_hash)
        results_list.append(res)

    # Compute DSR now that all 8 trials are recorded
    from trading_research.eval.trials import compute_dsr, load_trials

    trials_path = RUNS_ROOT / ".trials.json"
    all_trials = load_trials(trials_path)
    dsr = compute_dsr(all_trials, cohort=git_sha)
    log.info("dsr.computed", dsr=dsr, cohort=git_sha)

    # Build output directory
    run_hash = _run_hash(COST_VARIANTS)
    out_dir = RUNS_ROOT / f"vwap-reversion-v1-6E-{run_hash}"
    out_dir.mkdir(parents=True, exist_ok=True)
    eq_dir = out_dir / "equity-curves"
    eq_dir.mkdir(parents=True, exist_ok=True)

    # trial.json (standalone — not the registry file)
    trial_summary = []
    for r in results_list:
        m = r["agg_metrics"]
        cis = r["cis"]
        trial_summary.append({
            "label": r["label"],
            "variant": r["variant"],
            "n_trades": r["n_obs"],
            "calmar": m.get("calmar"),
            "calmar_ci": list(cis.get("calmar_ci", (None, None))),
            "sharpe": m.get("sharpe"),
            "sharpe_ci": list(cis.get("sharpe_ci", (None, None))),
            "win_rate": m.get("win_rate"),
            "trades_per_week": m.get("trades_per_week"),
            "max_drawdown_usd": m.get("max_drawdown_usd"),
            "drawdown_duration_days": m.get("drawdown_duration_days"),
            "max_consec_losses": m.get("max_consec_losses"),
            "dsr": dsr,
        })

    trial_json = {
        "strategy_id": "vwap-reversion-v1-6E",
        "git_sha": git_sha,
        "run_date": run_date,
        "n_variants": len(COST_VARIANTS),
        "dsr_cohort": dsr,
        "variants": trial_summary,
    }
    (out_dir / "trial.json").write_text(
        json.dumps(trial_json, indent=2, default=str),
        encoding="utf-8",
    )
    log.info("wrote trial.json", path=str(out_dir / "trial.json"))

    # per-fold-metrics.parquet
    all_pf = pd.concat([r["pf_df"] for r in results_list], ignore_index=True)
    all_pf.to_parquet(out_dir / "per-fold-metrics.parquet", engine="pyarrow", index=False)
    log.info("wrote per-fold-metrics.parquet")

    # aggregated-trades.parquet
    non_empty = [r["agg_trades"] for r in results_list if not r["agg_trades"].empty]
    if non_empty:
        all_agg_trades = pd.concat(non_empty, ignore_index=True)
        all_agg_trades.to_parquet(out_dir / "aggregated-trades.parquet", engine="pyarrow", index=False)
        log.info("wrote aggregated-trades.parquet", n_rows=len(all_agg_trades))

    # equity curves
    for r in results_list:
        eq = r["agg_eq"]
        label = r["label"]
        if not eq.empty:
            eq_df = eq.reset_index()
            eq_df.columns = ["exit_ts", "equity_usd"]
            eq_df.to_parquet(eq_dir / f"{label}.parquet", engine="pyarrow", index=False)
    log.info("wrote equity-curve parquets")

    # HTML report
    html = _build_html_report(results_list, git_sha, dsr, run_date)
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    log.info("wrote report.html", path=str(out_dir / "report.html"))

    # Print summary to stdout
    print(f"\n{'='*70}")
    print(f"Session 30a — 6E Cost Sweep Complete")
    print(f"Git SHA:     {git_sha}")
    print(f"Output dir:  {out_dir}")
    print(f"DSR (n=8):   {_fmt(dsr)}")
    print(f"\n{'Label':<22} {'Calmar':>8} {'Sharpe':>8} {'Trades':>7} {'T/Wk':>6}")
    print("-" * 55)
    for r in results_list:
        m = r["agg_metrics"]
        print(
            f"{r['label']:<22} "
            f"{_fmt(m.get('calmar')):>8} "
            f"{_fmt(m.get('sharpe')):>8} "
            f"{r['n_obs']:>7} "
            f"{_fmt(m.get('trades_per_week'), '.1f'):>6}"
        )
    print("=" * 70)
    print(f"Report: {out_dir / 'report.html'}")


if __name__ == "__main__":
    main()
