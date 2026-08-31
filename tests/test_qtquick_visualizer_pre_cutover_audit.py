"""Pre-cutover visualizer audit bars for H.

These tests encode source-backed gaps found at the b2a8cd85 pre-cutover audit.
They intentionally avoid choosing the final orchestration implementation where
the durable contract does not require one.

Expected on the audited checkpoint:
- retirement/join-barrier tests: RED;
- all-mode neutral logical configuration: RED for non-Bubble modes;
- presentation-only negative configuration bar: GREEN;
- production render-snapshot caller bar: RED.

Once the destination edge is corrected, these should all be GREEN before the
atomic DisplayManager cutover begins.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs
from widgets.spotify_visualizer.logical_tick_state import (
    install_default_logical_tick_state,
)
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)


ROOT = Path(__file__).resolve().parent.parent


def _logical_state(mode: str):
    controller = VisualizerRuntimeController(
        runtime_generation=77,
        bar_count=32,
        initial_mode=mode,
        engine_factory=lambda _bar_count: object(),
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=controller.bar_count)
    return controller, state


class _RetryableUnjoinedRuntime:
    """Fake authored runtime whose first join attempt fails, then can succeed."""

    def __init__(self) -> None:
        self.allow_join = False
        self.stop_calls = 0

    def is_running(self) -> bool:
        return not self.allow_join

    def stop(self) -> bool:
        self.stop_calls += 1
        return bool(self.allow_join)


class _ExplodingRuntime:
    def is_running(self) -> bool:
        return True

    def stop(self) -> bool:
        raise OSError("join failed")


def test_visualizer_owner_join_timeout_is_not_reported_as_retired() -> None:
    """A non-daemon logical runtime that did not join blocks owner retirement.

    The controller already preserves unresolved logical-runtime ownership.  The
    Quick owner must not convert that False result into successful terminal
    retirement, because generation/window teardown must remain blocked.
    """

    runtime = SimpleNamespace(runtime_generation=91)
    owner = QuickDisplayVisualizerOwner(
        runtime,
        bar_count=32,
        initial_mode="spectrum",
        engine_factory=lambda _bar_count: object(),
    )
    logical = _RetryableUnjoinedRuntime()
    owner.controller.adopt_logical_runtime(logical)  # type: ignore[arg-type]

    try:
        first_result = owner.retire()
    except Exception:
        # Raising is an acceptable hard-barrier signal; silently succeeding is not.
        first_result = False

    assert first_result is False
    assert owner.is_retired is False
    assert owner.controller.logical_runtime is logical
    assert logical.stop_calls == 1

    # The unresolved destruction owner must remain retryable.  Once the join can
    # complete, the same owner can finish terminal retirement.
    logical.allow_join = True
    assert owner.retire() is True
    assert owner.is_retired is True
    assert owner.controller.logical_runtime is None
    assert logical.stop_calls == 2


def test_visualizer_owner_stop_exception_is_not_swallowed() -> None:
    """A stop/join exception is a teardown failure, not successful retirement."""

    runtime = SimpleNamespace(runtime_generation=92)
    owner = QuickDisplayVisualizerOwner(
        runtime,
        bar_count=32,
        initial_mode="spectrum",
        engine_factory=lambda _bar_count: object(),
    )
    logical = _ExplodingRuntime()
    owner.controller.adopt_logical_runtime(logical)  # type: ignore[arg-type]

    with pytest.raises(Exception):
        owner.retire()

    assert owner.is_retired is False
    assert owner.controller.logical_runtime is logical


# Representative settings below are not selected because they "sound logical".
# Each is consumed by an authored logical/mode runtime on the current source path:
# SpectrumFrameRuntime, OscilloscopeFrameRuntime, SineFrameRuntime or
# DevCurveFrameRuntime.  They therefore require presentation-neutral ownership
# before SpotifyVisualizerWidget can be deleted.
_LOGICAL_CONFIG_CASES = (
    (
        "spectrum",
        {
            "spectrum_visual_smoothing_enabled": False,
            "spectrum_visual_smoothing": 0.27,
            "spectrum_ghosting_enabled": False,
            "spectrum_ghost_decay": 0.73,
        },
        {
            "_spectrum_visual_smoothing_enabled": False,
            "_spectrum_visual_smoothing": 0.27,
            "_spectrum_ghosting_enabled": False,
            "_spectrum_ghost_decay": 0.73,
        },
    ),
    (
        "oscilloscope",
        {
            "osc_speed": 0.33,
            "osc_line_amplitude": 2.4,
            "osc_ghosting_enabled": True,
            "osc_ghost_decay": 0.61,
        },
        {
            "_osc_speed": 0.33,
            "_osc_line_amplitude": 2.4,
            "_osc_ghosting_enabled": True,
            "_osc_ghost_decay": 0.61,
        },
    ),
    (
        "sine_wave",
        {
            "sine_speed": 0.44,
            "sine_wave_travel": 1,
            "sine_line1_shift": 0.20,
            "sine_width_reaction": 0.70,
            "sine_sensitivity": 2.10,
            "sine_ghosting_enabled": True,
            "sine_ghost_decay": 0.55,
            # Already neutral today; retained as a control beside the missing
            # Sine authored inputs.
            "sine_heartbeat": 0.40,
        },
        {
            "_sine_speed": 0.44,
            "_sine_wave_travel": 1,
            "_sine_line1_shift": 0.20,
            "_sine_width_reaction": 0.70,
            "_sine_sensitivity": 2.10,
            "_sine_ghosting_enabled": True,
            "_sine_ghost_decay": 0.55,
            "_sine_heartbeat": 0.40,
        },
    ),
    (
        "bubble",
        {
            "bubble_big_count": 11,
            "bubble_stream_direction": "left",
            "bubble_drift_amount": 0.63,
        },
        {
            "_bubble_big_count": 11,
            "_bubble_stream_direction": "left",
            "_bubble_drift_amount": 0.63,
        },
    ),
    (
        "devcurve",
        {
            "devcurve_base_level": 0.62,
            "devcurve_motion_power": 1.30,
            "devcurve_smoothness": 0.40,
            "devcurve_layer_bass_enabled": False,
            "devcurve_layer_bass_power": 1.80,
            "devcurve_layer_bass_offset": 0.11,
        },
        {
            "_devcurve_base_level": 0.62,
            "_devcurve_motion_power": 1.30,
            "_devcurve_smoothness": 0.40,
            "_devcurve_layer_bass_enabled": False,
            "_devcurve_layer_bass_power": 1.80,
            "_devcurve_layer_bass_offset": 0.11,
        },
    ),
)


@pytest.mark.parametrize(
    ("mode", "kwargs", "expected"),
    _LOGICAL_CONFIG_CASES,
    ids=("spectrum", "oscilloscope", "sine", "bubble-control", "devcurve"),
)
def test_neutral_logical_config_covers_authored_inputs_for_all_modes(
    mode: str,
    kwargs: dict[str, object],
    expected: dict[str, object],
) -> None:
    """Classify configuration by the actual authored consumer, not by its name."""

    _controller, state = _logical_state(mode)
    apply_logical_vis_mode_kwargs(state, kwargs)

    for attr, expected_value in expected.items():
        assert hasattr(state, attr), (
            f"{mode} authored input {attr} is still missing from the "
            "presentation-neutral logical configuration owner"
        )
        actual = getattr(state, attr)
        if isinstance(expected_value, float):
            assert actual == pytest.approx(expected_value), (
                f"{mode} authored input {attr} did not reach neutral logical state"
            )
        else:
            assert actual == expected_value, (
                f"{mode} authored input {attr} did not reach neutral logical state"
            )


def test_neutral_logical_config_does_not_absorb_presentation_only_style() -> None:
    """The correction must not turn logical state into the old widget field bag."""

    _controller, state = _logical_state("oscilloscope")
    apply_logical_vis_mode_kwargs(
        state,
        {
            "bar_fill_color": [1, 2, 3, 255],
            "bar_border_color": [4, 5, 6, 255],
            "osc_glow_color": [7, 8, 9, 255],
        },
    )

    assert not hasattr(state, "_bar_fill_color")
    assert not hasattr(state, "_bar_border_color")
    assert not hasattr(state, "_osc_glow_color")


def _production_render_snapshot_callers() -> list[tuple[Path, int]]:
    """Locate destination production calls to controller.publish_render_snapshot.

    This is deliberately a temporary source-level architecture bar.  Before the
    audit there was no behavioral synchronization entry point to drive: the
    controller method existed but no production caller composed logical +
    presentation state into the bound render bridge.  Once a behavioral
    destination synchronization test exists, it should be the stronger proof.
    """

    callers: list[tuple[Path, int]] = []
    roots = (
        ROOT / "rendering" / "quick",
        ROOT / "widgets" / "spotify_visualizer",
    )
    for source_root in roots:
        for directory, dirnames, filenames in os.walk(source_root, topdown=True):
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = Path(directory) / filename
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "publish_render_snapshot"
                    ):
                        callers.append((path.relative_to(ROOT), int(node.lineno)))
    return callers


def test_destination_has_production_render_snapshot_publication_caller() -> None:
    """Binding an empty bridge is not a complete Quick visualizer edge."""

    callers = _production_render_snapshot_callers()
    assert callers, (
        "No destination production code calls VisualizerRuntimeController."
        "publish_render_snapshot(). The logical mailbox and Quick render bridge "
        "therefore remain disconnected. Add the GUI/Quick synchronization owner "
        "that drains current logical state, resolves presentation state and "
        "publishes the complete immutable render snapshot before cutover."
    )
