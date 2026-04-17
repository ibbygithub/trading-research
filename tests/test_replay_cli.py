"""Tests for the replay CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from trading_research.cli.main import app

runner = CliRunner()


def test_replay_help_exits_zero():
    result = runner.invoke(app, ["replay", "--help"])
    assert result.exit_code == 0, result.output


def test_replay_invalid_symbol_exits_nonzero():
    """An unknown symbol should raise DataNotFoundError and exit with code 2."""
    result = runner.invoke(
        app,
        [
            "replay",
            "--symbol", "INVALID_SYMBOL_XYZ",
            "--from", "2024-01-02",
            "--to", "2024-01-31",
        ],
    )
    assert result.exit_code == 2, (
        f"Expected exit code 2, got {result.exit_code}.\nOutput:\n{result.output}"
    )
    assert "ERROR" in result.output


def test_replay_invalid_date_format_exits_2():
    result = runner.invoke(
        app,
        [
            "replay",
            "--symbol", "ZN",
            "--from", "not-a-date",
            "--to", "2024-01-31",
        ],
    )
    assert result.exit_code == 2
