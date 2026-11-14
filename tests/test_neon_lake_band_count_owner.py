"""One owner for the most analysis bands Neon Lake reads (1B.10 side defect).

Neon Lake's Analysis Bands admitted 96 while its renderer clamps the bands to the basin shader's ``uBars`` array
(64), so a count above it silently dropped the treble end. ``neon_lake_basin_options.NEON_LAKE_MAX_BANDS`` is the one
maximum: the spec's Analysis Bands, the renderer's clamp and the shader array read it.
"""
from __future__ import annotations

from core.settings.visualizer_mode_settings import RENDERED_BAND_LIMITS, require_mode_settings
from rendering.gl_programs.neon_lake_basin_options import NEON_LAKE_MAX_BANDS

MODE = "shockwave_grid"


def _band_control():
    controls = [control for control in require_mode_settings(MODE).controls if control.key.endswith("bar_count")]
    assert len(controls) == 1, [control.key for control in controls]
    return controls[0]


def test_analysis_bands_admit_no_more_than_the_renderer_reads() -> None:
    control = _band_control()
    assert control.high == NEON_LAKE_MAX_BANDS
    assert control.admit(control.high + 30, control.low) == NEON_LAKE_MAX_BANDS
    assert control.admit_runtime(control.high + 30, control.low) == NEON_LAKE_MAX_BANDS


def test_the_shader_array_holds_the_maximum() -> None:
    from rendering.quick.visualizer.implementations import shockwave_grid

    assert shockwave_grid._BARS_SIZE == NEON_LAKE_MAX_BANDS


def test_every_rendered_band_limit_matches_its_spec() -> None:
    for mode_id, limit in RENDERED_BAND_LIMITS.items():
        controls = [control for control in require_mode_settings(mode_id).controls
                    if control.key.endswith("bar_count")]
        assert [control.high for control in controls] == [limit], mode_id


def test_the_spec_maximum_reaches_the_shader() -> None:
    """At the highest admitted count every band reaches the levels the renderer uploads."""
    from rendering.quick.visualizer.implementations.spectrum import prepare_spectrum_shader_levels

    count = int(_band_control().high)
    bands = [0.2 + 0.6 * index / (count - 1) for index in range(count)]
    levels, _peaks = prepare_spectrum_shader_levels(bands, bands, bar_count=count)
    assert len(levels) >= count
    assert all(level > 0.0 for level in levels[:count])
    assert levels[count - 1] > levels[0]
