# Session 13 — Reporting v4: Portfolio & Multi-Strategy

## Objective

Lift reporting from single-strategy to multi-strategy and add portfolio-level
analytics so we can answer "how does this fit with everything else I
might run?" **No strategy changes this session.** Portfolio reporting
operates on the existing trade logs from any strategies that have been
backtested by this point.

By end of session:
- `uv run trading-research portfolio <run-id-1> <run-id-2> ...` produces
  a portfolio-level HTML report that overlays multiple strategies.
- Correlation matrix of strategy daily P&L is computed and displayed.
- Portfolio-level drawdown with per-strategy attribution.
- Risk-parity and vol-target position sizing comparisons.
- Kelly fraction reference calculations (clearly marked as reference,
  never as sizing recommendations).
- Capital efficiency metrics: return on margin, return on peak capital,
  return on max drawdown.
- Integration with TradeStation and IBKR margin tables where available.

**Non-goals:** no live execution, no real-time portfolio monitoring
(that's a separate session much later), no new strategies.

---

## Entry Criteria

- Session 12 complete: regime and ML analytics in place.
- At least two backtested strategies exist in `runs/`. If only one
  strategy exists by session 13 (zn_macd_pullback), create two
  synthetic variants with different parameters for portfolio
  demonstration purposes and label them clearly as variants.
- `configs/instruments.yaml` has accurate margin info for ZN, 6A, 6C,
  6N, plus a separate `broker_margins.yaml` with TradeStation and IBKR
  retail margin values.

---

## Deliverables

### 1. Multi-strategy loader

**File:** `src/trading_research/eval/portfolio.py`

Function `load_portfolio(run_ids: list[str]) -> Portfolio` that:

1. Loads each run's trade log, equity curve, summary JSON, and config.
2. Aligns all equity curves on a shared daily time index.
3. Computes per-strategy daily P&L series.
4. Computes combined portfolio daily P&L with equal weighting by default.
5. Returns a `Portfolio` dataclass with per-strategy and aggregate views.

### 2. Correlation analysis

**File:** `src/trading_research/eval/correlation.py`

Functions:
- `daily_pnl_correlation(portfolio)` — Pearson and Spearman correlation
  matrices of daily P&L across strategies.
- `rolling_correlation(portfolio, window_days=60)` — rolling 60-day
  correlation between each pair, for stability visualization.
- `return_correlation_vs_market(portfolio, benchmark='SPY')` — each
  strategy's return correlation with a benchmark (requires benchmark
  daily returns; fallback is to skip with a warning if none are loaded).

Report section: correlation matrix heatmap, rolling correlation lines,
benchmark correlation bars.

### 3. Portfolio drawdown with attribution

**File:** `src/trading_research/eval/portfolio_drawdown.py`

Function `portfolio_drawdown_attribution(portfolio)`:

1. Computes the combined portfolio equity curve.
2. Identifies every drawdown > 1%.
3. For each drawdown, decomposes the loss by strategy: how much of the
   portfolio drawdown came from each constituent during the drawdown
   window.
4. Returns a DataFrame with drawdown-level and strategy-level detail.

Report section: portfolio drawdown chart with per-strategy attribution
stacked bars overlaid.

### 4. Position sizing comparisons

**File:** `src/trading_research/eval/sizing.py`

Function `apply_sizing(trades, method, target_vol=0.10, lookback=60)`:

- `equal_weight` — current default, one contract per signal
- `vol_target` — size each trade inversely proportional to recent
  realized volatility so the portfolio targets a fixed annualized vol
- `risk_parity` — size each strategy so each contributes equally to
  portfolio variance
- `inverse_dd` — size each strategy inversely proportional to its
  recent drawdown
- `kelly_reference` — compute the Kelly fraction for each strategy
  (using mean and variance of historical trade returns) and display
  it, but **do not actually apply Kelly sizing**. The data scientist
  persona is explicit: Kelly is reference-only in this project.

Returns a re-simulated equity curve under each sizing regime and a
comparison table: Calmar, Sharpe, max DD, final P&L, trades/week.

**Hard constraint:** sizing re-simulation cannot look ahead. Any
lookback window (for vol estimation, DD calculation) must use only
data strictly before the trade's entry.

### 5. Kelly reference calculator

**File:** `src/trading_research/eval/kelly.py`

Function `kelly_fraction(returns, confidence=0.25)`:
- Full Kelly: f* = (mean_return / variance)
- Half Kelly, Quarter Kelly (the realistic range)
- Kelly with drawdown constraint — compute the Kelly fraction that
  would have kept historical max DD below a target threshold

The report section shows all three Kelly values side-by-side with a
prominent disclaimer: **"Kelly fractions are shown for reference only.
This project sizes positions via volatility targeting. Kelly assumes
the historical distribution of returns will repeat; real markets
violate this assumption and Kelly sizing has destroyed real traders
using real strategies that looked real on paper."**

The mentor persona wrote that disclaimer. It stays in the report
verbatim.

### 6. Capital efficiency metrics

**File:** `src/trading_research/eval/capital.py`

Functions:
- `return_on_margin(trades, broker_margins, broker='TradeStation')` —
  net profit divided by peak margin used.
- `return_on_peak_capital(trades, starting_capital)` — net profit
  divided by the largest equity peak reached during the backtest.
- `return_on_max_dd(equity_series)` — net profit divided by max dollar
  drawdown.
- `margin_utilization_series(trades, broker_margins)` — time series of
  margin used, useful for seeing how often the portfolio is near its
  margin ceiling.

For pairs strategies specifically, also compute:
- `theoretical_spread_margin(pair)` — what a real desk pays under CME
  reduced intercommodity spread margins
- `broker_actual_margin(pair, broker)` — what TradeStation or IBKR
  actually charges
- `margin_penalty_ratio(pair)` — actual / theoretical, the penalty for
  trading at retail

The mentor persona has been hammering this point since session 01:
pairs look great until you see the retail margin reality. The report
has to surface it.

### 7. Report v4 — portfolio template

**File:** `src/trading_research/eval/templates/portfolio_report.html.j2`

This is a **separate** report template from the single-strategy one.
It's not additive — portfolio reporting is its own artifact.

Sections:

1. **Header** — portfolio composition, strategies included, date range,
   sizing method, broker assumption, git SHAs of all constituent
   strategies.
2. **Combined equity curve** with per-strategy lines overlaid.
3. **Portfolio headline metrics** — Calmar, Sharpe, Sortino, max DD,
   trades/week, with CIs.
4. **Per-strategy summary table** — one row per strategy with its
   standalone metrics.
5. **Correlation matrix heatmap** (Pearson and Spearman).
6. **Rolling correlation lines** — every pair, 60-day rolling.
7. **Portfolio drawdown with attribution** — stacked attribution bars
   during each major DD.
8. **Sizing comparison table + chart** — equal_weight vs vol_target vs
   risk_parity vs inverse_dd, with Calmar/Sharpe/DD for each.
9. **Kelly reference block** — three Kelly values with the mentor's
   disclaimer verbatim.
10. **Capital efficiency table** — return on margin, return on peak
    capital, return on max DD, for each strategy and the portfolio.
11. **Margin utilization chart** — time series.
12. **Pairs margin penalty** (if any pair strategies present) — table
    comparing theoretical vs actual margin.
13. **Diversification benefit** — Sharpe of each strategy vs Sharpe
    of the combined portfolio; if the combined Sharpe isn't
    meaningfully higher than the best individual Sharpe, the portfolio
    is not diversifying and the combination is not useful.
14. **Data dictionary link** — link to the portfolio data dictionary.
15. **Run provenance footer**.

### 8. CLI command

```
uv run trading-research portfolio <run-id-1> <run-id-2> ... \
    [--sizing vol_target] [--broker TradeStation] [--output report.html]
```

Writes `runs/portfolio/<timestamp>/portfolio_report.html` by default
or a user-specified path.

### 9. Broker margin data

**File:** `configs/broker_margins.yaml`

Hand-maintained YAML with current margin values for TradeStation and
IBKR retail, for every instrument in `configs/instruments.yaml`. Include:
- overnight_initial
- overnight_maintenance
- day_trade_initial
- day_trade_maintenance
- intercommodity_spread (if applicable)

Update date and source URL for each value. This is human-maintained
data and must be refreshed periodically — add a note in the file
header with the last-updated date and a reminder.

### 10. Data dictionary — portfolio edition

**File:** `src/trading_research/eval/data_dictionary_portfolio.py`

Separate data dictionary for portfolio-level concepts: diversification
benefit, attribution, risk parity, vol target, Kelly fraction, margin
utilization. Clear plain-English definitions.

### 11. Tests

- `tests/test_portfolio.py` — synthetic two-strategy portfolio,
  verify alignment and combined equity computation.
- `tests/test_correlation.py` — known correlated and uncorrelated
  series, verify Pearson and rolling outputs.
- `tests/test_portfolio_drawdown.py` — synthetic drawdown with known
  attribution, verify decomposition.
- `tests/test_sizing.py` — verify each sizing method is deterministic
  and look-ahead-free.
- `tests/test_kelly.py` — known-answer Kelly on a synthetic return
  distribution.
- `tests/test_capital.py` — margin calculations against hand-computed
  values.
- Target: 380+ tests passing.

---

## Execution Order

1. Populate `configs/broker_margins.yaml` by hand (pre-work).
2. `eval/portfolio.py` + tests.
3. `eval/correlation.py` + tests.
4. `eval/portfolio_drawdown.py` + tests.
5. `eval/sizing.py` + tests.
6. `eval/kelly.py` + tests.
7. `eval/capital.py` + tests.
8. `portfolio_report.html.j2` template.
9. CLI command.
10. Run on the session 09 fixture plus a synthetic variant.
11. Data dictionary updates.
12. Work log.

---

## Success Criteria

- `uv run trading-research portfolio zn_macd_pullback_v1 zn_macd_pullback_v2`
  produces a self-contained HTML portfolio report.
- Correlation matrix is computed and legible.
- Sizing comparison shows meaningful differences between methods.
- Kelly block shows the disclaimer verbatim and Ibby rolls his eyes at
  it (the disclaimer is working as intended).
- All tests pass.
- Work log written.

---

## What Ibby Should See at the End

A separate, standalone portfolio report that shows him — at a glance —
whether running multiple strategies together is additive or redundant,
whether retail margin kills any of his pair ideas, and what sizing
regime he should be running. This is the document he hands to an
outside AI agent when he wants a sanity check on his full portfolio
design, not just a single-strategy review.
