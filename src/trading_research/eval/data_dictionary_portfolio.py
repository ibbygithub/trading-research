"""Portfolio Data Dictionary.

Definitions for all multi-strategy and portfolio metrics.
"""

PORTFOLIO_DICTIONARY = {
    "Correlation (Pearson)": "Linear correlation of daily PnL between two strategies. 1.0 means they move perfectly together, 0.0 means no relationship, -1.0 means perfect opposites.",
    "Correlation (Spearman)": "Rank correlation of daily PnL. Less sensitive to extreme outlier days than Pearson.",
    "Drawdown Attribution": "The percentage of the total portfolio loss during a specific drawdown period that was caused by a specific strategy.",
    "Equal Weight Sizing": "Allocates exactly 1 contract/unit to every strategy regardless of its volatility or drawdown.",
    "Vol Target Sizing": "Dynamically scales the size of each strategy inversely proportional to its recent historical volatility. Quieter strategies get larger sizes.",
    "Risk Parity Sizing": "Allocates capital such that each strategy contributes exactly the same amount of variance (risk) to the overall portfolio.",
    "Inverse DD Sizing": "Dynamically scales strategy size inversely to its recent drawdown. Strategies in deep drawdowns get their size reduced.",
    "Full Kelly Fraction": "The mathematically optimal fraction of bankroll to wager to maximize long-term geometric growth rate, assuming past return distributions repeat perfectly (which they never do). Reference only.",
    "Return on Margin (ROM)": "Total net profit divided by the peak overnight margin required to hold the positions. A truer measure of leverage efficiency.",
    "Retail Margin Penalty": "The ratio of margin required by a retail broker (like TradeStation) versus the theoretical exchange minimum margin. Often kills spread strategies.",
    "Diversification Benefit": "The difference between the portfolio's overall Sharpe ratio and the highest individual strategy Sharpe ratio."
}

def get_portfolio_dictionary() -> dict:
    return PORTFOLIO_DICTIONARY
