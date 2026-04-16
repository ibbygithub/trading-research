"""TradeStation REST client for historical bar requests.

One request, one window, no pagination. Pagination and resumability are
layered on top in ``download.py``. This module is deliberately thin so it
can be unit-tested against recorded fixtures without ever touching the
network.

Carry-overs from the legacy downloader:

- URL-encode ``@`` in continuous futures symbols (``@ZN`` -> ``%40ZN``).
- Never pass ``sessiontemplate`` for futures symbols — it's an equities-only
  knob and returns 404 on futures.
- Use date-range parameters (``firstdate``/``lastdate``), not ``barsback``,
  because our pagination unit is calendar-based.
- Honor ``Retry-After`` on 429.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from trading_research.utils.logging import get_logger

from .auth import TradeStationAuth
from .errors import (
    AuthenticationError,
    RateLimitError,
    SymbolNotFoundError,
    TradeStationError,
)

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.tradestation.com"
_REQUEST_TIMEOUT_SEC = 30.0
_POLITE_DELAY_SEC = 0.05  # 50ms between requests
_MAX_RETRIES = 5


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_retry(retry_state: RetryCallState) -> None:
    logger.warning(
        "tradestation_fetch_retry",
        attempt=retry_state.attempt_number,
        exception=type(retry_state.outcome.exception()).__name__
        if retry_state.outcome and retry_state.outcome.failed
        else None,
    )


class TradeStationClient:
    """Sync HTTP client for TradeStation historical bar endpoints."""

    def __init__(
        self,
        auth: TradeStationAuth,
        *,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.Client | None = None,
        polite_delay_sec: float = _POLITE_DELAY_SEC,
    ) -> None:
        self._auth = auth
        self._base_url = base_url.rstrip("/")
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=_REQUEST_TIMEOUT_SEC)
        self._polite_delay_sec = polite_delay_sec

    def __enter__(self) -> TradeStationClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def fetch_bar_window(
        self,
        symbol: str,
        first_date: datetime,
        last_date: datetime,
        *,
        interval: int = 1,
        unit: str = "Minute",
    ) -> list[dict[str, Any]]:
        """Fetch bars for one date window. Returns the raw ``Bars`` list.

        Raises:
            RateLimitError: 429 after retry budget exhausted.
            AuthenticationError: 401 from the API (token refresh did not help).
            SymbolNotFoundError: 404 from the API.
            TradeStationError: any other non-2xx response.
        """

        @retry(
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential_jitter(initial=1.0, max=60.0),
            retry=retry_if_exception_type((RateLimitError, httpx.TransportError)),
            before_sleep=_log_retry,
            reraise=True,
        )
        def _do() -> list[dict[str, Any]]:
            return self._fetch_once(symbol, first_date, last_date, interval, unit)

        bars = _do()
        if self._polite_delay_sec:
            time.sleep(self._polite_delay_sec)
        return bars

    def _fetch_once(
        self,
        symbol: str,
        first_date: datetime,
        last_date: datetime,
        interval: int,
        unit: str,
    ) -> list[dict[str, Any]]:
        sym_path = quote(symbol.upper(), safe="")
        url = f"{self._base_url}/v3/marketdata/barcharts/{sym_path}"
        params = {
            "interval": str(interval),
            "unit": unit,
            "firstdate": _iso_z(first_date),
            "lastdate": _iso_z(last_date),
        }
        headers = {"Authorization": f"Bearer {self._auth.get_access_token()}"}

        logger.debug(
            "tradestation_fetch_window",
            symbol=symbol,
            firstdate=params["firstdate"],
            lastdate=params["lastdate"],
        )
        resp = self._http.get(url, params=params, headers=headers)

        if resp.status_code == 429:
            retry_after_raw = resp.headers.get("Retry-After")
            retry_after: float | None = None
            if retry_after_raw is not None:
                try:
                    retry_after = float(retry_after_raw)
                except ValueError:
                    retry_after = None
            if retry_after and retry_after > 0:
                time.sleep(min(retry_after, 60.0))
            raise RateLimitError("HTTP 429 from TradeStation", retry_after=retry_after)

        if resp.status_code == 401:
            raise AuthenticationError(
                "HTTP 401 from TradeStation bars endpoint. Token may be invalid."
            )
        if resp.status_code == 404:
            raise SymbolNotFoundError(
                f"HTTP 404 for symbol {symbol!r}. Check the symbol exists on TradeStation."
            )
        if resp.status_code >= 400:
            body = resp.text[:500] if resp.content else ""
            raise TradeStationError(
                f"HTTP {resp.status_code} from TradeStation bars endpoint. Body: {body}"
            )

        data = resp.json() if resp.content else {}
        bars = data.get("Bars") if isinstance(data, dict) else None
        if bars is None:
            return []
        return list(bars)
