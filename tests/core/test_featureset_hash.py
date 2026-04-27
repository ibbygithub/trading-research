"""Tests for FeatureSet.compute_hash() canonicalization."""

from trading_research.core.featuresets import FeatureSet, FeatureSpec


def _make_fs(**overrides: object) -> FeatureSet:
    defaults: dict[str, object] = {
        "name": "base",
        "version": "v1",
        "features": [
            FeatureSpec("atr", {"period": 14}),
            FeatureSpec("rsi", {"period": 14}),
            FeatureSpec("macd", {"fast": 12, "slow": 26, "signal": 9}),
        ],
        "code_version": "abc1234",
    }
    defaults.update(overrides)
    return FeatureSet(**defaults)  # type: ignore[arg-type]


def test_stable_hash() -> None:
    fs1 = _make_fs()
    fs2 = _make_fs()
    assert fs1.compute_hash() == fs2.compute_hash()


def test_reorder_feature_list_same_hash() -> None:
    fs_forward = _make_fs(
        features=[
            FeatureSpec("atr", {"period": 14}),
            FeatureSpec("macd", {"fast": 12, "slow": 26, "signal": 9}),
            FeatureSpec("rsi", {"period": 14}),
        ]
    )
    fs_reversed = _make_fs(
        features=[
            FeatureSpec("rsi", {"period": 14}),
            FeatureSpec("macd", {"fast": 12, "slow": 26, "signal": 9}),
            FeatureSpec("atr", {"period": 14}),
        ]
    )
    assert fs_forward.compute_hash() == fs_reversed.compute_hash()


def test_different_param_different_hash() -> None:
    fs_14 = _make_fs(features=[FeatureSpec("atr", {"period": 14})])
    fs_20 = _make_fs(features=[FeatureSpec("atr", {"period": 20})])
    assert fs_14.compute_hash() != fs_20.compute_hash()


def test_code_version_affects_hash() -> None:
    fs_a = _make_fs(code_version="abc1234")
    fs_b = _make_fs(code_version="def5678")
    assert fs_a.compute_hash() != fs_b.compute_hash()
