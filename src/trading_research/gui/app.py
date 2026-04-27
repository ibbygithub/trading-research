from dash import Dash, html, dcc
from trading_research.gui.callbacks import register_callbacks

app = Dash(__name__, title="Quant Strategy Builder")

app.layout = html.Div(
    style={"fontFamily": "Inter, sans-serif", "backgroundColor": "#121212", "color": "#e0e0e0", "padding": "20px", "minHeight": "100vh"},
    children=[
        html.H1("Quant Strategy Builder", style={"borderBottom": "1px solid #333", "paddingBottom": "10px"}),
        html.Div(
            style={"display": "flex", "flexDirection": "row", "gap": "20px"},
            children=[
                # Sidebar Controls
                html.Div(
                    style={"flex": "0 0 350px", "backgroundColor": "#1e1e1e", "padding": "20px", "borderRadius": "8px"},
                    children=[
                        html.H3("Configuration", style={"marginTop": 0}),
                        
                        html.Label("Symbol"),
                        dcc.Dropdown(
                            id="input-symbol",
                            options=[{"label": "6E", "value": "6E"}, {"label": "6A", "value": "6A"}],
                            value="6E",
                            style={"color": "#000", "marginBottom": "15px"}
                        ),
                        
                        html.Label("Timeframe"),
                        dcc.Dropdown(
                            id="input-timeframe",
                            options=[{"label": "5m", "value": "5m"}, {"label": "15m", "value": "15m"}, {"label": "1h", "value": "1h"}],
                            value="5m",
                            style={"color": "#000", "marginBottom": "15px"}
                        ),
                        
                        html.Label("Feature Set"),
                        dcc.Dropdown(
                            id="input-features",
                            options=[{"label": "Base v1", "value": "base-v1"}, {"label": "Momentum v2", "value": "mom-v2"}],
                            value="base-v1",
                            style={"color": "#000", "marginBottom": "15px"}
                        ),
                        
                        html.Label("Date Range"),
                        html.Div(
                            dcc.DatePickerRange(
                                id="input-date-range",
                                min_date_allowed="2010-01-01",
                                max_date_allowed="2026-12-31",
                                start_date="2023-01-01",
                                end_date="2023-12-31",
                                style={"width": "100%"}
                            ),
                            style={"marginBottom": "15px", "color": "#000"}
                        ),

                        html.Label("Signal Module"),
                        dcc.Dropdown(
                            id="input-signal-module",
                            options=[
                                {"label": "ZN MACD Pullback", "value": "trading_research.strategies.zn_macd_pullback"}
                            ],
                            value="trading_research.strategies.zn_macd_pullback",
                            style={"color": "#000", "marginBottom": "15px"}
                        ),

                        html.Label("Max Holding Bars"),
                        dcc.Input(
                            id="input-max-holding",
                            type="number",
                            value=100,
                            style={"width": "100%", "padding": "8px", "marginBottom": "20px", "boxSizing": "border-box", "color": "#000", "backgroundColor": "#fff"}
                        ),
                        
                        html.Button(
                            "Run Backtest", 
                            id="btn-run", 
                            n_clicks=0,
                            style={"width": "100%", "padding": "12px", "backgroundColor": "#4CAF50", "color": "white", "border": "none", "borderRadius": "4px", "cursor": "pointer", "fontWeight": "bold"}
                        ),
                        
                        html.Div(id="run-status", style={"marginTop": "15px", "color": "#aaa", "fontSize": "14px"})
                    ]
                ),
                
                # Main Content Area
                html.Div(
                    style={"flex": "1", "backgroundColor": "#1e1e1e", "padding": "20px", "borderRadius": "8px", "display": "flex", "flexDirection": "column"},
                    children=[
                        html.H3("Evaluation Report", style={"marginTop": 0}),
                        dcc.Loading(
                            id="loading-report",
                            type="circle",
                            color="#4CAF50",
                            children=[
                                html.Iframe(
                                    id="report-iframe",
                                    srcDoc="<div style='color: white; font-family: sans-serif; text-align: center; margin-top: 50px;'>Run a backtest to view report.</div>",
                                    style={"width": "100%", "height": "800px", "border": "none", "backgroundColor": "#121212", "borderRadius": "4px"}
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)

register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
