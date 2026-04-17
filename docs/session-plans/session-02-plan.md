# Session 02 Plan — Scaffolding + Historical Bars Foundation

**Author:** Claude (Opus 4.6), drafted in session 01
**Date:** 2026-04-12
**Goal:** Stand the project up from an empty repo to a state where a 1-minute ZN download from TradeStation can be issued by a single command, lands as schema-conformant parquet in `data/raw/`, and has provenance metadata. Nothing further.

## Operating principles for session 02

- Agent does the work. Ibby provides credentials and the "go" signal.
- One topic, one session. We are *not* writing strategies, indicators, or backtests in session 02.
- Every step has a checkpoint where Ibby is shown a result and asked to approve before the next step begins.
- We follow the `project-layout` and `historical-bars` skills, with `data-management` consulted only for the canonical bar schema (so we don't paint ourselves into a corner on column names).

## Pre-flight (Ibby, before session starts)

1. Confirm `uv` is installed, or tell the agent to install it.
2. Have client_id, client_secret, and refresh_token from the legacy `config.py` accessible — they will be moved into a new `.env`.
3. Decide whether session 02 runs on Opus (recommended for the design conversation around schema + roll handling) or Sonnet (acceptable once the design is locked).

## Step 1 — Project scaffold (project-layout skill)

**What gets built:**

- `pyproject.toml` (uv-managed, Python 3.12)
- `uv.lock` via `uv sync`
- `.gitignore` with `.env`, `.venv/`, `data/`, `runs/`, `__pycache__/`, `*.parquet`, `.in_progress/`
- `.env.example` (committed) and `.env` (gitignored) with the four TradeStation variable names
- Directory tree per CLAUDE.md: `src/trading_research/{data,indicators,strategies,backtest,risk,eval,replay}/`, `configs/`, `data/{raw,clean,features}/`, `notebooks/`, `tests/`, `runs/`
- `src/trading_research/__init__.py` and stub `__init__.py` files in each subpackage
- `ruff.toml` or `[tool.ruff]` in pyproject, `pytest` config, `structlog` as a dependency
- A trivial `tests/test_smoke.py` that imports the package, so `uv run pytest` proves the install

**Dependencies pinned in pyproject.toml (initial set, only what Step 2 and 3 need):**
`httpx`, `tenacity`, `pandas`, `pyarrow`, `pandas-market-calendars`, `python-dotenv`, `structlog`, `pydantic`, `pytest`, `ruff`

**Checkpoint A:** `uv run pytest` is green. Ibby is shown the tree and the dependency list and approves before we move on.

## Step 2 — Canonical bar schema and instrument registry (data-management consulted)

This step is small but load-bearing: every later piece of code depends on these contracts.

**What gets built:**

- `src/trading_research/data/schema.py` — the canonical 1-minute bar schema as a pyarrow schema and a pydantic model. Fields: `timestamp_utc` (timestamp[ns, UTC], non-null), `timestamp_ny` (timestamp[ns, America/New_York], non-null), `open`, `high`, `low`, `close` (float64, non-null), `volume` (int64, non-null), `buy_volume` (int64, nullable), `sell_volume` (int64, nullable), `up_ticks` (int64, nullable), `down_ticks` (int64, nullable), `total_ticks` (int64, nullable). Schema versioning string is included in metadata.
- `configs/instruments.yaml` — initially populated with **ZN only**. Fields: root symbol, exchange, full name, tick size, tick value, contract value approx, session template hint, NY-time session windows (RTH and Globex), default roll convention (first business day of expiration month), CME group classification. 6A/6C/6N get added in a later session, not this one.
- `src/trading_research/data/instruments.py` — a typed loader for `instruments.yaml` returning an `InstrumentSpec` pydantic model. Hard fails if the YAML is missing a required field for an instrument we ask about.
- Unit tests for both: schema round-trip through parquet, instrument loader for ZN.

**Checkpoint B:** Tests green. Ibby reviews `instruments.yaml` and confirms the ZN spec matches what TradeStation will show. The data scientist persona reviews the schema for `buy_volume`/`sell_volume` nullability handling.

## Step 3 — TradeStation auth module (historical-bars skill)

This is the first piece that touches secrets. It is built carefully and tested in isolation before any bar requests are made.

**What gets built:**

- `src/trading_research/data/tradestation/auth.py` — a `TradeStationAuth` class:
  - Reads `TRADESTATION_CLIENT_ID`, `TRADESTATION_CLIENT_SECRET`, `TRADESTATION_REFRESH_TOKEN` from `.env` via `python-dotenv`.
  - `get_access_token()` returns a cached access token, refreshing via `POST https://signin.tradestation.com/oauth/token` with `grant_type=refresh_token` when expired or within a 60-second safety margin (token TTL is 1200 seconds per the docs).
  - Handles the rotating-refresh-token case: if the response includes a new `refresh_token`, the auth module rewrites `.env` in place and warns loudly in the log. (The legacy code intentionally does NOT do this; we change that behavior because the project policy is "the agent does the work.")
  - Never logs the token value. Never includes it in exception messages. Adds a unit test that asserts a logged record does not contain the token string.
- `src/trading_research/data/tradestation/errors.py` — typed exceptions: `AuthenticationError`, `RateLimitError`, `SymbolNotFoundError`, `IncompleteDownloadError`.
- A *manual* integration test (not run in CI): a short script that does one refresh and prints `len(token)` and `expires_at` — never the token itself.

**Checkpoint C:** Ibby pastes the three credentials into `.env`. Agent runs the manual integration test. Agent confirms refresh works without ever revealing the token. **No bar requests yet.**

## Step 4 — Bar fetch primitive (historical-bars skill)

**What gets built:**

- `src/trading_research/data/tradestation/client.py` — an async `TradeStationClient` wrapping `httpx.AsyncClient`:
  - `fetch_bar_window(symbol, unit, interval, first_date, last_date) -> list[dict]` — one request, no pagination, no retries (those are layered on top).
  - URL-encodes `@` for continuous symbols (carry-over from the legacy fix).
  - Always passes `interval=1`, `unit=Minute`, `firstdate`, `lastdate` in ISO-Z UTC.
  - Does NOT pass `sessiontemplate` for futures (carry-over from the legacy fix; this is correct).
  - Returns the raw `Bars` list from the response, or empty list if absent.
  - Wrapped in `tenacity` retry: exponential backoff with jitter, 5 attempts, honors `Retry-After` header on 429, polite 50ms gap between requests at the call-site layer (not in the retry).
  - Raises typed errors: `RateLimitError` after exhausting retries, `AuthenticationError` on 401 (so the layer above can refresh and retry once), `SymbolNotFoundError` on 404 with a sentinel message.
- `src/trading_research/data/tradestation/normalize.py` — converts the raw TradeStation `Bars` list into a DataFrame conforming to `schema.py`. Handles: parsing `TimeStamp` with `utc=True`, deriving `timestamp_ny`, mapping TS field names (`Open/High/Low/Close/TotalVolume/UpTicks/DownTicks/UpVolume/DownVolume/TotalTicks`) to schema names. Null-safe for fields TradeStation may omit.
- Unit tests against a recorded sample response (saved fixture, not a live API call).

**Checkpoint D:** Tests green. The data scientist persona reviews the normalization for any silent type coercions or missing-field handling that could mask bad data.

## Step 5 — Pagination and resumable download (historical-bars skill)

This is where the legacy downloader's design is replaced with the skill-conformant version.

**What gets built:**

- `src/trading_research/data/tradestation/download.py` — `download_historical_bars(symbol, start_date, end_date, ...)`:
  - Computes pagination windows. Default: 30 calendar days per window (well under the 57,600 bar cap and well under the 3-year date-range cap and well under the 500,000-minute bars-back cap).
  - For each window, calls `fetch_bar_window`, normalizes, accumulates.
  - Writes each window's bars to `data/raw/.in_progress/<run_id>/<window_index>.parquet` as it completes — so a crash mid-pull does not lose progress.
  - On resume (same `run_id`, or detected by hash of input params), skips windows that already have an `.in_progress` file.
  - After all windows complete, concatenates, sorts by `timestamp_utc`, drops duplicates on `timestamp_utc`, and writes the final parquet to `data/raw/<symbol>_1m_<start>_<end>.parquet`.
  - Writes a metadata JSON next to the parquet matching the `DownloadResult` shape from the skill (`rows_downloaded`, `expected_row_count_naive`, `api_calls_made`, `rate_limit_hits`, `duration_seconds`, `download_timestamp_utc`, `request_params`, etc.).
  - Performs *naive* gap analysis only — count expected vs actual, list largest gaps. Calendar validation is deferred to a later session under `data-management`.
  - Cleans up `.in_progress/<run_id>/` on success.
- **Continuous contract construction is deferred to session 03.** This session 02 deliverable will pull a single continuous symbol (`@ZN`) using TradeStation's own continuous-contract handling (which is what the legacy code does and what works today). Back-adjusted multi-contract stitching is a separate piece of work that needs design discussion.
- A CLI entry point: `python -m trading_research.data.tradestation.download --symbol ZN --start 2024-01-01 --end 2024-01-31` (small range for first end-to-end test).

**Checkpoint E:** Ibby approves the actual download. Agent runs a **one-month ZN pull** as the smoke test. Agent reports row count, naive gap stats, and points Ibby at the parquet + metadata files. The quant mentor reviews the row count against expectations for one month of CME Globex on ZN.

## Step 6 — End-of-session housekeeping

- Add a `README.md` section under `docs/` describing how to run the downloader (the *agent* runs it, but Ibby should be able to inspect what it does).
- Tag commit (Ibby decides commit cadence — agents do not push to `main`).
- File a session-03 plan stub for: full 14-year ZN pull, calendar validation via `data-management`, multi-contract back-adjusted stitching, and instrument additions for 6A/6C/6N.

## What is explicitly OUT OF SCOPE for session 02

- Indicators, strategies, backtests, evaluation metrics, replay app, ML modeling, risk management, live execution, streaming bars.
- Multi-contract back-adjustment / unadjusted secondary file. (Use TradeStation `@ZN` continuous for now, document the limitation.)
- Calendar validation against `pandas-market-calendars`. (Naive gap analysis only.)
- Higher-timeframe resampling.
- 6A/6C/6N instruments.
- Any conversion of the legacy `tradestation_interactive_downloader.py`. That orchestrator's job is replaced by the skill-conformant `download_historical_bars` + CLI; the legacy file stays in `legacy/` as historical reference and is not ported.

## Risk register for session 02

1. **Refresh token rotation.** If TradeStation has rotated Ibby's refresh token to expiring/30-min mode, the auth module must rewrite `.env`. We test for this path explicitly with the manual integration test.
2. **Session template / bar count expectations.** ZN's expected bars per Globex day is the sanity check at Checkpoint E. If the count is wildly off, we stop and investigate before considering Step 5 done.
3. **`@ZN` continuous symbol semantics.** TradeStation's continuous symbol uses their own roll convention, which may not match what we'd choose. Documented as a known limitation; full multi-contract stitching is session 03 work.
4. **Secrets leakage.** The auth unit test enforces that token strings never appear in logs. This is a non-negotiable gate.

## Personas at the end of session 02

- **Quant mentor:** "We can pull data. We can't trade yet. Don't get excited — the next session is where the schema gets stress-tested by reality and we find out what's actually in the bars."
- **Data scientist:** "We have provenance, naive gap counts, and a schema. We do *not* have calendar-validated data, and nothing in `data/raw/` should be touched by a strategy until `data-management` has promoted it to `data/clean/`. Enforce that with a tripwire in session 03."
