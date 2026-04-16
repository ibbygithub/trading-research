"""Manual integration test for TradeStation auth.

Run this ONCE after you've put real credentials in .env:

    uv run python scripts/verify_tradestation_auth.py

It will refresh an access token and print the token length and expiry.
It never prints the token itself.
"""

from __future__ import annotations

import time

from trading_research.data.tradestation.auth import TradeStationAuth
from trading_research.utils.logging import configure


def main() -> int:
    configure()
    auth = TradeStationAuth()
    t0 = time.time()
    token = auth.get_access_token()
    elapsed = time.time() - t0
    print("OK  refresh succeeded")
    print(f"    access_token length : {len(token)} chars")
    print(f"    refresh latency     : {elapsed:.3f}s")
    print("    (the token itself is intentionally not printed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
