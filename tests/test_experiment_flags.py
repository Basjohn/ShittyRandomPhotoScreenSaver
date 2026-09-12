"""Focused coverage for the diagnostic experiment-flag resolver.

These flags admit opt-in investigation instrumentation (visualizer switch/resource
telemetry and the A/B/C driver). They are deliberately owned here rather than in
``core/dev_gates.py``; the tests pin the parsing contract, the implicit telemetry
admission by ``--abc-drive``, argv-token stripping, and the once-at-startup
activation model.
"""

from __future__ import annotations

import pytest

from core.diagnostics import experiment_flags as ef


@pytest.fixture(autouse=True)
def _reset_active_flags():
    # The process admission is global; keep each test isolated and leave it clear.
    ef.override_active_flags_for_testing(None)
    yield
    ef.override_active_flags_for_testing(None)


def test_no_flags_admits_nothing():
    flags = ef.parse_experiment_flags(["main.py", "/s", "--usage", "--viz"])
    assert flags.abc_drive is None
    assert flags.viz_switch_telemetry is False
    assert flags.lifecycle_telemetry_admitted is False


def test_viz_switch_telemetry_flag_admits_only_telemetry():
    flags = ef.parse_experiment_flags(["main.py", "/s", "--viz-switch-telemetry"])
    assert flags.abc_drive is None
    assert flags.viz_switch_telemetry is True
    assert flags.lifecycle_telemetry_admitted is True


@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_abc_drive_equals_form(condition):
    flags = ef.parse_experiment_flags(["main.py", f"--abc-drive={condition.lower()}"])
    assert flags.abc_drive == condition
    # --abc-drive implicitly admits the boundary telemetry it scores.
    assert flags.lifecycle_telemetry_admitted is True


@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_abc_drive_space_form(condition):
    flags = ef.parse_experiment_flags(["main.py", "--abc-drive", condition])
    assert flags.abc_drive == condition
    assert flags.lifecycle_telemetry_admitted is True


def test_invalid_condition_is_ignored_not_raised():
    flags = ef.parse_experiment_flags(["main.py", "--abc-drive=Z"])
    assert flags.abc_drive is None
    assert flags.lifecycle_telemetry_admitted is False
    flags2 = ef.parse_experiment_flags(["main.py", "--abc-drive"])  # no value
    assert flags2.abc_drive is None


def test_experiment_tokens_stripped_include_consumed_value():
    argv = ["main.py", "/s", "--abc-drive", "B", "--viz-switch-telemetry", "--usage"]
    tokens = ef.experiment_flag_tokens(argv)
    assert "--abc-drive" in tokens
    assert "B" in tokens  # the value consumed by the space form
    assert "--viz-switch-telemetry" in tokens
    assert "--usage" not in tokens
    assert "/s" not in tokens


def test_experiment_tokens_equals_form_single_token():
    tokens = ef.experiment_flag_tokens(["main.py", "--abc-drive=A", "/c"])
    assert tokens == ("--abc-drive=A",)


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["main.py", "--abc-layout-slot=3"], "3"),
        (["main.py", "--abc-layout-slot", "5"], "5"),
        (["main.py", "/s"], None),
    ],
)
def test_abc_layout_slot_parsing(argv, expected):
    flags = ef.parse_experiment_flags(argv)
    assert flags.abc_layout_slot == expected


def test_abc_layout_slot_tokens_stripped_with_value():
    argv = ["main.py", "/s", "--abc-layout-slot", "2", "--abc-drive=C"]
    tokens = ef.experiment_flag_tokens(argv)
    assert "--abc-layout-slot" in tokens
    assert "2" in tokens
    assert "--abc-drive=C" in tokens
    assert "/s" not in tokens


def test_abc_layout_slot_activation_helper():
    ef.activate_experiment_flags(
        ef.parse_experiment_flags(["main.py", "--abc-drive=C", "--abc-layout-slot=4"])
    )
    assert ef.abc_layout_slot() == "4"


def test_activation_is_deliberate_and_defaults_disabled():
    # Before activation, the process admission is a disabled default.
    assert ef.active_experiment_flags().lifecycle_telemetry_admitted is False
    assert ef.abc_drive_condition() is None
    assert ef.visualizer_switch_telemetry_admitted() is False

    ef.activate_experiment_flags(
        ef.parse_experiment_flags(["main.py", "--abc-drive=C"])
    )
    assert ef.abc_drive_condition() == "C"
    assert ef.visualizer_switch_telemetry_admitted() is True


def test_activation_with_only_telemetry_flag_leaves_no_abc_condition():
    ef.activate_experiment_flags(
        ef.parse_experiment_flags(["main.py", "--viz-switch-telemetry"])
    )
    assert ef.abc_drive_condition() is None
    assert ef.visualizer_switch_telemetry_admitted() is True
