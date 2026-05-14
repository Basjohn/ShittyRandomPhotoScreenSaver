"""Regression tests for startup shader/program warmup policy."""

from rendering.gl_compositor_pkg.gl_lifecycle import (
    deferred_transition_program_specs,
    startup_transition_program_specs,
)
from widgets.spotify_bars_gl_overlay import prioritized_visualizer_compile_order


def test_startup_transition_programs_only_compile_minimal_subset() -> None:
    startup_names = [name for name, _, _ in startup_transition_program_specs()]
    deferred_names = [name for name, _, _ in deferred_transition_program_specs()]

    assert startup_names == ["crossfade"]
    assert "crossfade" not in deferred_names
    assert "burn" in deferred_names
    assert "warp" in deferred_names


def test_visualizer_compile_order_prioritizes_active_mode() -> None:
    order = prioritized_visualizer_compile_order(
        "spectrum",
        ["bubble", "devcurve", "oscilloscope", "sine_wave", "spectrum"],
    )

    assert order[0] == "spectrum"
    assert sorted(order) == ["bubble", "devcurve", "oscilloscope", "sine_wave", "spectrum"]


def test_visualizer_compile_order_falls_back_to_available_modes() -> None:
    order = prioritized_visualizer_compile_order(
        "nonexistent",
        ["bubble", "devcurve", "spectrum"],
    )

    assert order == ["bubble", "devcurve", "spectrum"]
