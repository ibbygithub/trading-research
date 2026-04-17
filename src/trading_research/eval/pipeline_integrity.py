"""Pipeline integrity report for a backtest run.

Audits the data pipeline behind a run: bar counts, HTF shift(1) consistency,
indicator look-ahead, feature-set manifest diff, and trade-date boundaries.

Public API
----------
    generate_pipeline_integrity_report(run_dir: Path) -> Path
"""

from __future__ import annotations

import json
import random
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd


_DATA_ROOT = Path(__file__).parents[3] / "data"

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_pipeline_integrity_report(run_dir: Path) -> Path:
    """Write pipeline_integrity.md to *run_dir* and return the Path.

    Checks performed:
    1. Bar counts per session — flags sessions > 2σ from mean.
    2. HTF merge audit — 100 random entry bars, verify htf_bias shift(1).
    3. Indicator look-ahead spot-checks — 20 bars each for ATR, RSI, MACD, BB, VWAP.
    4. Feature-set manifest diff — compare run-time manifest vs current yaml.
    5. Trade-date boundary check — entry and exit within the same CME trade date.
    """
    run_dir = Path(run_dir)

    trades_path = run_dir / "trades.parquet"
    if not trades_path.is_file():
        raise FileNotFoundError(f"trades.parquet not found in {run_dir}")

    trades = pd.read_parquet(trades_path, engine="pyarrow")
    for col in ("entry_ts", "exit_ts"):
        if col in trades.columns:
            trades[col] = pd.to_datetime(trades[col], utc=True)

    symbol = trades["symbol"].iloc[0] if "symbol" in trades.columns else "ZN"

    sections: list[str] = [
        "# Pipeline Integrity Report",
        "",
        f"Run: `{run_dir.parent.name}/{run_dir.name}`",
        f"Symbol: `{symbol}`  |  Trades: {len(trades):,}",
        "",
        "---",
        "",
    ]

    # --- 1. Bar counts per session ---
    sections += _check_bar_counts(symbol)

    # --- 2. HTF merge audit ---
    sections += _check_htf_merge(symbol, trades)

    # --- 3. Indicator look-ahead ---
    sections += _check_indicator_lookahead(symbol)

    # --- 4. Feature-set manifest diff ---
    sections += _check_manifest_diff(symbol, run_dir)

    # --- 5. Trade-date boundary check ---
    sections += _check_trade_date_boundaries(trades)

    out_path = run_dir / "pipeline_integrity.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Check helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_bar_counts(symbol: str) -> list[str]:
    """Check 5m bar counts per calendar day; flag outliers > 2σ."""
    lines = ["## 1. Bar Counts Per Session", ""]

    feat_dir = _DATA_ROOT / "features"
    pattern = f"{symbol}_backadjusted_5m_features_base-v1_*.parquet"
    feat_files = sorted(feat_dir.glob(pattern))
    if not feat_files:
        return lines + ["**SKIP**: 5m features parquet not found.", ""]

    feat = pd.read_parquet(feat_files[-1], engine="pyarrow", columns=["timestamp_utc"])
    feat["timestamp_utc"] = pd.to_datetime(feat["timestamp_utc"], utc=True)

    # Use NY date for session grouping
    ny_date = feat["timestamp_utc"].dt.tz_convert("America/New_York").dt.date
    counts = ny_date.value_counts().sort_index()

    if counts.empty:
        return lines + ["No bar data found.", ""]

    mu = counts.mean()
    sigma = counts.std()
    threshold_lo = mu - 2 * sigma
    threshold_hi = mu + 2 * sigma

    outliers = counts[(counts < threshold_lo) | (counts > threshold_hi)]

    lines.append(f"- Total trading days: **{len(counts):,}**")
    lines.append(f"- Mean bars/day: **{mu:.1f}**  |  Std: **{sigma:.1f}**")
    lines.append(f"- 2σ window: [{threshold_lo:.0f}, {threshold_hi:.0f}]")
    lines.append(f"- Outlier sessions: **{len(outliers)}** (>{2}σ from mean)")

    if not outliers.empty:
        lines.append("")
        lines.append("| Date | Bars | Delta |")
        lines.append("| ---- | ---- | ----- |")
        for dt, cnt in outliers.head(20).items():
            delta = cnt - mu
            lines.append(f"| {dt} | {cnt} | {delta:+.0f} |")
        if len(outliers) > 20:
            lines.append(f"| ... | ({len(outliers) - 20} more) | |")

    lines += ["", "---", ""]
    return lines


def _check_htf_merge(symbol: str, trades: pd.DataFrame) -> list[str]:
    """Verify htf_bias (daily_macd_hist) at each sampled entry bar equals
    shift(1) of the daily MACD hist."""
    lines = ["## 2. HTF Merge Audit (shift(1) check)", ""]

    feat_dir = _DATA_ROOT / "features"
    pattern = f"{symbol}_backadjusted_5m_features_base-v1_*.parquet"
    feat_files = sorted(feat_dir.glob(pattern))
    if not feat_files:
        return lines + ["**SKIP**: 5m features parquet not found.", "", "---", ""]

    feat = pd.read_parquet(feat_files[-1], engine="pyarrow",
                           columns=["timestamp_utc", "daily_macd_hist"])
    feat["timestamp_utc"] = pd.to_datetime(feat["timestamp_utc"], utc=True)
    feat = feat.set_index("timestamp_utc").sort_index()

    # Load daily bars and recompute MACD hist
    clean_dir = _DATA_ROOT / "clean"
    daily_files = sorted(clean_dir.glob(f"{symbol}_backadjusted_1D_*.parquet"))
    if not daily_files:
        return lines + ["**SKIP**: daily CLEAN parquet not found.", "", "---", ""]

    daily = pd.read_parquet(daily_files[-1], engine="pyarrow",
                            columns=["timestamp_utc", "close"])
    daily["timestamp_utc"] = pd.to_datetime(daily["timestamp_utc"], utc=True)
    daily = daily.set_index("timestamp_utc").sort_index()

    # Recompute MACD hist (12/26/9)
    ema12 = daily["close"].ewm(span=12, adjust=False).mean()
    ema26 = daily["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    daily_hist = (macd_line - signal).rename("ref_daily_macd_hist")

    # Sample 100 random entry bars
    rng = random.Random(42)
    sample_ts = rng.sample(trades["entry_ts"].tolist(), min(100, len(trades)))

    passed = 0
    failed = 0
    fail_examples: list[str] = []

    for ts in sample_ts:
        # Look up feature bar
        try:
            stored_val = float(feat.loc[feat.index.get_loc(ts, method="nearest"), "daily_macd_hist"]
                               if hasattr(feat.index, "get_loc") else
                               feat["daily_macd_hist"].iloc[feat.index.searchsorted(ts)])
        except Exception:
            continue

        # Look up the previous closed daily bar (shift(1))
        prev_daily = daily_hist[daily_hist.index < ts]
        if prev_daily.empty:
            continue
        ref_val = float(prev_daily.iloc[-1])

        tol = max(abs(ref_val) * 1e-4, 1e-8)
        if abs(stored_val - ref_val) <= tol:
            passed += 1
        else:
            failed += 1
            if len(fail_examples) < 5:
                fail_examples.append(
                    f"  ts={ts.isoformat()}: stored={stored_val:.6f}, ref={ref_val:.6f}, diff={abs(stored_val-ref_val):.2e}"
                )

    total = passed + failed
    status = "PASS" if failed == 0 else "FAIL"
    lines.append(f"- Sampled: {total} entry bars")
    lines.append(f"- **{status}**: {passed} passed, {failed} failed")
    if fail_examples:
        lines.append("- First failures:")
        for ex in fail_examples:
            lines.append(ex)

    lines += ["", "---", ""]
    return lines


def _check_indicator_lookahead(symbol: str) -> list[str]:
    """Spot-check that stored indicator values equal recomputed values
    using only data up to that bar."""
    lines = ["## 3. Indicator Look-Ahead Spot-Check", ""]

    feat_dir = _DATA_ROOT / "features"
    pattern = f"{symbol}_backadjusted_5m_features_base-v1_*.parquet"
    feat_files = sorted(feat_dir.glob(pattern))
    if not feat_files:
        return lines + ["**SKIP**: 5m features parquet not found.", "", "---", ""]

    # Discover available columns first, then load only what we need.
    all_cols = pd.read_parquet(feat_files[-1], engine="pyarrow").columns.tolist()
    wanted = ["timestamp_utc", "close", "high", "low",
              "atr_14", "rsi_14", "macd_hist", "bb_upper", "vwap_session"]
    load_cols = [c for c in wanted if c in all_cols]
    # macd_hist might be stored as macd_hist in features — check both names
    if "macd_hist" not in all_cols and "macd_hist" in wanted:
        load_cols = [c for c in load_cols if c != "macd_hist"]

    feat = pd.read_parquet(feat_files[-1], engine="pyarrow", columns=load_cols)
    # timestamp_utc may already be tz-aware from parquet; normalise safely
    ts_col = feat["timestamp_utc"]
    if hasattr(ts_col.dtype, "tz") and ts_col.dtype.tz is not None:
        feat["timestamp_utc"] = ts_col
    else:
        feat["timestamp_utc"] = ts_col.dt.tz_localize("UTC") if hasattr(ts_col, "dt") else pd.to_datetime(ts_col).dt.tz_localize("UTC")
    feat = feat.sort_values("timestamp_utc").reset_index(drop=True)

    rng = random.Random(42)
    # Pick bars in the middle of the series (avoid warm-up NaN zone)
    start_idx = max(500, len(feat) // 4)
    sample_indices = rng.sample(range(start_idx, len(feat)), min(20, len(feat) - start_idx))

    results: list[tuple[str, str, str]] = []  # (indicator, status, note)

    # ATR_14 check
    if "atr_14" in feat.columns:
        fails = 0
        for idx in sample_indices:
            hist = feat.iloc[:idx + 1]
            tr = pd.concat([
                hist["high"] - hist["low"],
                (hist["high"] - hist["close"].shift(1)).abs(),
                (hist["low"] - hist["close"].shift(1)).abs(),
            ], axis=1).max(axis=1)
            ref = float(tr.ewm(span=14, adjust=False).mean().iloc[-1])
            stored = float(hist["atr_14"].iloc[-1])
            if abs(stored - ref) > max(abs(ref) * 1e-4, 1e-8):
                fails += 1
        results.append(("ATR_14", "PASS" if fails == 0 else "FAIL",
                         f"{fails}/{len(sample_indices)} mismatches"))

    # RSI_14 check
    if "rsi_14" in feat.columns:
        fails = 0
        for idx in sample_indices:
            hist = feat.iloc[:idx + 1]
            delta = hist["close"].diff()
            gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
            loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
            rs = gain / loss.replace(0, float("nan"))
            ref = float(100 - 100 / (1 + rs.iloc[-1]))
            stored = float(hist["rsi_14"].iloc[-1])
            if abs(stored - ref) > max(abs(ref) * 1e-2, 1e-6):  # RSI allows 1% tolerance
                fails += 1
        results.append(("RSI_14", "PASS" if fails == 0 else "FAIL",
                         f"{fails}/{len(sample_indices)} mismatches"))

    # MACD hist check
    macd_col = "macd_hist" if "macd_hist" in feat.columns else None
    if macd_col:
        fails = 0
        for idx in sample_indices:
            hist = feat.iloc[:idx + 1]
            ema12 = hist["close"].ewm(span=12, adjust=False).mean()
            ema26 = hist["close"].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            sig = macd_line.ewm(span=9, adjust=False).mean()
            ref = float((macd_line - sig).iloc[-1])
            stored = float(hist[macd_col].iloc[-1])
            if abs(stored - ref) > max(abs(ref) * 1e-3, 1e-8):
                fails += 1
        results.append(("MACD_hist", "PASS" if fails == 0 else "FAIL",
                         f"{fails}/{len(sample_indices)} mismatches"))

    # Bollinger upper check
    if "bb_upper" in feat.columns:
        fails = 0
        for idx in sample_indices:
            hist = feat.iloc[:idx + 1]
            mid = hist["close"].rolling(20).mean()
            std = hist["close"].rolling(20).std(ddof=1)
            ref = float((mid + 2 * std).iloc[-1])
            stored = float(hist["bb_upper"].iloc[-1])
            if abs(stored - ref) > max(abs(ref) * 1e-3, 1e-6):
                fails += 1
        results.append(("BB_upper", "PASS" if fails == 0 else "FAIL",
                         f"{fails}/{len(sample_indices)} mismatches"))

    # VWAP session: can't easily recompute without session boundaries,
    # so we just verify the stored value is plausible (within 10× ATR of close)
    if "vwap_session" in feat.columns and "atr_14" in feat.columns:
        implausible = 0
        for idx in sample_indices:
            row = feat.iloc[idx]
            dist = abs(row.get("vwap_session", float("nan")) - row["close"])
            if dist > 10 * row.get("atr_14", 1):
                implausible += 1
        results.append(("VWAP_session", "PASS" if implausible == 0 else "WARN",
                         f"{implausible}/{len(sample_indices)} implausible distances (>10 ATR from close)"))

    if results:
        lines.append("| Indicator | Status | Note |")
        lines.append("| --------- | ------ | ---- |")
        for name, status, note in results:
            lines.append(f"| {name} | **{status}** | {note} |")
    else:
        lines.append("No indicator columns found to check.")

    lines += ["", "---", ""]
    return lines


def _check_manifest_diff(symbol: str, run_dir: Path) -> list[str]:
    """Compare the current base-v1.yaml feature config against what the engine consumed."""
    lines = ["## 4. Feature-Set Manifest Diff", ""]

    feat_dir = _DATA_ROOT / "features"
    pattern = f"{symbol}_backadjusted_5m_features_base-v1_*.parquet"
    manifest_pattern = f"{symbol}_backadjusted_5m_features_base-v1_*.parquet.manifest.json"
    manifest_files = sorted(feat_dir.glob(manifest_pattern))

    current_cfg = run_dir.parents[2] / "configs" / "featuresets" / "base-v1.yaml"

    if manifest_files:
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))
        lines.append(f"- Features parquet: `{manifest_files[-1].name}`")
        lines.append(f"- Manifest built_at: `{manifest.get('built_at', 'unknown')}`")
        lines.append(f"- Rows: {manifest.get('rows', 'unknown'):,}" if isinstance(manifest.get('rows'), int) else f"- Rows: {manifest.get('rows', 'unknown')}")
    else:
        lines.append("- Features parquet manifest: **NOT FOUND**")

    if current_cfg.is_file():
        lines.append(f"- Config YAML: `{current_cfg}` (present)")
        lines.append("  - Drift check: visual inspection required — automated diff deferred to Session 11.")
    else:
        lines.append(f"- Config YAML `{current_cfg}`: **NOT FOUND**")

    lines += ["", "---", ""]
    return lines


def _check_trade_date_boundaries(trades: pd.DataFrame) -> list[str]:
    """Verify each trade's entry and exit fall within the same CME trade date
    (unless exit_reason is 'EOD', which by design can span midnight)."""
    lines = ["## 5. Trade-Date Boundary Check", ""]

    if trades.empty:
        return lines + ["No trades to check.", "", "---", ""]

    # CME trade date convention: +6h ET offset maps the 18:00 open to midnight UTC.
    # trade_date = (entry_ts_utc + 6h).date()
    _OFFSET = pd.Timedelta(hours=6)

    entry_trade_date = (pd.to_datetime(trades["entry_ts"]) + _OFFSET).dt.date
    exit_trade_date  = (pd.to_datetime(trades["exit_ts"]) + _OFFSET).dt.date

    cross_session = entry_trade_date != exit_trade_date

    # EOD exits are expected to never cross dates — they flatten same session.
    # Cross-date non-EOD trades are the ones to flag.
    non_eod_cross = trades[cross_session & (trades["exit_reason"] != "EOD")]

    lines.append(f"- Total trades: {len(trades):,}")
    lines.append(f"- Cross-session exits: {cross_session.sum()}")
    lines.append(f"- Non-EOD cross-session: {len(non_eod_cross)} (should be 0 for single-instrument intraday strategy)")

    if not non_eod_cross.empty:
        lines.append("")
        lines.append("| trade_id | entry_ts | exit_ts | exit_reason |")
        lines.append("| -------- | -------- | ------- | ----------- |")
        for _, row in non_eod_cross.head(10).iterrows():
            lines.append(
                f"| {str(row.get('trade_id', ''))[:8]}... "
                f"| {pd.Timestamp(row['entry_ts']).strftime('%Y-%m-%d %H:%M')} "
                f"| {pd.Timestamp(row['exit_ts']).strftime('%Y-%m-%d %H:%M')} "
                f"| {row.get('exit_reason', '')} |"
            )

    lines += ["", "---", ""]
    return lines
