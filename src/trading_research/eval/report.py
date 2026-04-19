"""HTML report generator for a single backtest run.

Public API
----------
    generate_report(run_dir: Path) -> Path

Reads trades.parquet, equity_curve.parquet, and summary.json from *run_dir*,
locates the matching 5m features parquet, joins market context, and renders
a self-contained HTML report with 15 sections.

The report is written to ``run_dir/report.html`` and a data dictionary
to ``run_dir/data_dictionary.md``.  Both paths are returned as a
namedtuple-compatible tuple.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from importlib.resources import files as pkg_files
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from jinja2 import Environment, FileSystemLoader

from trading_research.data.instruments import load_instrument
from trading_research.eval.context import join_entry_context
from trading_research.eval.data_dictionary import generate_data_dictionary
from trading_research.eval.stats import (
    bootstrap_metric,
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    mar_ratio,
    ulcer_index,
    ulcer_performance_index,
    recovery_factor,
    pain_ratio,
    tail_ratio,
    omega_ratio,
    gain_to_pain_ratio,
)
from trading_research.eval.distribution import (
    return_distribution_stats,
    qq_plot_data,
    autocorrelation_data,
)
from trading_research.eval.drawdowns import catalog_drawdowns, time_underwater
from trading_research.eval.subperiod import subperiod_analysis
from trading_research.eval.monte_carlo import shuffle_trade_order
from trading_research.eval.trials import count_trials

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

_DATA_ROOT = Path(__file__).parents[3] / "data"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

_DARK_BG = "#0f172a"
_CARD_BG = "#1e293b"
_TEXT = "#e2e8f0"
_MUTED = "#64748b"
_GREEN = "#22c55e"
_RED = "#ef4444"
_YELLOW = "#eab308"
_BLUE = "#3b82f6"
_PURPLE = "#a855f7"


class ReportPaths(NamedTuple):
    report: Path
    data_dictionary: Path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_report(run_dir: Path, version: str = "v2") -> ReportPaths:
    """Generate a self-contained HTML report for a backtest run.

    Parameters
    ----------
    run_dir:
        Directory containing trades.parquet, equity_curve.parquet,
        and summary.json (e.g. ``runs/zn-macd-pullback-v1/2026-04-15-04-53``).

    Returns
    -------
    ReportPaths namedtuple with .report and .data_dictionary Path objects.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    trades_path = run_dir / "trades.parquet"
    equity_path = run_dir / "equity_curve.parquet"
    summary_path = run_dir / "summary.json"

    for p in (trades_path, equity_path, summary_path):
        if not p.is_file():
            raise FileNotFoundError(f"Required run file not found: {p}")

    # --- Load run data ---
    trades_raw = pd.read_parquet(trades_path, engine="pyarrow")
    for col in ("entry_ts", "exit_ts", "entry_trigger_ts", "exit_trigger_ts"):
        if col in trades_raw.columns:
            trades_raw[col] = pd.to_datetime(trades_raw[col], utc=True)

    equity_raw = pd.read_parquet(equity_path, engine="pyarrow")
    equity_raw["exit_ts"] = pd.to_datetime(equity_raw["exit_ts"], utc=True)
    equity_series = equity_raw.set_index("exit_ts")["equity_usd"]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # Detect strategy and symbol from trades
    strategy_id = trades_raw["strategy_id"].iloc[0] if "strategy_id" in trades_raw.columns else "unknown"
    symbol = trades_raw["symbol"].iloc[0] if "symbol" in trades_raw.columns else "ZN"

    # --- Load instrument ---
    try:
        inst = load_instrument(symbol)
    except KeyError:
        inst = None

    dollar_per_point = inst.point_value_usd if inst else 1000.0

    # --- Load features and join context ---
    feat_dir = _DATA_ROOT / "features"
    feat_pattern = f"{symbol}_backadjusted_5m_features_base-v1_*.parquet"
    feat_files = sorted(feat_dir.glob(feat_pattern))
    features = None
    if feat_files:
        features = pd.read_parquet(feat_files[-1], engine="pyarrow")
        features = features.set_index("timestamp_utc")
        features.index = pd.DatetimeIndex(features.index, tz="UTC")

    if features is not None:
        trades = join_entry_context(trades_raw, features)
    else:
        trades = trades_raw.copy()

    # --- Derive computed columns ---
    trades = _add_derived_columns(trades, dollar_per_point)

    # --- Metadata ---
    run_ts = run_dir.name
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(run_dir.parents[2]),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        git_sha = "unknown"

    feature_set_ver = "base-v1"
    date_range_str = (
        f"{trades['entry_ts'].min().date()} → {trades['exit_ts'].max().date()}"
        if not trades.empty else "N/A"
    )

    meta = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "run_id": run_dir.parent.name,
        "run_ts": run_ts,
        "git_sha": git_sha,
        "feature_set": feature_set_ver,
        "date_range": date_range_str,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "cost_per_trade_usd": (
            inst.backtest_defaults.slippage_ticks * inst.tick_value_usd * 2
            + inst.backtest_defaults.commission_usd * 2
            if inst else "N/A"
        ),
    }

    # --- Build sections ---
    sections = {}

    # Whether we have plotly loaded yet (inline first, cdn rest)
    plotly_loaded = [False]

    def _fig_to_html(fig: go.Figure) -> str:
        if not plotly_loaded[0]:
            plotly_loaded[0] = True
            return fig.to_html(include_plotlyjs="inline", full_html=False,
                               config={"displayModeBar": False, "responsive": True})
        return fig.to_html(include_plotlyjs=False, full_html=False,
                           config={"displayModeBar": False, "responsive": True})

    sections["s1_meta"] = meta
    sections["s2_metrics"] = _compute_headline_metrics(summary, trades)

    sections["s3_equity_html"] = _fig_to_html(_build_equity_chart(equity_series))
    sections["s4_top20_html"] = _build_top20_tables(trades)
    sections["s5_time_html"] = _fig_to_html(_build_time_in_trade(trades))
    sections["s6_exit_table"] = _build_exit_reason_table(trades)
    sections["s7_r_html"] = _fig_to_html(_build_r_distribution(trades))
    sections["s8_mae_mfe_html"] = _fig_to_html(_build_mae_mfe(trades))
    sections["s8_giveback_html"] = _build_giveback_table(trades)
    sections["s9_rolling_html"] = _fig_to_html(_build_rolling_expectancy(trades))
    sections["s10_streak_html"] = _fig_to_html(_build_streak_distribution(trades))
    sections["s11_heatmap_html"] = _fig_to_html(_build_heatmaps(trades))
    sections["s12_calendar_html"] = _build_calendar_tables(trades)
    sections["s13_cost_html"] = _fig_to_html(_build_cost_sensitivity(trades, dollar_per_point, inst))
    sections["s14_context_html"] = _fig_to_html(_build_market_context(trades))
    sections["s15_provenance"] = _build_provenance(meta, summary_path)

    # --- V2 sections (Risk Officer's view) ---
    if version == "v2":
        net_pnl = trades["net_pnl_usd"].values if not trades.empty else np.array([])

        # CIs — read from summary.json if available, else compute.
        ci_data = summary.get("confidence_intervals", {})

        # S16: CI-augmented headline metrics.
        sections["s16_ci_metrics"] = _build_ci_metrics(summary, ci_data)

        # S17: Deflated Sharpe / PSR.
        sections["s17_dsr"] = _build_dsr_section(
            summary, net_pnl, run_dir, trades
        )

        # S18: Extended risk metrics.
        sections["s18_risk"] = _build_extended_risk(equity_series, net_pnl)

        # S19: Drawdown forensics.
        sections["s19_drawdowns"] = _build_dd_forensics(equity_series, trades)

        # S20: Time underwater.
        sections["s20_underwater"] = _build_underwater_section(equity_series, _fig_to_html)

        # S21: Return distribution.
        sections["s21_distribution"] = _build_distribution_section(net_pnl, trades, _fig_to_html)

        # S22: Subperiod stability.
        sections["s22_subperiod"] = _build_subperiod_section(trades, equity_series, _fig_to_html)

        # S23: Monte Carlo.
        sections["s23_mc"] = _build_monte_carlo_section(trades, _fig_to_html)

        # S24: Walk-forward (loaded from files if they exist).
        sections["s24_wf"] = _build_walkforward_section(run_dir, _fig_to_html)

    # --- Render template ---

    if version == "v3":
        # Copy V2 sections first so they are available in V3
        net_pnl = trades["net_pnl_usd"].values if not trades.empty else np.array([])
        ci_data = summary.get("confidence_intervals", {})
        sections["s16_ci_metrics"] = _build_ci_metrics(summary, ci_data)
        sections["s17_dsr"] = _build_dsr_section(summary, net_pnl, run_dir, trades)
        sections["s18_risk"] = _build_extended_risk(equity_series, net_pnl)
        sections["s19_drawdowns"] = _build_dd_forensics(equity_series, trades)
        sections["s20_underwater"] = _build_underwater_section(equity_series, _fig_to_html)
        sections["s21_distribution"] = _build_distribution_section(net_pnl, trades, _fig_to_html)
        sections["s22_subperiod"] = _build_subperiod_section(trades, equity_series, _fig_to_html)
        sections["s23_mc"] = _build_monte_carlo_section(trades, _fig_to_html)
        sections["s24_wf"] = _build_walkforward_section(run_dir, _fig_to_html)

        import yaml
        from trading_research.eval.regimes import tag_regimes
        from trading_research.eval.regime_metrics import breakdown_by_regime
        from trading_research.eval.classifier import train_winner_classifier
        from trading_research.eval.shap_analysis import compute_shap_per_trade
        from trading_research.eval.meta_label import evaluate_meta_labeling
        from trading_research.eval.event_study import event_study
        from trading_research.eval.clustering import cluster_trades

        try:
            with open("configs/calendars/fomc_dates.yaml") as f:
                fomc_dates = yaml.safe_load(f)["fomc_dates"]
        except Exception:
            fomc_dates = []
            
        tagged_trades = tag_regimes(trades, fomc_dates)
        
        def _tbl(dict_list):
            if not dict_list: return "<p>No data</p>"
            df = pd.DataFrame(dict_list)
            for c in ["total_pnl", "avg_pnl"]:
                if c in df: df[c] = df[c].map(lambda x: f"${x:,.0f}")
            for c in ["win_rate", "calmar", "sharpe", "trades_per_week"]:
                if c in df: df[c] = df[c].map(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
            return df.to_html(index=False, classes="report-table", border=0)

        def _regime_section(regime_col, title):
            data = breakdown_by_regime(tagged_trades, regime_col)
            html = _tbl(data)
            if data:
                df = pd.DataFrame(data)
                fig = go.Figure(go.Bar(x=df["cluster"] if "cluster" in df else df["regime"], y=df["total_pnl"]))
                fig.update_layout(title=f"{title} - Total PnL", template="plotly_dark", height=300)
                html += _fig_to_html(fig)
            return {"html": html}

        sections["s25_regime_vol"] = _regime_section("vol_regime", "Volatility Regime")
        sections["s26_regime_trend"] = _regime_section("trend_regime", "Trend Regime")
        sections["s27_regime_fomc"] = _regime_section("fomc_regime", "FOMC Cycle")
        
        cls_res = train_winner_classifier(tagged_trades)
        if "error" not in cls_res:
            imp_df = cls_res["permutation_importance"]
            fig_imp = go.Figure(go.Bar(
                x=imp_df["importance"], 
                y=imp_df["feature"], 
                orientation="h",
                error_x=dict(type='data', array=imp_df.get('importance_ci', None))
            ))
            fig_imp.update_layout(title="Permutation Importance (with 95% CI)", template="plotly_dark", height=400)
            sections["s30_importance_html"] = _fig_to_html(fig_imp)
            
            pdp_data = cls_res.get("pdp_data", {})
            if pdp_data:
                from plotly.subplots import make_subplots
                valid_feats = [f for f in pdp_data.keys() if "error" not in pdp_data[f]]
                if valid_feats:
                    fig_pdp = make_subplots(rows=1, cols=len(valid_feats), subplot_titles=valid_feats)
                    for i, feat in enumerate(valid_feats):
                        fig_pdp.add_trace(go.Scatter(
                            x=pdp_data[feat]["values"],
                            y=pdp_data[feat]["average"],
                            mode="lines"
                        ), row=1, col=i+1)
                    fig_pdp.update_layout(title="Partial Dependence Plots (Top 5)", template="plotly_dark", height=300, showlegend=False)
                    sections["s31_pdp_html"] = _fig_to_html(fig_pdp)
                else:
                    sections["s31_pdp_html"] = "<p>No valid PDP data.</p>"
            else:
                sections["s31_pdp_html"] = ""
            
            X_train = cls_res["X_train"]
            shap_df = compute_shap_per_trade(cls_res["model"], X_train)
            
            enriched = tagged_trades.loc[X_train.index].copy()
            enriched = pd.concat([enriched, shap_df], axis=1)
            
            scols = ["entry_ts", "net_pnl_usd", "shap_top_pos_1", "shap_top_pos_2", "shap_top_neg_1", "shap_top_neg_2"]
            av_cols = [c for c in scols if c in enriched.columns]
            
            w = enriched.sort_values("net_pnl_usd", ascending=False).head(20)[av_cols]
            l = enriched.sort_values("net_pnl_usd", ascending=True).head(20)[av_cols]
            sections["s32_shap_winners_html"] = w.to_html(index=False, classes="report-table", border=0)
            sections["s32_shap_losers_html"] = l.to_html(index=False, classes="report-table", border=0)
            
            meta_res = evaluate_meta_labeling(tagged_trades, X_train.index, cls_res["oof_preds"])
            if "error" not in meta_res:
                df_meta = meta_res["sweep_data"]
                fig_meta = go.Figure()
                fig_meta.add_trace(go.Scatter(
                    x=df_meta["threshold"], y=df_meta["calmar"],
                    mode="lines+markers", name="Calmar", yaxis="y1",
                ))
                if "precision" in df_meta.columns:
                    fig_meta.add_trace(go.Scatter(
                        x=df_meta["threshold"], y=df_meta["precision"],
                        mode="lines+markers", name="Precision", yaxis="y2",
                    ))
                    fig_meta.add_trace(go.Scatter(
                        x=df_meta["threshold"], y=df_meta["recall"],
                        mode="lines+markers", name="Recall", yaxis="y2",
                    ))
                    fig_meta.add_trace(go.Scatter(
                        x=df_meta["threshold"], y=df_meta["f1"],
                        mode="lines+markers", name="F1", yaxis="y2",
                    ))
                fig_meta.update_layout(
                    title="Meta-Labeling: Threshold vs Calmar / Precision / Recall / F1",
                    template="plotly_dark",
                    height=350,
                    yaxis={"title": "Calmar"},
                    yaxis2={"title": "Precision / Recall / F1", "overlaying": "y", "side": "right", "range": [0, 1]},
                    legend={"orientation": "h"},
                )
                sections["s33_meta_label"] = {
                    "interpretation": meta_res["interpretation"],
                    "html": _fig_to_html(fig_meta)
                }
            else:
                sections["s33_meta_label"] = {"interpretation": "", "html": ""}
                
            clust_res = cluster_trades(tagged_trades, X_train)
            if "error" not in clust_res:
                html_clust = _tbl(clust_res["summary"])
                if "umap_x" in clust_res:
                    df_umap = pd.DataFrame({
                        "x": clust_res["umap_x"],
                        "y": clust_res["umap_y"],
                        "cluster": [str(lbl) for lbl in clust_res["labels"]]
                    })
                    fig_umap = px.scatter(df_umap, x="x", y="y", color="cluster", title="UMAP Trade Clusters")
                    fig_umap.update_layout(template="plotly_dark", height=400)
                    html_clust += _fig_to_html(fig_umap)
                sections["s35_clustering"] = {"html": html_clust}
            else:
                sections["s35_clustering"] = {"html": ""}
        else:
            sections["s30_importance_html"] = "<p>Not enough data to train classifier.</p>"
            sections["s31_pdp_html"] = ""
            sections["s32_shap_winners_html"] = ""
            sections["s32_shap_losers_html"] = ""
            sections["s33_meta_label"] = {"interpretation": "", "html": ""}
            sections["s35_clustering"] = {"html": ""}
            
        ev_res = event_study(tagged_trades, fomc_dates)
        if "error" not in ev_res:
            fig_ev = go.Figure(go.Scatter(x=ev_res["curve_x"], y=ev_res["curve_y"], mode="lines"))
            fig_ev.update_layout(title="Average Cumulative PnL around FOMC", template="plotly_dark", height=300)
            sections["s34_event_fomc_html"] = _fig_to_html(fig_ev)
        else:
            sections["s34_event_fomc_html"] = "<p>Event study error</p>"

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=False,
    )
    template_name = f"report_{version}.html.j2"
    template = env.get_template(template_name)
    html_out = template.render(sections=sections, meta=meta)

    report_path = run_dir / "report.html"
    report_path.write_text(html_out, encoding="utf-8")

    dd_path = generate_data_dictionary(run_dir)

    return ReportPaths(report=report_path, data_dictionary=dd_path)


# ---------------------------------------------------------------------------
# Derived columns
# ---------------------------------------------------------------------------

def _add_derived_columns(trades: pd.DataFrame, dollar_per_point: float) -> pd.DataFrame:
    df = trades.copy()

    # Initial risk in USD
    risk_pts = (df["entry_price"] - df["initial_stop"]).abs()
    risk_usd = risk_pts * dollar_per_point
    risk_usd = risk_usd.replace(0, float("nan"))
    df["initial_risk_usd"] = risk_usd

    # R-multiples
    df["pnl_r"] = df["net_pnl_usd"] / risk_usd
    df["mae_r"] = (df["mae_points"].abs() * dollar_per_point) / risk_usd
    df["mfe_r"] = (df["mfe_points"].abs() * dollar_per_point) / risk_usd

    # Hold time
    hold_delta = pd.to_datetime(df["exit_ts"]) - pd.to_datetime(df["entry_ts"])
    df["hold_minutes"] = hold_delta.dt.total_seconds() / 60
    df["hold_bars"] = (df["hold_minutes"] / 5).round().clip(lower=0).astype(int)

    # Outcome
    df["outcome"] = "scratch"
    df.loc[df["net_pnl_usd"] > 0, "outcome"] = "winner"
    df.loc[df["net_pnl_usd"] < 0, "outcome"] = "loser"

    # Day of week / hour in NY
    if "entry_ts" in df.columns:
        entry_ny = pd.to_datetime(df["entry_ts"]).dt.tz_convert("America/New_York")
        df["entry_dow"] = entry_ny.dt.day_name()
        df["entry_hour"] = entry_ny.dt.hour

    return df


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _fmt(v: object, fmt: str = ".2f") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    if isinstance(v, float):
        return f"{v:{fmt}}"
    return str(v)


def _compute_headline_metrics(summary: dict, trades: pd.DataFrame) -> list[dict]:
    """Return list of {label, value, highlight} dicts for the metrics table."""
    n = len(trades)
    win_rate = summary.get("win_rate", float("nan"))
    rows = [
        ("Total trades",          f"{n:,}",                        False),
        ("Win rate",               f"{win_rate:.1%}" if not math.isnan(win_rate) else "N/A", False),
        ("Profit factor",          _fmt(summary.get("profit_factor")),        False),
        ("Expectancy (USD)",       _fmt(summary.get("expectancy_usd"), ".2f"), False),
        ("Expectancy (R)",         _fmt(trades["pnl_r"].mean() if "pnl_r" in trades.columns else float("nan")), False),
        ("Trades / week",          _fmt(summary.get("trades_per_week"), ".1f"), False),
        ("Calmar  [headline]",     _fmt(summary.get("calmar")),              True),
        ("Sharpe (ann.)",          _fmt(summary.get("sharpe")),              False),
        ("Sortino (ann.)",         _fmt(summary.get("sortino")),             False),
        ("Max drawdown (USD)",     _fmt(summary.get("max_drawdown_usd"), ".0f"), False),
        ("Max drawdown (%)",       f"{summary.get('max_drawdown_pct', float('nan')):.1%}" if not math.isnan(summary.get('max_drawdown_pct', float('nan'))) else "N/A", False),
        ("Drawdown duration (d)",  _fmt(summary.get("drawdown_duration_days"), ".0f"), False),
        ("Max consec. losses",     str(summary.get("max_consec_losses", "N/A")), False),
        ("Avg MAE (pts)",          _fmt(summary.get("avg_mae_points")),      False),
        ("Avg MFE (pts)",          _fmt(summary.get("avg_mfe_points")),      False),
    ]
    return [{"label": r[0], "value": r[1], "highlight": r[2]} for r in rows]


def _build_equity_chart(equity: pd.Series) -> go.Figure:
    """Two stacked charts: cumulative P&L + percent drawdown."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.04,
        subplot_titles=["Cumulative Net P&L (USD)", "Drawdown (%)"],
    )

    # Equity
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        mode="lines", line=dict(color=_BLUE, width=1.5),
        name="Equity", fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
        xaxis="x", yaxis="y",
    ), row=1, col=1)

    # Drawdown
    peak = equity.cummax()
    dd_pct = ((equity - peak) / peak.replace(0, float("nan"))) * 100
    fig.add_trace(go.Scatter(
        x=dd_pct.index, y=dd_pct.values,
        mode="lines", line=dict(color=_RED, width=1.2),
        name="Drawdown %", fill="tozeroy",
        fillcolor="rgba(239,68,68,0.1)",
        xaxis="x2", yaxis="y2",
    ), row=2, col=1)

    _apply_dark_theme(fig, height=500)
    return fig


def _build_top20_tables(trades: pd.DataFrame) -> str:
    """Return HTML string with three styled tables."""
    cols = ["entry_ts", "exit_ts", "direction", "entry_price", "exit_price",
            "net_pnl_usd", "pnl_r", "hold_bars", "hold_minutes", "exit_reason",
            "mae_r", "mfe_r"]
    avail = [c for c in cols if c in trades.columns]

    def _tbl(df: pd.DataFrame, title: str) -> str:
        top = df.head(20)[avail].copy()
        # Format timestamps
        for tc in ("entry_ts", "exit_ts"):
            if tc in top.columns:
                top[tc] = pd.to_datetime(top[tc]).dt.strftime("%Y-%m-%d %H:%M")
        for fc in ("entry_price", "exit_price"):
            if fc in top.columns:
                top[fc] = top[fc].map(lambda v: f"{v:.5f}")
        for rc in ("net_pnl_usd",):
            if rc in top.columns:
                top[rc] = top[rc].map(lambda v: f"${v:,.0f}")
        for rc in ("pnl_r", "mae_r", "mfe_r"):
            if rc in top.columns:
                top[rc] = top[rc].map(lambda v: f"{v:.2f}" if pd.notna(v) else "N/A")
        for rc in ("hold_minutes",):
            if rc in top.columns:
                top[rc] = top[rc].map(lambda v: f"{v:.0f}m" if pd.notna(v) else "N/A")
        html_tbl = top.to_html(index=False, classes="report-table", border=0, na_rep="N/A")
        return f"<h3>{title}</h3>{html_tbl}"

    top_winners = trades.sort_values("net_pnl_usd", ascending=False)
    top_losers  = trades.sort_values("net_pnl_usd", ascending=True)
    top_r = trades.sort_values("pnl_r", ascending=False) if "pnl_r" in trades.columns else trades

    return (
        _tbl(top_winners, "Top 20 Winners by Dollar P&L") +
        _tbl(top_losers,  "Top 20 Losers by Dollar P&L") +
        _tbl(top_r,       "Top 20 by R-Multiple")
    )


def _build_time_in_trade(trades: pd.DataFrame) -> go.Figure:
    """Hold-time histograms split by outcome and exit reason."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Hold bars (all)", "Hold bars by outcome",
            "Hold bars by exit reason", "Time to MAE / MFE (bars)",
        ],
        vertical_spacing=0.14,
        horizontal_spacing=0.08,
    )

    # Row 1, Col 1: all hold bars
    if "hold_bars" in trades.columns:
        fig.add_trace(go.Histogram(
            x=trades["hold_bars"].clip(0, 200),
            nbinsx=50, name="All", marker_color=_BLUE,
            xaxis="x", yaxis="y",
        ), row=1, col=1)

        # Row 1, Col 2: by outcome
        for outcome, color in [("winner", _GREEN), ("loser", _RED), ("scratch", _YELLOW)]:
            sub = trades[trades["outcome"] == outcome]["hold_bars"] if "outcome" in trades.columns else pd.Series(dtype=float)
            fig.add_trace(go.Histogram(
                x=sub.clip(0, 200), nbinsx=40, name=outcome.capitalize(),
                marker_color=color, opacity=0.75,
                xaxis="x2", yaxis="y2",
            ), row=1, col=2)

        # Row 2, Col 1: by exit reason
        if "exit_reason" in trades.columns:
            for reason, color in [
                ("signal", _BLUE), ("stop", _RED), ("target", _GREEN), ("EOD", _YELLOW)
            ]:
                sub = trades[trades["exit_reason"] == reason]["hold_bars"]
                fig.add_trace(go.Histogram(
                    x=sub.clip(0, 200), nbinsx=40, name=reason,
                    marker_color=color, opacity=0.75,
                    xaxis="x3", yaxis="y3",
                ), row=2, col=1)

    # Row 2, Col 2: time to MAE / MFE (proxied by hold_bars since we don't
    # track per-bar MAE progression — flag for session 12 enhancement)
    if "mae_r" in trades.columns and "mfe_r" in trades.columns:
        fig.add_trace(go.Histogram(
            x=trades["mae_r"].clip(-5, 0), nbinsx=40, name="MAE R",
            marker_color=_RED, opacity=0.75,
            xaxis="x4", yaxis="y4",
        ), row=2, col=2)
        fig.add_trace(go.Histogram(
            x=trades["mfe_r"].clip(0, 5), nbinsx=40, name="MFE R",
            marker_color=_GREEN, opacity=0.75,
            xaxis="x4", yaxis="y4",
        ), row=2, col=2)

    _apply_dark_theme(fig, height=600)
    return fig


def _build_exit_reason_table(trades: pd.DataFrame) -> list[dict]:
    """Return list of dicts for the exit-reason breakdown table."""
    if "exit_reason" not in trades.columns:
        return []
    rows = []
    for reason in ["signal", "stop", "target", "EOD"]:
        sub = trades[trades["exit_reason"] == reason]
        if sub.empty:
            continue
        wins = (sub["net_pnl_usd"] > 0).sum()
        rows.append({
            "exit_reason": reason,
            "count": len(sub),
            "total_pnl": f"${sub['net_pnl_usd'].sum():,.0f}",
            "avg_pnl": f"${sub['net_pnl_usd'].mean():.0f}",
            "win_rate": f"{wins / len(sub):.1%}",
            "median_hold_bars": f"{sub['hold_bars'].median():.0f}" if "hold_bars" in sub.columns else "N/A",
            "median_mae_r": f"{sub['mae_r'].median():.2f}" if "mae_r" in sub.columns else "N/A",
            "median_mfe_r": f"{sub['mfe_r'].median():.2f}" if "mfe_r" in sub.columns else "N/A",
        })
    return rows


def _build_r_distribution(trades: pd.DataFrame) -> go.Figure:
    if "pnl_r" not in trades.columns:
        return go.Figure()

    r = trades["pnl_r"].dropna().clip(-5, 5)
    expectancy_r = float(r.mean())

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=r, nbinsx=60,
        marker_color=_BLUE, opacity=0.8,
        name="R-multiple",
    ))
    fig.add_vline(x=0, line=dict(color=_MUTED, dash="dash", width=1))
    fig.add_vline(x=expectancy_r, line=dict(color=_YELLOW, dash="dot", width=2),
                  annotation_text=f"E[R] = {expectancy_r:.3f}",
                  annotation_font_color=_YELLOW)

    fig.update_layout(
        title=f"R-Multiple Distribution  |  Expectancy = {expectancy_r:.4f} R",
        xaxis_title="R-multiple",
        yaxis_title="Count",
    )
    _apply_dark_theme(fig, height=400)
    return fig


def _build_mae_mfe(trades: pd.DataFrame) -> go.Figure:
    """MAE and MFE scatter vs final P&L."""
    if "mae_r" not in trades.columns or "pnl_r" not in trades.columns:
        return go.Figure()

    df = trades.dropna(subset=["mae_r", "mfe_r", "pnl_r"])
    colors = df["outcome"].map({"winner": _GREEN, "loser": _RED, "scratch": _YELLOW})

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["MAE_R vs final PnL_R", "MFE_R vs final PnL_R"],
        horizontal_spacing=0.08,
    )

    fig.add_trace(go.Scatter(
        x=df["mae_r"].clip(-5, 0), y=df["pnl_r"].clip(-5, 5),
        mode="markers", marker=dict(color=colors, size=3, opacity=0.4),
        name="MAE scatter",
        xaxis="x", yaxis="y",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["mfe_r"].clip(0, 5), y=df["pnl_r"].clip(-5, 5),
        mode="markers", marker=dict(color=colors, size=3, opacity=0.4),
        name="MFE scatter",
        xaxis="x2", yaxis="y2",
    ), row=1, col=2)

    _apply_dark_theme(fig, height=420)
    return fig


def _build_giveback_table(trades: pd.DataFrame) -> str:
    """Trades where MFE_R > 1.0 but final P&L is a loss (gave back winners)."""
    if "mfe_r" not in trades.columns or "pnl_r" not in trades.columns:
        return "<p>No R-multiple data available.</p>"

    gave_back = trades[(trades["mfe_r"] > 1.0) & (trades["net_pnl_usd"] < 0)].copy()
    if gave_back.empty:
        return "<p>No trades with MFE_R &gt; 1.0 that closed at a loss.</p>"

    cols = ["entry_ts", "exit_ts", "direction", "net_pnl_usd", "pnl_r", "mfe_r", "exit_reason"]
    avail = [c for c in cols if c in gave_back.columns]
    tbl = gave_back.sort_values("mfe_r", ascending=False).head(30)[avail].copy()

    for tc in ("entry_ts", "exit_ts"):
        if tc in tbl.columns:
            tbl[tc] = pd.to_datetime(tbl[tc]).dt.strftime("%Y-%m-%d %H:%M")
    for fc in ("net_pnl_usd",):
        if fc in tbl.columns:
            tbl[fc] = tbl[fc].map(lambda v: f"${v:,.0f}")
    for fc in ("pnl_r", "mfe_r"):
        if fc in tbl.columns:
            tbl[fc] = tbl[fc].map(lambda v: f"{v:.2f}")

    return f"<p><strong>{len(gave_back)}</strong> trades had MFE_R &gt; 1.0 but closed at a loss. Top 30:</p>" + \
        tbl.to_html(index=False, classes="report-table", border=0, na_rep="N/A")


def _build_rolling_expectancy(trades: pd.DataFrame) -> go.Figure:
    """20-, 50-, 100-trade rolling expectancy in R."""
    if "pnl_r" not in trades.columns:
        return go.Figure()

    r = trades["pnl_r"].reset_index(drop=True)
    fig = go.Figure()

    for window, color in [(20, _BLUE), (50, _GREEN), (100, _YELLOW)]:
        rolling = r.rolling(window).mean()
        fig.add_trace(go.Scatter(
            x=list(range(len(rolling))),
            y=rolling.values,
            mode="lines",
            name=f"{window}-trade E[R]",
            line=dict(color=color, width=1.5),
        ))

    fig.add_hline(y=0, line=dict(color=_MUTED, dash="dash", width=1))
    fig.update_layout(
        title="Rolling Expectancy (R-multiples)",
        xaxis_title="Trade #",
        yaxis_title="E[R]",
    )
    _apply_dark_theme(fig, height=380)
    return fig


def _build_streak_distribution(trades: pd.DataFrame) -> go.Figure:
    """Win/loss streak distribution histograms."""
    net = trades["net_pnl_usd"].values
    win_streaks, loss_streaks = _compute_streaks(net)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[f"Win streak distribution (max={max(win_streaks, default=0)})",
                        f"Loss streak distribution (max={max(loss_streaks, default=0)})"],
        horizontal_spacing=0.1,
    )
    if win_streaks:
        fig.add_trace(go.Histogram(
            x=win_streaks, name="Win streaks", marker_color=_GREEN, nbinsx=20,
            xaxis="x", yaxis="y",
        ), row=1, col=1)
    if loss_streaks:
        fig.add_trace(go.Histogram(
            x=loss_streaks, name="Loss streaks", marker_color=_RED, nbinsx=20,
            xaxis="x2", yaxis="y2",
        ), row=1, col=2)

    _apply_dark_theme(fig, height=380)
    return fig


def _compute_streaks(net: np.ndarray) -> tuple[list[int], list[int]]:
    win_streaks: list[int] = []
    loss_streaks: list[int] = []
    cur_win = cur_loss = 0
    for v in net:
        if v > 0:
            cur_win += 1
            if cur_loss > 0:
                loss_streaks.append(cur_loss)
                cur_loss = 0
        else:
            cur_loss += 1
            if cur_win > 0:
                win_streaks.append(cur_win)
                cur_win = 0
    if cur_win > 0:
        win_streaks.append(cur_win)
    if cur_loss > 0:
        loss_streaks.append(cur_loss)
    return win_streaks, loss_streaks


def _build_heatmaps(trades: pd.DataFrame) -> go.Figure:
    """Day-of-week × hour heatmaps for P&L and trade count."""
    if "entry_dow" not in trades.columns or "entry_hour" not in trades.columns:
        return go.Figure()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    hours = list(range(24))

    pnl_pivot = (
        trades.groupby(["entry_dow", "entry_hour"])["net_pnl_usd"]
        .sum()
        .unstack(fill_value=0)
        .reindex(index=days, columns=hours, fill_value=0)
    )
    cnt_pivot = (
        trades.groupby(["entry_dow", "entry_hour"])["net_pnl_usd"]
        .count()
        .unstack(fill_value=0)
        .reindex(index=days, columns=hours, fill_value=0)
    )

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Total P&L by Day × Hour (ET)", "Trade Count by Day × Hour (ET)"],
        horizontal_spacing=0.08,
    )

    fig.add_trace(go.Heatmap(
        z=pnl_pivot.values,
        x=[f"{h:02d}:00" for h in hours],
        y=days,
        colorscale="RdYlGn",
        name="P&L",
        colorbar=dict(x=0.44, thickness=12),
        xaxis="x", yaxis="y",
    ), row=1, col=1)

    fig.add_trace(go.Heatmap(
        z=cnt_pivot.values,
        x=[f"{h:02d}:00" for h in hours],
        y=days,
        colorscale="Blues",
        name="Count",
        colorbar=dict(x=1.0, thickness=12),
        xaxis="x2", yaxis="y2",
    ), row=1, col=2)

    _apply_dark_theme(fig, height=360)
    return fig


def _build_calendar_tables(trades: pd.DataFrame) -> str:
    """Monthly P&L calendar + per-year summary as HTML tables."""
    if trades.empty:
        return "<p>No trades.</p>"

    df = trades.copy()
    df["exit_year"] = pd.to_datetime(df["exit_ts"]).dt.year
    df["exit_month"] = pd.to_datetime(df["exit_ts"]).dt.month

    # Calendar table
    cal = (
        df.groupby(["exit_year", "exit_month"])["net_pnl_usd"]
        .sum()
        .unstack(fill_value=0)
    )
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }
    cal.columns = [month_names.get(c, str(c)) for c in cal.columns]
    cal["Total"] = cal.sum(axis=1)
    cal = cal.reset_index().rename(columns={"exit_year": "Year"})
    # Format dollars
    for col in cal.columns[1:]:
        cal[col] = cal[col].map(lambda v: f"${v:,.0f}")
    cal_html = cal.to_html(index=False, classes="report-table", border=0)

    # Per-year summary
    yr = df.groupby("exit_year").agg(
        trades=("net_pnl_usd", "count"),
        pnl=("net_pnl_usd", "sum"),
        win_rate=("net_pnl_usd", lambda x: (x > 0).mean()),
    ).reset_index().rename(columns={"exit_year": "Year"})
    yr["pnl"] = yr["pnl"].map(lambda v: f"${v:,.0f}")
    yr["win_rate"] = yr["win_rate"].map(lambda v: f"{v:.1%}")
    yr_html = yr.to_html(index=False, classes="report-table", border=0)

    return "<h3>Monthly P&L Calendar</h3>" + cal_html + "<h3>Per-Year Summary</h3>" + yr_html


def _build_cost_sensitivity(
    trades: pd.DataFrame,
    dollar_per_point: float,
    inst,
) -> go.Figure:
    """Re-run P&L at 1×, 2×, 3× cost assumption and overlay equity curves."""
    base_cost = (
        (inst.backtest_defaults.slippage_ticks * inst.tick_value_usd * 2
         + inst.backtest_defaults.commission_usd * 2)
        if inst else 0
    )

    fig = go.Figure()

    for mult, color, name in [(1, _BLUE, "1× cost (baseline)"),
                               (2, _YELLOW, "2× cost"),
                               (3, _RED, "3× cost")]:
        extra_cost = base_cost * (mult - 1)
        adj_net = trades["net_pnl_usd"] - extra_cost
        equity = adj_net.cumsum()
        fig.add_trace(go.Scatter(
            x=list(range(len(equity))), y=equity.values,
            mode="lines", name=name,
            line=dict(color=color, width=1.5),
        ))

    fig.update_layout(
        title=f"Cost Sensitivity (base cost = ${base_cost:.2f}/rt)",
        xaxis_title="Trade #",
        yaxis_title="Cumulative Net P&L (USD)",
    )
    _apply_dark_theme(fig, height=380)
    return fig


def _build_market_context(trades: pd.DataFrame) -> go.Figure:
    """Histograms of ATR pct rank, VWAP distance, HTF bias strength + regime P&L bars."""
    context_cols = ["atr_14_pct_rank_252", "vwap_distance_atr", "htf_bias_strength"]
    available = [c for c in context_cols if c in trades.columns]

    has_regime = "session_regime" in trades.columns

    rows = 2
    cols = max(2, len(available))
    specs = [[{"type": "xy"}] * cols] * rows

    subplot_titles = (
        [c.replace("_", " ").title() for c in available] +
        (["Session Regime P&L"] if has_regime else []) +
        [""] * (rows * cols)
    )[:rows * cols]

    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=subplot_titles,
        vertical_spacing=0.14,
        horizontal_spacing=0.08,
    )

    for i, col in enumerate(available):
        r, c = divmod(i, cols)
        fig.add_trace(go.Histogram(
            x=trades[col].dropna(),
            nbinsx=40, name=col,
            marker_color=_BLUE, opacity=0.8,
        ), row=r + 1, col=c + 1)

    # Regime P&L bar chart
    if has_regime:
        regime_pnl = trades.groupby("session_regime")["net_pnl_usd"].sum().sort_values()
        colors = [_GREEN if v >= 0 else _RED for v in regime_pnl.values]
        regime_row = rows
        regime_col = cols
        fig.add_trace(go.Bar(
            x=regime_pnl.index.tolist(),
            y=regime_pnl.values,
            marker_color=colors,
            name="Regime P&L",
        ), row=regime_row, col=regime_col)

    _apply_dark_theme(fig, height=520)
    return fig


def _build_provenance(meta: dict, summary_path: Path) -> dict:
    """Collect run provenance info for the footer."""
    cfg_path = summary_path.parent.parent.parent / "configs" / "strategies"
    strategy_yaml = ""
    for f in cfg_path.glob("*.yaml"):
        if meta["strategy_id"].replace("-", "_") in f.stem or f.stem in meta["strategy_id"]:
            try:
                strategy_yaml = f.read_text(encoding="utf-8")
            except Exception:
                pass
            break

    return {
        "git_sha": meta.get("git_sha", "unknown"),
        "python_version": meta.get("python_version", "unknown"),
        "feature_set": meta.get("feature_set", "unknown"),
        "strategy_yaml": strategy_yaml or "(config file not found)",
    }


# ---------------------------------------------------------------------------
# Theme helper
# ---------------------------------------------------------------------------

def _apply_dark_theme(fig: go.Figure, height: int = 400) -> None:
    fig.update_layout(
        height=height,
        paper_bgcolor=_DARK_BG,
        plot_bgcolor=_CARD_BG,
        font=dict(color=_TEXT, size=11),
        legend=dict(
            bgcolor="rgba(30,41,59,0.8)",
            bordercolor=_MUTED,
            borderwidth=1,
        ),
        margin=dict(l=60, r=30, t=50, b=40),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(100,116,139,0.2)",
        zerolinecolor="rgba(100,116,139,0.3)",
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(100,116,139,0.2)",
        zerolinecolor="rgba(100,116,139,0.3)",
    )


# ---------------------------------------------------------------------------
# V2 Section builders — Risk Officer's view
# ---------------------------------------------------------------------------

def _build_ci_metrics(summary: dict, ci_data: dict) -> list[dict]:
    """Section 16: headline metrics with bootstrap CI bands."""
    def _ci_str(key: str) -> str:
        ci = ci_data.get(f"{key}_ci")
        if not ci or len(ci) != 2:
            return ""
        lo, hi = ci
        if lo is None or hi is None:
            return ""
        try:
            if math.isnan(float(lo)) or math.isnan(float(hi)):
                return ""
        except (TypeError, ValueError):
            return ""
        return f"[{float(lo):.2f}, {float(hi):.2f}]"

    win_rate = summary.get("win_rate", float("nan"))
    rows = [
        ("Sharpe (ann.)",      _fmt(summary.get("sharpe")),          _ci_str("sharpe"),       False),
        ("Sortino (ann.)",     _fmt(summary.get("sortino")),         _ci_str("sortino"),      False),
        ("Calmar [headline]",  _fmt(summary.get("calmar")),          _ci_str("calmar"),       True),
        ("Win rate",           f"{win_rate:.1%}" if math.isfinite(win_rate) else "N/A",
                                _ci_str("win_rate"),                                           False),
        ("Profit factor",      _fmt(summary.get("profit_factor")),   _ci_str("profit_factor"), False),
        ("Expectancy (USD)",   _fmt(summary.get("expectancy_usd")),  _ci_str("expectancy_usd"), False),
    ]
    return [
        {"label": r[0], "value": r[1], "ci": r[2], "highlight": r[3]}
        for r in rows
    ]


def _build_dsr_section(
    summary: dict,
    net_pnl: np.ndarray,
    run_dir: Path,
    trades: pd.DataFrame,
) -> dict:
    """Section 17: Deflated Sharpe and PSR."""
    from scipy import stats as scipy_stats

    sharpe = summary.get("sharpe", float("nan"))
    n_obs = len(net_pnl)

    # Get trial count from registry.
    runs_root = run_dir.parent.parent
    strategy_id = run_dir.parent.name
    n_trials = count_trials(runs_root=runs_root, strategy_id=strategy_id)

    skew = kurtosis = float("nan")
    if len(net_pnl) >= 4:
        skew = float(scipy_stats.skew(net_pnl[np.isfinite(net_pnl)]))
        kurtosis = float(scipy_stats.kurtosis(net_pnl[np.isfinite(net_pnl)], fisher=False))

    dsr = deflated_sharpe_ratio(
        sharpe=sharpe,
        n_obs=n_obs,
        n_trials=n_trials,
        skewness=skew if math.isfinite(skew) else 0.0,
        kurtosis_pearson=kurtosis if math.isfinite(kurtosis) else 3.0,
    )
    psr_0 = probabilistic_sharpe_ratio(
        sharpe=sharpe,
        n_obs=n_obs,
        skewness=skew if math.isfinite(skew) else 0.0,
        kurtosis_pearson=kurtosis if math.isfinite(kurtosis) else 3.0,
        sr_benchmark=0.0,
    )
    psr_1 = probabilistic_sharpe_ratio(
        sharpe=sharpe,
        n_obs=n_obs,
        skewness=skew if math.isfinite(skew) else 0.0,
        kurtosis_pearson=kurtosis if math.isfinite(kurtosis) else 3.0,
        sr_benchmark=1.0,
    )

    return {
        "raw_sharpe": _fmt(sharpe),
        "n_trials": n_trials,
        "n_obs": n_obs,
        "skewness": _fmt(skew),
        "kurtosis": _fmt(kurtosis),
        "dsr": _fmt(dsr),
        "psr_vs_0": f"{psr_0:.1%}" if math.isfinite(psr_0) else "N/A",
        "psr_vs_1": f"{psr_1:.1%}" if math.isfinite(psr_1) else "N/A",
        "interpretation": _dsr_interpretation(dsr),
    }


def _dsr_interpretation(dsr: float) -> str:
    if not math.isfinite(dsr):
        return "Insufficient data to compute."
    if dsr > 0.95:
        return f"DSR = {dsr:.1%}: Strong evidence of edge after adjusting for {{}}-trial bias."
    if dsr > 0.80:
        return f"DSR = {dsr:.1%}: Moderate evidence — likely real edge, but not conclusive."
    if dsr > 0.50:
        return f"DSR = {dsr:.1%}: Weak evidence — edge is statistically questionable after multiple-testing correction."
    return f"DSR = {dsr:.1%}: No meaningful evidence of edge — result is consistent with noise."


def _build_extended_risk(equity: pd.Series, net_pnl: np.ndarray) -> list[dict]:
    """Section 18: MAR, UI, UPI, Recovery Factor, Pain Ratio, Tail Ratio, Omega, GtP."""
    rows = []

    def _r(label: str, value: object, note: str = "") -> None:
        rows.append({"label": label, "value": _fmt(value), "note": note})

    _r("MAR Ratio",         mar_ratio(equity),                      "CAGR / |max DD|")
    _r("Ulcer Index",       ulcer_index(equity),                    "RMS of % drawdowns — lower is better")
    _r("Ulcer Perf. Index", ulcer_performance_index(equity),        "(CAGR - rf) / UI — higher is better")
    _r("Recovery Factor",   recovery_factor(equity),                "Net profit / |max DD|")
    _r("Pain Ratio",        pain_ratio(equity),                     "CAGR / avg DD%")

    fin = net_pnl[np.isfinite(net_pnl)] if len(net_pnl) > 0 else np.array([])
    _r("Tail Ratio (95/5)", tail_ratio(fin),                        "|p95| / |p5| — >1 means fat right tail")
    _r("Omega Ratio",       omega_ratio(fin, threshold=0.0),        "Gain probability mass / loss probability mass")

    # Monthly returns from daily P&L groupby.
    monthly = _monthly_returns_from_pnl(net_pnl, equity)
    _r("Gain-to-Pain",      gain_to_pain_ratio(monthly),            "Sum(+months) / |Sum(-months)|")

    return rows


def _monthly_returns_from_pnl(net_pnl: np.ndarray, equity: pd.Series) -> np.ndarray:
    """Aggregate equity curve into monthly P&L."""
    if equity.empty:
        return np.array([])
    try:
        monthly = equity.resample("ME").last().diff()
        return monthly.dropna().values
    except Exception:
        return np.array([])


def _build_dd_forensics(equity: pd.Series, trades: pd.DataFrame) -> dict:
    """Section 19: drawdown catalog table."""
    dd_df = catalog_drawdowns(equity, trades=trades if not trades.empty else None, threshold_pct=0.01)

    if dd_df.empty:
        return {"html": "<p>No drawdowns exceeding 1% found.</p>", "count": 0}

    display = dd_df.copy()
    for col in ("start_date", "trough_date", "recovery_date"):
        if col in display.columns:
            display[col] = pd.to_datetime(display[col]).dt.strftime("%Y-%m-%d").fillna("N/A") if col == "recovery_date" else pd.to_datetime(display[col]).dt.strftime("%Y-%m-%d")

    if "recovery_date" in display.columns:
        display["recovery_date"] = display["recovery_date"].fillna("unrecovered")

    for col in ("depth_usd",):
        if col in display.columns:
            display[col] = display[col].map(lambda v: f"${v:,.0f}")
    if "depth_pct" in display.columns:
        display["depth_pct"] = display["depth_pct"].map(lambda v: f"{v:.1%}")

    html = display.to_html(index=False, classes="report-table", border=0, na_rep="N/A")
    return {"html": html, "count": len(dd_df)}


def _build_underwater_section(equity: pd.Series, fig_to_html) -> dict:
    """Section 20: time underwater histogram and summary."""
    result = time_underwater(equity)

    pct = result["pct_time_underwater"]
    longest_days = result["longest_run_days"]
    runs = result["run_lengths"]

    # Histogram of underwater run lengths.
    fig = go.Figure()
    if runs:
        fig.add_trace(go.Histogram(
            x=runs,
            nbinsx=min(50, len(runs)),
            marker_color=_RED,
            opacity=0.8,
            name="Underwater run (bars)",
        ))
    fig.update_layout(
        title="Underwater Run Lengths (bars)",
        xaxis_title="Run length (bars)",
        yaxis_title="Count",
    )
    _apply_dark_theme(fig, height=350)

    return {
        "pct_str": f"{pct:.1%}" if math.isfinite(pct) else "N/A",
        "longest_days": longest_days,
        "n_runs": len(runs),
        "chart_html": fig_to_html(fig),
    }


def _build_distribution_section(net_pnl: np.ndarray, trades: pd.DataFrame, fig_to_html) -> dict:
    """Section 21: return distribution diagnostics."""
    fin = net_pnl[np.isfinite(net_pnl)] if len(net_pnl) > 0 else np.array([])
    stats_dict = return_distribution_stats(fin)

    # QQ plot.
    qq = qq_plot_data(fin)
    qq_fig = go.Figure()
    if len(qq["theoretical_quantiles"]) > 0:
        qq_fig.add_trace(go.Scatter(
            x=qq["theoretical_quantiles"], y=qq["sample_quantiles"],
            mode="markers", marker=dict(color=_BLUE, size=3, opacity=0.4),
            name="Observed",
        ))
        qq_fig.add_trace(go.Scatter(
            x=qq["fit_line_x"], y=qq["fit_line_y"],
            mode="lines", line=dict(color=_YELLOW, dash="dash"),
            name="Normal reference",
        ))
    qq_fig.update_layout(title="Q-Q Plot vs Normal", xaxis_title="Theoretical", yaxis_title="Sample")
    _apply_dark_theme(qq_fig, height=380)

    # ACF of trade-level returns.
    acf_data = autocorrelation_data(fin, max_lags=20)
    acf_fig = go.Figure()
    lags = acf_data["lags"]
    acf_vals = acf_data["acf"]
    bounds = acf_data["confidence_bounds"]
    finite_mask = np.isfinite(acf_vals)
    if np.any(finite_mask):
        acf_fig.add_trace(go.Bar(
            x=lags[finite_mask], y=acf_vals[finite_mask],
            marker_color=_BLUE, name="ACF",
        ))
    if math.isfinite(bounds):
        acf_fig.add_hline(y=bounds, line=dict(color=_YELLOW, dash="dot"), annotation_text="95% CI")
        acf_fig.add_hline(y=-bounds, line=dict(color=_YELLOW, dash="dot"))
    acf_fig.add_hline(y=0, line=dict(color=_MUTED, width=1))
    acf_fig.update_layout(title="ACF of Trade Returns (lags 1-20)", xaxis_title="Lag", yaxis_title="Autocorrelation")
    _apply_dark_theme(acf_fig, height=320)

    # Return distribution histogram.
    hist_fig = go.Figure()
    if len(fin) > 0:
        hist_fig.add_trace(go.Histogram(
            x=fin, nbinsx=60, marker_color=_BLUE, opacity=0.8, name="Returns",
        ))
        mean_val = float(np.mean(fin))
        hist_fig.add_vline(x=0, line=dict(color=_MUTED, dash="dash"))
        hist_fig.add_vline(x=mean_val, line=dict(color=_YELLOW, dash="dot"),
                           annotation_text=f"Mean={mean_val:.0f}")
    hist_fig.update_layout(title="Return Distribution", xaxis_title="Net P&L (USD)", yaxis_title="Count")
    _apply_dark_theme(hist_fig, height=320)

    return {
        "stats": stats_dict,
        "normality_flag": stats_dict["normality_flag"],
        "normality_warning": stats_dict["normality_warning"],
        "qq_html": fig_to_html(qq_fig),
        "acf_html": fig_to_html(acf_fig),
        "hist_html": fig_to_html(hist_fig),
        "lb_pvalue": _fmt(acf_data.get("ljung_box_pvalue", float("nan"))),
        "serial_correlation_flag": acf_data.get("serial_correlation_flag", False),
    }


def _build_subperiod_section(trades: pd.DataFrame, equity: pd.Series, fig_to_html) -> dict:
    """Section 22: subperiod stability table and bar chart."""
    result = subperiod_analysis(trades, equity, splits="yearly")
    table_df = result["table"]

    if table_df.empty:
        return {
            "html": "<p>Insufficient data for subperiod analysis.</p>",
            "chart_html": "",
            "degradation_flag": False,
            "degradation_message": "",
        }

    # Format table.
    display = table_df.copy()
    for col in ("win_rate",):
        if col in display.columns:
            display[col] = display[col].map(lambda v: f"{v:.1%}" if math.isfinite(v) else "N/A")
    for col in ("profit_factor", "sharpe", "calmar", "expectancy_usd"):
        if col in display.columns:
            display[col] = display[col].map(lambda v: f"{v:.2f}" if math.isfinite(v) else "N/A")
    if "max_dd_usd" in display.columns:
        display["max_dd_usd"] = display["max_dd_usd"].map(lambda v: f"${v:,.0f}" if math.isfinite(v) else "N/A")

    html = display.to_html(index=False, classes="report-table", border=0)

    # Calmar bar chart by year.
    fig = go.Figure()
    calmar_vals = table_df["calmar"].values.astype(float)
    periods = table_df["period"].values
    colors = [_GREEN if math.isfinite(v) and v > 0 else _RED for v in calmar_vals]
    fig.add_trace(go.Bar(
        x=periods,
        y=[v if math.isfinite(v) else 0 for v in calmar_vals],
        marker_color=colors,
        name="Calmar",
    ))
    fig.add_hline(y=0, line=dict(color=_MUTED, dash="dash"))
    fig.update_layout(title="Calmar Ratio by Year", xaxis_title="Period", yaxis_title="Calmar")
    _apply_dark_theme(fig, height=360)

    return {
        "html": html,
        "chart_html": fig_to_html(fig),
        "degradation_flag": result["degradation_flag"],
        "degradation_message": result["degradation_message"],
    }


def _build_monte_carlo_section(trades: pd.DataFrame, fig_to_html) -> dict:
    """Section 23: Monte Carlo trade-order shuffle."""
    mc = shuffle_trade_order(trades, n_iter=1000, seed=42)

    if mc["n_trades"] == 0:
        return {
            "fan_html": "",
            "dd_hist_html": "",
            "calmar_hist_html": "",
            "actual_dd_pctile": "N/A",
            "actual_calmar_pctile": "N/A",
            "interpretation": "No trades.",
            "n_iter": 0,
        }

    # Fan chart (sample 100 curves from 1000).
    fan_fig = go.Figure()
    n_curves = min(100, mc["n_iter"])
    rng = np.random.default_rng(0)
    sample_idx = rng.choice(mc["n_iter"], size=n_curves, replace=False)
    for idx in sample_idx:
        fan_fig.add_trace(go.Scatter(
            x=list(range(mc["n_trades"])),
            y=mc["equity_curves"][idx],
            mode="lines",
            line=dict(color="rgba(59,130,246,0.06)", width=1),
            showlegend=False,
        ))
    # Actual equity overlay.
    actual_eq = np.cumsum(trades["net_pnl_usd"].values.astype(float))
    fan_fig.add_trace(go.Scatter(
        x=list(range(len(actual_eq))),
        y=actual_eq,
        mode="lines",
        line=dict(color=_YELLOW, width=2),
        name="Actual",
    ))
    fan_fig.update_layout(title="Monte Carlo Equity Fan (1000 shuffles, 100 shown)", xaxis_title="Trade #", yaxis_title="Cumulative P&L (USD)")
    _apply_dark_theme(fan_fig, height=400)

    # Max DD histogram.
    dd_fig = go.Figure()
    dd_fig.add_trace(go.Histogram(
        x=mc["max_dd_dist"], nbinsx=50, marker_color=_RED, opacity=0.8, name="Shuffle max DD",
    ))
    if math.isfinite(mc["actual_max_dd"]):
        dd_fig.add_vline(x=mc["actual_max_dd"], line=dict(color=_YELLOW, dash="dash"),
                          annotation_text=f"Actual ({mc['actual_max_dd_pctile']:.0f}th pctile)")
    dd_fig.update_layout(title="Max Drawdown Distribution (shuffled)", xaxis_title="Max DD (USD)", yaxis_title="Count")
    _apply_dark_theme(dd_fig, height=340)

    # Calmar histogram.
    cal_fig = go.Figure()
    fin_calmar = mc["calmar_dist"][np.isfinite(mc["calmar_dist"])]
    if len(fin_calmar) > 0:
        cal_fig.add_trace(go.Histogram(
            x=fin_calmar, nbinsx=50, marker_color=_BLUE, opacity=0.8, name="Shuffle Calmar",
        ))
    if math.isfinite(mc["actual_calmar"]):
        cal_fig.add_vline(x=mc["actual_calmar"], line=dict(color=_YELLOW, dash="dash"),
                          annotation_text=f"Actual ({mc['actual_calmar_pctile']:.0f}th pctile)")
    cal_fig.update_layout(title="Calmar Distribution (shuffled)", xaxis_title="Calmar", yaxis_title="Count")
    _apply_dark_theme(cal_fig, height=340)

    return {
        "fan_html": fig_to_html(fan_fig),
        "dd_hist_html": fig_to_html(dd_fig),
        "calmar_hist_html": fig_to_html(cal_fig),
        "actual_dd_pctile": f"{mc['actual_max_dd_pctile']:.0f}th" if math.isfinite(mc["actual_max_dd_pctile"]) else "N/A",
        "actual_calmar_pctile": f"{mc['actual_calmar_pctile']:.0f}th" if math.isfinite(mc["actual_calmar_pctile"]) else "N/A",
        "interpretation": mc["interpretation"],
        "n_iter": mc["n_iter"],
    }


def _build_walkforward_section(run_dir: Path, fig_to_html) -> dict:
    """Section 24: Walk-forward results, loaded from parquet if available."""
    wf_path = run_dir / "walkforward.parquet"
    wf_eq_path = run_dir / "walkforward_equity.parquet"

    if not wf_path.exists():
        return {
            "available": False,
            "table_html": "",
            "equity_html": "",
            "aggregated": {},
        }

    try:
        per_fold = pd.read_parquet(wf_path, engine="pyarrow")
        wf_equity = pd.read_parquet(wf_eq_path, engine="pyarrow") if wf_eq_path.exists() else None
    except Exception as e:
        return {"available": False, "table_html": f"<p>Error loading walk-forward data: {e}</p>", "equity_html": "", "aggregated": {}}

    # Format the per-fold table.
    display = per_fold.copy()
    for col in ("test_start", "test_end"):
        if col in display.columns:
            display[col] = pd.to_datetime(display[col]).dt.strftime("%Y-%m-%d")
    for col in ("win_rate",):
        if col in display.columns:
            display[col] = display[col].map(lambda v: f"{v:.1%}" if math.isfinite(float(v if v == v else float('nan'))) else "N/A")
    for col in ("calmar", "sharpe", "expectancy_usd", "profit_factor"):
        if col in display.columns:
            display[col] = display[col].map(lambda v: f"{v:.2f}" if math.isfinite(float(v if v == v else float('nan'))) else "N/A")

    table_html = display.to_html(index=False, classes="report-table", border=0, na_rep="N/A")

    # OOS equity chart.
    equity_html = ""
    if wf_equity is not None and not wf_equity.empty and "equity_usd" in wf_equity.columns:
        eq_ts = pd.to_datetime(wf_equity["exit_ts"])
        eq_vals = wf_equity["equity_usd"].values
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eq_ts, y=eq_vals,
            mode="lines", line=dict(color=_GREEN, width=1.5),
            name="OOS Equity", fill="tozeroy", fillcolor="rgba(34,197,94,0.08)",
        ))
        fig.add_hline(y=0, line=dict(color=_MUTED, dash="dash"))
        fig.update_layout(title="Walk-Forward OOS Equity Curve", xaxis_title="Date", yaxis_title="Cumulative P&L (USD)")
        _apply_dark_theme(fig, height=380)
        equity_html = fig_to_html(fig)

    # Aggregated totals.
    aggregated = {}
    if not per_fold.empty:
        total_trades = int(per_fold["trades"].sum()) if "trades" in per_fold.columns else 0
        aggregated = {
            "n_folds": len(per_fold),
            "total_trades": total_trades,
        }

    return {
        "available": True,
        "table_html": table_html,
        "equity_html": equity_html,
        "aggregated": aggregated,
    }
