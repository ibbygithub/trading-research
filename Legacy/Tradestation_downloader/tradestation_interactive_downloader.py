#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
from __future__ import annotations
import argparse, json, os, re, sys, time, subprocess, tempfile, shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from types import SimpleNamespace  # <-- IMPORT ADDED HERE

# ---------- Defaults (Windows-first; override via env/CLI) ----------
HERE = Path(__file__).resolve().parent
DEF_VENVPY       = os.environ.get("VENVPY", "")  # if blank, use current interpreter
DEF_DOWNLOADER = os.environ.get("DOWNLOADER", str((HERE / "tradestation_downloader_fixed.py").resolve()))
DEF_ROOT_OUT     = os.environ.get("ROOT_OUT", r"C:\ML-data\markets\futures")
DEF_LOGDIR       = os.environ.get("LOGDIR", r"C:\ML-data\markets\futures\_logs")

# ---------- TF list (includes 1 minute) ----------
TFS_DEFAULT = [
    "1 month","1 week","1 day","1440 minutes",
    "240 minutes","120 minutes","60 minutes","30 minutes",
    "20 minutes","15 minutes","10 minutes","5 minutes","3 minutes",
    "1 minute",
]

# Map human TF -> token used in outdir
TF_TOKEN_MAP = {
    "1 month":"1mo","1 week":"1w","1 day":"1d","1440 minutes":"1440m",
    "240 minutes":"240m","120 minutes":"120m","60 minutes":"60m","30 minutes":"30m",
    "20 minutes":"20m","15 minutes":"15m","10 minutes":"10m","5 minutes":"5m",
    "3 minutes":"3m","1 minute":"1m","1 minutes":"1m",  # <- allow both spellings
}

# Accept aliases from CLI and normalize
TF_ALIASES = {
    "1m":"1 minute","1min":"1 minute","1minute":"1 minute","1 minutes":"1 minute",
    "3m":"3 minutes","5m":"5 minutes","10m":"10 minutes","15m":"15 minutes",
    "20m":"20 minutes","30m":"30 minutes","60m":"60 minutes","120m":"120 minutes","240m":"240 minutes",
    "1d":"1 day","1w":"1 week","1mo":"1 month","1440m":"1440 minutes",
}

def normalize_tf(tf: str) -> str:
    t = tf.strip().lower()
    return TF_ALIASES.get(t, tf)

def tf_to_token(tf: str) -> str:
    key = tf.strip()
    if key not in TF_TOKEN_MAP:
        raise SystemExit(f"Unknown timeframe: {tf}")
    return TF_TOKEN_MAP[key]

def infer_exchange(sym_up: str) -> str:
    if sym_up in {"GC","SI","HG","PA","PL"}:     return "COMEX"
    if sym_up in {"CL","NG","RB","HO","BZ"}:     return "NYMEX"
    if sym_up in {"ES","NQ","YM","RTY","MES","MNQ","MYM"}: return "CME"
    if sym_up in {"ZC","C","ZW","W","ZS","S","ZM","BO","KE","ZR"}: return "CBOT"
    if sym_up in {"GE","SR3","ED","ZB","ZN","ZF","ZT","TN"}: return "CME"
    if sym_up in {"6A","6B","6C","6E","6J","6M","6N","DX"}:   return "CME"
    return "CME"

def now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def pick_python_exe(cli_py: Optional[str]) -> str:
    if cli_py and Path(cli_py).exists(): return cli_py
    if DEF_VENVPY and Path(DEF_VENVPY).exists(): return DEF_VENVPY
    return sys.executable

RETRY_AFTER_RE = re.compile(r"Retry-After:\s*(\d+)", re.IGNORECASE)

def run_with_retries(cmd: List[str], logfile: Path,
                      max_retries: int = 4, base_sleep: float = 5.0,
                      polite_gap: float = 5.0, tee_console: bool = True) -> int:
    attempt = 0; backoff = base_sleep
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("a", encoding="utf-8") as f:
        while True:
            attempt += 1
            stamp = now_utc_str()
            f.write(f"\n==== {stamp} ATTEMPT {attempt} ====\n"); f.flush()
            if tee_console: print(f"[{stamp}] RUN: {' '.join(cmd)}")

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, text=True, encoding="utf-8", errors="replace"
            )
            retry_after_sec = None
            for line in proc.stdout:
                f.write(line)
                if tee_console: print(line.rstrip())
                m = RETRY_AFTER_RE.search(line)
                if m:
                    try: retry_after_sec = int(m.group(1))
                    except: retry_after_sec = None

            rc = proc.wait()
            f.write(f"==== EXIT CODE: {rc} ====\n"); f.flush()
            if rc == 0:
                time.sleep(polite_gap)
                return 0
            if attempt > max_retries:
                return rc
            sleep_for = (retry_after_sec + 2) if (retry_after_sec and retry_after_sec > 0) else backoff
            if retry_after_sec is None: backoff *= 2
            if tee_console:
                print(f"Retrying in {sleep_for:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_for)

def build_outdir(root_out: Path, exchange: str, symbol_dir: str, tf_token: str) -> Path:
    return root_out / exchange / symbol_dir / "continuous" / "raw" / tf_token / "v1"

def years_in_range(start_year: int, end_year: int) -> List[int]:
    if end_year < start_year: raise SystemExit("END_YEAR must be >= START_YEAR")
    return list(range(int(start_year), int(end_year) + 1))

# --- PROBE: find a 1-minute alias the downloader accepts ---
ONE_MINUTE_CANDIDATES = [
    "1 minutes", "1 minute", "1min", "1m", "1 Minute", "1 MINUTE",
]

def probe_1m_alias(venv_py: str, downloader: Path, symbol: str,
                   start_year: int, outdir: Path, skip_existing: bool, verbose: bool,
                   logdir: Path) -> Optional[str]:
    probe_dir = logdir / "_probe_1m"
    ensure_dir(probe_dir)
    # Keep outdir valid but isolated so we don't pollute production during probe
    tmp_out = probe_dir / "out"
    ensure_dir(tmp_out)
    for cand in ONE_MINUTE_CANDIDATES:
        cmd = [
            venv_py, str(downloader),
            "--symbol", symbol, "--timeframe", cand,
            "--start-year", str(start_year), "--end-year", str(start_year),
            "--outdir", str(tmp_out),
        ]
        if skip_existing: cmd += ["--skip-existing"]
        if verbose: cmd += ["--verbose"]

        # Capture output once; we want to know if error mentions timeframe
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        except Exception as e:
            print(f"[probe] {cand}: exception {e}")
            continue

        out = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
        if "Unrecognized timeframe" in out or "Unknown timeframe" in out:
            print(f"[probe] reject '{cand}' -> downloader says unrecognized")
            continue
        # If exit 0 or it progressed past TF parsing (e.g., started downloading/segmenting), accept and stop
        if res.returncode == 0 or "Starting new HTTPS connection" in out or "oauth/token" in out:
            print(f"[probe] accept '{cand}' as 1-minute alias")
            # Cleanup any files it may have created
            try: shutil.rmtree(tmp_out, ignore_errors=True)
            except: pass
            return cand

        print(f"[probe] ambiguous '{cand}' (rc={res.returncode}); output len={len(out)} -> skipping")
    return None

# =========================================================================
# === NEW FUNCTION TO GET SETTINGS INTERACTIVELY ===
# =========================================================================

def get_interactive_settings() -> SimpleNamespace:
    """
    Asks the user for settings interactively, providing defaults.
    Returns an object that mimics the 'args' object from argparse.
    """
    print("--- 📥 Configure Download ---")
    print("Hit 'Enter' to accept the default value shown in [brackets].\n")

    # --- Get defaults ---
    # Using @GC as the default based on your goal to build a bot for gold futures
    default_symbol = "@GC"
    default_start_year = 2005
    default_end_year = datetime.now().year # Default to the current year
    default_tfs = "1 minute, 5 minutes, 60 minutes, 1 day" # A more focused default set
    
    # --- Symbol ---
    symbol = input(f"Enter symbol [default: {default_symbol}]: ") or default_symbol

    # --- Start Year (with type conversion and validation) ---
    while True:
        try:
            start_year_str = input(f"Enter start year [default: {default_start_year}]: ") or str(default_start_year)
            start_year = int(start_year_str)
            break
        except ValueError:
            print("Invalid input. Please enter a number (e.g., 2005).")

    # --- End Year (with type conversion and validation) ---
    while True:
        try:
            end_year_str = input(f"Enter end year [default: {default_end_year}]: ") or str(default_end_year)
            end_year = int(end_year_str)
            if end_year < start_year:
                print(f"End year must be {start_year} or later.")
            else:
                break
        except ValueError:
            print(f"Invalid input. Please enter a number (e.g., {default_end_year}).")

    # --- Timeframes ---
    tfs = input(f"Enter TFs (comma-separated) [default: {default_tfs}]: ") or default_tfs

    # --- Boolean Flags (like --per-year) ---
    per_year_input = input("Download per-year? (y/n) [default: n]: ").lower()
    per_year = per_year_input in ['y', 'yes']

    skip_existing_input = input("Skip existing files? (y/n) [default: y]: ").lower()
    skip_existing = skip_existing_input not in ['n', 'no'] # Default to True
    
    # --- Create the 'args' object ---
    # We fill this with *all* the values your main() function expects,
    # even ones we didn't ask for (using their original defaults).
    
    print("\n--- ⚙️ Settings Applied ---")
    print(f"Symbol:     {symbol}")
    print(f"Years:      {start_year} - {end_year}")
    print(f"Timeframes: {tfs}")
    print(f"Per-Year:   {per_year}")
    print(f"Skip Files: {skip_existing}")
    print("----------------------------\n")
    
    return SimpleNamespace(
        # Values from user
        symbol=symbol,
        start_year=start_year,
        end_year=end_year,
        tfs=tfs,
        per_year=per_year,
        skip_existing=skip_existing,
        
        # --- Default values for other args your script needs ---
        # These are the same defaults from your original argparse setup
        downloader=DEF_DOWNLOADER,
        venvpy=None,
        root_out=DEF_ROOT_OUT,
        logdir=DEF_LOGDIR,
        base_url=None,
        intraday_cap=None,
        segment_days=None,
        equities_session_template=None,
        verbose=False,
        max_retries=4,
        base_sleep=5.0,
        polite_gap=5.0,
        no_tee=False,
        dry_run=False,
        probe_1m=True
    )

# =========================================================================
# === MODIFIED MAIN FUNCTION ===
# =========================================================================

def main() -> int:
    # --- DELETED argparse block ---
    # --- REPLACED with interactive settings ---
    try:
        args = get_interactive_settings()
    except KeyboardInterrupt:
        print("\n[CANCELLED] Setup aborted by user.")
        return 1
    
    # --- ALL CODE BELOW THIS POINT IS YOUR ORIGINAL SCRIPT, UNCHANGED ---
    symbol_raw = args.symbol
    start_year = int(args.start_year); end_year = int(args.end_year)

    venv_py = pick_python_exe(args.venvpy)
    downloader = Path(args.downloader)
    if not downloader.exists():
        raise SystemExit(f"Downloader not found: {downloader}")

    root_out = Path(args.root_out); ensure_dir(root_out)
    logdir   = Path(args.logdir);   ensure_dir(logdir)

    symbol_dir = symbol_raw.lstrip("@"); sym_up = symbol_dir.upper()
    exchange = os.environ.get("EXCHANGE_OVERRIDE") or infer_exchange(sym_up)

    tfs_in = [t.strip() for t in args.tfs.split(",")] if args.tfs else list(TFS_DEFAULT)
    tfs_norm = [normalize_tf(t) for t in tfs_in]

    runlog = logdir / f"run_all_{symbol_dir}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"
    with runlog.open("a", encoding="utf-8") as rl:
        rl.write(f"== {now_utc_str()} Start: SYM={symbol_raw} ({exchange}) Years={start_year}-{end_year}\n")
        rl.write(f"[paths] root_out={root_out}\n[paths] logdir={logdir}\n[paths] downloader={downloader}\n")

    summary: Dict[str, Any] = {
        "symbol": symbol_raw, "exchange": exchange,
        "years": [start_year, end_year],
        "tfs": tfs_norm, "start_utc": now_utc_str(), "details": [],
    }

    # If 1-minute is requested, optionally probe aliases
    one_min_alias: Optional[str] = None
    if args.probe_1m and any(tf.lower() in {"1 minute", "1 minutes"} for tf in tfs_norm):
        print("[probe] Probing 1-minute aliases accepted by downloader...")
        one_min_alias = probe_1m_alias(
            venv_py, downloader, symbol_raw, start_year,
            root_out, args.skip_existing, args.verbose, logdir
        )
        if one_min_alias:
            print(f"[probe] Resolved 1-minute -> '{one_min_alias}'")
        else:
            print("[probe] Could not resolve 1-minute alias; will try '1 minutes' and '1min' during actual runs.")

    try:
        for tf in tfs_norm:
            # Swap in probed alias for 1-minute if available
            tf_effective = (one_min_alias if tf.lower() in {"1 minute", "1 minutes"} and one_min_alias else tf)

            tf_token = tf_to_token(tf)  # token for outdir naming based on normalized TF (not alias)
            outdir = build_outdir(root_out, exchange, symbol_dir, tf_token)
            ensure_dir(outdir)
            safe_tf = tf_token  # short/clean token in filenames
            tflog = logdir / f"{symbol_dir}_{safe_tf}.log"

            tf_result: Dict[str, Any] = {
                "timeframe": tf,
                "alias_used": tf_effective if tf_effective != tf else None,
                "token": tf_token, "outdir": str(outdir), "log": str(tflog),
                "calls": []
            }
            summary["details"].append(tf_result)

            with runlog.open("a", encoding="utf-8") as rl:
                rl.write(f"-- {now_utc_str()} {symbol_raw} {tf_effective} {start_year}->{end_year} -> {outdir}\n")

            # build calls (per-year or span)
            yr_list = years_in_range(start_year, end_year) if args.per_year else [None]
            for y in yr_list:
                syear = (y if y is not None else start_year)
                eyear = (y if y is not None else end_year)
                cmd = [
                    venv_py, str(downloader),
                    "--symbol", symbol_raw,
                    "--timeframe", tf_effective,
                    "--start-year", str(syear),
                    "--end-year", str(eyear),
                    "--outdir", str(outdir),
                ]
                if args.base_url: cmd += ["--base-url", args.base_url]
                if args.intraday_cap is not None: cmd += ["--intraday-cap", str(args.intraday_cap)]
                if args.segment_days is not None: cmd += ["--segment-days", str(args.segment_days)]
                if args.equities_session_template: cmd += ["--equities-session-template", args.equities_session_template]
                if args.skip_existing: cmd += ["--skip-existing"]
                if args.verbose: cmd += ["--verbose"]

                tf_result["calls"].append({"year": y, "cmd": cmd})
                if args.dry_run:
                    print(f"[DRY-RUN] {' '.join(cmd)}")
                    continue

                if not args.no_tee:
                    print(f"[{now_utc_str()}] START {tf_effective} year={eyear if y else f'{start_year}-{end_year}'} -> {outdir}")
                rc = run_with_retries(
                    cmd, tflog,
                    max_retries=args.max_retries, base_sleep=args.base_sleep,
                    polite_gap=args.polite_gap, tee_console=(not args.no_tee)
                )
                tf_result["calls"][-1]["exit_code"] = rc
                if rc != 0:
                    with runlog.open("a", encoding="utf-8") as rl:
                        rl.write(f"[ERROR] {tf_effective} year={y}: exit={rc}, see {tflog}\n")
            time.sleep(0.2)

    except KeyboardInterrupt:
        print("[CANCELLED] KeyboardInterrupt, writing summary...")
    finally:
        summary["end_utc"] = now_utc_str()
        sum_path = logdir / f"run_all_{symbol_dir}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_summary.json"
        try: sum_path.write_text(json.dumps(summary, indent=2), encoding="f-8")
        except: pass
        print(json.dumps(summary, indent=2))
        with runlog.open("a", encoding="utf-8") as rl:
            rl.write(f"== {summary['end_utc']} Complete: SYM={symbol_raw} ({exchange}) Years={start_year}-{end_year} ==\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())