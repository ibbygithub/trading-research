"""Calendar-aware bar dataset validator.

Compares an actual parquet of 1-minute bars against the exchange trading
calendar to detect gaps, duplicates, and data integrity issues. The result
is written as a ``.quality.json`` file next to the parquet.

Usage::

    from trading_research.data.validate import validate_bar_dataset

    report = validate_bar_dataset(
        parquet_path=Path("data/raw/ZN_1m_2024-01-01_2024-01-31.parquet"),
        symbol="ZN",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
    )
    if not report["passed"]:
        for f in report["failures"]:
            print(f)

Design notes
------------

Missing bars from the calendar perspective are NOT all treated as failures.
CME futures trade ~23 hours/day; TradeStation does not return bars for
minutes with zero activity. A single missing bar in the overnight session
is almost certainly a zero-trade minute — not a data problem.

The ``passed`` verdict is based on *structural* failures only:

- Duplicate timestamps in the dataset
- Negative volumes (data corruption indicator)
- Inverted OHLC (high < low, etc.)
- Complete sessions missing (a full trading day absent from data)
- Structural large gaps: > 5 consecutive bars that are NOT in an excluded
  window (see below)

Excluded gap windows (not counted as failures):
- **Post-maintenance window**: CME has a daily halt 16:00–17:00 CT.
  TradeStation consistently does not return bars for the first 30 minutes
  after the session reopens at 17:00 CT. These gaps are systematic and
  structural — the calendar model is wrong, not the data.
- **Calendar-patch holidays**: Juneteenth (June 19, observed, 2022+) is a
  CME closure that is missing from the CBOT_Bond calendar in
  pandas-market-calendars. Bars expected by the calendar for these dates
  are removed before gap analysis.

All excluded gaps are tracked in ``excluded_gaps`` in the report for full
transparency. Structural large gaps are in ``large_gaps``. The distinction
is explicit in the report, not hidden.

Failure reporting reports ALL structural failures — not a summary of the
top-N. If there are 500 structural large gaps, all 500 appear in the
report's ``large_gaps`` list, and the ``failures`` list contains an accurate
summary plus individual entries for each RTH gap (since those are the most
operationally significant).

Small gaps (≤ 5 consecutive missing bars) are counted and reported as
``minor_gaps_informational`` but do not cause failure. They are almost
always zero-activity minutes in the overnight session.
"""

from __future__ import annotations

import importlib.metadata
import json
from datetime import UTC, date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pandas_market_calendars as mcal
import pyarrow.parquet as pq

from trading_research.data.instruments import default_registry
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)

# Gap thresholds differ by session:
# - RTH: any gap > 5 consecutive bars is structural. Real market hours; even a
#   6-minute gap is suspicious.
# - Off-hours / overnight: the market trades thinly outside RTH. Runs of
#   6-60 missing bars are common zero-activity periods and not data errors.
#   Only gaps > 60 bars (1 hour) in the overnight session are structural.
_LARGE_GAP_BARS_RTH = 5        # > 5 bars in RTH → structural
_LARGE_GAP_BARS_OVERNIGHT = 60 # > 60 bars off-hours → structural; 6-60 = overnight_minor
_LARGE_GAP_BARS = _LARGE_GAP_BARS_RTH  # kept for backwards-compat in tests

# RTH window is per-instrument and is read from InstrumentRegistry at validation time.
# ZN: 08:20–15:00 ET; 6A/6C/6N: 08:00–17:00 ET.

# CME daily maintenance halt: 16:00–17:00 CT. TradeStation does not reliably
# return bars for the first 30 minutes after the session reopens at 17:00 CT.
# This window is excluded from the large-gap verdict.
_CME_MAINTENANCE_REOPEN_CT = pd.Timedelta(hours=17, minutes=0)  # 17:00 CT
_CME_POST_MAINTENANCE_EXCLUSION_MIN = 30  # minutes after reopen to exclude

# Calendars for which we apply Juneteenth exclusion. Juneteenth (June 19,
# observed) became a CME closure from 2022 onwards but is absent from
# pandas-market-calendars CBOT and CMEGlobex calendars as of 5.x.
_JUNETEENTH_CALENDARS = {"CBOT_Bond", "CMEGlobex_FX", "CME"}


def _pmcal_version() -> str:
    try:
        return "pandas-market-calendars==" + importlib.metadata.version(
            "pandas-market-calendars"
        )
    except Exception:
        return "pandas-market-calendars==unknown"


def _get_calendar_name(symbol: str) -> str:
    """Look up the pandas-market-calendars name for a symbol."""
    reg = default_registry()
    try:
        spec = reg.get(symbol)
        if spec.data.calendar:
            return spec.data.calendar
    except KeyError:
        pass
    raise ValueError(
        f"No calendar configured for symbol {symbol!r}. "
        "Add 'calendar' under the 'data' key in configs/instruments.yaml."
    )


def _consecutive_runs(sorted_series: list[pd.Timestamp]) -> list[list[pd.Timestamp]]:
    """Group consecutive (1-minute apart) timestamps into runs."""
    if not sorted_series:
        return []
    runs: list[list[pd.Timestamp]] = []
    current_run = [sorted_series[0]]
    for ts in sorted_series[1:]:
        if ts - current_run[-1] == pd.Timedelta(minutes=1):
            current_run.append(ts)
        else:
            runs.append(current_run)
            current_run = [ts]
    runs.append(current_run)
    return runs


def _is_post_maintenance_gap(run: list[pd.Timestamp]) -> bool:
    """True if this gap falls within the 30-min post-CME-maintenance window.

    CME halts daily 16:00–17:00 CT. TradeStation systematically omits the
    first ~30 minutes after the 17:00 CT reopen. A gap is classified as
    post-maintenance if:
    - it is at most 30 bars long (a longer gap cannot be this window), AND
    - it starts between 17:00 CT and 17:30 CT.

    The length cap is the primary guard. A gap spanning hours may start at
    17:01 CT but can only be structural — not a routine post-maintenance gap.
    """
    if len(run) > _CME_POST_MAINTENANCE_EXCLUSION_MIN:
        return False
    run_start_ct = run[0].tz_convert("America/Chicago")
    time_of_day_ct = pd.Timedelta(
        hours=run_start_ct.hour,
        minutes=run_start_ct.minute,
    )
    window_end_ct = _CME_MAINTENANCE_REOPEN_CT + pd.Timedelta(
        minutes=_CME_POST_MAINTENANCE_EXCLUSION_MIN
    )
    return _CME_MAINTENANCE_REOPEN_CT <= time_of_day_ct < window_end_ct


def _juneteenth_sessions_to_remove(
    schedule: pd.DataFrame,
    cal_name: str,
    start_date: date,
    end_date: date,
) -> set[pd.Timestamp]:
    """Return the set of expected timestamps to strip for Juneteenth closures.

    Juneteenth (June 19, observed) is a CME closure from 2022 onwards but is
    missing from pandas-market-calendars CBOT/CMEGlobex calendars. We compute
    the observed date for each year in range and remove those sessions from the
    expected set before gap analysis.
    """
    if cal_name not in _JUNETEENTH_CALENDARS:
        return set()

    to_remove: set[pd.Timestamp] = set()
    start_year = start_date.year
    end_year = end_date.year

    for year in range(max(start_year, 2022), end_year + 1):
        raw = pd.Timestamp(year=year, month=6, day=19, tz="UTC")
        # If June 19 is Sunday, observe Monday; if Saturday, observe Friday.
        if raw.dayofweek == 6:  # Sunday
            observed = raw + pd.Timedelta(days=1)
        elif raw.dayofweek == 5:  # Saturday
            observed = raw - pd.Timedelta(days=1)
        else:
            observed = raw

        observed_date = observed.date()
        if not (start_date <= observed_date <= end_date):
            continue
        # Find this date's session in the schedule and collect its timestamps.
        observed_ts = pd.Timestamp(observed_date)
        matching = [d for d in schedule.index if d.date() == observed_date]
        for trade_date in matching:
            sess_open = schedule.loc[trade_date, "market_open"]
            sess_close = schedule.loc[trade_date, "market_close"]
            session_range = pd.date_range(
                start=sess_open,
                end=sess_close,
                freq="1min",
                tz="UTC",
            )
            to_remove.update(session_range)

    return to_remove


def validate_bar_dataset(
    parquet_path: Path,
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    calendar_name: str | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    """Validate a 1-minute bar parquet against the exchange trading calendar.

    Parameters
    ----------
    parquet_path:
        Path to the parquet file (in data/raw/ or data/clean/).
    symbol:
        Root symbol (e.g. ``"ZN"``). Used to look up the calendar if
        ``calendar_name`` is not explicitly provided.
    start_date, end_date:
        Date range to validate against the calendar. Should match the
        date range of the download.
    calendar_name:
        pandas-market-calendars calendar name. If omitted, looked up from
        the instrument registry via ``symbol``.
    write_report:
        If True (default), write the report as ``{parquet_path.stem}.quality.json``
        next to the parquet. The caller can pass False to suppress this for
        testing purposes.

    Returns
    -------
    dict
        The quality report. ``report["passed"]`` is True iff no structural
        failures were detected. ``report["failures"]`` is a list of
        human-readable failure descriptions covering ALL failures (not a
        truncated summary).
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    cal_name = calendar_name or _get_calendar_name(symbol)

    # Read RTH window from the instrument registry so 6A (08:00–17:00 ET)
    # and ZN (08:20–15:00 ET) are classified correctly without hardcoding.
    spec = default_registry().get(symbol)
    rth_open_et = pd.Timedelta(
        hours=spec.session.rth.open.hour,
        minutes=spec.session.rth.open.minute,
    )
    rth_close_et = pd.Timedelta(
        hours=spec.session.rth.close.hour,
        minutes=spec.session.rth.close.minute,
    )

    logger.info(
        "validate_start",
        symbol=symbol,
        parquet=str(parquet_path),
        calendar=cal_name,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )

    # --- Load data -----------------------------------------------------------
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    actual_count = len(df)

    # --- Build expected timestamp set from calendar --------------------------
    cal = mcal.get_calendar(cal_name)
    schedule = cal.schedule(
        start_date.isoformat(),
        end_date.isoformat(),
    )
    expected_ts_index: pd.DatetimeIndex = mcal.date_range(schedule, frequency="1min")
    expected_ts_set: set[pd.Timestamp] = set(expected_ts_index)

    # Apply Juneteenth patch: remove sessions the library wrongly marks as open.
    juneteenth_removed = _juneteenth_sessions_to_remove(
        schedule, cal_name, start_date, end_date
    )
    expected_ts_set -= juneteenth_removed
    expected_count = len(expected_ts_set)

    # Normalize actual timestamps to UTC
    actual_ts_series = pd.to_datetime(df["timestamp_utc"], utc=True)
    actual_ts_set: set[pd.Timestamp] = set(actual_ts_series)

    missing_ts = sorted(expected_ts_set - actual_ts_set)
    extra_ts = sorted(actual_ts_set - expected_ts_set)

    # --- Structural checks ---------------------------------------------------
    failures: list[str] = []

    # 1. Duplicates
    dup_count = int(actual_ts_series.duplicated().sum())
    if dup_count:
        failures.append(f"{dup_count} duplicate timestamp(s) found.")

    # 2. Negative volumes
    neg_vol = int((df["volume"] < 0).sum())
    if neg_vol:
        failures.append(f"{neg_vol} bar(s) with negative volume.")

    # 3. Inverted OHLC
    inv_hl = int((df["high"] < df["low"]).sum())
    if inv_hl:
        failures.append(f"{inv_hl} bar(s) with high < low.")
    inv_ho = int((df["high"] < df["open"]).sum())
    if inv_ho:
        failures.append(f"{inv_ho} bar(s) with high < open.")
    inv_hc = int((df["high"] < df["close"]).sum())
    if inv_hc:
        failures.append(f"{inv_hc} bar(s) with high < close.")
    inv_lo = int((df["low"] > df["open"]).sum())
    if inv_lo:
        failures.append(f"{inv_lo} bar(s) with low > open.")
    inv_lc = int((df["low"] > df["close"]).sum())
    if inv_lc:
        failures.append(f"{inv_lc} bar(s) with low > close.")

    # 4. Null required fields
    required = ["timestamp_utc", "timestamp_ny", "open", "high", "low", "close", "volume"]
    null_req = 0
    for col in required:
        if col in df.columns:
            n = int(df[col].isnull().sum())
            if n:
                failures.append(f"Required column '{col}' has {n} null(s).")
                null_req += n

    # 5. Gap analysis ---------------------------------------------------------
    missing_runs = _consecutive_runs(missing_ts)
    minor_gaps: list[dict[str, Any]] = []
    overnight_minor_gaps: list[dict[str, Any]] = []  # off-hours, 6-60 bars, not structural
    large_gaps: list[dict[str, Any]] = []             # structural — count against passed
    excluded_gaps: list[dict[str, Any]] = []          # known systematic — excluded from verdict

    for run in missing_runs:
        gap_info: dict[str, Any] = {
            "start_utc": run[0].isoformat(),
            "end_utc": run[-1].isoformat(),
            "bars_missing": len(run),
        }
        # Classify RTH using the gap start time in ET.
        run_start_ny = run[0].tz_convert("America/New_York")
        time_of_day_et = pd.Timedelta(
            hours=run_start_ny.hour,
            minutes=run_start_ny.minute,
        )
        in_rth = bool(rth_open_et <= time_of_day_et <= rth_close_et)
        gap_info["in_rth"] = in_rth

        # Select the applicable large-gap threshold.
        large_gap_threshold = _LARGE_GAP_BARS_RTH if in_rth else _LARGE_GAP_BARS_OVERNIGHT

        if len(run) <= _LARGE_GAP_BARS_RTH:
            # Minor gap regardless of session — ≤5 bars is never structural.
            minor_gaps.append(gap_info)
        elif _is_post_maintenance_gap(run):
            gap_info["exclusion_reason"] = "post_maintenance"
            excluded_gaps.append(gap_info)
        elif not in_rth and len(run) <= _LARGE_GAP_BARS_OVERNIGHT:
            # Off-hours gap of 6-60 bars: thin market, not structural.
            overnight_minor_gaps.append(gap_info)
        else:
            large_gaps.append(gap_info)

    # Report ALL structural large gaps — not just the top-N.
    # RTH gaps are listed individually; non-RTH gaps are summarised.
    rth_large = [g for g in large_gaps if g["in_rth"]]
    non_rth_large = [g for g in large_gaps if not g["in_rth"]]

    if rth_large:
        for g in sorted(rth_large, key=lambda x: x["bars_missing"], reverse=True):
            failures.append(
                f"Large gap (RTH!): {g['bars_missing']} missing bars "
                f"starting {g['start_utc']}."
            )
    if non_rth_large:
        # Summarise count; list the top-10 by size for context.
        failures.append(
            f"{len(non_rth_large)} large overnight/off-hours gap(s) found "
            f"(total {sum(g['bars_missing'] for g in non_rth_large)} missing bars)."
        )
        top10 = sorted(non_rth_large, key=lambda g: g["bars_missing"], reverse=True)[:10]
        for g in top10:
            failures.append(
                f"  Overnight gap: {g['bars_missing']} bars starting {g['start_utc']}."
            )

    # 6. Missing complete sessions -------------------------------------------
    session_dates = list(schedule.index)
    missing_sessions: list[str] = []
    for trade_date in session_dates:
        # Skip Juneteenth-patched sessions — they were intentionally removed.
        if trade_date.date() in {ts.date() for ts in juneteenth_removed}:
            continue
        sess_open = schedule.loc[trade_date, "market_open"]
        sess_close = schedule.loc[trade_date, "market_close"]
        in_session = actual_ts_series[
            (actual_ts_series >= sess_open) & (actual_ts_series < sess_close)
        ]
        if len(in_session) == 0:
            missing_sessions.append(trade_date.isoformat())

    if missing_sessions:
        failures.append(
            f"{len(missing_sessions)} complete session(s) missing: "
            + ", ".join(missing_sessions[:5])
            + ("..." if len(missing_sessions) > 5 else "")
        )

    # --- Buy/sell volume coverage -------------------------------------------
    bv_non_null = int(df["buy_volume"].notna().sum()) if "buy_volume" in df.columns else 0
    sv_non_null = int(df["sell_volume"].notna().sum()) if "sell_volume" in df.columns else 0
    coverage_pct = round(100.0 * bv_non_null / actual_count, 2) if actual_count else 0.0

    # --- Assemble report ----------------------------------------------------
    missing_bars_unexplained = sum(g["bars_missing"] for g in large_gaps)
    missing_bars_minor = sum(g["bars_missing"] for g in minor_gaps)
    missing_bars_excluded = sum(g["bars_missing"] for g in excluded_gaps)
    missing_bars_overnight_minor = sum(g["bars_missing"] for g in overnight_minor_gaps)

    # session_count: use trade-date count, not unique UTC dates.
    # juneteenth_removed spans two UTC calendar dates per session, so we
    # count sessions by matching the schedule index directly.
    patched_trade_dates: set[date] = set()
    for tdate in schedule.index:
        if tdate.date() in {d.date() for d in [
            pd.Timestamp(year=yr, month=6, day=19)
            + (pd.Timedelta(days=1) if pd.Timestamp(year=yr, month=6, day=19).dayofweek == 6 else pd.Timedelta(0))
            + (pd.Timedelta(days=-1) if pd.Timestamp(year=yr, month=6, day=19).dayofweek == 5 else pd.Timedelta(0))
            for yr in range(max(start_date.year, 2022), end_date.year + 1)
        ]}:
            patched_trade_dates.add(tdate.date())

    sessions_expected = len(session_dates) - len(patched_trade_dates)
    sessions_present = sessions_expected - len(missing_sessions)

    report: dict[str, Any] = {
        "dataset_path": str(parquet_path),
        "symbol": symbol,
        "timeframe": "1m",
        "date_range": [start_date.isoformat(), end_date.isoformat()],
        "calendar": cal_name,
        "calendar_patches_applied": (
            ["juneteenth_2022+"] if juneteenth_removed else []
        ),
        "row_count": actual_count,
        "expected_row_count": expected_count,
        "missing_bars_total": len(missing_ts),
        "missing_bars_minor_gaps": missing_bars_minor,
        "missing_bars_overnight_minor": missing_bars_overnight_minor,
        "missing_bars_excluded_gaps": missing_bars_excluded,
        "missing_bars_structural": missing_bars_unexplained,
        # kept for backwards compat — same value as missing_bars_structural
        "missing_bars_unexplained": missing_bars_unexplained,
        "extra_bars_outside_calendar": len(extra_ts),
        "duplicate_timestamps": dup_count,
        "negative_volumes": neg_vol,
        "inverted_high_low": inv_hl,
        "null_required_fields": null_req,
        "buy_sell_volume_coverage_pct": coverage_pct,
        "large_gaps": large_gaps,
        "excluded_gaps_count": len(excluded_gaps),
        "excluded_gaps": excluded_gaps,
        "overnight_minor_gap_count": len(overnight_minor_gaps),
        "minor_gap_count": len(minor_gaps),
        "missing_sessions": missing_sessions,
        "session_count_expected": sessions_expected,
        "session_count_present": sessions_present,
        "failures": failures,
        "passed": len(failures) == 0,
        "validation_timestamp_utc": datetime.now(UTC).isoformat(),
        "calendar_library_version": _pmcal_version(),
    }

    if write_report:
        report_path = parquet_path.with_suffix("").with_suffix("").parent / (
            parquet_path.stem + ".quality.json"
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info(
            "validate_complete",
            symbol=symbol,
            passed=report["passed"],
            missing_total=report["missing_bars_total"],
            structural=report["missing_bars_structural"],
            excluded=report["missing_bars_excluded_gaps"],
            failures=len(failures),
            report_path=str(report_path),
        )

    return report
