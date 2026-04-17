"""TradeStation OAuth 2.0 refresh-token handling.

Design points:

- Secrets are read from ``.env`` via ``python-dotenv``, never from a Python
  module. The .env file is gitignored.
- Access tokens are held in memory only. TTL is ~1200s per the docs; we
  refresh when within ``_REFRESH_SAFETY_MARGIN_SEC`` of expiry.
- If the token endpoint returns a new refresh_token (rotating-refresh mode),
  we rewrite the .env file in place and log a warning. This contradicts the
  legacy downloader, which intentionally did not rewrite config.py — we
  change the behavior because project policy is "the agent does the work."
- Token values are never logged, never included in exception messages,
  never included in repr/str of this class.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

from trading_research.utils.logging import get_logger

from .errors import AuthenticationError

logger = get_logger(__name__)

_TOKEN_URL = "https://signin.tradestation.com/oauth/token"
_REFRESH_SAFETY_MARGIN_SEC = 60.0
_REQUEST_TIMEOUT_SEC = 30.0


@dataclass
class _TokenState:
    access_token: str
    expires_at_epoch: float
    # refresh_token is tracked here for rotation detection, but is never logged.
    refresh_token: str


class TradeStationAuth:
    """Handles OAuth 2.0 token lifecycle for TradeStation WebAPI v3.

    Read-through semantics: call ``get_access_token()`` whenever you need a
    token. The first call refreshes; subsequent calls return the cached
    token until it's near expiry, at which point a background refresh runs.
    Thread-/task-safe is out of scope for this module — callers should
    serialize token acquisition if needed.
    """

    def __init__(
        self,
        env_path: Path | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._env_path = (env_path or Path(".env")).resolve()
        load_dotenv(self._env_path, override=False)

        client_id = os.environ.get("TRADESTATION_CLIENT_ID", "").strip()
        client_secret = os.environ.get("TRADESTATION_CLIENT_SECRET", "").strip()
        refresh_token = os.environ.get("TRADESTATION_REFRESH_TOKEN", "").strip()

        missing = [
            name
            for name, val in (
                ("TRADESTATION_CLIENT_ID", client_id),
                ("TRADESTATION_CLIENT_SECRET", client_secret),
                ("TRADESTATION_REFRESH_TOKEN", refresh_token),
            )
            if not val
        ]
        if missing:
            raise AuthenticationError(
                f"Missing required env vars: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in the values."
            )

        self._client_id = client_id
        self._client_secret = client_secret
        self._initial_refresh_token = refresh_token
        self._state: _TokenState | None = None
        self._http = http_client  # if None, a short-lived client is used per call

    def __repr__(self) -> str:
        # Intentionally does not expose any token or secret material.
        has_token = self._state is not None
        return f"TradeStationAuth(client_id=***, has_access_token={has_token})"

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        now = time.time()
        if self._state is None or now >= (self._state.expires_at_epoch - _REFRESH_SAFETY_MARGIN_SEC):
            self._refresh()
        assert self._state is not None
        return self._state.access_token

    def _refresh(self) -> None:
        current_refresh = (
            self._state.refresh_token if self._state is not None else self._initial_refresh_token
        )
        data = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": current_refresh,
        }
        headers = {"content-type": "application/x-www-form-urlencoded"}

        logger.info("tradestation_auth_refresh_start")
        try:
            if self._http is not None:
                resp = self._http.post(
                    _TOKEN_URL, data=data, headers=headers, timeout=_REQUEST_TIMEOUT_SEC
                )
            else:
                with httpx.Client(timeout=_REQUEST_TIMEOUT_SEC) as client:
                    resp = client.post(_TOKEN_URL, data=data, headers=headers)
        except httpx.HTTPError as exc:
            # Scrub: never include request body in the error chain.
            raise AuthenticationError(
                f"Network error contacting TradeStation token endpoint: {type(exc).__name__}"
            ) from None

        if resp.status_code != 200:
            # Intentionally do not include resp.text — it may echo credentials
            # on some error paths. Only include the status code.
            raise AuthenticationError(
                f"Refresh failed: HTTP {resp.status_code}. Verify client_id, "
                f"client_secret, and refresh_token in .env."
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise AuthenticationError("Refresh response was not valid JSON.") from exc

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not access_token or not isinstance(expires_in, (int, float)):
            raise AuthenticationError(
                "Refresh response missing access_token or expires_in."
            )

        new_refresh = payload.get("refresh_token")
        if new_refresh and new_refresh != current_refresh:
            logger.warning(
                "tradestation_refresh_token_rotated",
                note="writing new refresh token to .env",
                env_path=str(self._env_path),
            )
            self._rewrite_refresh_token_in_env(new_refresh)
            effective_refresh = new_refresh
        else:
            effective_refresh = current_refresh

        self._state = _TokenState(
            access_token=access_token,
            expires_at_epoch=time.time() + float(expires_in),
            refresh_token=effective_refresh,
        )
        logger.info(
            "tradestation_auth_refresh_ok",
            expires_in_sec=float(expires_in),
            rotated=bool(new_refresh and new_refresh != current_refresh),
        )

    def _rewrite_refresh_token_in_env(self, new_value: str) -> None:
        """Rewrite the TRADESTATION_REFRESH_TOKEN line in the .env file in place.

        Preserves other lines, order, and comments. Creates the file if it
        does not exist (unlikely — we read it at init — but handled).
        """
        if not self._env_path.exists():
            self._env_path.write_text(
                f"TRADESTATION_REFRESH_TOKEN={new_value}\n", encoding="utf-8"
            )
            return

        lines = self._env_path.read_text(encoding="utf-8").splitlines()
        out: list[str] = []
        found = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("TRADESTATION_REFRESH_TOKEN="):
                out.append(f"TRADESTATION_REFRESH_TOKEN={new_value}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"TRADESTATION_REFRESH_TOKEN={new_value}")
        self._env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        # Also update the process environment so subsequent code sees it.
        os.environ["TRADESTATION_REFRESH_TOKEN"] = new_value
