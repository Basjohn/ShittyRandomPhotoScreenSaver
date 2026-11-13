"""Focused coverage for the diagnostic experiment-flag resolver.

These flags admit retained opt-in diagnostics (visualizer switch/resource
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


def test_gpu_pass_timing_is_admitted_only_by_its_own_token():
    # N2.6: the native core's per-pass GPU timer. Absent (or misspelt), nothing admits it.
    assert ef.parse_experiment_flags(["main.py", "/s", "--frame-trace"]).gpu_pass_timing is False
    assert ef.parse_experiment_flags(["main.py", "--gpu-pass-timing=1"]).gpu_pass_timing is False
    flags = ef.parse_experiment_flags(["main.py", "/s", ef.GPU_PASS_TIMING_FLAG])
    assert flags.gpu_pass_timing is True
    assert flags.lifecycle_telemetry_admitted is False          # it admits nothing else
    assert ef.experiment_flag_tokens(["main.py", ef.GPU_PASS_TIMING_FLAG, "/s"]) == (ef.GPU_PASS_TIMING_FLAG,)


def test_gpu_pass_timing_activation_and_its_trace_condition():
    from rendering.native.gpu_timing import gpu_pass_timing_wanted

    assert ef.gpu_pass_timing_admitted() is False
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", ef.GPU_PASS_TIMING_FLAG]))
    assert ef.gpu_pass_timing_admitted() is True
    flags = ef.active_experiment_flags()
    # The timer writes only into a frame trace: admitted without a sink, it stays off.
    assert gpu_pass_timing_wanted(flags, object()) is True
    assert gpu_pass_timing_wanted(flags, None) is False
    assert gpu_pass_timing_wanted(ef.ExperimentFlags(), object()) is False


def test_graphics_backend_is_requested_only_by_its_own_token_and_named_backends():
    # N2.7, D10 point 1: the diagnostic switch of the Vulkan rehearsal. Absent, misspelt, valueless or naming an
    # unknown backend, nothing is requested (the owner runs OpenGL).
    for argv in (["main.py", "/s"], ["main.py", ef.GRAPHICS_BACKEND_FLAG, "vulkan"],
                 ["main.py", f"{ef.GRAPHICS_BACKEND_FLAG}=metal"], ["main.py", f"{ef.GRAPHICS_BACKEND_FLAG}="]):
        assert ef.parse_experiment_flags(argv).graphics_backend is None, argv
    for backend in ef.GRAPHICS_BACKENDS:
        token = f"{ef.GRAPHICS_BACKEND_FLAG}={backend.upper()}"
        flags = ef.parse_experiment_flags(["main.py", "/s", token])
        assert flags.graphics_backend == backend
        assert flags.lifecycle_telemetry_admitted is False and flags.gpu_pass_timing is False   # it admits nothing else
        # Stripped from the argv screensaver mode detection reads (one token: only the "=" form exists).
        assert ef.experiment_flag_tokens(["main.py", token, "/s"]) == (token,)


def test_graphics_backend_request_is_read_after_deliberate_activation_only():
    assert ef.graphics_backend_request() is None
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", f"{ef.GRAPHICS_BACKEND_FLAG}=vulkan"]))
    assert ef.graphics_backend_request() == "vulkan"


def test_graphics_backend_names_match_the_owner():
    from rendering.quick import bootstrap

    assert ef.GRAPHICS_BACKENDS == bootstrap.QUICK_BACKENDS


def test_activation_with_only_telemetry_flag_leaves_no_abc_condition():
    ef.activate_experiment_flags(
        ef.parse_experiment_flags(["main.py", "--viz-switch-telemetry"])
    )
    assert ef.abc_drive_condition() is None
    assert ef.visualizer_switch_telemetry_admitted() is True
