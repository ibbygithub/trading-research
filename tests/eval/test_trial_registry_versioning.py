"""Acceptance tests for session 24 — trial registry cohort versioning."""

import json
import math
import tempfile
from pathlib import Path

import pytest

from trading_research.eval.trials import (
    Trial,
    compute_dsr,
    load_trials,
    migrate_trials,
    record_trial,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trial(
    sharpe: float,
    cohort: str,
    n_obs: int = 252,
    skewness: float = 0.0,
    kurtosis_pearson: float = 3.0,
) -> Trial:
    return Trial(
        timestamp="2026-01-01T00:00:00+00:00",
        strategy_id="test-strat",
        config_hash="abc123",
        sharpe=sharpe,
        trial_group="test-strat",
        code_version=cohort,
        featureset_hash=None,
        cohort_label=cohort,
        n_obs=n_obs,
        skewness=skewness,
        kurtosis_pearson=kurtosis_pearson,
    )


def _legacy_registry(path: Path) -> None:
    """Write a pre-migration flat-list JSON registry."""
    entries = [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "strategy_id": "old-strat",
            "config_hash": "abc",
            "sharpe": 1.2,
            "trial_group": "old-strat",
        },
        {
            "timestamp": "2026-02-01T00:00:00+00:00",
            "strategy_id": "old-strat",
            "config_hash": "def",
            "sharpe": 0.8,
            "trial_group": "old-strat",
        },
    ]
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


def test_new_trial_has_code_version() -> None:
    """A trial written via record_trial must carry a non-empty code_version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        record_trial(root, "my-strat", Path("nonexistent.yaml"), 1.5)
        trials = load_trials(root / ".trials.json")
        assert len(trials) == 1
        t = trials[0]
        assert t.code_version, "code_version must be non-empty"
        assert t.code_version != "pre-hardening", (
            "new trial should carry a real git SHA, not the migration sentinel"
        )
        # cohort_label defaults to code_version when not supplied
        assert t.cohort_label == t.code_version


def test_migration_idempotent() -> None:
    """Running migrate_trials twice produces the same output as running it once."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = Path(tmpdir) / ".trials.json"
        _legacy_registry(registry)

        migrate_trials(registry, backup=False)
        after_first = registry.read_text(encoding="utf-8")

        migrate_trials(registry, backup=False)
        after_second = registry.read_text(encoding="utf-8")

        assert after_first == after_second, "migration must be idempotent"

        # Verify the sentinel values were set.
        data = json.loads(after_first)
        assert "trials" in data, "migrated registry must use {'trials': [...]}"
        for entry in data["trials"]:
            assert entry["code_version"] == "pre-hardening"
            assert entry["cohort_label"] == "pre-hardening"
            assert "featureset_hash" in entry


def test_dsr_within_cohort() -> None:
    """compute_dsr returns a finite float for a cohort with >= MIN_TRIALS_FOR_DSR trials."""
    trials = [
        _make_trial(sharpe=1.2, cohort="sha-abc"),
        _make_trial(sharpe=0.8, cohort="sha-abc"),
        _make_trial(sharpe=1.5, cohort="sha-abc"),
    ]
    result = compute_dsr(trials, cohort="sha-abc")
    assert result is not None, "DSR must return a value for a valid cohort"
    assert isinstance(result, float)
    assert math.isfinite(result), f"DSR must be finite, got {result}"
    assert 0.0 <= result <= 1.0, f"DSR is a probability; expected [0,1], got {result}"


def test_dsr_across_cohorts_returns_none(capsys: pytest.CaptureFixture) -> None:
    """compute_dsr with cohort=None returns None and emits a warning."""
    trials = [
        _make_trial(sharpe=1.2, cohort="sha-abc"),
        _make_trial(sharpe=0.9, cohort="sha-def"),
    ]
    result = compute_dsr(trials, cohort=None)

    assert result is None, "cross-cohort DSR must return None"
    # structlog routes to stdout by default in test environments.
    captured = capsys.readouterr()
    output = (captured.out + captured.err).lower()
    assert "cohort" in output or "dsr" in output, (
        "a warning mentioning cohort or DSR must be emitted"
    )
