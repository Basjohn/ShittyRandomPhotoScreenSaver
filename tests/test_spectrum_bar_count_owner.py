"""One owner for the most bars a bar-drawing mode draws (1B.10 side defect).

The spec admitted Bar Count up to 96 while Spectrum's renderer, its shader arrays and the native core stop at 64, so a
count above 64 drew only the first 64 bands (the treble end was cut off). ``spectrum_options.SPECTRUM_MAX_BARS`` is
the one maximum: the spec's Bar Count of every bar-drawing mode, the frame inputs, the display rule, both renderers
and the shader's arrays read or are held to it.
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
from core.settings.visualizer_mode_settings import require_mode_settings
from rendering.gl_programs.spectrum_options import SPECTRUM_MAX_BARS

BAR_MODES = tuple(descriptor.mode_id for descriptor in iter_all_visualizer_mode_descriptors()
                  if descriptor.draws_bars)


def _bar_count_control(mode_id: str):
    controls = [control for control in require_mode_settings(mode_id).controls
                if control.key.endswith("bar_count")]
    assert len(controls) == 1, (mode_id, [control.key for control in controls])
    return controls[0]


def test_there_are_bar_drawing_modes() -> None:
    assert "spectrum" in BAR_MODES


@pytest.mark.parametrize("mode_id", BAR_MODES)
def test_bar_count_admits_no_more_bars_than_are_drawn(mode_id: str) -> None:
    control = _bar_count_control(mode_id)
    assert control.high == SPECTRUM_MAX_BARS
    assert control.admit(control.high + 30, control.low) == SPECTRUM_MAX_BARS
    assert control.admit_runtime(control.high + 30, control.low) == SPECTRUM_MAX_BARS


def test_every_reader_takes_the_one_maximum() -> None:
    from rendering.quick.visualizer.implementations import extruded_spectrum, spectrum
    from widgets.spotify_visualizer.spectrum_display_bar_count import SPECTRUM_MAX_DISPLAY_BARS
    from widgets.spotify_visualizer.spectrum_frame_inputs import MAX_LEVELS

    assert MAX_LEVELS == SPECTRUM_MAX_DISPLAY_BARS == SPECTRUM_MAX_BARS
    assert spectrum._MAX_BARS == extruded_spectrum._MAX_BARS == SPECTRUM_MAX_BARS


def test_the_shader_arrays_hold_the_maximum() -> None:
    from rendering.quick.visualizer.implementations.spectrum import SPECTRUM_BLOCK

    assert SPECTRUM_BLOCK is not None
    kinds = dict(SPECTRUM_BLOCK.fields)
    for name in ("u_bars", "u_peaks"):
        assert kinds[name] == f"float[{SPECTRUM_MAX_BARS}]", name


def test_the_spec_maximum_draws_every_band() -> None:
    """At the spec's highest Bar Count every band reaches the shader and the layout lays every bar out."""
    from rendering.quick.visualizer.implementations.spectrum import (
        compute_quick_spectrum_layout,
        prepare_spectrum_shader_levels,
    )

    count = int(_bar_count_control("spectrum").high)
    bands = [0.2 + 0.6 * index / (count - 1) for index in range(count)]
    levels, peaks = prepare_spectrum_shader_levels(bands, bands, bar_count=count)
    assert all(level > 0.0 for level in levels[:count])
    assert levels[count - 1] > levels[0]
    layout = compute_quick_spectrum_layout(local_content_rect=(0.0, 0.0, 1600.0, 240.0),
                                           viewport_extent=(1600.0, 240.0), visual_scale=1.0, bar_count=count)
    assert layout.bar_width > 0.0
