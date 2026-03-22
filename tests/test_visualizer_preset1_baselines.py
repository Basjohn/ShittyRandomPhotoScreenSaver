from __future__ import annotations

import json

import pytest

from tests.visualizer_preset1_baseline_utils import (
    BASELINE_PATH,
    generate_preset1_baseline_snapshot,
)


def _assert_snapshot_matches(actual, expected, *, path: str = "root") -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected dict, got {type(actual).__name__}"
        assert set(actual) == set(expected), (
            f"{path}: key mismatch\nactual={sorted(actual)}\nexpected={sorted(expected)}"
        )
        for key in expected:
            _assert_snapshot_matches(actual[key], expected[key], path=f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: expected list, got {type(actual).__name__}"
        assert len(actual) == len(expected), f"{path}: length mismatch"
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            _assert_snapshot_matches(actual_item, expected_item, path=f"{path}[{index}]")
        return

    if isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=0.02), (
            f"{path}: expected {expected:.6f}, got {float(actual):.6f}"
        )
        return

    assert actual == expected, f"{path}: expected {expected!r}, got {actual!r}"


def test_visualizer_preset1_baseline_file_exists():
    assert BASELINE_PATH.exists(), "Preset-1 visualizer baseline snapshot must exist"


@pytest.mark.qt
def test_visualizer_preset1_baselines_match_recorded_snapshot(qt_app):
    expected = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    actual = generate_preset1_baseline_snapshot()
    _assert_snapshot_matches(actual, expected)
