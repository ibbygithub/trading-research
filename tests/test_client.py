"""Tests for TradeStationClient using httpx MockTransport."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from trading_research.data.tradestation.auth import TradeStationAuth
from trading_research.data.tradestation.client import TradeStationClient
from trading_research.data.tradestation.errors import (
    AuthenticationError,
    RateLimitError,
    SymbolNotFoundError,
    TradeStationError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tradestation_zn_sample.json"


@pytest.fixture
def auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TradeStationAuth:
    env = tmp_path / ".env"
    env.write_text(
        "TRADESTATION_CLIENT_ID=cid\n"
        "TRADESTATION_CLIENT_SECRET=csec\n"
        "TRADESTATION_REFRESH_TOKEN=rtok\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADESTATION_CLIENT_ID", "cid")
    monkeypatch.setenv("TRADESTATION_CLIENT_SECRET", "csec")
    monkeypatch.setenv("TRADESTATION_REFRESH_TOKEN", "rtok")

    def token_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "FAKE-ACCESS", "expires_in": 1200}
        )

    token_http = httpx.Client(transport=httpx.MockTransport(token_handler))
    return TradeStationAuth(env_path=env, http_client=token_http)


def _window():
    return (
        datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 35, tzinfo=UTC),
    )


def test_fetch_ok_returns_bars_list(auth: TradeStationAuth):
    payload = json.loads(FIXTURE.read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        # httpx decodes %40 back to @ in .url.path; check the raw bytes.
        assert b"%40ZN" in request.url.raw_path
        assert request.headers["Authorization"] == "Bearer FAKE-ACCESS"
        assert request.url.params["interval"] == "1"
        assert request.url.params["unit"] == "Minute"
        return httpx.Response(200, json=payload)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        bars = c.fetch_bar_window("@ZN", lo, hi)
    assert len(bars) == 3
    assert bars[0]["TimeStamp"] == "2024-01-02T14:30:00Z"


def test_fetch_404_raises_symbol_not_found(auth: TradeStationAuth):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        with pytest.raises(SymbolNotFoundError):
            c.fetch_bar_window("@BOGUS", lo, hi)


def test_fetch_401_raises_auth_error(auth: TradeStationAuth):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        with pytest.raises(AuthenticationError):
            c.fetch_bar_window("@ZN", lo, hi)


def test_fetch_429_then_success_retries(auth: TradeStationAuth):
    calls = {"n": 0}
    payload = {"Bars": []}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")
        return httpx.Response(200, json=payload)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        bars = c.fetch_bar_window("@ZN", lo, hi)
    assert bars == []
    assert calls["n"] == 3


def test_fetch_429_exhausts_retry_budget(auth: TradeStationAuth):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        with pytest.raises(RateLimitError):
            c.fetch_bar_window("@ZN", lo, hi)


def test_fetch_500_raises_tradestation_error(auth: TradeStationAuth):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        with pytest.raises(TradeStationError):
            c.fetch_bar_window("@ZN", lo, hi)


def test_empty_response_returns_empty_list(auth: TradeStationAuth):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with TradeStationClient(auth, http_client=http, polite_delay_sec=0) as c:
        lo, hi = _window()
        bars = c.fetch_bar_window("@ZN", lo, hi)
    assert bars == []
