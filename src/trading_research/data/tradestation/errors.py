"""Typed exceptions for TradeStation API interactions.

These exist so call sites can catch specific failure modes rather than
doing string-matching on a generic ``HTTPError``. Every exception has a
short, actionable message; none of them contain secret values.
"""

from __future__ import annotations


class TradeStationError(Exception):
    """Base class for all TradeStation-related errors."""


class AuthenticationError(TradeStationError):
    """OAuth token acquisition or refresh failed.

    Raised when the refresh token is rejected, the client credentials are
    wrong, or the token endpoint returns an unexpected response. The call
    site should surface this to the human — re-authorization may be needed.
    """


class RateLimitError(TradeStationError):
    """HTTP 429 after retry budget exhausted."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SymbolNotFoundError(TradeStationError):
    """HTTP 404 from the bar endpoint — symbol doesn't exist or has no data."""


class IncompleteDownloadError(TradeStationError):
    """The API returned fewer bars than expected for reasons other than
    known calendar gaps. Raised by the pagination layer after all retries."""
