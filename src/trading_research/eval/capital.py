import pandas as pd
import yaml
from pathlib import Path

def load_broker_margins(path: Path = Path("configs/broker_margins.yaml")) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f)

def return_on_margin(trades: pd.DataFrame, broker_margins: dict, broker: str = "tradestation") -> float:
    """Net profit divided by peak margin used."""
    if trades.empty or broker not in broker_margins:
        return 0.0
        
    net_profit = trades["net_pnl_usd"].sum()
    
    # Simple peak margin: max contracts open at once * initial margin.
    # For now, we assume 1 contract per trade.
    symbol = trades["symbol"].iloc[0] if "symbol" in trades.columns else None
    if symbol not in broker_margins[broker]:
        return 0.0
        
    margin_req = broker_margins[broker][symbol].get("overnight_initial", 0)
    if margin_req == 0:
        return 0.0
        
    # Assume peak margin is just margin_req * max holding. Since we only trade 1 contract per strategy in this demo,
    # peak margin is just margin_req.
    peak_margin = margin_req
    return net_profit / peak_margin

def return_on_peak_capital(trades: pd.DataFrame, starting_capital: float = 100000.0) -> float:
    """Net profit divided by the largest equity peak reached."""
    if trades.empty:
        return 0.0
    eq = trades["net_pnl_usd"].cumsum() + starting_capital
    peak_cap = eq.max()
    net_profit = trades["net_pnl_usd"].sum()
    return net_profit / peak_cap

def return_on_max_dd(equity_series: pd.Series) -> float:
    """Net profit divided by max dollar drawdown."""
    if equity_series.empty:
        return 0.0
    net_profit = equity_series.iloc[-1]
    running_max = equity_series.cummax()
    dd = running_max - equity_series
    max_dd = dd.max()
    if max_dd <= 0:
        return float("inf")
    return net_profit / max_dd

def margin_penalty_ratio(symbol: str, theoretical_margin: float, broker_margins: dict, broker: str = "tradestation") -> float:
    """Actual retail margin / theoretical CME margin."""
    if broker not in broker_margins or symbol not in broker_margins[broker]:
        return 1.0
    actual = broker_margins[broker][symbol].get("overnight_initial", theoretical_margin)
    if theoretical_margin <= 0:
        return 1.0
    return actual / theoretical_margin
