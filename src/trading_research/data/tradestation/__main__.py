"""CLI entry for historical bar downloads.

Usage:

    uv run python -m trading_research.data.tradestation.download \\
        --symbol ZN --start 2024-01-01 --end 2024-01-31
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from trading_research.utils.logging import configure

from .download import DEFAULT_RAW_DIR, DEFAULT_WINDOW_DAYS, download_historical_bars


@click.command()
@click.option("--symbol", required=True, help="Root symbol, e.g. ZN")
@click.option("--start", "start_str", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", "end_str", required=True, help="End date YYYY-MM-DD")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_RAW_DIR,
    show_default=True,
)
@click.option(
    "--window-days", type=int, default=DEFAULT_WINDOW_DAYS, show_default=True
)
def main(symbol: str, start_str: str, end_str: str, output_dir: Path, window_days: int) -> None:
    configure()
    start_date = date.fromisoformat(start_str)
    end_date = date.fromisoformat(end_str)
    result = download_historical_bars(
        symbol,
        start_date,
        end_date,
        output_dir=output_dir,
        window_days=window_days,
    )
    click.echo(f"rows_downloaded     : {result.rows_downloaded}")
    click.echo(f"expected_naive      : {result.expected_row_count_naive}")
    click.echo(f"api_calls_made      : {result.api_calls_made}")
    click.echo(f"rate_limit_hits     : {result.rate_limit_hits}")
    click.echo(f"duration_seconds    : {result.duration_seconds}")
    click.echo(f"parquet             : {result.parquet_path}")
    click.echo(f"metadata            : {result.metadata_path}")


if __name__ == "__main__":
    main()
