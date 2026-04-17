"""Data dictionary generator.

Writes a Markdown document defining every column in the enriched trade log
and every metric in the HTML report.

Public API
----------
    generate_data_dictionary(run_dir: Path) -> Path
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Column definitions — trade log (base schema + context join additions)
# ---------------------------------------------------------------------------

TRADE_LOG_COLUMNS: list[dict] = [
    # ── Base schema ──────────────────────────────────────────────────────────
    {"name": "trade_id",           "dtype": "str",             "units": "-",      "definition": "UUID4 assigned at fill time; unique per trade."},
    {"name": "strategy_id",        "dtype": "str",             "units": "-",      "definition": "Strategy identifier from the YAML config (e.g. zn-macd-pullback-v1)."},
    {"name": "symbol",             "dtype": "str",             "units": "-",      "definition": "Root symbol of the instrument (e.g. ZN)."},
    {"name": "direction",          "dtype": "str",             "units": "-",      "definition": "'long' or 'short'."},
    {"name": "quantity",           "dtype": "int",             "units": "contracts", "definition": "Number of contracts traded."},
    {"name": "entry_trigger_ts",   "dtype": "datetime[UTC]",   "units": "-",      "definition": "Bar timestamp that generated the entry signal (trigger bar open time)."},
    {"name": "entry_ts",           "dtype": "datetime[UTC]",   "units": "-",      "definition": "Bar timestamp of the fill bar (next-bar-open fill model → trigger bar + 1)."},
    {"name": "entry_price",        "dtype": "float",           "units": "points", "definition": "Fill price at entry (open of fill bar under next-bar-open model)."},
    {"name": "exit_trigger_ts",    "dtype": "datetime[UTC]",   "units": "-",      "definition": "Bar timestamp that generated the exit signal."},
    {"name": "exit_ts",            "dtype": "datetime[UTC]",   "units": "-",      "definition": "Bar timestamp of the exit fill."},
    {"name": "exit_price",         "dtype": "float",           "units": "points", "definition": "Fill price at exit."},
    {"name": "exit_reason",        "dtype": "str",             "units": "-",      "definition": "One of: 'signal' (exit signal fired), 'stop' (initial stop hit), 'target' (initial target hit), 'EOD' (end-of-day flat)."},
    {"name": "initial_stop",       "dtype": "float",           "units": "points", "definition": "Initial stop-loss price set at entry."},
    {"name": "initial_target",     "dtype": "float | None",    "units": "points", "definition": "Initial take-profit price set at entry, or NaN when no fixed target."},
    {"name": "pnl_points",         "dtype": "float",           "units": "points", "definition": "Gross P&L in price points: (exit_price - entry_price) × direction_sign."},
    {"name": "pnl_usd",            "dtype": "float",           "units": "USD",    "definition": "Gross P&L in USD: pnl_points × point_value_usd."},
    {"name": "slippage_usd",       "dtype": "float",           "units": "USD",    "definition": "Round-trip slippage cost (slippage_ticks × tick_value × 2 sides)."},
    {"name": "commission_usd",     "dtype": "float",           "units": "USD",    "definition": "Round-trip commission."},
    {"name": "net_pnl_usd",        "dtype": "float",           "units": "USD",    "definition": "Net P&L after slippage and commission: pnl_usd - slippage_usd - commission_usd."},
    {"name": "mae_points",         "dtype": "float",           "units": "points", "definition": "Maximum adverse excursion in price points (most negative intra-trade move against the position, signed). Always ≤ 0 for both longs and shorts."},
    {"name": "mfe_points",         "dtype": "float",           "units": "points", "definition": "Maximum favourable excursion in price points (best intra-trade unrealised P&L). Always ≥ 0."},
    # ── Context join additions (eval/context.py) ─────────────────────────────
    {"name": "atr_14_pct_rank_252","dtype": "float",           "units": "0–1",    "definition": "Rolling 252-session percentile rank of ATR_14 at entry. 0 = lowest vol seen in past year; 1 = highest. Computed from ~22,680 5m bars (1 year × 90 bars/day). NaN during the first year of history."},
    {"name": "daily_range_used_pct","dtype": "float",          "units": "ratio",  "definition": "(entry_close - daily_open) / (daily_high_so_far - daily_low_so_far). Measures how far into the day's developing range the trade entered. NaN when daily range is zero."},
    {"name": "vwap_distance_atr",  "dtype": "float",           "units": "ATRs",   "definition": "(close - vwap_session) / atr_14 at the entry bar. Positive = above session VWAP. Useful for VWAP-relative entry timing."},
    {"name": "htf_bias_strength",  "dtype": "float",           "units": "pts",    "definition": "Absolute value of the daily MACD histogram at entry. Larger values indicate stronger higher-timeframe directional momentum. Used as a proxy for 'regime conviction' at entry."},
    {"name": "session_regime",     "dtype": "str",             "units": "-",      "definition": "Session window at entry time (America/New_York): Asia (18:00–03:00), London (03:00–08:00), NY pre-open (08:00–09:30), NY RTH (09:30–16:00), NY close (16:00–17:00), Overnight (17:00–18:00)."},
    {"name": "entry_atr_14",       "dtype": "float",           "units": "points", "definition": "Raw ATR_14 value at the entry bar. Used to audit stop sizing: initial_stop should be ≈ N × entry_atr_14 from entry_price."},
    # ── Derived columns (eval/report.py) ────────────────────────────────────
    {"name": "initial_risk_usd",   "dtype": "float",           "units": "USD",    "definition": "Initial risk in dollars: abs(entry_price - initial_stop) × point_value_usd. NaN when initial_stop is NaN."},
    {"name": "pnl_r",              "dtype": "float",           "units": "R",      "definition": "R-multiple: net_pnl_usd / initial_risk_usd. Normalises trade outcomes by the initial risk taken. E[pnl_r] > 0 is required for positive expectancy after costs."},
    {"name": "mae_r",              "dtype": "float",           "units": "R",      "definition": "MAE expressed in R-multiples: abs(mae_points × point_value_usd) / initial_risk_usd. A trade that hit its stop exactly has mae_r = 1.0."},
    {"name": "mfe_r",              "dtype": "float",           "units": "R",      "definition": "MFE expressed in R-multiples: abs(mfe_points × point_value_usd) / initial_risk_usd. Trades with large mfe_r that closed at a loss are 'gave-back winners'."},
    {"name": "hold_minutes",       "dtype": "float",           "units": "minutes","definition": "Total trade duration in minutes: (exit_ts - entry_ts).total_seconds() / 60."},
    {"name": "hold_bars",          "dtype": "int",             "units": "bars",   "definition": "Trade duration in 5-minute bars: round(hold_minutes / 5). Minimum 0."},
    {"name": "outcome",            "dtype": "str",             "units": "-",      "definition": "'winner' (net_pnl_usd > 0), 'loser' (net_pnl_usd < 0), 'scratch' (net_pnl_usd == 0)."},
    {"name": "entry_dow",          "dtype": "str",             "units": "-",      "definition": "Day of week of entry_ts in America/New_York (Monday–Friday)."},
    {"name": "entry_hour",         "dtype": "int",             "units": "hour",   "definition": "Hour of day of entry_ts in America/New_York (0–23)."},
    # ── Session 12: Machine Learning & Regimes ──────────────────────────────
    {"name": "vol_regime",         "dtype": "str",             "units": "-",      "definition": "Volatility regime (low, mid, high) based on trailing 252-session ATR percentiles at entry."},
    {"name": "trend_regime",       "dtype": "str",             "units": "-",      "definition": "Trend regime (weak, moderate, strong) based on ADX_14 at entry."},
    {"name": "fomc_regime",        "dtype": "str",             "units": "-",      "definition": "Distance to nearest FOMC meeting (fomc_today, fomc_week, fomc_far, etc.)."},
    {"name": "shap_top_pos_1",     "dtype": "str",             "units": "-",      "definition": "The top feature contributing positively to the ML classifier's probability prediction for this trade."},
    {"name": "shap_top_neg_1",     "dtype": "str",             "units": "-",      "definition": "The top feature contributing negatively to the ML classifier's probability prediction for this trade."},
    {"name": "cluster",            "dtype": "int",             "units": "-",      "definition": "Trade cluster ID identified by HDBSCAN based on the entry-bar feature vector (-1 = noise)."},
]

# ---------------------------------------------------------------------------
# Metric definitions — HTML report sections
# ---------------------------------------------------------------------------

REPORT_METRICS: list[dict] = [
    {"name": "Total trades",        "formula": "COUNT(trades)",                       "units": "trades",   "interpretation": "Total number of completed round trips in the backtest window."},
    {"name": "Win rate",            "formula": "COUNT(net_pnl > 0) / COUNT(all)",     "units": "%",        "interpretation": "Fraction of trades with positive net P&L. High win rates with small R:R can be as dangerous as low win rates with large R:R — always pair with profit factor and expectancy."},
    {"name": "Profit factor",       "formula": "SUM(wins) / SUM(|losses|)",           "units": "-",        "interpretation": "Ratio of gross winning P&L to gross losing P&L. PF > 1 is profitable before considering if the sample size supports the estimate."},
    {"name": "Expectancy (USD)",    "formula": "MEAN(net_pnl_usd)",                   "units": "USD",      "interpretation": "Average net P&L per trade in dollars. Must be > 0 for the strategy to be profitable over time."},
    {"name": "Expectancy (R)",      "formula": "MEAN(pnl_r)",                         "units": "R",        "interpretation": "Average R-multiple per trade. Unlike dollar expectancy, this is scale-independent and comparable across strategies. E[R] > 0.1 is a reasonable minimum bar."},
    {"name": "Trades / week",       "formula": "total_trades / span_weeks",           "units": "trades",   "interpretation": "Average trading frequency. Very high rates (40+/week) suggest over-fitting or market microstructure dependency. Very low rates (<2/week) create sample-size problems."},
    {"name": "Calmar",              "formula": "annualised_return / |max_drawdown_usd|","units": "-",       "interpretation": "Headline metric. Annual return divided by the maximum drawdown in dollars. Higher is better. A Calmar of 2 means the worst drawdown was half the annual return — the strategy can recover from the worst-case scenario in about 6 months."},
    {"name": "Sharpe (ann.)",       "formula": "MEAN(daily_pnl) / STD(daily_pnl) × √252","units": "-",     "interpretation": "Annualised Sharpe on daily P&L series. Reported for comparison but NOT the headline metric because it penalises upside volatility and assumes normally distributed returns. Mean-reversion strategies have non-normal return distributions."},
    {"name": "Sortino (ann.)",      "formula": "MEAN(daily_pnl) / STD(negative_pnl) × √252","units": "-",  "interpretation": "Like Sharpe but only penalises downside deviation. More appropriate than Sharpe for strategies with non-normal return distributions."},
    {"name": "Max drawdown (USD)",  "formula": "MIN(equity - running_peak)",           "units": "USD",      "interpretation": "Worst peak-to-trough loss in dollar terms. This is what breaks traders psychologically — it must be at a level where the trader can stay in their seat."},
    {"name": "Max drawdown (%)",    "formula": "max_drawdown_usd / peak_at_max",      "units": "%",        "interpretation": "Worst drawdown as a percentage of equity at the time of the peak. For a $25K account, a 20% drawdown means $5K lost at the worst point."},
    {"name": "Drawdown duration",   "formula": "MAX(peak_to_recovery_in_calendar_days)","units": "days",   "interpretation": "Longest period from a new equity high to the next equity high. Long drawdown durations are often more psychologically damaging than large drawdown depths — a 3-month flat period can cause a trader to abandon a strategy at the worst moment."},
    {"name": "Max consec. losses",  "formula": "MAX(consecutive losing trade count)",  "units": "trades",  "interpretation": "Longest sequence of consecutive losing trades. Sequences of 10+ consecutive losers will test most traders' confidence even in a profitable strategy."},
    {"name": "Avg MAE (pts)",       "formula": "MEAN(mae_points)",                    "units": "points",   "interpretation": "Average maximum adverse excursion per trade in price points. Compared to stop size to assess stop placement efficiency."},
    {"name": "Avg MFE (pts)",       "formula": "MEAN(mfe_points)",                    "units": "points",   "interpretation": "Average maximum favourable excursion per trade. If avg MFE greatly exceeds avg exit move, the trade management is leaving money on the table."},
    {"name": "Rolling E[R]",        "formula": "ROLLING(N, MEAN(pnl_r))",             "units": "R",        "interpretation": "N-trade rolling average R-multiple. Trend in rolling expectancy reveals regime sensitivity — if a 100-trade rolling expectancy drifts from positive to negative, the strategy's edge is degrading."},
    {"name": "E[R] cost sensitivity","formula": "re-run with 1×/2×/3× base_cost",    "units": "USD",      "interpretation": "Shows how sensitive the strategy's profitability is to cost assumptions. If doubling costs flips the strategy from profitable to unprofitable, the edge is thin and execution quality is critical."},
    {"name": "ATR pct rank (252)",   "formula": "rolling_252_session_percentile(atr_14)","units": "0–1",   "interpretation": "Where the current ATR sits within the past year of ATR values. High values (>0.8) mean high volatility regime; low values (<0.2) mean low volatility. Entry timing relative to the vol regime affects R:R."},
    {"name": "Session regime P&L",  "formula": "SUM(net_pnl) grouped by session_regime","units": "USD",   "interpretation": "Total P&L earned in each session window (Asia, London, NY RTH, etc.). Reveals which sessions drive the strategy's edge and whether the strategy should be session-filtered."},

    # ── Session 11: Risk Officer metrics ─────────────────────────────────────
    {"name": "Bootstrap CI",         "formula": "percentile([boot_stat], [2.5,97.5])",  "units": "-",        "interpretation": "90% confidence interval for a metric computed by resampling the trade-level P&L 1,000 times with replacement. Wide CIs mean the point estimate is unreliable — look at the lower bound as the pessimistic expectation. A Calmar of 2 with CI [0.8, 3.2] is much weaker evidence than a Calmar of 2 with CI [1.7, 2.3]."},
    {"name": "Deflated Sharpe (DSR)","formula": "Φ((SR - E[SR_max]) / sqrt(Var(SR)))",  "units": "prob.",    "interpretation": "Probability that the true Sharpe exceeds zero, adjusted for the number of strategy variants tested (n_trials). When you run 30 variants and pick the best, the best Sharpe is biased upward — DSR corrects for this. A DSR of 0.95 means 95% confidence the edge is real after multiple-testing correction. A DSR below 0.5 is statistically indistinguishable from noise. Reference: Lopez de Prado (2014)."},
    {"name": "n_trials",             "formula": "COUNT(trials.json entries by trial_group)","units": "count", "interpretation": "Number of distinct strategy variants recorded in the trials registry (runs/.trials.json) for this trial group. Used as the multiple-testing correction factor in DSR. Each call to 'uv run trading-research backtest' or 'walkforward' records one trial. If n_trials=1, DSR equals PSR — no correction applied."},
    {"name": "Probabilistic Sharpe (PSR)","formula": "Φ((SR - SR_benchmark) / sqrt(Var(SR)))", "units": "prob.", "interpretation": "Probability that the true Sharpe exceeds a benchmark Sharpe (0 or 1), computed from the observed Sharpe and its estimation error. Unlike DSR, PSR does not correct for multiple testing — it answers 'is this Sharpe estimate statistically different from the benchmark?' Reference: Bailey & Lopez de Prado (2012)."},
    {"name": "MAR Ratio",            "formula": "CAGR / |max_drawdown_usd|",            "units": "-",        "interpretation": "Compound Annual Growth Rate divided by maximum drawdown in absolute terms. Identical to Calmar when computed on dollar P&L. Higher is better. A MAR of 1 means the worst drawdown consumed a full year of returns; a MAR of 3 means the worst drawdown was a third of a year of returns."},
    {"name": "Ulcer Index (UI)",     "formula": "sqrt(MEAN((dd_pct)^2))",               "units": "pct",      "interpretation": "Root-mean-square of percentage drawdowns from the running peak. Unlike max drawdown, UI captures both the frequency and severity of all drawdowns — a strategy that has many small drawdowns vs a strategy with one large drawdown can have the same max DD but very different UIs. Lower is better."},
    {"name": "Ulcer Performance Index (UPI)","formula": "(CAGR - rf) / UI",             "units": "-",        "interpretation": "Pain-adjusted return metric: return above risk-free rate divided by Ulcer Index. The UPI equivalent of Sharpe but using UI (all drawdowns) instead of standard deviation (all returns). Higher is better. The UPI is particularly useful for mean-reversion strategies where Sharpe is misleading."},
    {"name": "Recovery Factor",      "formula": "net_profit / |max_drawdown_usd|",      "units": "-",        "interpretation": "Total net profit divided by maximum drawdown. Answers: how many times over did the strategy earn back the worst-case loss? A Recovery Factor of 5 means the strategy earned 5× its worst drawdown in total. Related to MAR but uses total profit rather than annualised return."},
    {"name": "Pain Ratio",           "formula": "CAGR / |MEAN(dd_pct)|",                "units": "-",        "interpretation": "Like UPI but uses average drawdown percentage instead of RMS. Slightly less punishing on single deep events than UPI. A high Pain Ratio with a low UPI indicates the strategy has one catastrophic drawdown but is otherwise well-behaved."},
    {"name": "Tail Ratio (95/5)",    "formula": "|p95(returns)| / |p5(returns)|",       "units": "-",        "interpretation": "Ratio of the 95th percentile return to the absolute 5th percentile return. Tail Ratio > 1 means the right tail is fatter than the left tail — wins are larger than losses at the extremes. Mean-reversion strategies typically have Tail Ratio < 1 (fat left tails from gap risk). Tail Ratio > 1.5 is a positive sign."},
    {"name": "Omega Ratio",          "formula": "SUM(gains > 0) / SUM(|losses < 0|)",   "units": "-",        "interpretation": "Probability-weighted gain/loss ratio computed from the full return distribution without normality assumptions. Omega > 1 means more probability mass above zero than below. Unlike Sharpe, Omega uses the full empirical distribution and is appropriate for non-normal returns. Omega = 1 is breakeven."},
    {"name": "Gain-to-Pain (GPR)",   "formula": "SUM(positive_months) / |SUM(negative_months)|", "units": "-", "interpretation": "Sum of positive monthly returns divided by the absolute sum of negative monthly returns. Measures how much you earn vs how much you give back across calendar months. GPR > 1 means total gains exceed total losses across all months. A GPR of 2 means you earn twice as much in good months as you lose in bad months."},
    {"name": "Jarque-Bera test",     "formula": "JB = n/6 × (S² + K²/4); p = 1 - chi2_cdf(JB, df=2)", "units": "p-value", "interpretation": "Tests whether trade returns are normally distributed. A low p-value (< 0.05) rejects normality. Mean-reversion strategies almost always reject normality due to high win rates and occasional large losses — this is expected and is why we use Sortino/Calmar rather than Sharpe as the primary metric."},
    {"name": "Ljung-Box test",       "formula": "Q = n(n+2) Σ rk² / (n-k)",            "units": "p-value",  "interpretation": "Tests whether trade returns have serial autocorrelation at lags 1-20. A low p-value indicates systematic clustering of wins and losses. Some autocorrelation is expected in mean-reversion strategies (consecutive signals in the same direction). Strong autocorrelation may indicate look-ahead bias or strategy-specific clustering."},
    {"name": "Time underwater",      "formula": "COUNT(equity < running_peak) / COUNT(all)", "units": "%",    "interpretation": "Percentage of equity-curve bars spent below a prior high-water mark. 60%+ time underwater is psychologically difficult for most traders. Best-in-class strategies spend 20-30% of time underwater. This metric is often more important than max drawdown depth for predicting whether a trader will actually stick to a strategy."},
    {"name": "Subperiod stability",  "formula": "per-year metrics (Calmar, Sharpe, win_rate)", "units": "-",  "interpretation": "Headline metrics computed separately for each calendar year. A strategy is 'stable' when subperiod metrics are consistent rather than front-loaded. The degradation flag fires when the most recent year is worse than the worst historical year — a key early warning of out-of-sample decay."},
    {"name": "Monte Carlo shuffle",  "formula": "permute(trade_order) × 1000; compute metrics per permutation", "units": "-", "interpretation": "Resamples trade order 1,000 times preserving individual P&Ls. The distribution of max drawdown and Calmar across shuffles reveals how much of the historical equity path was structural (strategy edge) vs lucky (trade sequencing). If the actual max DD is at the 90th+ percentile of shuffle outcomes, the historical path was lucky."},
    {"name": "Walk-forward OOS",     "formula": "fit on folds 0..k-1, test on fold k, purge gap_bars, embargo embargo_bars", "units": "-", "interpretation": "Purged walk-forward: splits the full dataset into n_folds contiguous windows, excludes gap_bars between train and test (prevents label leakage), excludes embargo_bars after test (prevents correlation). Per-fold OOS metrics are the honest out-of-sample performance estimate. For rule-based strategies with fixed parameters, the walk-forward is a subperiod robustness test."},
    # ── Session 12: ML & Analytics ───────────────────────────────────────────
    {"name": "Permutation Importance", "formula": "drop_in_AUC(shuffle(feature))", "units": "Δ AUC", "interpretation": "Measures how much the classifier's performance drops when a feature is randomly shuffled on held-out data. Unlike built-in tree importance, it is unbiased toward high-cardinality features."},
    {"name": "SHAP value",           "formula": "E[f(x|S U {i})] - E[f(x|S)]",  "units": "log-odds", "interpretation": "The marginal contribution of a feature to the model's prediction for a specific trade. Sums to the total model output. Used to explain exactly why the model liked or disliked a trade setup."},
    {"name": "Meta-labeling sweep",  "formula": "Metrics(trades where P(win) > threshold)", "units": "-", "interpretation": "Simulates applying the classifier as a filter on the base strategy. If the filtered strategy's Calmar exceeds the base Calmar by a wide margin, the base rules are leaving money on the table."},
    {"name": "HDBSCAN Clusters",     "formula": "density-based spatial clustering", "units": "-", "interpretation": "Unsupervised clustering of trades based on their entry features. Reveals natural 'trade types' (e.g. morning reversal, afternoon trend). If one cluster holds all the losses, it is a prime filter candidate."},
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_data_dictionary(run_dir: Path) -> Path:
    """Write data_dictionary.md to *run_dir* and return the Path.

    The dictionary defines every column in the enriched trade log (base schema
    + context join columns + derived report columns) and every metric in the
    HTML report.
    """
    run_dir = Path(run_dir)

    lines: list[str] = [
        "# Data Dictionary",
        "",
        f"Generated for run: `{run_dir.parent.name}/{run_dir.name}`",
        "",
        "---",
        "",
        "## Trade Log Columns",
        "",
        "All columns present in the enriched trade log after the market-context join.",
        "",
        "| Column | dtype | Units | Definition |",
        "| ------ | ----- | ----- | ---------- |",
    ]

    for col in TRADE_LOG_COLUMNS:
        defn = col["definition"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{col['name']}` | `{col['dtype']}` | {col['units']} | {defn} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Report Metrics",
        "",
        "All metrics appearing in the HTML report, with formulas and interpretation.",
        "",
        "| Metric | Formula | Units | Interpretation |",
        "| ------ | ------- | ----- | -------------- |",
    ]

    for m in REPORT_METRICS:
        interp = m["interpretation"].replace("|", "\\|").replace("\n", " ")
        formula = m["formula"].replace("|", "\\|")
        lines.append(
            f"| **{m['name']}** | `{formula}` | {m['units']} | {interp} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Notes",
        "",
        "- All timestamps are tz-aware UTC, displayed in America/New_York in the report.",
        "- Monetary values are in USD unless noted.",
        "- R-multiples are signed: positive = profit, negative = loss.",
        "- 'points' for ZN = price in full points (1 point = $1,000 at 1 contract).",
        "- ATR percentile rank uses ~22,680 bars (252 trading days × 90 bars/day at 5m resolution).",
        "- Context columns use only data available at entry_ts — no look-ahead.",
        "",
    ]

    out_path = run_dir / "data_dictionary.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Column name set (for test assertions)
# ---------------------------------------------------------------------------

def documented_columns() -> set[str]:
    """Return the set of column names defined in the data dictionary."""
    return {col["name"] for col in TRADE_LOG_COLUMNS}
