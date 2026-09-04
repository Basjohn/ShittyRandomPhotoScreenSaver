"""Real-GL pixel oracles for Bubble's authored radius and aspect contract."""

from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


_WIDTHS = (140, 280, 420, 630, 1260)
_HEIGHTS = (140, 280, 420, 630, 1260)


def _presentation(
    width: int,
    height: int,
    *,
    scale: float = 1.0,
):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(float(width), float(height)),
        viewport_extent=(float(width), float(height)),
        uniform_visual_scale=scale,
        border_width=0.0,
        corner_radius=0.0,
        content_inset=0.0,
        shadow_enabled=False,
    )


def _snapshot(
    presentation,
    *,
    radius: float,
    count: int = 1,
    extras: tuple[float, float, float, float] = (0.8, 0.0, 0.0, 0.0),
    overrides: dict[str, object] | None = None,
):
    values = {
            "bubble_trail_strength": 0.0,
            "bubble_tail_opacity": 0.0,
            "bubble_ghosting_enabled": False,
            "bubble_ghost_alpha": 0.0,
            "bubble_gradient_direction": "top",
            "bubble_specular_direction": "top_left",
            "bubble_gradient_light": (0, 0, 0, 255),
            "bubble_gradient_dark": (0, 0, 0, 255),
            "bubble_outline_color": (255, 255, 255, 255),
            "bubble_specular_color": (255, 255, 255, 255),
            "bubble_pop_color": (255, 255, 255, 255, 255),
            "rainbow_enabled": False,
        }
    if overrides:
        values.update(overrides)
    parameters = freeze_render_fields(values)
    positions = (0.5, 0.5, radius, 1.0) if count else ()
    frame_extras = extras if count else ()
    logical = VisualizerLogicalFrame(
        runtime_generation=1,
        engine_generation=2,
        activation_id=3,
        source_generation=2,
        source_activation_id=3,
        mode_id="bubble",
        playing=True,
        logical_timestamp=1.0,
        source_timestamp=1.0,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(
            bars=(),
            bar_count=0,
            energy=VisualizerEnergyState(),
        ),
        mode_state=BubbleFrame(
            positions=positions,
            extras=frame_extras,
            trails=(),
            bubble_count=count,
            source_timestamp=1.0,
            simulation_timestamp=1.0,
            parameters=parameters,
        ),
    )
    return compose_visualizer_render_snapshot(
        logical,
        presentation,
        logical_revision=1,
    )


def _bounds(image: bytes, baseline: bytes, width: int, height: int):
    points = []
    for index in range(width * height):
        offset = index * 4
        difference = max(
            abs(image[offset + channel] - baseline[offset + channel])
            for channel in range(3)
        )
        if difference > 8:
            points.append((index % width, index // width))
    assert points, "Bubble frame did not differ from the count=0 baseline"
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _diameter(bounds):
    return (bounds[2] - bounds[0] + 1, bounds[3] - bounds[1] + 1)


def _render(host, gl, snapshot, width: int, height: int, matrix):
    gl.glViewport(0, 0, width, height)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    assert (
        host.render(
            snapshot=snapshot,
            viewport=(0, 0, width, height),
            logical_size=(float(width), float(height)),
            matrix_values=matrix,
        )
        == "bubble"
    )
    return bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))


def _matrix(width: int, height: int):
    return (
        2 / width,
        0,
        0,
        0,
        0,
        2 / height,
        0,
        0,
        0,
        0,
        1,
        0,
        -1,
        -1,
        0,
        1,
    )


@pytest.fixture
def _real_gl(qt_app):
    """Yield a production host on a real offscreen OpenGL framebuffer."""
    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 1)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.1 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        surface.destroy()
        pytest.skip("offscreen OpenGL context unavailable")

    max_width = max(_WIDTHS)
    max_height = max(_HEIGHTS)
    fbo = color = depth = 0
    host = QuickVisualizerRenderHost()
    try:
        color = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, color)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA8,
            max_width,
            max_height,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            None,
        )
        depth = gl.glGenRenderbuffers(1)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, depth)
        gl.glRenderbufferStorage(
            gl.GL_RENDERBUFFER,
            gl.GL_DEPTH_COMPONENT24,
            max_width,
            max_height,
        )
        fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER,
            gl.GL_COLOR_ATTACHMENT0,
            gl.GL_TEXTURE_2D,
            color,
            0,
        )
        gl.glFramebufferRenderbuffer(
            gl.GL_FRAMEBUFFER,
            gl.GL_DEPTH_ATTACHMENT,
            gl.GL_RENDERBUFFER,
            depth,
        )
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE

        def render(snapshot, width: int, height: int):
            return _render(host, gl, snapshot, width, height, _matrix(width, height))

        yield gl, render
    finally:
        host.release_resources()
        if fbo:
            gl.glDeleteFramebuffers(1, [fbo])
        if depth:
            gl.glDeleteRenderbuffers(1, [depth])
        if color:
            gl.glDeleteTextures([color])
        context.doneCurrent()
        surface.destroy()


@pytest.mark.qt
def test_real_gl_bubble_radius_is_height_authored_and_aspect_correct(_real_gl):
    """A width-only resize must change occupancy, not physical Bubble radius."""
    _, render = _real_gl
    width_results = {}
    for width in _WIDTHS:
        height = 280
        baseline = render(
            _snapshot(_presentation(width, height), radius=0.04, count=0),
            width,
            height,
        )
        width_results[width] = []
        for radius in (0.04, 0.08):
            image = render(
                _snapshot(_presentation(width, height), radius=radius),
                width,
                height,
            )
            width_results[width].append(
                _diameter(_bounds(image, baseline, width, height))
            )

    for width, diameters in width_results.items():
        for diameter in diameters:
            assert abs(diameter[0] - diameter[1]) <= 2
    for radius_index in (0, 1):
        values = [width_results[width][radius_index][0] for width in _WIDTHS]
        assert max(values) - min(values) <= 3
    deltas = [
        width_results[width][1][0] - width_results[width][0][0]
        for width in _WIDTHS
    ]
    assert max(deltas) - min(deltas) <= 3
    occupancy = [
        width_results[width][1][0] / width
        for width in _WIDTHS
    ]
    assert all(left > right for left, right in zip(occupancy, occupancy[1:]))

    height_results = {}
    width = 420
    for height in _HEIGHTS:
        presentation = _presentation(width, height)
        baseline = render(
            _snapshot(presentation, radius=0.04, count=0),
            width,
            height,
        )
        image = render(
            _snapshot(presentation, radius=0.04),
            width,
            height,
        )
        height_results[height] = _diameter(
            _bounds(image, baseline, width, height)
        )
    for height, diameter in height_results.items():
        assert abs(diameter[0] - diameter[1]) <= 2
    normalized = [height_results[height][0] / height for height in _HEIGHTS]
    assert max(normalized) - min(normalized) <= 0.03
    assert all(
        left < right
        for left, right in zip(
            (height_results[height][0] for height in _HEIGHTS),
            (height_results[height][0] for height in _HEIGHTS[1:]),
        )
    )

    base_presentation = _presentation(420, 280)
    scaled_presentation = _presentation(420, 280, scale=0.65)
    base = render(
        _snapshot(base_presentation, radius=0.04, count=0),
        420,
        280,
    )
    base_image = render(
        _snapshot(base_presentation, radius=0.04),
        420,
        280,
    )
    scaled = render(
        _snapshot(scaled_presentation, radius=0.04, count=0),
        420,
        280,
    )
    scaled_image = render(
        _snapshot(scaled_presentation, radius=0.04),
        420,
        280,
    )
    base_diameter = _diameter(_bounds(base_image, base, 420, 280))[0]
    scaled_diameter = _diameter(_bounds(scaled_image, scaled, 420, 280))[0]
    assert scaled_diameter == pytest.approx(base_diameter * 0.65, abs=3.0)

    # Exceeding the display width invokes the common uniform screen-fit owner.
    # Its pixels must match an explicitly authored equal scale, with no second
    # Bubble aspect compensation or radius authority.
    fitted = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(420.0, 280.0),
        viewport_extent=(840.0, 280.0),
        border_width=0.0,
        corner_radius=0.0,
        shadow_enabled=False,
    )
    explicit = _presentation(840, 280, scale=0.5)
    assert fitted.uniform_visual_scale == 0.5
    assert render(_snapshot(fitted, radius=0.08), 420, 280) == render(
        _snapshot(explicit, radius=0.08), 420, 280,
    )


@pytest.mark.qt
def test_real_gl_bubble_specular_crop_is_constant_across_widths(_real_gl):
    """The highlight's authored-pixel crop must survive a width-only resize."""
    _, render = _real_gl
    crop_radius = 40
    style = {
        "bubble_gradient_light": (0, 0, 0, 255),
        "bubble_gradient_dark": (0, 0, 0, 255),
        "bubble_outline_color": (0, 0, 0, 255),
        "bubble_specular_color": (255, 255, 255, 255),
        "bubble_pop_color": (0, 0, 0, 255),
        "bubble_specular_direction": "top_left",
    }
    crops = {}
    height = 280
    for width in _WIDTHS:
        image = render(
            _snapshot(
                _presentation(width, height),
                radius=0.08,
                extras=(0.8, 0.0, 0.15, 0.0),
                overrides=style,
            ),
            width,
            height,
        )
        center_x = width // 2
        center_y = height // 2
        x0, y0 = center_x - crop_radius, center_y - crop_radius
        crops[width] = tuple(
            image[(y * width + x) * 4 + channel]
            for y in range(y0, center_y + crop_radius)
            for x in range(x0, center_x + crop_radius)
            for channel in range(3)
        )

    reference = crops[420]
    assert max(reference) > 0, "specular-only crop is empty"
    differences = {
        width: max(
            abs(left - right) for left, right in zip(crops[width], reference)
        )
        for width in _WIDTHS
    }
    for width in _WIDTHS:
        assert len(crops[width]) == len(reference)
    assert max(differences.values()) <= 1, differences
