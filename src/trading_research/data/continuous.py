"""Multi-contract back-adjusted continuous series builder.

Motivation
----------
TradeStation's ``@TY`` continuous contract rolls on its own undocumented
schedule. As confirmed by the September 2023 diagnostic, TS held @ZN on
TYU23 (September contract) well past the point where all real liquidity
had migrated to TYZ23. The result was 10+ days of near-empty RTH bars in
the continuous series — unusable for backtesting.

This module builds our own continuous series by downloading each quarterly
contract individually, rolling at a deterministic date, and applying an
additive back-adjustment to eliminate price gaps at each roll.

Adjustment method: additive
    We add a constant to all prior contract prices at each roll so that the
    stitched series is gap-free. Additive is correct for a fixed-notional
    rate product like ZN; ratio adjustment would distort tick-size arithmetic.
    ZN price range has been ~95–135 over the project history; the cumulative
    additive adjustment should stay small.

Roll convention for ZN (configurable via roll_days_before parameter)
    CME rule: ZN last trading day = 7 business days before the last business
    day of the delivery month.
    Our roll date = last_trading_day − roll_days_before (default 5 business days).
    This rolls roughly 2 weeks before expiry, well ahead of TS's default and
    aligned with when TY liquidity actually migrates.

Roll date for September 2023 (roll_days_before=5):
    - Last biz day of September 2023 = Sept 29
    - Last trading day = Sept 29 − 7 biz = Sept 20
    - Roll date = Sept 20 − 5 biz = Sept 13
    This is before the data degradation that TS's continuous exhibited.

Output layout:
    data/clean/{symbol}_1m_backadjusted_{start}_{end}.parquet  — adjusted prices
    data/clean/{symbol}_1m_unadjusted_{start}_{end}.parquet   — raw stitched prices
    data/clean/{symbol}_roll_log_{start}_{end}.json           — roll dates + deltas
    data/raw/contracts/{ts_root}{code}{year}_1m_{start}_{end}.parquet  — cached per-contract
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from trading_research.data.instruments import default_registry
from trading_research.data.schema import BAR_SCHEMA
from trading_research.data.tradestation.auth import TradeStationAuth
from trading_research.data.tradestation.client import TradeStationClient
from trading_research.data.tradestation.normalize import bars_json_to_table
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

# Quarterly contract month codes.
_QUARTERLY_MONTHS: dict[int, str] = {3: "H", 6: "M", 9: "U", 12: "Z"}
_CODE_TO_MONTH: dict[str, int] = {v: k for k, v in _QUARTERLY_MONTHS.items()}

DEFAULT_CLEAN_DIR = Path("data/clean")
DEFAULT_CONTRACTS_DIR = Path("data/raw/contracts")
DEFAULT_ROLL_DAYS_BEFORE = 5   # business days before last trading day


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _is_biz_day(d: date) -> bool:
    """True if d is a weekday (Mon–Fri). Does not account for holidays."""
    return d.weekday() < 5


def _last_biz_day_of_month(year: int, month: int) -> date:
    """Last weekday in the given year/month (no holiday calendar)."""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while not _is_biz_day(d):
        d -= timedelta(days=1)
    return d


def _subtract_biz_days(d: date, n: int) -> date:
    """Return d minus n business days (weekdays only)."""
    remaining = n
    cur = d
    while remaining > 0:
        cur -= timedelta(days=1)
        if _is_biz_day(cur):
            remaining -= 1
    return cur


def last_trading_day_quarterly_cme(expiry_year: int, expiry_month: int) -> date:
    """Last trading day for quarterly CME futures: 7 business days before last biz day of delivery month.

    Applies to ZN (10-Year T-Note), 6A (AUD), 6C (CAD), 6N (NZD), and other
    quarterly CME contracts that follow this convention. Trading ceases at the
    last business day of the contract month minus 7 business days.
    """
    last_biz = _last_biz_day_of_month(expiry_year, expiry_month)
    return _subtract_biz_days(last_biz, 7)


def roll_date_for_contract(
    expiry_year: int,
    expiry_month: int,
    roll_days_before: int = DEFAULT_ROLL_DAYS_BEFORE,
) -> date:
    """Our roll date = last_trading_day - roll_days_before business days."""
    ltd = last_trading_day_quarterly_cme(expiry_year, expiry_month)
    return _subtract_biz_days(ltd, roll_days_before)


# ---------------------------------------------------------------------------
# Contract sequence
# ---------------------------------------------------------------------------

@dataclass
class ContractPeriod:
    """One quarterly contract and the date window we pull from it."""
    ts_symbol: str          # e.g. "TYU23"
    expiry_year: int
    expiry_month: int
    data_start: date        # first day we need data from this contract
    data_end: date          # last day we need data from this contract (= roll_date - 1)
    roll_date: date         # the day we switch TO the next contract


def contract_sequence(
    ts_root: str,
    start_date: date,
    end_date: date,
    roll_days_before: int = DEFAULT_ROLL_DAYS_BEFORE,
) -> list[ContractPeriod]:
    """Generate ordered quarterly contracts that cover [start_date, end_date].

    Each ContractPeriod's data window is [data_start, data_end], where
    data_end is roll_date - 1 business day. The next contract starts on
    roll_date.
    """
    # Find the quarterly cycle that covers start_date.
    # Walk backward to find the first contract whose roll date >= start_date.
    # Build the full sequence of contracts in the range.
    periods: list[ContractPeriod] = []
    quarterly_months = sorted(_QUARTERLY_MONTHS.keys())  # [3, 6, 9, 12]

    # Generate candidates for all quarterly contracts from the year before
    # start_date through the year after end_date.
    candidates: list[tuple[int, int]] = []
    for yr in range(start_date.year - 1, end_date.year + 2):
        for mo in quarterly_months:
            candidates.append((yr, mo))

    # Keep only contracts whose roll date is >= start_date and whose
    # previous contract's roll date is <= end_date.
    filtered: list[tuple[int, int, date]] = []
    for yr, mo in candidates:
        rd = roll_date_for_contract(yr, mo, roll_days_before)
        filtered.append((yr, mo, rd))

    filtered.sort(key=lambda x: x[2])  # sort by roll date

    # Find the first roll date >= start_date (the contract that's active at start).
    # The contract active *at* start_date is the one whose roll_date >= start_date
    # and whose previous contract's roll_date < start_date.
    first_idx = 0
    for idx, (yr, mo, rd) in enumerate(filtered):
        if rd >= start_date:
            first_idx = max(0, idx - 1)
            break

    # Slice to only contracts relevant to [start_date, end_date].
    relevant: list[tuple[int, int, date]] = []
    for yr, mo, rd in filtered[first_idx:]:
        if rd > end_date and relevant:
            # Last contract: its roll date is after our end — include it
            # so the last period has a defined end.
            relevant.append((yr, mo, rd))
            break
        relevant.append((yr, mo, rd))
        if rd > end_date:
            break

    # Build ContractPeriod objects.
    # Semantics:
    #   rd  = the roll_date of THIS contract = when we switch FROM it TO the next.
    #   data_start = previous contract's roll_date (or start_date for the first).
    #   data_end   = one biz day before rd (last day we use this contract),
    #                EXCEPT for the last contract which uses end_date.
    #   ContractPeriod.roll_date = rd (the date we switch to the next contract).
    #
    # relevant[-1] is the contract still active at end_date (its roll_date >
    # end_date). It is the "sentinel" used for boundary-computing in the loop
    # below, and ALSO gets its own ContractPeriod covering [prev_roll, end_date].
    for i, (yr, mo, rd) in enumerate(relevant):
        code = _QUARTERLY_MONTHS[mo]
        ts_sym = f"{ts_root}{code}{yr % 100:02d}"

        prev_roll = relevant[i - 1][2] if i > 0 else start_date
        data_start = max(prev_roll, start_date)

        is_last = (i == len(relevant) - 1)
        if is_last:
            # Currently-active contract: covers up to end_date, not roll_date-1.
            data_end = end_date
        else:
            data_end = min(_subtract_biz_days(rd, 1), end_date)

        # Skip contracts whose active window doesn't overlap our date range
        # (e.g. the lookback contract that already rolled before start_date).
        if data_start > data_end:
            continue

        periods.append(
            ContractPeriod(
                ts_symbol=ts_sym,
                expiry_year=yr,
                expiry_month=mo,
                data_start=data_start,
                data_end=data_end,
                roll_date=rd,
            )
        )

    return periods


# ---------------------------------------------------------------------------
# Per-contract download (with caching)
# ---------------------------------------------------------------------------

def _contracts_cache_path(
    ts_symbol: str,
    start_date: date,
    end_date: date,
    contracts_dir: Path,
) -> Path:
    fname = f"{ts_symbol}_1m_{start_date.isoformat()}_{end_date.isoformat()}.parquet"
    return contracts_dir / fname


def download_contract(
    ts_symbol: str,
    start_date: date,
    end_date: date,
    client: TradeStationClient,
    contracts_dir: Path = DEFAULT_CONTRACTS_DIR,
    window_days: int = 30,
) -> pa.Table:
    """Download bars for a single quarterly contract, using cached parquet if present.

    The downloaded data is cached to contracts_dir so subsequent runs skip
    the API call. Returns a pyarrow Table conforming to BAR_SCHEMA.
    """
    contracts_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _contracts_cache_path(ts_symbol, start_date, end_date, contracts_dir)

    if cache_path.exists():
        logger.info("contract_cache_hit", symbol=ts_symbol, path=str(cache_path))
        return pq.read_table(cache_path)

    logger.info(
        "contract_download_start",
        symbol=ts_symbol,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )

    # Paginate in 30-day windows.
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC).replace(microsecond=0)

    cur = start_dt
    tables: list[pa.Table] = []
    while cur <= end_dt:
        nxt = min(cur + timedelta(days=window_days), end_dt)
        try:
            raw = client.fetch_bar_window(ts_symbol, cur, nxt)
        except Exception as exc:
            logger.warning(
                "contract_window_error",
                symbol=ts_symbol,
                window_start=cur.isoformat(),
                error=str(exc),
            )
            raw = []
        if raw:
            tables.append(bars_json_to_table(raw))
        time.sleep(0.05)  # polite pacing
        cur = nxt + timedelta(seconds=1)

    if not tables:
        logger.warning("contract_no_data", symbol=ts_symbol)
        return pa.table(
            {col: pa.array([], type=BAR_SCHEMA.field(col).type) for col in BAR_SCHEMA.names},
            schema=BAR_SCHEMA,
        )

    combined = pa.concat_tables(tables)
    # Deduplicate and sort.
    df = combined.to_pandas()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc")
    result = pa.Table.from_pandas(df, schema=BAR_SCHEMA, preserve_index=False)

    pq.write_table(result, cache_path)
    logger.info(
        "contract_download_complete",
        symbol=ts_symbol,
        rows=result.num_rows,
        path=str(cache_path),
    )
    return result


# ---------------------------------------------------------------------------
# Back-adjustment
# ---------------------------------------------------------------------------

@dataclass
class RollEvent:
    roll_date: date
    from_contract: str
    to_contract: str
    adjustment_delta: float   # added to all prices before this roll
    from_last_close: float
    to_first_open: float


@dataclass
class ContinuousResult:
    adjusted_path: Path
    unadjusted_path: Path
    roll_log_path: Path
    symbol: str
    ts_root: str
    start_date: date
    end_date: date
    roll_days_before: int
    adjustment_method: str
    total_rows: int
    roll_events: list[RollEvent] = field(default_factory=list)


def build_back_adjusted_continuous(
    symbol: str,
    start_date: date,
    end_date: date,
    roll_days_before: int = DEFAULT_ROLL_DAYS_BEFORE,
    adjustment_method: str = "additive",
    output_dir: Path = DEFAULT_CLEAN_DIR,
    contracts_dir: Path = DEFAULT_CONTRACTS_DIR,
    auth: TradeStationAuth | None = None,
) -> ContinuousResult:
    """Build a back-adjusted continuous series for ``symbol`` (e.g. ``"ZN"``).

    Steps
    -----
    1. Resolve the TradeStation root symbol from the instrument registry.
    2. Generate the sequence of quarterly contracts covering [start_date, end_date].
    3. For each contract, download bars (or load from cache in contracts_dir).
    4. Compute the additive adjustment at each roll:
           delta = to_contract_first_bar_close(roll_date) - from_contract_last_bar_close(roll_date - 1)
       All prices for the from_contract (and all prior) shift by delta.
    5. Write the adjusted and unadjusted parquets plus a roll log JSON.

    The adjustment is applied backward (all historical prices shift to match
    current contract levels). This is the standard method for rate products.
    """
    if adjustment_method != "additive":
        raise NotImplementedError("Only 'additive' adjustment is supported.")

    spec = default_registry().get(symbol)
    # Extract TS root from the continuous symbol (e.g. "@TY" → "TY").
    ts_root = spec.continuous_symbol.lstrip("@")

    if auth is None:
        auth = TradeStationAuth()
    client = TradeStationClient(auth)

    output_dir.mkdir(parents=True, exist_ok=True)
    contracts_dir.mkdir(parents=True, exist_ok=True)

    periods = contract_sequence(ts_root, start_date, end_date, roll_days_before)
    logger.info(
        "continuous_build_start",
        symbol=symbol,
        contracts=len(periods),
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        roll_days_before=roll_days_before,
    )

    # Download all contracts.
    contract_tables: dict[str, pa.Table] = {}
    for period in periods:
        contract_tables[period.ts_symbol] = download_contract(
            period.ts_symbol,
            period.data_start,
            period.data_end,
            client,
            contracts_dir,
        )

    # Build the unadjusted stitched series + compute roll adjustments.
    roll_events: list[RollEvent] = []
    cumulative_adjustment = 0.0
    segment_dfs: list[pd.DataFrame] = []

    for i, period in enumerate(periods):
        tbl = contract_tables[period.ts_symbol]
        if tbl.num_rows == 0:
            logger.warning("contract_empty_skipping", symbol=period.ts_symbol)
            continue

        df = tbl.to_pandas()
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        df["contract"] = period.ts_symbol

        # Filter to the contract's active window.
        start_ts = pd.Timestamp(period.data_start, tz="UTC")
        end_ts = pd.Timestamp(period.data_end, tz="UTC") + pd.Timedelta(days=1)
        df = df[(df["timestamp_utc"] >= start_ts) & (df["timestamp_utc"] < end_ts)].copy()

        if df.empty:
            logger.warning("contract_empty_after_filter", symbol=period.ts_symbol)
            continue

        # Compute roll adjustment for the transition TO the next contract.
        if i + 1 < len(periods):
            next_period = periods[i + 1]
            next_tbl = contract_tables.get(next_period.ts_symbol)
            if next_tbl is not None and next_tbl.num_rows > 0:
                next_df = next_tbl.to_pandas()
                next_df["timestamp_utc"] = pd.to_datetime(next_df["timestamp_utc"], utc=True)
                next_df = next_df.sort_values("timestamp_utc")

                # from_contract: last bar on or before roll_date
                roll_ts = pd.Timestamp(period.roll_date, tz="UTC")
                from_bars = df[df["timestamp_utc"].dt.normalize() <= roll_ts]
                # to_contract: first bar on or after roll_date
                to_bars = next_df[next_df["timestamp_utc"].dt.normalize() >= roll_ts]

                if not from_bars.empty and not to_bars.empty:
                    from_close = float(from_bars.iloc[-1]["close"])
                    to_open = float(to_bars.iloc[0]["open"])
                    delta = to_open - from_close
                    cumulative_adjustment += delta

                    roll_events.append(
                        RollEvent(
                            roll_date=period.roll_date,
                            from_contract=period.ts_symbol,
                            to_contract=next_period.ts_symbol,
                            adjustment_delta=delta,
                            from_last_close=from_close,
                            to_first_open=to_open,
                        )
                    )
                    logger.info(
                        "roll_computed",
                        from_contract=period.ts_symbol,
                        to_contract=next_period.ts_symbol,
                        roll_date=period.roll_date.isoformat(),
                        delta=round(delta, 6),
                        cumulative=round(cumulative_adjustment, 6),
                    )

        df["_cumulative_adj"] = cumulative_adjustment
        segment_dfs.append(df)

    if not segment_dfs:
        raise RuntimeError(f"No data downloaded for {symbol} [{start_date}–{end_date}]")

    # Concatenate in reverse order (oldest first) and apply backward adjustment.
    # Each segment already knows its cumulative_adj; apply forward pass in
    # time-ascending order, applying the FUTURE adjustments to each segment.
    # Equivalently: re-run in chronological order, tracking total_adj accumulated
    # from the end backward.

    # Build cumulative adjustments per segment (oldest segment gets all future deltas).
    # We stored _cumulative_adj as "the delta that will accumulate AFTER this segment."
    # Reverse: oldest segment needs the SUM of all roll deltas after it.
    all_deltas = [e.adjustment_delta for e in roll_events]
    total_adj = sum(all_deltas)

    # For segment i (0=oldest), the adjustment to apply is:
    #   sum of all deltas for rolls 0..n-1 EXCEPT those belonging to segments after i.
    # Equivalently: oldest segment gets total_adj, each subsequent segment gets less.
    running_adj = total_adj
    unadjusted_parts: list[pd.DataFrame] = []
    adjusted_parts: list[pd.DataFrame] = []

    for i, df in enumerate(segment_dfs):
        df = df.copy()
        df.drop(columns=["_cumulative_adj"], inplace=True)

        # Unadjusted: raw prices
        unadjusted_parts.append(df.copy())

        # Adjusted: shift OHLC prices by running_adj
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col] + running_adj

        adjusted_parts.append(df)

        # After this segment, we used one roll delta — subtract it from running_adj.
        if i < len(all_deltas):
            running_adj -= all_deltas[i]

    # Build final DataFrames.
    unadjusted_df = pd.concat(unadjusted_parts, ignore_index=True)
    adjusted_df = pd.concat(adjusted_parts, ignore_index=True)

    for df in [unadjusted_df, adjusted_df]:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df.drop_duplicates(subset=["timestamp_utc"], inplace=True)
        df.sort_values("timestamp_utc", inplace=True)
        df.reset_index(drop=True, inplace=True)

    # Drop the helper 'contract' column before writing (not in schema).
    price_cols = ["open", "high", "low", "close", "volume",
                  "buy_volume", "sell_volume", "up_ticks", "down_ticks",
                  "total_ticks", "timestamp_utc", "timestamp_ny"]
    schema_cols = [c for c in price_cols if c in unadjusted_df.columns]

    # Write parquets.
    date_tag = f"{start_date.isoformat()}_{end_date.isoformat()}"
    adj_path = output_dir / f"{symbol}_1m_backadjusted_{date_tag}.parquet"
    unadj_path = output_dir / f"{symbol}_1m_unadjusted_{date_tag}.parquet"
    roll_log_path = output_dir / f"{symbol}_roll_log_{date_tag}.json"

    def _write(df: pd.DataFrame, path: Path) -> None:
        cols = [c for c in BAR_SCHEMA.names if c in df.columns]
        sub = df[cols].copy()
        tbl = pa.Table.from_pandas(sub, schema=BAR_SCHEMA, preserve_index=False)
        pq.write_table(tbl, path)

    _write(adjusted_df, adj_path)
    _write(unadjusted_df, unadj_path)

    # Write roll log.
    roll_log: dict[str, Any] = {
        "symbol": symbol,
        "ts_root": ts_root,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "roll_days_before_expiry": roll_days_before,
        "adjustment_method": adjustment_method,
        "total_cumulative_adjustment": round(total_adj, 6),
        "total_rows": len(adjusted_df),
        "contracts_used": [p.ts_symbol for p in periods],
        "rolls": [
            {
                "roll_date": e.roll_date.isoformat(),
                "from_contract": e.from_contract,
                "to_contract": e.to_contract,
                "adjustment_delta": round(e.adjustment_delta, 6),
                "from_last_close": round(e.from_last_close, 6),
                "to_first_open": round(e.to_first_open, 6),
            }
            for e in roll_events
        ],
        "built_utc": datetime.now(UTC).isoformat(),
    }
    roll_log_path.write_text(json.dumps(roll_log, indent=2), encoding="utf-8")

    logger.info(
        "continuous_build_complete",
        symbol=symbol,
        rows=len(adjusted_df),
        rolls=len(roll_events),
        total_adj=round(total_adj, 6),
        adj_path=str(adj_path),
    )

    return ContinuousResult(
        adjusted_path=adj_path,
        unadjusted_path=unadj_path,
        roll_log_path=roll_log_path,
        symbol=symbol,
        ts_root=ts_root,
        start_date=start_date,
        end_date=end_date,
        roll_days_before=roll_days_before,
        adjustment_method=adjustment_method,
        total_rows=len(adjusted_df),
        roll_events=roll_events,
    )
