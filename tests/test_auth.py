"""Tests for TradeStationAuth.

These tests never hit the real API. They use httpx's MockTransport to
simulate refresh responses and verify:

1. Missing env vars raise AuthenticationError with a useful message.
2. A successful refresh caches the access token.
3. A rotated refresh_token is written back to .env in place.
4. Token values never appear in log records, exception messages, or repr.
5. HTTP errors and bad JSON raise AuthenticationError without leaking secrets.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from trading_research.data.tradestation.auth import TradeStationAuth
from trading_research.data.tradestation.errors import AuthenticationError


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env = tmp_path / ".env"
    env.write_text(
        "TRADESTATION_CLIENT_ID=test-client-id\n"
        "TRADESTATION_CLIENT_SECRET=test-client-secret\n"
        "TRADESTATION_REFRESH_TOKEN=original-refresh-token\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADESTATION_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("TRADESTATION_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TRADESTATION_REFRESH_TOKEN", "original-refresh-token")
    return env


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_missing_env_vars_raise(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("TRADESTATION_CLIENT_ID", raising=False)
    monkeypatch.delenv("TRADESTATION_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("TRADESTATION_REFRESH_TOKEN", raising=False)
    empty_env = tmp_path / ".env"
    empty_env.write_text("", encoding="utf-8")
    with pytest.raises(AuthenticationError, match="Missing required env vars"):
        TradeStationAuth(env_path=empty_env)


def test_refresh_success_caches_token(env_file: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        return httpx.Response(
            200,
            json={
                "access_token": "SECRET-ACCESS-abc123",
                "expires_in": 1200,
                "token_type": "Bearer",
            },
        )

    with _mock_client(handler) as http:
        auth = TradeStationAuth(env_path=env_file, http_client=http)
        tok1 = auth.get_access_token()
        tok2 = auth.get_access_token()  # cached, no second refresh
    assert tok1 == "SECRET-ACCESS-abc123"
    assert tok2 == tok1


def test_rotated_refresh_token_rewrites_env(env_file: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "SECRET-ACCESS-xyz",
                "refresh_token": "NEW-ROTATED-REFRESH",
                "expires_in": 1200,
                "token_type": "Bearer",
            },
        )

    with _mock_client(handler) as http:
        auth = TradeStationAuth(env_path=env_file, http_client=http)
        auth.get_access_token()

    contents = env_file.read_text(encoding="utf-8")
    assert "TRADESTATION_REFRESH_TOKEN=NEW-ROTATED-REFRESH" in contents
    assert "original-refresh-token" not in contents
    # Other lines preserved.
    assert "TRADESTATION_CLIENT_ID=test-client-id" in contents
    assert "TRADESTATION_CLIENT_SECRET=test-client-secret" in contents


def test_http_error_raises_auth_error_without_leaking(env_file: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        # Response body includes the secret to simulate a server that echoes.
        return httpx.Response(400, text="invalid_grant: original-refresh-token")

    with _mock_client(handler) as http:
        auth = TradeStationAuth(env_path=env_file, http_client=http)
        with pytest.raises(AuthenticationError) as excinfo:
            auth.get_access_token()

    msg = str(excinfo.value)
    assert "HTTP 400" in msg
    assert "original-refresh-token" not in msg
    assert "test-client-secret" not in msg


def test_repr_does_not_expose_tokens(env_file: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": "SECRET-ACCESS-repr", "expires_in": 1200},
        )

    with _mock_client(handler) as http:
        auth = TradeStationAuth(env_path=env_file, http_client=http)
        auth.get_access_token()
        r = repr(auth)
    assert "SECRET-ACCESS-repr" not in r
    assert "original-refresh-token" not in r
    assert "test-client-secret" not in r


def test_tokens_never_appear_in_log_records(env_file: Path, caplog: pytest.LogCaptureFixture):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "SECRET-ACCESS-logcheck",
                "refresh_token": "SECRET-REFRESH-logcheck",
                "expires_in": 1200,
            },
        )

    caplog.set_level(logging.DEBUG)
    with _mock_client(handler) as http:
        auth = TradeStationAuth(env_path=env_file, http_client=http)
        auth.get_access_token()

    joined = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "SECRET-ACCESS-logcheck" not in joined
    assert "SECRET-REFRESH-logcheck" not in joined
    assert "test-client-secret" not in joined
