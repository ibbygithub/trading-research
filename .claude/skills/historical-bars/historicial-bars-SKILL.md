---
name: historical-bars
description: Use when downloading historical bar data from TradeStation, handling API authentication, paginating large date ranges, managing rate limits, constructing continuous contracts across futures rolls, or writing raw downloaded data to disk. Invoke for any task involving the TradeStation REST API for historical market data, for re-downloading existing datasets with updated parameters, or for diagnosing gaps and quality issues in raw downloads. This skill writes to data/raw/ only — validation and promotion to data/clean/ is handled by data-management.
---

# Historical Bars

This skill owns the relationship between the project and TradeStation's historical bar API. Its job is to land clean, complete, schema-conformant 1-minute bar data on disk in `data/raw/`, with full provenance metadata, and to fail loudly when the data isn't right rather than silently producing something subtly wrong.

The principle: **the agent does the work, the human provides credentials and consent.** Pulling 14 years of 1-minute bar data for ZN involves authentication, pagination, rate limit management, contract roll handling, gap analysis, and parquet writing. None of that is the human's job. The human's job is to provide the API credentials once and to say "pull ZN from 2010 to today." Everything between those two events is the agent's responsibility.

## What this skill covers

- TradeStation REST API authentication (OAuth 2.0)
- Historical bar requests for futures contracts
- Pagination across large date ranges
- Rate limit handling and retry logic
- Continuous contract construction across futures rolls
- Buy/sell volume extraction where available
- Raw parquet writes to `data/raw/` with metadata
- Gap detection and reporting (validation against the calendar happens in `data-management`)
- Re-pulling and updating existing datasets

## What this skill does NOT cover

- Real-time/streaming data (see `streaming-bars`)
- Validating raw data against the trading calendar (see `data-management`)
- Resampling 1-minute bars to higher timeframes (see `data-management`)
- Computing indicators (see `indicators`)
- Anything about strategy logic or backtesting

## TradeStation API basics

TradeStation provides a REST API for historical market data via their WebAPI v3. The relevant endpoints for this skill:

- **OAuth 2.0 token endpoint** for authentication
- **`/marketdata/barcharts/{symbol}`** for historical bar requests
- **`/marketdata/symbols/{symbol}`** for instrument metadata (used to validate symbols and discover contract specs)

Key facts about the API that affect how this skill is built:

1. **Authentication is OAuth 2.0 with refresh tokens.** The initial flow requires the human to authorize the app via a browser redirect. After that, the agent can refresh access tokens silently. Refresh tokens are long-lived but not infinite; if a refresh fails, the agent prompts the human to re-authorize.

2. **Bar requests are limited per call.** TradeStation caps the number of bars returned per request (historically 57,600 bars). For 1-minute bars over a year, that's about 90 calls. For 14 years, about 1,260 calls. The skill paginates automatically.

3. **Rate limits exist.** TradeStation enforces per-second and per-minute request limits. The exact numbers vary by account tier and have changed over time. The skill uses exponential backoff with jitter on 429 responses and never assumes a specific rate limit value.

4. **Futures symbols include month and year codes.** `ZNH25` is the March 2025 10-Year Note contract. To get a continuous historical series, the skill must request multiple contract months and stitch them together at roll points.

5. **Buy/sell volume is in a separate field set** that requires explicitly requesting "extended" bar data. By default, TradeStation returns only OHLCV. The skill always requests extended data because order flow is a first-class field in our schema.

6. **Timestamps from TradeStation are in NY local time** (with DST handling on their side, supposedly correctly). The skill always parses with `utc=True` to force UTC awareness, then converts to NY for the dual-column write — never trusting that the API's tz handling matches ours.

7. **Holiday and session metadata is NOT in the bar response.** TradeStation just returns whatever bars exist. Determining whether a missing bar is a holiday gap or a real data hole is not this skill's job — it's `data-management`'s job, using `pandas-market-calendars`. This skill reports what it downloaded; the validator decides whether it's complete.

## Authentication flow

The agent handles OAuth 2.0 with the following sequence:

**First-time setup (one human interaction):**

1. Agent reads `.env` for `TRADESTATION_CLIENT_ID` and `TRADESTATION_CLIENT_SECRET`. If absent, agent informs the human these need to be obtained from the TradeStation developer portal and added to `.env`. Agent does not proceed until they exist.
2. Agent constructs the authorization URL with the required scopes (`MarketData ReadAccount`).
3. Agent prints the URL and asks the human to open it in a browser, authorize the app, and paste the redirect URL (which contains the auth code) back into the chat.
4. Agent exchanges the auth code for an access token + refresh token.
5. Agent writes the refresh token to `.env` as `TRADESTATION_REFRESH_TOKEN`. The access token is held in memory only (it expires in ~20 minutes anyway).

**Subsequent runs:**

1. Agent reads the refresh token from `.env`.
2. Agent exchanges the refresh token for a fresh access token.
3. Agent makes API calls with the access token.
4. If the access token expires mid-session, agent silently refreshes and retries.
5. If the refresh token itself is rejected (rare, but happens after long inactivity), agent informs the human and walks them through re-authorization.

The human's involvement is exactly two events: pasting credentials into `.env` once, and pasting an auth redirect URL once. After that, the agent handles auth without bothering them.

**Implementation skeleton:**

```python
# src/trading_research/ingest/tradestation.py
import os
from pathlib import Path
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

class TradeStationAuth:
    """Handles OAuth 2.0 token lifecycle for TradeStation WebAPI v3."""

    TOKEN_URL = "https://signin.tradestation.com/oauth/token"
    AUTH_URL = "https://signin.tradestation.com/authorize"

    def __init__(self, env_path: Path = Path(".env")):
        self.env_path = env_path
        self.client_id = os.environ["TRADESTATION_CLIENT_ID"]
        self.client_secret = os.environ["TRADESTATION_CLIENT_SECRET"]
        self.refresh_token: Optional[str] = os.environ.get("TRADESTATION_REFRESH_TOKEN")
        self._access_token: Optional[str] = None
        self._access_token_expires_at: float = 0

    async def get_access_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        # ... full implementation by agent at build time
```

**Critical: secrets handling.** The `.env` file is gitignored. The skill never logs secret values. The skill never includes secrets in error messages. If an API error response contains a header with credentials echoed back (some APIs do this), the skill scrubs them before logging.

## Historical bar requests

The skill exposes a single high-level function and several lower-level helpers. The high-level function is what other skills and CLI commands use; the lower-level helpers are for advanced cases.

```python
async def download_historical_bars(
    symbol: str,                       # canonical root symbol, e.g. "ZN"
    start_date: date,                  # inclusive
    end_date: date,                    # inclusive
    timeframe: str = "1m",             # only "1m" supported by this skill
    output_dir: Path = Path("data/raw"),
    continuous_method: str = "back_adjusted",  # or "ratio_adjusted" or "unadjusted"
    request_extended: bool = True,     # always True; here for explicitness
) -> DownloadResult:
    """Download historical bars for a futures contract over a date range.

    Resolves the contract roll schedule, requests bars for each contract
    month, stitches them together according to continuous_method, writes
    a parquet file to output_dir, and writes a metadata JSON file alongside.

    Returns a DownloadResult with paths and stats. Does NOT validate the
    result against the trading calendar — that's data-management's job.

    Raises:
        AuthenticationError: if OAuth fails and re-auth is needed
        RateLimitError: if rate limits exceed retry budget
        SymbolNotFoundError: if the symbol doesn't exist on TradeStation
        IncompleteDownloadError: if the API returned fewer bars than expected
            for reasons other than known calendar gaps
    """
```

**Why timeframe is restricted to 1m here:** the data-management skill is explicit that 1-minute is the canonical base resolution and all higher timeframes come from resampling. There's no point in this skill supporting 5-minute downloads when the answer would always be "download 1m and resample." Restricting the API surface prevents accidental violations of the resampling rule.

**The DownloadResult dataclass:**

```python
@dataclass(frozen=True)
class DownloadResult:
    parquet_path: Path
    metadata_path: Path
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    rows_downloaded: int
    expected_row_count_naive: int      # bars/day * trading_days, no calendar awareness
    api_calls_made: int
    rate_limit_hits: int
    duration_seconds: float
    contract_months_used: list[str]    # e.g. ["ZNH25", "ZNM25", "ZNU25", "ZNZ25"]
    roll_dates: list[date]             # dates where contract changed
    continuous_method: str
    api_version: str
    download_timestamp_utc: datetime
```

**The metadata JSON file:** for every parquet write, a JSON file is written next to it with the full DownloadResult plus the request parameters. This is the provenance trail. Six months from now when something looks weird in a backtest, the metadata file tells you exactly what was downloaded, when, and how.

```json
{
  "parquet_path": "data/raw/ZN_1m_2010-01-01_2024-12-31.parquet",
  "symbol": "ZN",
  "timeframe": "1m",
  "start_date": "2010-01-01",
  "end_date": "2024-12-31",
  "rows_downloaded": 5234567,
  "expected_row_count_naive": 5400000,
  "api_calls_made": 1247,
  "rate_limit_hits": 3,
  "duration_seconds": 1842.4,
  "contract_months_used": ["ZNH10", "ZNM10", "ZNU10", ...],
  "roll_dates": ["2010-02-26", "2010-05-28", ...],
  "continuous_method": "back_adjusted",
  "api_version": "v3",
  "download_timestamp_utc": "2025-01-15T03:42:11Z",
  "tradestation_account_id": "REDACTED",
  "request_params": {
    "interval": 1,
    "unit": "Minute",
    "session_template": "USEQPreAndPost",
    "extended": true
  }
}
```

## Pagination

TradeStation caps bars per request. The skill paginates by date range, not by bar count, because bar counts vary with session length and the cap math is annoying. A safe pagination unit for 1-minute bars on CME futures is 30 days per request, which gives roughly 30,000 bars (well under any historical cap).

**The pagination loop:**

```
for each contract_month in contract_months:
    for each 30-day window in (contract_start, contract_end):
        request bars for this window
        accumulate into a list
        sleep briefly to be polite (50ms between requests by default)
    deduplicate any overlapping bars at window boundaries
    write the contract's bars to a temporary file
stitch contracts together into the continuous series
write the final parquet
```

**Resumability:** if a download fails partway through (network blip, rate limit, etc.), the skill should be able to resume from where it left off, not restart from scratch. Implementation: write each contract month's bars to a temporary parquet under `data/raw/.in_progress/<run_id>/` as they complete. On retry, check what's already on disk and skip those windows. Clean up `.in_progress/` only after the final stitched parquet is written successfully.

This matters because a 14-year ZN download is roughly 30 minutes wall clock under good conditions, and you don't want to start over because of one network hiccup.

## Rate limits and retry

TradeStation returns 429 (Too Many Requests) when rate limits are hit. The skill handles this with:

1. **Exponential backoff with jitter** via `tenacity`. Initial backoff 1 second, max 60 seconds, jitter ±25%.
2. **Max retries per request: 5.** Beyond that, the rate limit is treated as an outage and surfaced to the human with a "wait and retry" message.
3. **Honor `Retry-After` headers** when present. TradeStation sometimes includes them.
4. **Rate limit hit counter** in the metadata file. If a download has 100+ rate limit hits, that's diagnostic information worth surfacing.

```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type((httpx.HTTPError, RateLimitError)),
    reraise=True,
)
async def _request_bar_window(self, ...) -> list[dict]:
    ...
```

**Polite default delay:** 50 milliseconds between requests. This is well under any documented rate limit and means a 1,247-call download adds about a minute of polite delay total. Negligible.

## Continuous contract construction

Futures contracts expire. To get a continuous historical series suitable for backtesting, the skill must stitch consecutive contract months together at roll points. Three methods are supported:

**Back-adjusted (default).** When rolling from contract A to contract B at the roll date, all of contract A's prior history is shifted by `(B's price at roll - A's price at roll)`. The result is a continuous series where the most recent contract's prices are unchanged and historical prices are adjusted to remove the roll gap. This is the standard for technical analysis and backtesting because indicators (moving averages, etc.) compute correctly across the join.

The downside: historical "prices" in a back-adjusted series are not the prices that actually traded on those dates. They're synthetic. This matters for absolute-price-dependent strategies (like "buy when price > $100") but doesn't matter for relative-move strategies (like "buy when RSI < 30").

**Ratio-adjusted.** Like back-adjusted, but the adjustment is multiplicative rather than additive. Better for very long historical series where compounding the additive adjustments creates large distortions. Slightly less common.

**Unadjusted.** Contracts are concatenated with no adjustment. The series has visible gaps at every roll date. Use only for inspection or for strategies that explicitly handle the gaps. Never the default.

**Roll date selection:** the skill rolls on a fixed schedule, defaulting to the **first business day of the expiration month** for most CME futures. This is configurable per instrument in `instruments.yaml` if a particular contract has a different convention.

The choice of roll date affects strategy performance. A backtest that rolls on a different schedule than the live trading will roll on is making a subtle assumption error. The roll dates used are recorded in the metadata file so this is auditable.

**Storing the unadjusted series alongside:** the skill always writes the back-adjusted (or whatever the default) continuous series as the primary parquet, AND writes the unadjusted series as a secondary file. This makes it possible to verify any backtest result against unadjusted prices when needed.

```
data/raw/
├── ZN_1m_2010-01-01_2024-12-31.parquet              # primary, back-adjusted
├── ZN_1m_2010-01-01_2024-12-31.metadata.json
├── ZN_1m_2010-01-01_2024-12-31.unadjusted.parquet   # secondary, unadjusted
└── ZN_1m_2010-01-01_2024-12-31.unadjusted.metadata.json
```

## Gap detection (this skill's role)

After a download completes, the skill performs a *naive* gap analysis: count expected bars vs actual bars, identify date ranges with no bars at all, and report them in the metadata file. This is NOT validation against the trading calendar — that's `data-management`'s responsibility. This is just a sanity check that surfaces obvious problems immediately.

```python
# In the DownloadResult metadata:
{
  "naive_gap_analysis": {
    "expected_bars_naive": 5400000,
    "actual_bars": 5234567,
    "missing_bars_naive": 165433,
    "largest_gaps": [
      {"start": "2012-10-29T00:00:00Z", "end": "2012-10-31T23:59:00Z", "duration_hours": 72, "likely_cause": "Hurricane Sandy market closure"},
      {"start": "2020-04-20T00:00:00Z", "end": "2020-04-20T23:59:00Z", "duration_hours": 24, "likely_cause": "unknown"}
    ]
  }
}
```

The "likely cause" field is heuristic — known major closures (9/11, Sandy, COVID circuit breakers) get labeled. Everything else is "unknown" and gets resolved by `data-management`'s calendar validation.

**The agent never decides whether a gap is acceptable.** It downloads, reports what it found, and hands off to validation. If validation says the data is unusable, the human is informed and asked how to proceed.

## Re-pulling and updating

A common operation is "extend the existing ZN dataset to include the most recent month." The skill supports this without re-downloading everything:

```python
async def update_historical_bars(
    symbol: str,
    output_dir: Path = Path("data/raw"),
    through_date: Optional[date] = None,  # defaults to yesterday
) -> DownloadResult:
    """Extend an existing dataset to a more recent date.

    Reads the most recent existing parquet for this symbol, finds its
    end date, downloads bars from there to through_date, appends to the
    existing parquet, and updates the metadata file with both the original
    and update download events.
    """
```

This is the operation the agent runs daily (or whenever the human says "update the data"). The first call might be a multi-hour 14-year initial pull. Subsequent calls are seconds-to-minutes.

**Re-validation after update:** any update invalidates the existing data quality report. The data-management skill must re-validate after an update completes. The skill enforces this by deleting the existing `.quality.json` file when an update happens, so any subsequent code that tries to read the dataset gets a "not validated" error until validation runs.

## Standing rules this skill enforces

1. **Never write to `data/clean/` or `data/features/`.** This skill writes only to `data/raw/`. Promotion happens in `data-management`.
2. **Always request extended bar data.** Buy/sell volume is a first-class field; downloading without it would create a permanent hole in the schema for that date range.
3. **Always parse timestamps with `utc=True`.** Never trust the API's tz handling silently.
4. **Always write a metadata file alongside every parquet.** No metadata = no provenance = the data is suspect.
5. **Never expose secrets in logs, errors, or user-facing messages.** API tokens, refresh tokens, account IDs are all scrubbed.
6. **Never silently re-download what already exists.** If a parquet for the requested range is already on disk, the skill asks the human whether to overwrite, append, or skip. Unless the call is explicitly `update_historical_bars`, in which case appending is the default behavior.
7. **Never claim a download is complete if the API returned errors.** A partial download is reported as partial, not as complete-with-gaps.
8. **The agent does the work.** Auth flows, pagination, retries, file management — all automatic. The human's only involvements are providing credentials once and approving the initial OAuth redirect once.

## When to invoke this skill

Load this skill when the task involves:

- Downloading historical bar data for the first time on a new symbol
- Extending an existing dataset to a more recent date
- Diagnosing why a dataset has unexpected gaps or row counts
- Setting up TradeStation API credentials and OAuth flow
- Re-downloading existing data with different parameters (different roll method, different date range)
- Any direct interaction with the TradeStation REST API for historical data

Don't load this skill for:

- Streaming/real-time data (use `streaming-bars`)
- Reading or analyzing data that's already on disk (use `data-management`)
- Computing indicators or running backtests (use those skills)

## Open questions for build time

1. **Account tier and exact rate limits.** Ibby's account tier determines actual rate limits; the conservative defaults in this skill should hold for any tier, but if downloads are slow, tuning the polite delay is the lever.
2. **Session template choice.** TradeStation has multiple session templates (`USEQPreAndPost`, `USEQ`, `Default`, etc.). For CME futures, the right one is the one that includes the full Globex session. Verify at build time with a test pull on ZN and confirm the bar count matches expectations.
3. **Historical depth limits.** TradeStation's historical depth varies by instrument and account tier. ZN may have 14+ years available; an obscure micro contract may have only a few years. The skill should query the symbol metadata first to determine the actual available range, and warn if the requested range exceeds it.
4. **Roll method per asset class.** Default is back-adjusted. Bonds and FX may want this; ags may want unadjusted with explicit roll handling because seasonal patterns matter. Decide per-instrument when those instruments come online.
