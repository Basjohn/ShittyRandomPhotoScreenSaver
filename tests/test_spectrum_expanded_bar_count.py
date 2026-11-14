"""Spectrum draws 20% more bars while the Visualizer is expanded and its content is horizontal (operator, 8 Nov).

The rule has one owner (``widgets/spotify_visualizer/spectrum_display_bar_count.py``) and is read from the record the
card is drawn from (``ResolvedVisualizerPresentation.expanded_display``), so the count changes only where the
fade-through swaps records (its midpoint, card invisible). Authored counts are never test values: the renders use
synthetic bars and the bounds come from the Settings control.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from widgets.spotify_visualizer.spectrum_display_bar_count import (
    SPECTRUM_MAX_DISPLAY_BARS, resample_levels, resolve_display_bar_count,
)


def _scaled(count: int) -> int:
    return min(SPECTRUM_MAX_DISPLAY_BARS, int(count * 1.2 + 0.5))


def _spectrum_bar_bounds() -> range:
    from core.settings.visualizer_mode_settings import require_mode_settings
    control = require_mode_settings("spectrum").control("spectrum_bar_count")
    return range(max(1, int(control.low)), min(SPECTRUM_MAX_DISPLAY_BARS, int(control.high)) + 1)


def test_expanded_horizontal_spectrum_draws_a_fifth_more_bars_and_nothing_else_changes():
    for count in _spectrum_bar_bounds():
        for quarters in (0, 2):                                    # horizontal: upright or half-turned
            assert resolve_display_bar_count("spectrum", count, expanded=True,
                                             content_rotation_quarters=quarters) == _scaled(count)
        # Negative controls: a quarter-turned card, the ordinary card and Extruded Spectrum keep the authored count.
        for quarters in (1, 3):
            assert resolve_display_bar_count("spectrum", count, expanded=True,
                                             content_rotation_quarters=quarters) == count
        for quarters in range(4):
            assert resolve_display_bar_count("spectrum", count, expanded=False,
                                             content_rotation_quarters=quarters) == count
            assert resolve_display_bar_count("extruded_spectrum", count, expanded=True,
                                             content_rotation_quarters=quarters) == count
    assert any(_scaled(count) > count for count in _spectrum_bar_bounds())


def test_resampling_keeps_the_ends_and_stays_between_neighbours():
    values = [0.1, 0.9, 0.3, 0.7, 0.2]
    out = resample_levels(values, 6)
    assert len(out) == 6 and out[0] == values[0] and out[-1] == values[-1]
    assert min(values) <= min(out) and max(out) <= max(values)
    assert resample_levels(values, len(values)) == values


def test_only_the_display_wide_record_is_marked_expanded():
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation
    from widgets.spotify_visualizer.presentation_geometry import (
        resize_visualizer_presentation, resolve_expanded_visualizer_presentation,
    )

    ordinary = resolve_presentation(policy=get_visualizer_presentation_policy("spectrum"),
                                    display_size=(420.0, 280.0), viewport_extent=(420.0, 280.0))
    expanded = resolve_expanded_visualizer_presentation(ordinary, display_size=(2560.0, 1440.0))
    assert ordinary.expanded_display is False and expanded.expanded_display is True
    assert resize_visualizer_presentation(expanded, display_size=(2560.0, 1440.0), outer_origin=(0.0, 0.0),
                                          relative_scale=1.0).expanded_display is True


# ------------------------------------------------------------------------------- the production renderer
WIDTH, HEIGHT = 1260, 280
COUNT = 20
BARS = tuple(0.3 + 0.02 * i for i in range(COUNT))


@pytest.fixture(scope="module")
def draw(qt_app):
    """Draw one synthetic Spectrum frame through the production render host into an offscreen FBO (no window)."""
    import numpy as np
    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests._visualizer_presentation import resolve_presentation
    from widgets.spotify_visualizer.render_state import (
        SpectrumFrame, VisualizerCommonState, VisualizerLogicalFrame, compose_visualizer_render_snapshot,
        freeze_render_fields,
    )
    from widgets.spotify_visualizer.spectrum_decor import DECOR_KEYS

    disable_per_call_gl_error_checking()
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.6 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        surface.destroy()
        pytest.skip("offscreen OpenGL context unavailable")
    color = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, color)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, WIDTH, HEIGHT, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    fbo = gl.glGenFramebuffers(1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
    host = QuickVisualizerRenderHost()
    base = resolve_presentation(policy=get_visualizer_presentation_policy("spectrum"),
                                display_size=(float(WIDTH), float(HEIGHT)),
                                viewport_extent=(float(WIDTH), float(HEIGHT)))
    defaults = require_canonical_default("widgets.spotify_visualizer")
    params = {key: defaults[key] for key in DECOR_KEYS}
    params.update({f"spectrum_{n}_mix": 0.0 for n in ("ghost_custom", "ghost_fill", "ghost_gradient",
                                                       "fill_gradient", "peak_caps", "pattern")})
    params.update({f"spectrum_glow_{side}_mix": 1.0 for side in ("left", "right")})      # the rim's sides (glow off)
    params.update(spectrum_pattern_shown="Off", spectrum_pattern_anchor_shown=defaults["spectrum_pattern_anchor"],
                  spectrum_ghosting_enabled=False, spectrum_ghost_alpha=0.0, spectrum_glow_enabled=False,
                  spectrum_glow_intensity=0.0, spectrum_glow_color=(255, 255, 255, 255), rainbow_enabled=False,
                  rainbow_per_bar=False, rainbow_speed=1.0, spectrum_rainbow_ghost=False,
                  spectrum_rainbow_fill=False, spectrum_rainbow_border=False)

    def render(*, expanded: bool, quarters: int = 0):
        presentation = replace(base, expanded_display=expanded)
        logical = VisualizerLogicalFrame(
            runtime_generation=2, engine_generation=5, activation_id=7, source_generation=5,
            source_activation_id=7, mode_id="spectrum", playing=True, logical_timestamp=1.0,
            source_timestamp=1.0, changed=True, present_frame=True, mode_reveal_ready=True,
            common=VisualizerCommonState(bars=BARS, bar_count=COUNT, style=freeze_render_fields({
                "fill_color": (0, 0, 255, 255), "border_color": (0, 0, 255, 255), "single_piece": True,
                "border_radius": 0.0})),
            mode_state=SpectrumFrame(peaks=BARS, ghost_bars=BARS, parameters=freeze_render_fields(params)))
        if quarters:
            presentation = replace(presentation, content_rotation_quarters=quarters,
                                   current_aspect_ratio=presentation.viewport_extent[1]
                                   / presentation.viewport_extent[0])
        snapshot = compose_visualizer_render_snapshot(logical, presentation, logical_revision=1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        matrix = (2 / WIDTH, 0, 0, 0, 0, 2 / HEIGHT, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)
        assert host.render(snapshot=snapshot, viewport=(0, 0, WIDTH, HEIGHT),
                           logical_size=(float(WIDTH), float(HEIGHT)), matrix_values=matrix) == "spectrum"
        raw = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.frombuffer(bytes(raw), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)

    yield render
    host.release_resources()
    gl.glDeleteFramebuffers(1, [fbo])
    gl.glDeleteTextures([color])
    context.doneCurrent()
    surface.destroy()


def _bars_drawn(pixels) -> int:
    """Separate bar columns along the row a third of the way up the field (every bar reaches it)."""
    import numpy as np
    drawn = pixels[..., 3] > 0
    rows = np.nonzero(drawn.any(axis=1))[0]
    row = drawn[rows.min() + (rows.max() - rows.min()) * 2 // 3]
    return int(np.count_nonzero(np.diff(row.astype(int)) == 1) + int(row[0]))


@pytest.mark.qt
def test_the_renderer_draws_a_fifth_more_bars_on_the_expanded_horizontal_card(draw):
    """The display-wide record draws round(1.2 x) the engine's bars; the ordinary record (negative control) draws
    exactly the engine's bars from the same logical frame."""
    assert _bars_drawn(draw(expanded=False)) == COUNT
    assert _bars_drawn(draw(expanded=True)) == _scaled(COUNT)
    # Negative control: the same display-wide record turned a quarter draws exactly what the ordinary one does.
    import numpy as np
    assert np.array_equal(draw(expanded=True, quarters=1), draw(expanded=False, quarters=1))
    assert (draw(expanded=True, quarters=1)[..., 3] > 0).sum() > 1000
