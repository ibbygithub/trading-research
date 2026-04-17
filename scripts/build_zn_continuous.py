"""One-shot script: download all quarterly TY contracts and build the
back-adjusted ZN continuous series.

Run:
    uv run python scripts/build_zn_continuous.py

Output:
    data/clean/ZN_1m_backadjusted_2010-01-01_2026-04-11.parquet
    data/clean/ZN_1m_unadjusted_2010-01-01_2026-04-11.parquet
    data/clean/ZN_roll_log_2010-01-01_2026-04-11.json
    data/raw/contracts/TY*_1m_*.parquet   (cached per-contract files)
"""

import sys
from datetime import date
from pathlib import Path

# Ensure the project src is importable when running from repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_research.data.continuous import build_back_adjusted_continuous
from trading_research.utils.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    start = date(2010, 1, 1)
    end = date(2026, 4, 11)

    logger.info("build_zn_continuous_start", start=start.isoformat(), end=end.isoformat())

    result = build_back_adjusted_continuous(
        symbol="ZN",
        start_date=start,
        end_date=end,
    )

    logger.info(
        "build_zn_continuous_done",
        adjusted=str(result.adjusted_path),
        unadjusted=str(result.unadjusted_path),
        roll_log=str(result.roll_log_path),
        total_rows=result.total_rows,
        rolls=len(result.roll_events),
        total_adj=round(sum(e.adjustment_delta for e in result.roll_events), 6),
    )
    print(f"\nDone. {result.total_rows:,} rows, {len(result.roll_events)} rolls.")
    print(f"Adjusted  : {result.adjusted_path}")
    print(f"Unadjusted: {result.unadjusted_path}")
    print(f"Roll log  : {result.roll_log_path}")


if __name__ == "__main__":
    main()
