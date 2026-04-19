---
name: risk-management
description: Use when implementing or modifying position sizing, daily/weekly loss limits, portfolio-level exposure tracking, margin calculations (both theoretical exchange-spread and actual broker margin), kill switches, or any logic that constrains how much risk a strategy can take. This skill defines the volatility-targeting default sizing model, the rules for re-entries and combined risk, the dual-margin model for pairs trading, and the standing rules that protect capital regardless of what a strategy thinks it wants to do. Invoke when building risk controls into a new strategy, when debugging a backtest's sizing behavior, when computing pair margins, or when designing kill switches for paper or live trading.
---

# Risk Management

This skill owns the rules and the mechanisms that protect Ibby's capital from his strategies. Its job is to be the second voice in the room when a strategy says "let me take this trade" — the voice that asks "with what size, against what limits, with what exposure already on the book, and with what capital at stake if this trade is the worst-case version of itself."

The principle: **the strategy decides direction, the risk system decides size.** A strategy that's allowed to size its own positions is a strategy that will eventually blow up, because strategies are designed to look for opportunities and risk systems are designed to limit damage. Separating the two means the strategy can be aggressive in finding signals while the risk system stays conservative in sizing them. Both jobs done well, neither job compromised.

The second principle: **consistency over heroics.** Ibby is retired and trading his own money. The goal is consistent compounding, not maximum P&L. Every default in this skill is calibrated for that goal. Volatility targeting over Kelly. Hard daily and weekly stops. Reduced sizing during drawdowns. No averaging down. The framework will not optimize for the best possible upside because optimizing for upside means accepting downside that this account cannot afford.

## What this skill covers

- Position sizing models (volatility targeting default, fixed fractional, fixed contracts, Kelly as override)
- Daily and weekly loss limits with hard stops
- Per-strategy and account-level exposure tracking
- Re-entry combined-risk validation
- Margin calculation: theoretical exchange-spread vs. actual broker margin
- Pair-trading capital efficiency math
- Kill switches at strategy, instrument, and account levels
- Drawdown-based sizing reduction
- The risk integration with the backtest engine

## What this skill does NOT cover

- The strategy logic that produces signals (see `backtesting` and individual strategy files)
- Computing the metrics that inform sizing decisions (see `strategy-evaluation`)
- Live order placement (see `live-execution`)
- The theoretical math behind metrics like Sharpe (see `strategy-evaluation`)

## The position sizing models

The risk system supports four sizing models. The default is volatility targeting; everything else requires explicit configuration and a justification.

**Volatility targeting (default).** The position size is calculated so that the expected daily P&L volatility of the position equals a target dollar amount. Larger sizes during quiet markets, smaller sizes during volatile markets. The mathematical effect is to smooth the equity curve at the cost of some upside.

The formula:

```
target_daily_pnl_vol_usd = account_equity * vol_target_pct
position_volatility = recent_atr_in_dollars * sqrt(252) / sqrt(bars_per_day)
contracts = target_daily_pnl_vol_usd / position_volatility
```

Where:
- `vol_target_pct` is typically 0.5% to 1.0% of account equity per position
- `recent_atr_in_dollars` is the ATR over the last N bars converted to dollars via `atr_ticks * tick_value_usd`
- The annualization factor handles the conversion from bar-level volatility to daily volatility

The default `vol_target_pct` is **0.4%** per position for day-trading accounts under $50k. For Ibby's $25k account, that's $100 of expected daily P&L volatility per open position. With a typical maximum of 2-3 simultaneous positions during day-trading hours, total daily P&L volatility tops out at $200-300. This is the "consistency over heroics" calibration sized for a smaller account: a 2-sigma day is around $400-600, a 3-sigma day is around $600-900. Painful but survivable on a $25k base.

**A note on TradeStation day-trading margins.** TradeStation offers reduced day-trading margins of around $500 or less per contract on most CME futures (ZN, ES, CL, GC, etc.) during US session hours, which is dramatically lower than the overnight maintenance margin (typically $1,500-$2,500). Micro contracts like MGC and MZC are under $100 day-trade. This means a $25k account can comfortably trade 2-3 simultaneous standard contracts during day session even though the same positions held overnight would exceed the account's margin capacity.

**The implication for sizing:** the framework needs to know whether a strategy is day-trading (flat by EOD, qualifies for reduced margins) or swing-trading (holds overnight, uses overnight margins). This is read from the strategy's `category` field — `single_instrument` strategies enforce EOD flat and qualify for day-trade margins; strategies with `category: pairs` or `category: swing` use overnight margins. The exposure caps and the sizing calculations both respect this distinction.

For Ibby's account specifically: stay in `single_instrument` day-trading mode for ZN, 6A, 6C, 6N work. For pairs trading, default to micro contracts (M6A, M6C, M6N, MYN if they exist, or fall back to standard if not) so that overnight margin requirements stay within reach of a $25k base. Standard contracts on swing strategies are forbidden by default — overriding requires explicit configuration and a noted justification, because a single overnight standard-contract position can consume more margin than the entire account.

```python
# src/trading_research/risk/sizing.py
from dataclasses import dataclass
import polars as pl
import numpy as np

@dataclass(frozen=True)
class SizingDecision:
    contracts: float
    method: str
    rationale: dict          # the inputs that went into the decision
    capped_by: str | None    # name of the cap that was hit, if any

class VolatilityTargetSizer:
    """Vol-targeted position sizing.

    The recent ATR is converted to dollars via the instrument's tick_value_usd,
    annualized, and used to compute the contract count that produces the
    target daily P&L volatility.
    """

    def __init__(
        self,
        target_pct_per_position: float = 0.005,   # 0.5% of equity per position
        atr_lookback_bars: int = 14,
        atr_period: int = 14,
        bars_per_day: int = 390,                  # 6.5h * 60m = 390 1m bars
        max_contracts_cap: int = 10,
        min_contracts: float = 0.0,               # 0 means no trade if below
    ):
        self.target_pct = target_pct_per_position
        self.atr_lookback = atr_lookback_bars
        self.atr_period = atr_period
        self.bars_per_day = bars_per_day
        self.max_contracts_cap = max_contracts_cap
        self.min_contracts = min_contracts

    def size(
        self,
        bars: pl.DataFrame,
        bar_index: int,
        account_equity_usd: float,
        instrument: "Instrument",
    ) -> SizingDecision:
        """Compute the position size for a signal at bar_index."""
        # ATR over the lookback window
        atr_values = compute_atr(bars[:bar_index + 1], period=self.atr_period)
        recent_atr_ticks = atr_values[-1]

        if recent_atr_ticks is None or np.isnan(recent_atr_ticks):
            return SizingDecision(0, "volatility_target", {"reason": "atr_unavailable"}, None)

        atr_dollars = recent_atr_ticks * instrument.tick_value_usd

        # Annualize: bar_atr * sqrt(bars_per_day) gives daily vol estimate
        daily_vol_per_contract = atr_dollars * np.sqrt(self.bars_per_day) / np.sqrt(self.atr_period)

        target_daily_vol = account_equity_usd * self.target_pct
        raw_contracts = target_daily_vol / daily_vol_per_contract

        # Apply caps
        capped_by = None
        contracts = raw_contracts
        if contracts > self.max_contracts_cap:
            contracts = self.max_contracts_cap
            capped_by = "max_contracts_cap"
        if contracts < self.min_contracts:
            contracts = 0.0
            capped_by = "below_minimum"

        return SizingDecision(
            contracts=contracts,
            method="volatility_target",
            rationale={
                "atr_ticks": float(recent_atr_ticks),
                "atr_dollars": float(atr_dollars),
                "daily_vol_per_contract": float(daily_vol_per_contract),
                "target_daily_vol": float(target_daily_vol),
                "raw_contracts": float(raw_contracts),
                "account_equity": float(account_equity_usd),
            },
            capped_by=capped_by,
        )
```

**Fixed fractional sizing (override).** Risk a fixed percentage of account equity per trade, where "risk" means the dollar distance from entry to stop loss. Simpler than vol targeting but it doesn't account for market regime — a 1% risk in a quiet market is the same number of contracts as 1% in a volatile market, even though the second is more likely to hit.

```python
class FixedFractionalSizer:
    def __init__(self, risk_pct_per_trade: float = 0.005):
        self.risk_pct = risk_pct_per_trade

    def size(self, signal, account_equity_usd, instrument):
        # contracts = (equity * risk_pct) / (stop_distance_ticks * tick_value)
        ...
```

**Fixed contracts (override).** Always trade N contracts. Useful for testing, useless for production. Requires explicit config and a comment.

**Kelly criterion (override, requires double-explicit override).** Mathematically optimal for long-run capital growth, psychologically brutal in the short run. Fractional Kelly (typically 1/4 or 1/2 Kelly) is what some practitioners use, but full Kelly is rarely the right answer for retail accounts. Available but flagged loudly by the data scientist persona on every use.

## Daily and weekly loss limits

Per `CLAUDE.md`'s standing rules, every strategy that goes to paper or live must have daily and weekly loss limits. Backtest-only strategies can omit them but the framework warns.

The limits are enforced by the engine, not by the strategy. A strategy cannot opt out by sizing around them; the engine refuses any signal that would, if it lost its full risk amount, push the account past the daily or weekly stop.

```yaml
# In a strategy config (calibrated for a $25k day-trading account)
risk_limits:
  daily_loss_limit_usd: 250         # 1% of account
  weekly_loss_limit_usd: 750        # 3% of account
  per_trade_max_loss_usd: 125       # 0.5% of account, combined with stop distance
  account_equity_drawdown_pct: 0.10 # halt the strategy if account drops 10% from peak
```

**Calibration notes:** these defaults are sized for a $25k account using "1% per day, 3% per week" guidance, which is on the conservative side but appropriate for a retired trader's primary account. The point is not these specific numbers — it's the *ratio* to account size. For different account sizes, scale linearly. For a $50k account, double the limits. For a $100k account, quadruple them. The framework is account-size-aware via the volatility-targeting sizer; the limit YAMLs need to be configured per strategy.

**The daily limit logic:**

1. Track realized P&L for the current trading day (NY time, with the day boundary at the start of the Globex evening session).
2. Track open position P&L (mark-to-market based on the most recent bar's close).
3. If `realized + worst_case_open <= -daily_loss_limit_usd`, the strategy is halted for the day. Any new signals are rejected with reason `daily_limit_locked`. Open positions are flattened immediately.
4. The strategy resumes the next trading day automatically.

**The weekly limit logic:** same as daily, but on a rolling 5-trading-day window. When the weekly limit is hit, the strategy is halted for the rest of the week and resumes on Monday.

**The account drawdown limit:** if the account equity drops by more than `account_equity_drawdown_pct` from its all-time peak, the strategy is halted entirely until the human manually re-enables it. This is the soft kill switch that catches cases where the daily and weekly limits are being defeated by a slow grind down.

## Re-entry combined-risk validation

Per the conversation history and `CLAUDE.md`, planned re-entries are permitted when triggered by a fresh signal with combined target and combined risk defined before the second entry. The risk system enforces this:

```python
def validate_reentry(
    signal: Signal,
    parent_position: Position,
    instrument: Instrument,
    account_equity_usd: float,
    daily_realized_pnl_usd: float,
    daily_loss_limit_usd: float,
) -> ValidationResult:
    """Validate that a re-entry signal is acceptable.

    Required:
        1. signal.action == "reentry"
        2. signal.parent_trade_id matches an open position
        3. signal.combined_target_price is not None
        4. signal.combined_risk_usd is not None
        5. signal.side matches the parent position's side
        6. The combined position, if it loses its full combined risk,
           does not push the day's P&L past the daily loss limit.
        7. The combined risk does not exceed the per_trade_max_loss limit.

    If any check fails, return a result with passed=False and a reason.
    The engine logs the rejection and does not place the order.
    """
```

The combined risk calculation is the key check. If the parent position has a $200 stop and the re-entry adds another $200 of risk, the combined risk is $400. If the daily limit is $600 and the strategy is already down $300 for the day, the combined risk of $400 would push the worst case to $700, which exceeds the limit. The re-entry is rejected.

This is the friction that prevents the planned-re-entry pattern from accidentally becoming a martingale. The pattern is legitimate when the math works; the math has to work.

## Margin calculation: theoretical vs. actual

This is the section that comes from the mentor's specific knowledge about TradeStation and IBKR not honoring CME intercommodity spread margins. It matters operationally because it can make a paper-profitable pairs strategy unprofitable in your actual account.

**Theoretical exchange-spread margin.** What CME or CBOT charges on a pair when the legs are recognized as an intercommodity spread. For a yield curve trade like ZN/ZB, the exchange offers something like 70-80% margin offset between the legs because they know the legs offset each other's risk. Total margin for a 1-leg-each spread might be $2,500 instead of $4,000+ for the legs separately.

**Actual broker margin.** What TradeStation or IBKR retail actually charges. They treat the legs as independent positions, charge full margin on each, and ignore the exchange's offset. For the same ZN/ZB pair, the actual margin might be $4,000+. You're paying for capital efficiency you don't get.

**The dual-margin model:**

```python
# src/trading_research/risk/margins.py
from dataclasses import dataclass

@dataclass(frozen=True)
class MarginCalculation:
    legs: list[dict]              # per-leg contract count and instrument
    theoretical_margin_usd: float # what the exchange charges on a recognized spread
    actual_margin_usd: float      # what the broker actually charges
    capital_efficiency_ratio: float  # theoretical / actual
    spread_recognized: bool       # whether the legs form a recognized spread
    notes: str                    # explanation of how the numbers were derived

def compute_pair_margin(
    leg_a_symbol: str,
    leg_a_contracts: float,
    leg_b_symbol: str,
    leg_b_contracts: float,
    instruments: dict,
    broker: str = "tradestation",
) -> MarginCalculation:
    """Compute both theoretical and actual margin for a pair trade.

    Theoretical margin uses the CME/CBOT intercommodity spread tables for
    recognized spreads. If the pair is not a recognized spread, theoretical
    equals the sum of the legs (no offset).

    Actual margin is the broker's calculation, which currently ignores
    intercommodity offsets at TradeStation and IBKR retail.
    """
    leg_a = instruments[leg_a_symbol]
    leg_b = instruments[leg_b_symbol]

    # Naive sum (used for actual margin at retail brokers)
    actual = (
        leg_a.typical_initial_margin_usd * abs(leg_a_contracts) +
        leg_b.typical_initial_margin_usd * abs(leg_b_contracts)
    )

    # Theoretical: check if this is a recognized spread
    spread_key = canonical_spread_key(leg_a_symbol, leg_b_symbol)
    spread_table = load_intercommodity_spread_table()  # static yaml

    if spread_key in spread_table:
        offset_pct = spread_table[spread_key]["offset_pct"]
        theoretical = actual * (1 - offset_pct)
        recognized = True
    else:
        theoretical = actual
        recognized = False

    return MarginCalculation(
        legs=[
            {"symbol": leg_a_symbol, "contracts": leg_a_contracts, "margin": leg_a.typical_initial_margin_usd},
            {"symbol": leg_b_symbol, "contracts": leg_b_contracts, "margin": leg_b.typical_initial_margin_usd},
        ],
        theoretical_margin_usd=theoretical,
        actual_margin_usd=actual,
        capital_efficiency_ratio=theoretical / actual if actual > 0 else 1.0,
        spread_recognized=recognized,
        notes=(
            f"Spread {spread_key} recognized by exchange with {offset_pct:.0%} offset. "
            f"Broker {broker} does not honor intercommodity offsets at retail tier."
            if recognized else
            f"Spread {spread_key} not in intercommodity table. Treating as naive sum."
        ),
    )
```

**The intercommodity spread table.** Stored as a static YAML file in `configs/intercommodity_spreads.yaml`, listing the recognized spreads and their offset percentages. The data comes from CME's published spread tables and needs to be updated when CME revises them (rarely).

```yaml
# configs/intercommodity_spreads.yaml
ZN_ZB:    # 10-year vs 30-year Treasury
  exchange: CBOT
  offset_pct: 0.75
  description: "10-Year Note vs 30-Year Bond yield curve spread"
  ratio: [3, 2]   # 3 ZN to 2 ZB for hedge ratio neutral

ZN_ZF:    # 10-year vs 5-year
  exchange: CBOT
  offset_pct: 0.70
  description: "10-Year Note vs 5-Year Note"
  ratio: [1, 1]

ZC_ZS:    # corn vs soybeans
  exchange: CBOT
  offset_pct: 0.65
  description: "Corn vs Soybeans grain spread"

# ... etc
```

**The mentor's job here:** every time a pairs strategy is on the table, the mentor surfaces both numbers and says "this looks great with $2,500 of capital tied up, but at TradeStation it'll actually cost you $4,000 — does the strategy still pencil out at that capital efficiency, or are you better off doing this on a different pair where the offset is smaller and the broker doesn't matter as much?" The dual-margin output is what feeds that conversation.

## Drawdown-based sizing reduction

When a strategy is in drawdown, the volatility-targeting sizer can be configured to scale down position sizes. This is the mathematical implementation of "trade smaller when you're losing":

```yaml
risk_limits:
  drawdown_sizing_reduction:
    enabled: true
    threshold_pct: 0.05      # start reducing at 5% drawdown
    floor_pct: 0.50          # don't reduce below 50% of normal size
    recovery_threshold_pct: 0.02  # restore full size when drawdown recovers to 2%
```

**The math:** at 5% drawdown, sizes are at 100%. At 10% drawdown, sizes are at 50%. Linear interpolation between. Below 50%, sizes don't shrink further (the floor). When drawdown recovers above the recovery threshold, sizes return to 100%.

**Why this is opt-in rather than default:** drawdown-based sizing is a form of pro-cyclical risk management that some practitioners argue makes drawdowns longer (because you're trading smaller during the recovery, which is exactly when you want to be sized normally). Others argue it's the right way to preserve capital during periods when the strategy may be broken. Both positions are defensible. The default is off because the standing daily/weekly stops already provide a hard floor; this is for strategies where additional smoothing is desired.

## Kill switches

Three levels, each more drastic than the last:

**Strategy-level kill switch.** A single strategy is halted (no new positions, open positions exited) without affecting other strategies. Triggered by the daily limit, the weekly limit, the account drawdown limit, or manual intervention. The strategy resumes the next trading day (for daily) or the next week (for weekly) or never (for account drawdown, until the human re-enables).

**Instrument-level kill switch.** All strategies trading a specific instrument are halted. Used when the human suspects something is wrong with the data for that instrument, or when an external event (delisting, contract change, exchange notice) makes the instrument untradeable. Manual only.

**Account-level kill switch.** All strategies are halted. The nuclear option. Used when the human realizes something is fundamentally wrong and needs everything to stop now. Manual only, and the resumption requires an explicit confirmation in the chat.

The kill switches are implemented as a state file at `runs/.kill_switches.json` that the engine checks before processing any signal:

```json
{
  "account_kill": false,
  "instruments_killed": [],
  "strategies_killed": {
    "zn_macd_rev_v1": {
      "until": "2025-01-16T00:00:00Z",
      "reason": "daily_loss_limit",
      "triggered_at": "2025-01-15T14:32:11Z"
    }
  }
}
```

The file is read at the start of every signal processing call. Kill switches are not in-memory state — they survive restarts, which matters for any strategy running in a long-lived paper or live mode.

## Exposure tracking

For multi-strategy and multi-instrument operation, the risk system tracks exposure at several levels:

- **Per-strategy exposure:** total notional value of open positions for one strategy
- **Per-instrument exposure:** total notional across all strategies for one instrument
- **Per-asset-class exposure:** total notional across all bonds, all FX, etc.
- **Account exposure:** total notional across everything

Each level can have a configured cap. The default caps:

```yaml
exposure_caps:
  per_strategy_pct_equity: 0.20         # one strategy can't have positions > 20% of equity
  per_instrument_pct_equity: 0.15       # one instrument can't have > 15% of equity
  per_asset_class_pct_equity: 0.40      # one asset class can't have > 40% of equity
  total_pct_equity: 1.00                # total positions can't exceed 100% of equity (no leverage by default)
```

**Why these defaults:** they enforce diversification at multiple levels. A single strategy that dominates the account is a single point of failure. A single asset class that dominates means one regime change can wipe everything. The defaults are conservative and the human can loosen them with explicit overrides if a particular regime calls for concentration.

The exposure check happens at signal validation time. A signal that would push any exposure level past its cap is rejected with reason `exposure_cap_exceeded`.

## Integration with the backtest engine

The risk system is called by the backtest engine at three points:

1. **Before any new signal is converted to an order.** The risk system computes the size, checks all the limits, and either approves the signal with a size or rejects it with a reason. Rejected signals are logged but don't stop the backtest.

2. **At the open of every bar.** The risk system updates its tracking of realized and unrealized P&L, checks daily and weekly limits, and triggers strategy-level kill switches if any limit is breached.

3. **At end-of-day for single-instrument strategies.** The risk system enforces the EOD flat rule by emitting forced-exit signals for any open positions in single-instrument strategies. (This duplicates the engine's EOD enforcement; the duplication is intentional belt-and-suspenders.)

The risk system is **stateful** within a backtest run. It accumulates realized P&L, tracks open positions, maintains the kill switch state. At the start of each backtest run, the state is initialized fresh. Across walk-forward steps, the state typically resets between steps (each step is an independent test window), but this is configurable.

## Standing rules this skill enforces

1. **Volatility targeting is the default sizing model.** Every other model requires explicit configuration and the data scientist persona will note the choice in any output.
2. **Kelly sizing is forbidden by default.** It can be enabled with explicit configuration, but the data scientist persona will flag every backtest result that uses it.
3. **Daily and weekly loss limits are required for paper and live strategies.** Backtest-only strategies can omit them with a warning.
4. **Re-entries are validated for combined risk before the order is placed.** Without combined target and combined risk in the signal, the re-entry is rejected.
5. **Pair strategies compute both theoretical and actual margin.** The dual numbers are surfaced in any output.
6. **Exposure caps are enforced at signal validation time.** A signal that would breach any cap is rejected.
7. **Kill switches survive restarts.** They're stored in a state file, not in memory.
8. **The risk system rejects, the strategy doesn't override.** A strategy cannot bypass the risk system by sizing around its decisions.

## When to invoke this skill

Load this skill when the task involves:

- Implementing or modifying position sizing for a strategy
- Setting daily, weekly, or per-trade loss limits
- Computing margin requirements for a pair trade
- Designing exposure caps or asset-class limits
- Building or modifying kill switches
- Validating re-entries against combined risk constraints
- Any task where capital protection is the primary concern

Don't load this skill for:

- Strategy signal logic (use `backtesting`)
- Computing performance metrics (use `strategy-evaluation`)
- The math behind ATR or volatility estimators (use `indicators`)

## Open questions for build time

1. **The intercommodity spread table needs to be populated from CME's published data.** This is a one-time research task at build time; the agent should fetch the current spread tables from CME's website and populate `configs/intercommodity_spreads.yaml`. The values change rarely but they do change occasionally.
2. **Whether the volatility-targeting annualization factor should account for the actual session length** of each instrument or use a single global value. The current default assumes 390 bars per day (US equity hours); CME futures actually have ~1380 1m bars per day (23-hour Globex). Verify and tune at build time.
3. **Whether to track P&L in account currency or in instrument currency.** For Ibby's account this is the same (USD), but for any future non-USD instruments (e.g., Japanese yen-denominated contracts), the conversion needs to happen somewhere. Defer until non-USD instruments come online.
4. **How aggressively to enforce exposure caps for paper trading vs. backtesting.** Backtests can explore boundary conditions; live and paper should be hard-stopped at the caps. The current design enforces in both modes; if backtest exploration becomes painful, add a config flag to relax caps in backtest only.
