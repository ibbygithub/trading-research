#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TradeStation Historical Downloader (uses config.py)
--------------------------------------------------
- Reads OAuth info from config.py (client_id, client_secret, refresh_token)
  and refreshes an access token. If TS_TOKEN env var is set, it is used instead.
- Fixes classic 404s for continuous futures:
    * URL-encodes '@' in path (e.g., @GC -> %40GC)
    * Uses date-range (firstdate/lastdate) — DO NOT send 'bars' with this style
    * Skips 'sessiontemplate' for futures (equities-only knob)
    * Falls back to v2 if v3 slice returns 404
    * Honors 429 Retry-After, polite rate limiting
- Segments intraday requests to respect ~57,600 bars/request cap.
- Writes per-year CSVs + .meta.json with UTC-aware timestamps.

Usage example (PowerShell / bash):
  python tradestation_downloader.py --symbol @GC --timeframe 60m \
    --start-year 2011 --end-year 2011 \
    --outdir /path/to/per_year/60m --verbose
"""

import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd
from urllib.parse import quote

# ---------- Constants ----------
DEFAULT_BASE_URL = "https://api.tradestation.com"
OAUTH_TOKEN_URL = "https://signin.tradestation.com/oauth/token"

DEFAULT_INTRADAY_CAP = 57600       # intraday bars/request ceiling
DEFAULT_SEGMENT_DAYS = 30          # will auto-size under cap anyway
REQUEST_TIMEOUT = 30               # seconds
SLICE_DELAY_SEC = 1                # be polite between slices

# ---------- Logging ----------
def setup_logger(verbose: bool = True) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

# ---------- Helpers ----------
def parse_timeframe(tf: str) -> Tuple[str, int, str]:
    s = tf.strip().lower().replace(" ", "")
    if s.endswith("m") and s[:-1].isdigit():
        return "Minute", int(s[:-1]), s
    if s in ("1d", "d", "daily", "day"):
        return "Daily", 1, "1d"
    if s in ("1w", "w", "weekly", "week"):
        return "Weekly", 1, "1w"
    if s in ("1mo", "mo", "monthly", "month"):
        return "Monthly", 1, "1mo"
    raise SystemExit(f"Unrecognized timeframe: {tf!r}")

def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def bars_per_day_for_minute(interval: int) -> int:
    return max(1, (24 * 60) // max(1, interval))

def compute_segment_days(unit: str, interval: int, intraday_cap: int, default_days: int) -> int:
    if unit != "Minute":
        return 36500  # single-shot for D/W/M
    bpd = bars_per_day_for_minute(interval)
    cap_days = max(1, intraday_cap // bpd)
    return max(1, min(default_days, cap_days))

def daterange_chunks(start: datetime, end: datetime, days: int):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt + timedelta(seconds=1)

# ---------- Auth (env or config.py) ----------
def refresh_access_token_via_config() -> str:
    """
    Import config.py (must be on PYTHONPATH or in working dir) and refresh access token.
    config.py must define: client_id, client_secret (optional), refresh_token
    """
    try:
        import config as _cfg  # your config.py
    except Exception as e:
        raise SystemExit("Could not import config.py. Ensure it is alongside this script or on PYTHONPATH.") from e

    client_id = getattr(_cfg, "client_id", "").strip()
    client_secret = getattr(_cfg, "client_secret", "").strip()
    refresh_token = getattr(_cfg, "refresh_token", "").strip()
    if not client_id or not refresh_token:
        raise SystemExit("config.py must define client_id and refresh_token (client_secret optional).")

    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret

    headers = {"content-type": "application/x-www-form-urlencoded"}
    resp = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise SystemExit(f"Refresh failed: HTTP {resp.status_code} {resp.text[:300]}")
    j = resp.json()
    atok = j.get("access_token")
    if not atok:
        raise SystemExit("Refresh succeeded but no access_token returned.")
    # NOTE: if a rotated refresh_token is returned, we do NOT overwrite config.py per your request.
    return atok

def resolve_access_token() -> str:
    env_tok = os.getenv("TS_TOKEN")
    if env_tok:
        logging.info("Using access token from TS_TOKEN environment variable.")
        return env_tok
    logging.info("TS_TOKEN not set; refreshing access token via config.py")
    return refresh_access_token_via_config()

# ---------- HTTP ----------
def ts_request(base_url: str, symbol: str, params: Dict[str, str], headers: Dict[str, str]) -> requests.Response:
    """
    GET v3; on 404, retry v2. Honor 429 Retry-After.
    """
    sym_path = quote(symbol.upper(), safe="")  # encode '@' for continuous symbols
    url_v3 = f"{base_url}/v3/marketdata/barcharts/{sym_path}"

    s = requests.Session()
    r = s.get(url_v3, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After")
        try:
            wait_s = int(retry_after) if retry_after else 2
        except Exception:
            wait_s = 2
        logging.warning(f"429 received; waiting {wait_s}s then retrying v3 slice...")
        time.sleep(wait_s)
        r = s.get(url_v3, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    if r.status_code == 404:
        url_v2 = f"{base_url}/v2/marketdata/barcharts/{sym_path}"
        logging.warning(f"404 on v3; retrying slice on v2: {url_v2}")
        r = s.get(url_v2, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    r.raise_for_status()
    return r

def fetch_slice(base_url: str,
                symbol: str,
                unit: str,
                interval: int,
                lo: datetime,
                hi: datetime,
                access_token: str,
                equities_session_template: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch one date-window slice using date-range params only.
    Skips 'sessiontemplate' for futures (symbols starting with '@').
    """
    params: Dict[str, str] = {
        "interval": str(interval if unit == "Minute" else 1),
        "unit": unit,
        "firstdate": iso_z(lo),
        "lastdate":  iso_z(hi),
    }
    if not symbol.startswith("@") and equities_session_template:
        params["sessiontemplate"] = equities_session_template

    headers = {"Authorization": f"Bearer {access_token}"}
    resp = ts_request(base_url, symbol, params, headers)

    data = resp.json() if resp.content else {}
    bars = data.get("Bars") if isinstance(data, dict) else None
    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(bars)

    # Normalize TimeStamp (UTC-aware)
    if "TimeStamp" not in df.columns:
        raise RuntimeError("Response missing 'TimeStamp' field.")
    df["TimeStamp"] = pd.to_datetime(
        df["TimeStamp"].astype(str).str.rstrip("Z"),
        format="%Y-%m-%dT%H:%M:%S",
        utc=True,
        errors="coerce",
    )
    df = df.dropna(subset=["TimeStamp"]).reset_index(drop=True)

    # Normalize OHLCV-ish columns
    want_cols = [
        "Open", "High", "Low", "Close",
        "TotalVolume", "DownTicks", "DownVolume",
        "TotalTicks", "UpTicks", "UpVolume",
    ]
    for c in want_cols:
        if c not in df.columns:
            if c == "TotalVolume" and "Volume" in df.columns:
                df["TotalVolume"] = df["Volume"]
            else:
                df[c] = 0

    # Epoch (UTC seconds)
    df["Epoch"] = (df["TimeStamp"].astype("int64") // 10**9)

    return df[["TimeStamp", "Epoch"] + want_cols]

# ---------- Year fetch ----------
def fetch_year(base_url: str,
               symbol: str,
               unit: str,
               interval: int,
               year: int,
               segment_days: int,
               access_token: str,
               equities_session_template: Optional[str] = None) -> pd.DataFrame:
    y0 = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    y1 = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    if unit != "Minute":
        return fetch_slice(base_url, symbol, unit, interval, y0, y1, access_token, equities_session_template)

    frames: List[pd.DataFrame] = []
    for lo, hi in daterange_chunks(y0, y1, segment_days):
        logging.info(f"Fetching {symbol} {interval}{'m' if unit=='Minute' else ''} slice {iso_z(lo)} -> {iso_z(hi)}")
        try:
            df = fetch_slice(base_url, symbol, unit, interval, lo, hi, access_token, equities_session_template)
        except requests.HTTPError as e:
            logging.error(f"HTTP error on slice {iso_z(lo)}->{iso_z(hi)}: {e}")
            continue
        if not df.empty:
            frames.append(df)
        time.sleep(SLICE_DELAY_SEC)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("TimeStamp", kind="mergesort").drop_duplicates(subset=["TimeStamp"], keep="last").reset_index(drop=True)
    return out

# ---------- Writing ----------
def write_outputs(outdir: Path, symbol: str, tf_token: str, year: int, df: pd.DataFrame):
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / f"{symbol.upper()}-{tf_token}-{year}.csv"
    meta_path = outdir / f"{symbol.upper()}-{tf_token}-{year}.meta.json"

    df.to_csv(csv_path, index=False)
    meta = {
        "symbol": symbol.upper(),
        "timeframe": tf_token,
        "year": year,
        "rows": int(len(df)),
        "first": str(df["TimeStamp"].min()) if not df.empty else None,
        "last": str(df["TimeStamp"].max()) if not df.empty else None,
        "note": "UTC timestamps; v3 with v2 fallback; no sessiontemplate for futures.",
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    logging.info(f"Wrote {csv_path} rows={len(df)}")
    return csv_path, meta_path

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="TradeStation historical downloader (uses config.py)")
    ap.add_argument("--symbol", required=True, help="Symbol, e.g., @GC for continuous futures")
    ap.add_argument("--timeframe", required=True, help="e.g., 60m, 15m, 3m, 1d, 1w, 1mo")
    ap.add_argument("--start-year", type=int, required=True)
    ap.add_argument("--end-year", type=int, required=True)
    ap.add_argument("--outdir", required=True, help="Folder to write per-year CSVs")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL (default: https://api.tradestation.com)")
    ap.add_argument("--intraday-cap", type=int, default=DEFAULT_INTRADAY_CAP, help="Max intraday bars per request")
    ap.add_argument("--segment-days", type=int, default=DEFAULT_SEGMENT_DAYS, help="Preferred intraday segment (days)")
    ap.add_argument("--equities-session-template", default=None, help="Optional, only for equities symbols (NOT futures)")
    ap.add_argument("--skip-existing", action="store_true", help="Skip year if output CSV already exists")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = ap.parse_args()

    setup_logger(verbose=args.verbose)

    access_token = resolve_access_token()

    symbol = args.symbol.strip()
    unit, interval, tf_token = parse_timeframe(args.timeframe)
    outdir = Path(args.outdir)
    seg_days = compute_segment_days(unit, interval, args.intraday_cap, args.segment_days)

    logging.info(f"Symbol={symbol} unit={unit} interval={interval} tf_token={tf_token} seg_days={seg_days}")

    for year in range(args.start_year, args.end_year + 1):
        csv_path = outdir / f"{symbol.upper()}-{tf_token}-{year}.csv"
        if args.skip_existing and csv_path.exists():
            logging.info(f"Skipping existing {csv_path}")
            continue

        logging.info(f"==== {symbol.upper()} {tf_token} — Year {year} ====")
        df = fetch_year(
            args.base_url, symbol, unit, interval, year, seg_days, access_token,
            equities_session_template=args.equities_session_template
        )
        write_outputs(outdir, symbol, tf_token, year, df)

    logging.info("All requested years complete.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Interrupted. Exiting.")
        sys.exit(1)
