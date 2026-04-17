---
title: Trading Desk Master Plan
version: 2026-04
status: active
adopted: 2026-04-17
source: trading_desk_master_plan_for_claude_code.md (provided as chat content 2026-04-17)
amendments: see session-14 work-log (2026-04-17-14-30-summary.md)
---

# Trading Desk Master Plan — April 2026

## Mission

Grow a $25k CME futures account to $35k, then take regular draws. Capital preservation with consistent income, not maximum return. Single-instrument ZN mean reversion is the primary strategy. FX pairs (6A, 6C, 6N) add a second income stream once ZN is validated.

## Amended Positions (Session 14 Planning, 2026-04-17)

The master plan was reviewed by both personas (quant-mentor + data-scientist) in the Session 14 planning conversation. The following amendments were agreed:

1. **ML/portfolio layers frozen until walk-forward + DSR spine exists.** The original plan called for ML augmentation early. Amendment: ML work begins only after a rule-based strategy passes walk-forward validation with honest DSR. The DSR spine (Sessions 11+) is the prerequisite, not an optional layer.

2. **Event-day no-trade filter is a first-class regime filter for ZN.** Fed (FOMC), CPI, and NFP release days have structurally different microstructure (wider spreads, higher volatility, non-mean-reverting behavior). Explicitly excluding these days is not overfitting — it is market-structure awareness. Blackout filter slots into Session 17 (Regime Baselines).

3. **Look-ahead audit folds into Indicator Census (Session 15).** Not a separate session. The three Antigravity open risks are Session 15 scope.

4. **$500/week reframed as hypothesis-to-test, not target-to-hit.** The mentor's position: "targets create pressure that corrupts discipline." The research goal is to find strategies with honest positive expectancy. Whether $500/week is achievable is a hypothesis the validated strategy will answer, not a constraint the research must satisfy.

## Second Instrument: 6A (Aussie) over 6C (Canadian)

**Decision:** 6A recommended as the second instrument (after ZN is validated), over 6C.

**Reasoning (quant-mentor):** 6A has a cleaner mean-reversion character for futures-based strategies. The Canadian dollar (6C) is more closely dominated by crude oil — it behaves like a commodity contract with FX wrapping, not a pure FX instrument. 6A is more responsive to global risk sentiment and the China-commodity complex, which makes its mean-reversion cycles more regular and less driven by binary energy supply events. 6A also anchors naturally into future commodity-currency pairs work (6A/6N is a real desk spread).

**Pipeline readiness:** State B. Adding 6A requires a ~4-hour fix session before data can be pulled. See Session 14 pipeline robustness audit.

## Session Ordering (Active)

| # | Name | Status | Blocking |
|---|---|---|---|
| 14 | Repo Census, Pipeline Audit, Governance Bootstrap | **Active** | Session 15 |
| 15 | Indicator Census | Planned | Session 16 |
| 16 | Feature War Chest | Planned | Session 17 |
| 17 | Regime Baselines | Planned | First real strategy run |

Sessions are executed one at a time. `/clear` between sessions.

## Floor Plan (Canonical Roadmap)

```
PENTHOUSE  Live Execution
           Kill switches (strategy / instrument / account level)
           Connection heartbeat + alert
           Idempotent orders, broker fill reconciliation

FLOOR 4    Paper Trading + Draw Tracking
           Forward-test scaffold (same engine as backtest, live data feed)
           Account equity tracker, draw log
           Minimum 30 trading days paper period before any live capital

FLOOR 3    First Strategy + Forensic Report
           ZN mean reversion (MACD divergence + OFI confirmation)
           Walk-forward validation (not single train/test split)
           One-page HTML report: Calmar/DSR/Ulcer + confidence intervals
           Event-day blackout filter (FOMC/CPI/NFP)

FLOOR 2    Backtest Engine + Portfolio Risk          [COMPLETE — Sessions 08-09]
           BacktestEngine: next-bar-open fills, pessimistic TP/SL, time-stop
           Portfolio Manager: N strategy instances, combined margin tracking
           Risk module: account-level daily loss limit (YAML config), EOD flatten

FLOOR 1    Visual Forensics — The Cockpit            [COMPLETE — Session 07]
           Dash + Plotly replay app
           4-pane MTF: 5m / 15m / 60m / 1D
           Synced crosshairs, OFI subplot, VWAP+Bollinger overlays

GROUND     CLI Automation                            [COMPLETE — Session 06]
           verify / rebuild clean / rebuild features / inventory

FOUNDATION Data Pipeline                             [COMPLETE — Sessions 02-05]
           RAW/CLEAN/FEATURES for ZN, 14 years, 154+ tests passing

BASEMENT   Reporting Suite                           [COMPLETE — Sessions 10-13]
           Report v1 (Trader's Desk) + v2 (Risk Officer) — 24 sections
           Walk-forward runner, DSR/PSR, Monte Carlo, drawdown catalog
           Trials registry for honest deflated Sharpe
```

## Standing Rules (Non-Negotiable)

All rules from `CLAUDE.md` apply. Key ones for active work:

- **Fill model:** next-bar-open. Same-bar fills require written justification.
- **TP/SL ambiguous bars:** pessimistic by default (assume stop hit first).
- **Re-entries:** only on fresh, pre-defined signals with combined risk defined before entry. Averaging down without a fresh signal is forbidden.
- **Daily loss limit:** required before paper trading. YAML config.
- **Headline metric:** Calmar (not Sharpe). Sharpe reported but not centered.
- **Deflated Sharpe:** computed whenever multiple variants have been tested. Trials registry is the n_trials source.
- **Micro contracts:** default for any new strategy. Standard contracts require justification.
- **Pairs margin:** both CBOT theoretical spread margin AND retail broker margin always computed. Reduced spread margins do not apply at TradeStation retail.

## Annex: Deferred / Parallel Work

| Item | Unblocked by |
|---|---|
| 6A data pull + pipeline fix | Session 14 pipeline audit (done) |
| 6C/6N as third/fourth instruments | 6A validated first |
| Pairs framework (6A/6N, ZN/ZB) | ZN + 6A both validated |
| ML layer | Rule-based strategy validated with honest DSR |
| News/event blackout calendar automation | Session 17 regime baselines |
| Live execution kill switches | Penthouse phase only |
