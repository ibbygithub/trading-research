"""Tests for session 35 — parameter sweep tool and trial leaderboard.

Coverage:
- expand_params: cartesian product expansion
- run_sweep: mock-runner integration, trial recording
- build_leaderboard / format_table / generate_html
- Trial schema migration (mode + parent_sweep_id backfill)
- CLI smoke tests for sweep and leaderboard commands
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from trading_research.cli.main import app
from trading_research.cli.sweep import expand_params, run_sweep
from trading_research.eval.leaderboard import build_leaderboard, generate_html
from trading_research.eval.trials import Trial, load_trials, migrate_trials

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

runner = CliRunner()


def _make_mock_runner(sharpe: float = 0.5, calmar: float = 0.8, trades: int = 30):
    """Return a runner callable that returns synthetic results without real I/O."""

    def _runner(config_path: Path, signal_params_override: dict, runs_root: Path, sweep_id: str, data_root: Path) -> dict:
        return {
            "strategy_id": "test-strat",
            "symbol": "6A",
            "timeframe": "15m",
            "signal_params_override": signal_params_override,
            "summary": {
                "sharpe": sharpe,
                "calmar": calmar,
                "max_drawdown_usd": -500.0,
                "win_rate": 0.45,
                "total_trades": trades,
            },
        }

    return _runner


def _dummy_config(tmpdir: Path) -> Path:
    """Write a minimal strategy YAML config for testing."""
    cfg = {
        "strategy_id": "test-strat",
        "symbol": "6A",
        "timeframe": "15m",
        "signal_module": "trading_research.strategies.fx_vwap_reversion_adx",
        "signal_params": {"entry_atr_mult": 1.5, "adx_max": 22.0},
        "backtest": {"fill_model": "next_bar_open", "eod_flat": True, "quantity": 1},
    }
    import yaml

    p = tmpdir / "test-strat.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# expand_params tests
# ---------------------------------------------------------------------------


def test_expand_params_cartesian_product() -> None:
    combos = expand_params(["a=1,2,3", "b=x,y"])
    assert len(combos) == 6  # 3 × 2
    keys = {frozenset(c.keys()) for c in combos}
    assert keys == {frozenset({"a", "b"})}


def test_expand_params_single_param() -> None:
    combos = expand_params(["entry_atr_mult=1.0,1.5,2.0"])
    assert len(combos) == 3
    values = [c["entry_atr_mult"] for c in combos]
    assert values == [1.0, 1.5, 2.0]


def test_expand_params_coerces_numeric() -> None:
    combos = expand_params(["x=1,2.5,3"])
    assert combos[0]["x"] == 1       # int
    assert combos[1]["x"] == 2.5     # float
    assert combos[2]["x"] == 3       # int


def test_expand_params_empty_produces_one_empty_combo() -> None:
    combos = expand_params([])
    assert combos == [{}]


def test_expand_params_rejects_missing_equals() -> None:
    with pytest.raises(ValueError, match="expected"):
        expand_params(["no_equals_sign"])


def test_expand_params_twelve_variant_grid() -> None:
    """Acceptance: 3×4 grid produces exactly 12 combinations."""
    combos = expand_params(["entry_atr_mult=1.0,1.5,2.0", "adx_max=18,22,25,28"])
    assert len(combos) == 12


# ---------------------------------------------------------------------------
# run_sweep tests (mock runner)
# ---------------------------------------------------------------------------


def test_sweep_produces_n_trials() -> None:
    """Sweep with a 3×2 grid produces 6 trial entries in the registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = _dummy_config(root)

        results = run_sweep(
            config_path=config,
            param_specs=["entry_atr_mult=1.0,1.5,2.0", "adx_max=18,22"],
            runs_root=root,
            data_root=root,
            runner=_make_mock_runner(),
        )

        assert len(results) == 6
        trials = load_trials(root / ".trials.json")
        assert len(trials) == 6


def test_sweep_trials_have_exploration_mode() -> None:
    """All sweep-generated trials must be tagged mode='exploration'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = _dummy_config(root)

        run_sweep(
            config_path=config,
            param_specs=["entry_atr_mult=1.0,2.0"],
            runs_root=root,
            data_root=root,
            runner=_make_mock_runner(),
        )

        trials = load_trials(root / ".trials.json")
        assert all(t.mode == "exploration" for t in trials)


def test_sweep_trials_share_parent_sweep_id() -> None:
    """All variants in one sweep share the same parent_sweep_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = _dummy_config(root)

        run_sweep(
            config_path=config,
            param_specs=["adx_max=18,22,25"],
            runs_root=root,
            data_root=root,
            runner=_make_mock_runner(),
        )

        trials = load_trials(root / ".trials.json")
        sweep_ids = {t.parent_sweep_id for t in trials}
        # All three should share one sweep ID.
        assert len(sweep_ids) == 1
        assert None not in sweep_ids


def test_sweep_stores_metrics_in_registry() -> None:
    """Sweep stores calmar, win_rate, instrument, timeframe in registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = _dummy_config(root)

        run_sweep(
            config_path=config,
            param_specs=["entry_atr_mult=1.5"],
            runs_root=root,
            data_root=root,
            runner=_make_mock_runner(calmar=1.2, sharpe=0.8, trades=45),
        )

        trials = load_trials(root / ".trials.json")
        assert len(trials) == 1
        t = trials[0]
        assert t.calmar == pytest.approx(1.2)
        assert t.win_rate == pytest.approx(0.45)
        assert t.total_trades == 45
        assert t.instrument == "6A"
        assert t.timeframe == "15m"


def test_sweep_two_sweeps_have_distinct_ids() -> None:
    """Two separate sweeps produce distinct parent_sweep_ids."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = _dummy_config(root)

        run_sweep(
            config_path=config,
            param_specs=["adx_max=18,22"],
            runs_root=root,
            data_root=root,
            runner=_make_mock_runner(),
        )
        run_sweep(
            config_path=config,
            param_specs=["adx_max=25,28"],
            runs_root=root,
            data_root=root,
            runner=_make_mock_runner(),
        )

        trials = load_trials(root / ".trials.json")
        assert len(trials) == 4
        sweep_ids = {t.parent_sweep_id for t in trials}
        assert len(sweep_ids) == 2  # two distinct sweep IDs


# ---------------------------------------------------------------------------
# build_leaderboard tests
# ---------------------------------------------------------------------------


def _seed_registry(root: Path, entries: list[dict]) -> None:
    """Write trial entries directly to .trials.json for testing."""
    path = root / ".trials.json"
    path.write_text(json.dumps({"trials": entries}, indent=2), encoding="utf-8")


def test_leaderboard_filter_by_mode() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "2026-01-01T00:00:00+00:00", "strategy_id": "s1",
             "config_hash": "a", "sharpe": 1.2, "trial_group": "s1",
             "code_version": "abc", "featureset_hash": None, "cohort_label": "abc",
             "mode": "exploration", "calmar": 1.5, "instrument": "6A", "timeframe": "15m"},
            {"timestamp": "2026-01-02T00:00:00+00:00", "strategy_id": "s2",
             "config_hash": "b", "sharpe": 0.8, "trial_group": "s2",
             "code_version": "abc", "featureset_hash": None, "cohort_label": "abc",
             "mode": "validation", "calmar": 0.6, "instrument": "6E", "timeframe": "5m"},
        ])

        trials = build_leaderboard(
            registry_path=root / ".trials.json",
            filters=["mode=exploration"],
        )
        assert len(trials) == 1
        assert trials[0].strategy_id == "s1"


def test_leaderboard_filter_by_instrument() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "T1", "strategy_id": "a", "config_hash": "", "sharpe": 1.0,
             "trial_group": "a", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "instrument": "6A", "timeframe": "5m"},
            {"timestamp": "T2", "strategy_id": "b", "config_hash": "", "sharpe": 1.5,
             "trial_group": "b", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "instrument": "6C", "timeframe": "60m"},
        ])

        trials = build_leaderboard(
            registry_path=root / ".trials.json",
            filters=["instrument=6A"],
        )
        assert len(trials) == 1
        assert trials[0].instrument == "6A"


def test_leaderboard_sort_by_calmar_descending() -> None:
    """Default sort (descending) puts highest Calmar first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "T1", "strategy_id": "low", "config_hash": "", "sharpe": 0.5,
             "trial_group": "low", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "calmar": 0.3},
            {"timestamp": "T2", "strategy_id": "mid", "config_hash": "", "sharpe": 1.0,
             "trial_group": "mid", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "calmar": 1.5},
            {"timestamp": "T3", "strategy_id": "high", "config_hash": "", "sharpe": 1.5,
             "trial_group": "high", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "calmar": 3.0},
        ])

        trials = build_leaderboard(
            registry_path=root / ".trials.json",
            sort_key="calmar",
        )
        calmars = [t.calmar for t in trials]
        assert calmars == sorted(calmars, reverse=True)


def test_leaderboard_none_calmar_sorts_last() -> None:
    """Trials with no Calmar value sort after trials that have one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "T1", "strategy_id": "no-calmar", "config_hash": "",
             "sharpe": 2.0, "trial_group": "x", "code_version": "x",
             "featureset_hash": None, "cohort_label": "x", "mode": "exploration"},
            {"timestamp": "T2", "strategy_id": "has-calmar", "config_hash": "",
             "sharpe": 0.5, "trial_group": "y", "code_version": "x",
             "featureset_hash": None, "cohort_label": "x",
             "mode": "exploration", "calmar": 1.0},
        ])

        trials = build_leaderboard(
            registry_path=root / ".trials.json",
            sort_key="calmar",
        )
        # The trial with calmar=1.0 should come before the one with calmar=None.
        assert trials[0].strategy_id == "has-calmar"


def test_leaderboard_returns_all_when_no_filters() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "T1", "strategy_id": "a", "config_hash": "", "sharpe": 1.0,
             "trial_group": "a", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration"},
            {"timestamp": "T2", "strategy_id": "b", "config_hash": "", "sharpe": 0.5,
             "trial_group": "b", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "validation"},
        ])

        trials = build_leaderboard(registry_path=root / ".trials.json")
        assert len(trials) == 2


# ---------------------------------------------------------------------------
# HTML generation tests
# ---------------------------------------------------------------------------


def test_leaderboard_html_contains_table() -> None:
    trials = [
        Trial(
            timestamp="2026-01-01T00:00:00+00:00",
            strategy_id="test",
            config_hash="abc",
            sharpe=1.2,
            trial_group="test",
            code_version="sha",
            featureset_hash=None,
            cohort_label="sha",
            mode="exploration",
            calmar=2.0,
            instrument="6A",
            timeframe="15m",
        )
    ]
    html = generate_html(trials, sort_key="calmar", filters=["mode=exploration"])
    assert "<table>" in html
    assert "6A" in html
    assert "exploration" in html
    assert "2.000" in html  # calmar formatted


def test_leaderboard_html_written_to_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "T1", "strategy_id": "a", "config_hash": "", "sharpe": 1.0,
             "trial_group": "a", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "calmar": 1.5,
             "instrument": "6A", "timeframe": "15m"},
        ])

        out_path = root / "lb.html"
        result = runner.invoke(
            app,
            [
                "leaderboard",
                "--filter", "mode=exploration",
                "--sort", "calmar",
                "--html-out", str(out_path),
                "--out", str(root),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out_path.exists()
        html_content = out_path.read_text(encoding="utf-8")
        assert "<table>" in html_content


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


def test_migration_adds_mode_field() -> None:
    """migrate_trials backfills mode='validation' for entries that lack it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / ".trials.json"
        path.write_text(
            json.dumps({"trials": [
                {"timestamp": "2026-01-01T00:00:00+00:00", "strategy_id": "old",
                 "config_hash": "x", "sharpe": 1.0, "trial_group": "old",
                 "code_version": "pre", "featureset_hash": None, "cohort_label": "pre"},
            ]}),
            encoding="utf-8",
        )

        migrate_trials(path, backup=False)

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["trials"][0]["mode"] == "validation"
        assert data["trials"][0]["parent_sweep_id"] is None


def test_migration_idempotent_with_new_fields() -> None:
    """Running migrate_trials twice doesn't change the output (idempotency)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / ".trials.json"
        path.write_text(
            json.dumps({"trials": [
                {"timestamp": "T", "strategy_id": "x", "config_hash": "h",
                 "sharpe": 0.5, "trial_group": "x", "code_version": "sha",
                 "featureset_hash": None, "cohort_label": "sha"},
            ]}),
            encoding="utf-8",
        )

        migrate_trials(path, backup=False)
        after_first = path.read_text(encoding="utf-8")
        migrate_trials(path, backup=False)
        after_second = path.read_text(encoding="utf-8")
        assert after_first == after_second


def test_existing_trial_defaults_to_validation() -> None:
    """Trials loaded from legacy registry without 'mode' field default to 'validation'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / ".trials.json"
        path.write_text(
            json.dumps({"trials": [
                {"timestamp": "T", "strategy_id": "x", "config_hash": "h",
                 "sharpe": 0.5, "trial_group": "x", "code_version": "sha",
                 "featureset_hash": None, "cohort_label": "sha"},
            ]}),
            encoding="utf-8",
        )

        trials = load_trials(path)
        assert trials[0].mode == "validation"


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


def test_leaderboard_cli_empty_registry() -> None:
    """Leaderboard CLI exits 0 with a helpful message when no trials exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # No .trials.json exists yet.
        result = runner.invoke(app, ["leaderboard", "--out", str(root)])
        assert result.exit_code == 0
        assert "No trials" in result.output


def test_leaderboard_cli_filter_and_sort() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _seed_registry(root, [
            {"timestamp": "T1", "strategy_id": "a", "config_hash": "", "sharpe": 1.0,
             "trial_group": "a", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "exploration", "calmar": 1.5, "instrument": "6A"},
            {"timestamp": "T2", "strategy_id": "b", "config_hash": "", "sharpe": 0.5,
             "trial_group": "b", "code_version": "x", "featureset_hash": None,
             "cohort_label": "x", "mode": "validation", "calmar": 0.8, "instrument": "6E"},
        ])

        result = runner.invoke(
            app,
            ["leaderboard", "--filter", "mode=exploration", "--sort", "calmar", "--out", str(root)],
        )
        assert result.exit_code == 0
        # strategy_id "a" and its instrument "6A" should appear.
        assert "6A" in result.output
        # strategy_id "b"'s instrument "6E" should NOT appear (filtered out).
        assert "6E" not in result.output


def test_sweep_cli_smoke_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sweep CLI command runs without error when the runner is monkeypatched."""
    import trading_research.cli.sweep as sweep_mod

    call_count = {"n": 0}

    def _fake_runner(config_path, signal_params_override, runs_root, sweep_id, data_root):
        call_count["n"] += 1
        return {
            "strategy_id": "test-strat",
            "symbol": "6A",
            "timeframe": "15m",
            "signal_params_override": signal_params_override,
            "summary": {"sharpe": 0.5, "calmar": 0.8, "max_drawdown_usd": -200.0,
                        "win_rate": 0.4, "total_trades": 20},
        }

    monkeypatch.setattr(sweep_mod, "_real_runner", _fake_runner)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = _dummy_config(root)

        result = runner.invoke(
            app,
            [
                "sweep",
                "--strategy", str(config),
                "--param", "adx_max=18,22,25",
                "--out", str(root),
            ],
        )
        assert result.exit_code == 0, result.output
        assert call_count["n"] == 3
        trials = load_trials(root / ".trials.json")
        assert len(trials) == 3
        assert all(t.mode == "exploration" for t in trials)
