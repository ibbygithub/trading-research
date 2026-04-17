import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from trading_research.eval.portfolio import Portfolio, load_portfolio
from trading_research.eval.correlation import daily_pnl_correlation, rolling_correlation
from trading_research.eval.portfolio_drawdown import portfolio_drawdown_attribution
from trading_research.eval.sizing import apply_sizing, compare_sizing_methods
from trading_research.eval.kelly import portfolio_kelly
from trading_research.eval.capital import load_broker_margins, return_on_margin

def _fig_to_html(fig: go.Figure) -> str:
    return fig.to_html(include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False, "responsive": True})

def generate_portfolio_report(run_ids: list[str], output_dir: Path):
    run_paths = [Path("runs") / rid for rid in run_ids]
    portfolio = load_portfolio(run_paths)
    
    if len(portfolio.strategies) < 2:
        raise ValueError("Portfolio requires at least 2 valid runs.")
        
    sections = {}
    
    # 1. Meta
    meta = {
        "strategies": list(portfolio.strategies.keys()),
        "sizing_method": "Equal Weight"
    }
    
    # 2. Headline Metrics (Using Equal weight by default)
    eq = portfolio.combined_equity
    if not eq.empty:
        span_years = len(eq) / 252.0 if len(eq) > 0 else 1.0
        final_pnl = eq.iloc[-1]
        max_dd = (eq.cummax() - eq).max()
        calmar = (final_pnl / span_years) / max_dd if max_dd > 0 else np.nan
        
        headline = pd.DataFrame([{
            "Total PnL": f"${final_pnl:,.0f}",
            "Max Drawdown": f"${max_dd:,.0f}",
            "Calmar": f"{calmar:.2f}" if not np.isnan(calmar) else "N/A"
        }])
        sections["s2_headline"] = headline.to_html(index=False, classes="report-table", border=0)
    else:
        sections["s2_headline"] = "<p>No equity curve data</p>"
        
    # 3. Capital Efficiency
    broker_margins = load_broker_margins()
    cap_data = []
    for sid, strat in portfolio.strategies.items():
        rom = return_on_margin(strat.trades, broker_margins, "tradestation")
        cap_data.append({"Strategy": sid, "Return on Margin": f"{rom:.2%}"})
    sections["s3_capital"] = pd.DataFrame(cap_data).to_html(index=False, classes="report-table", border=0)
        
    # 4. Combined Equity
    if not eq.empty:
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(x=eq.index, y=eq.values, mode='lines', name='Portfolio (Equal Weight)', line=dict(width=3, color='#4CAF50')))
        for sid, strat in portfolio.strategies.items():
            fig_eq.add_trace(go.Scatter(x=strat.equity.index, y=strat.equity.values, mode='lines', name=sid, opacity=0.5))
        fig_eq.update_layout(template="plotly_dark", height=400)
        sections["s4_equity"] = _fig_to_html(fig_eq)
    else:
        sections["s4_equity"] = ""

    # 5. Correlation
    corr_res = daily_pnl_correlation(portfolio)
    if "error" not in corr_res:
        pc = corr_res["pearson"].round(2)
        fig_corr = px.imshow(pc, text_auto=True, color_continuous_scale='RdBu_r', aspect='auto', zmin=-1, zmax=1)
        fig_corr.update_layout(template="plotly_dark", height=300)
        sections["s5_corr_pearson"] = _fig_to_html(fig_corr)
        
        roll = rolling_correlation(portfolio)
        fig_roll = go.Figure()
        for pair, s in roll.items():
            fig_roll.add_trace(go.Scatter(x=s.index, y=s.values, mode='lines', name=pair))
        fig_roll.update_layout(template="plotly_dark", height=300, yaxis_range=[-1, 1])
        sections["s6_corr_rolling"] = _fig_to_html(fig_roll)
    else:
        sections["s5_corr_pearson"] = "<p>Error computing correlation</p>"
        sections["s6_corr_rolling"] = ""

    # 7. Drawdown Attribution
    dd_df = portfolio_drawdown_attribution(portfolio)
    if not dd_df.empty:
        sections["s7_dd"] = dd_df.head(5).to_html(index=False, classes="report-table", border=0)
    else:
        sections["s7_dd"] = "<p>No drawdowns found.</p>"
        
    # 8. Sizing
    sizing_res = compare_sizing_methods(portfolio)
    if sizing_res:
        sz_data = []
        fig_sz = go.Figure()
        for m, s in sizing_res.items():
            sz_data.append({
                "Method": m,
                "Final PnL": f"${s['final_pnl']:,.0f}",
                "Max DD": f"${s['max_dd']:,.0f}",
                "Calmar": f"{s['calmar']:.2f}"
            })
            fig_sz.add_trace(go.Scatter(x=s["equity_curve"].index, y=s["equity_curve"].values, mode='lines', name=m))
            
        fig_sz.update_layout(template="plotly_dark", height=400)
        sections["s8_sizing_table"] = pd.DataFrame(sz_data).to_html(index=False, classes="report-table", border=0)
        sections["s8_sizing_chart"] = _fig_to_html(fig_sz)
    else:
        sections["s8_sizing_table"] = ""
        sections["s8_sizing_chart"] = ""

    # 9. Kelly
    kelly_res = portfolio_kelly(portfolio)
    k_data = []
    for sid, k in kelly_res.items():
        if k:
            k_data.append({
                "Strategy": sid,
                "Full Kelly": f"{k['full_kelly']:.4f}",
                "Half Kelly": f"{k['half_kelly']:.4f}",
                "DD Constrained": f"{k['dd_constrained_kelly']:.4f}"
            })
    if k_data:
        sections["s9_kelly"] = pd.DataFrame(k_data).to_html(index=False, classes="report-table", border=0)
    else:
        sections["s9_kelly"] = "<p>Error computing Kelly.</p>"

    # Render
    env = Environment(loader=FileSystemLoader("src/trading_research/eval/templates"), autoescape=False)
    template = env.get_template("portfolio_report.html.j2")
    html_out = template.render(sections=sections, meta=meta)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "portfolio_report.html"
    report_path.write_text(html_out, encoding="utf-8")
    
    # Write Data Dictionary
    from trading_research.eval.data_dictionary_portfolio import get_portfolio_dictionary
    import json
    dd_path = output_dir / "data_dictionary.json"
    with open(dd_path, "w") as f:
        json.dump(get_portfolio_dictionary(), f, indent=2)
        
    return report_path
