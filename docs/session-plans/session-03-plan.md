# Session 03 Plan — Stub

**Status:** Draft, written at the end of session 02. This is a hook list for
the next session, not a finished plan. Expand it when session 03 starts.

## Assumed inputs from session 02

- Project scaffold in place, tests green.
- Canonical bar schema locked (`BAR_SCHEMA`, version `bar-1m.v1`).
- Instrument registry exists with ZN only.
- TradeStation auth + client + paginated resumable downloader wired and
  unit-tested against fixtures.
- **Pre-requisite before session 03 starts:** Ibby has pasted real
  credentials into `.env`, run `scripts/verify_tradestation_auth.py`, and
  run a one-month ZN smoke pull. The downloader has produced a
  `data/raw/ZN_1m_2024-01-01_2024-01-31.parquet` that we can inspect.

If the smoke pull has not happened yet, session 03 starts there before
doing any of the work below.

## Goals for session 03 (in priority order)

1. **Calendar validation under `data-management`.** Use
   `pandas-market-calendars` with the CBOT/CME calendar to compute the
   *expected* set of 1-minute bars for a given date range and compare
   against the downloaded file. Output a `.quality.json` sidecar that
   records: calendar used, expected vs actual bar count, per-day gap
   summary, holiday/early-close accounting, and a pass/fail verdict.
   A file with no `.quality.json` or with a failing verdict is a tripwire
   — downstream code refuses to read it.

2. **Full 14-year ZN pull.** With the validator in place, run the real
   pull for ZN from 2010-2026. Measure duration, rate limit hits,
   row counts per year. This is the first time we find out what TradeStation
   actually gives us for long history. Be ready for surprises.

3. **Multi-contract back-adjusted continuous construction.** Replace
   the current `tradestation_continuous` method with our own stitching:
   download each quarterly contract (ZNH/ZNM/ZNU/ZNZ) individually, roll
   on the first business day of the expiration month, back-adjust
   historical prices by the additive price gap at each roll, and write
   both the adjusted primary and the unadjusted secondary parquet. The
   roll dates are recorded in metadata for auditability. The quant mentor
   and data scientist should both be in the loop for the design
   conversation — this is the step where we stop trusting TradeStation's
   hidden roll logic.

4. **Add 6A, 6C, 6N to the instrument registry.** Tick sizes, sessions,
   roll conventions. Pull one month of each as a sanity check. Do not
   pull full history for these in session 03 — this is registry expansion
   and smoke testing, not a long download.

5. **Slash command: `/data-quality-check`.** Runs the validator against a
   named dataset, prints the verdict and the largest gaps, and writes a
   human-readable HTML report next to the parquet. First entry in
   `.claude/commands/`.

## Explicitly out of scope for session 03

- Indicators. Not yet.
- Any strategy code.
- Resampling to higher timeframes (probably session 04 under
  `data-management`).
- Streaming data.
- Anything in `risk`, `backtest`, `eval`, `replay`, `live`.

## Open questions to resolve early in session 03

- What's the right roll date convention for ZN specifically? First business
  day of expiration month is a reasonable default, but check whether liquidity
  actually migrates earlier — some desks roll a few days before.
- For back-adjustment, which contract's price at the roll date do we use —
  the outgoing contract's settlement or the incoming contract's open? The
  convention affects the magnitude of the adjustment. Document the choice.
- How do we handle TradeStation's own `@ZN` continuous series going forward?
  Probably: keep it as a third parquet for cross-checking, but stop treating
  it as the source of truth.
