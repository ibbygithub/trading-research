from dataclasses import dataclass, field
import pandas as pd
from pathlib import Path
import json

@dataclass
class PortfolioStrategy:
    run_id: str
    trades: pd.DataFrame
    equity: pd.Series
    summary: dict
    daily_pnl: pd.Series

@dataclass
class Portfolio:
    strategies: dict[str, PortfolioStrategy]
    combined_daily_pnl: pd.Series = field(init=False)
    combined_equity: pd.Series = field(init=False)
    
    def __post_init__(self):
        if not self.strategies:
            self.combined_daily_pnl = pd.Series(dtype=float)
            self.combined_equity = pd.Series(dtype=float)
            return
            
        # Align all daily PnL series on a common index
        all_pnl = pd.DataFrame({sid: s.daily_pnl for sid, s in self.strategies.items()})
        all_pnl = all_pnl.fillna(0.0)
        
        self.combined_daily_pnl = all_pnl.sum(axis=1)
        self.combined_equity = self.combined_daily_pnl.cumsum()

def load_portfolio(run_dirs: list[Path]) -> Portfolio:
    """Load multiple strategy runs into a single Portfolio object."""
    strategies = {}
    
    for run_dir in run_dirs:
        if not run_dir.exists():
            continue
            
        run_id = run_dir.name
        
        # Load Trades
        trades_path = run_dir / "trades.parquet"
        if not trades_path.exists():
            continue
        trades = pd.read_parquet(trades_path)
        
        # Load Equity
        eq_path = run_dir / "equity_curve.parquet"
        if not eq_path.exists():
            continue
        eq_df = pd.read_parquet(eq_path)
        equity = eq_df.set_index("exit_ts")["equity_usd"]
        
        # Load Summary
        summary_path = run_dir / "summary.json"
        summary = {}
        if summary_path.exists():
            with open(summary_path, "r") as f:
                summary = json.load(f)
                
        # Compute Daily PnL
        # Group by the date of the exit_ts in UTC
        daily_pnl = trades.groupby(pd.to_datetime(trades["exit_ts"]).dt.date)["net_pnl_usd"].sum()
        daily_pnl.index = pd.DatetimeIndex(daily_pnl.index)
        
        strategies[run_id] = PortfolioStrategy(
            run_id=run_id,
            trades=trades,
            equity=equity,
            summary=summary,
            daily_pnl=daily_pnl
        )
        
    return Portfolio(strategies=strategies)
