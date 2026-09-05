"""Production-shaped rendering contracts for the experimental Sphere mode."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.implementations import sphere as sphere_module
from rendering.quick.visualizer.implementations.sphere import (
    QuickSphereRenderer,
    build_sphere_mesh,
    sphere_pixel_geometry,
)
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
from widgets.spotify_visualizer.render_state import (
    SphereFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


def _presentation(*, extent=(256.0, 256.0), display_size=None, scale=1.0, inset=0.0):
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("sphere"),
        display_size=extent if display_size is None else display_size,
        viewport_extent=extent,
        uniform_visual_scale=scale,
        content_inset=inset,
        shadow_enabled=False,
    )
    if inset:
        x, y, width, height = presentation.content_rect
        presentation = replace(
            presentation,
            content_rect=(x + inset, y + inset, width - 2 * inset, height - 2 * inset),
        )
    return presentation


def _snapshot(*, energy=(0.0, 0.0, 0.0), material="Chrome", authored_time=1.3,
              extent=(256.0, 256.0), display_size=None, scale=1.0, inset=0.0, overrides=None):
    parameters = freeze_render_fields({
        "sphere_material": material,
        "sphere_deformation": 1.0,
        "sphere_rotation_speed": 0.35,
        "sphere_gloss": 0.65,
        "sphere_specular": 0.8,
        "sphere_light_direction": "NW",
        "sphere_idle_motion": 0.12,
    })
    if overrides:
        parameters = freeze_render_fields({**dict(parameters), **overrides})
    bass, mid, high = energy
    logical = VisualizerLogicalFrame(
        runtime_generation=1, engine_generation=2, activation_id=3,
        source_generation=2, source_activation_id=3, mode_id="sphere",
        playing=True, logical_timestamp=authored_time, source_timestamp=authored_time,
        changed=True, present_frame=True, mode_reveal_ready=True,
        common=VisualizerCommonState(
            bars=(), bar_count=0,
            energy=VisualizerEnergyState(bass=bass, mid=mid, high=high, overall=max(energy)),
        ),
        mode_state=SphereFrame(authored_time=authored_time, parameters=parameters),
    )
    return compose_visualizer_render_snapshot(logical, _presentation(extent=extent, display_size=display_size, scale=scale, inset=inset), logical_revision=1)


def test_sphere_mesh_is_bounded_finite_unit_outward_and_has_real_z():
    mesh = build_sphere_mesh(4)
    assert len(mesh) % 9 == 0
    assert 0 < len(mesh) // 9 <= 5120
    assert all(math.isfinite(value) for value in mesh)
    assert any(abs(mesh[index]) > 0.05 for index in range(2, len(mesh), 3))
    for offset in range(0, len(mesh), 9):
        a, b, c = (mesh[offset + index : offset + index + 3] for index in (0, 3, 6))
        assert math.isclose(math.sqrt(sum(value * value for value in a)), 1.0, abs_tol=1e-5)
        normal = (
            (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
            (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
            (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
        )
        assert sum(component * component for component in normal) > 1e-12
        centroid = tuple((a[index] + b[index] + c[index]) / 3.0 for index in range(3))
        assert sum(normal[index] * centroid[index] for index in range(3)) > 0.0


def test_sphere_pixel_geometry_uses_resolved_content_metric_across_aspects_and_scale():
    wide = _presentation(extent=(560.0, 280.0))
    tall = _presentation(extent=(280.0, 560.0))
    scaled = _presentation(extent=(420.0, 300.0), scale=0.65)
    for presentation in (wide, tall, scaled):
        center_x, center_y, radius = sphere_pixel_geometry(presentation)
        assert center_x == pytest.approx(presentation.content_rect[0] - presentation.outer_rect[0] + presentation.content_rect[2] * 0.5)
        assert center_y == pytest.approx(presentation.content_rect[1] - presentation.outer_rect[1] + presentation.content_rect[3] * 0.5)
        fraction = sphere_module.SPHERE_RADIUS_FRACTION
        assert radius == pytest.approx(min(presentation.content_rect[2:]) * fraction)
    assert sphere_pixel_geometry(wide)[2] == pytest.approx(sphere_pixel_geometry(tall)[2])
    doubled = _presentation(extent=(420.0, 300.0), display_size=(840.0, 600.0), scale=2.0)
    baseline = _presentation(extent=(420.0, 300.0), display_size=(840.0, 600.0))
    assert sphere_pixel_geometry(doubled)[2] == pytest.approx(sphere_pixel_geometry(baseline)[2] * 2.0)


def test_sphere_pixel_geometry_ignores_authored_extent_when_visible_footprint_matches():
    """The persisted huge CUSTOM world must not shrink the displayed Sphere."""
    # The rejected profile authored this very wide world, which resolves to a
    # roughly 1400x268 on-screen footprint.  Compare it with the identical
    # footprint authored directly: presentation-local Sphere pixels must agree.
    visible_size = (1398.5560481317289, 268.0)
    huge_world = _presentation(
        extent=(8240.0, 1579.0), display_size=(1400.0, 268.0), scale=1.0,
    )
    direct_world = _presentation(
        extent=visible_size, display_size=visible_size, scale=1.0,
    )
    assert huge_world.content_rect[2:] == pytest.approx(direct_world.content_rect[2:])
    huge_radius = sphere_pixel_geometry(huge_world)[2]
    assert huge_radius == pytest.approx(sphere_pixel_geometry(direct_world)[2])
    assert huge_radius == pytest.approx(268.0 * sphere_module.SPHERE_RADIUS_FRACTION)
    # The old baseline-height-times-uniform-scale formula produced ~13px here.
    assert huge_radius > 70.0


def test_canonical_viewport_reserves_full_bounded_deformation_envelope():
    # Sum absolute maxima of the independent shader fields, including maximum
    # idle detail and all three bands at their maximum supported strength.
    maximum_radius = 1.0 + 0.14 + 2.0 * (0.09 + 0.035 + 0.10 + 0.025)
    camera_distance = 4.6
    perspective_radius = maximum_radius * camera_distance / math.sqrt(camera_distance**2 - maximum_radius**2)
    pixels = 280.0 * sphere_module.SPHERE_RADIUS_FRACTION * perspective_radius
    assert pixels < 138.0  # 140px half-height, with a visible safety margin.


@pytest.mark.qt
def test_real_gl_sphere_host_is_deterministic_reactive_material_distinct_and_depth_fenced(qt_app, monkeypatch):
    """Exercise the production host/fence with a depth FBO, not a fake renderer."""
    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    fmt = QSurfaceFormat(); fmt.setRenderableType(QSurfaceFormat.OpenGL); fmt.setProfile(QSurfaceFormat.CoreProfile); fmt.setVersion(4, 1)
    context = QOpenGLContext(); context.setFormat(fmt)
    if not context.create(): pytest.skip("OpenGL 4.1 context unavailable")
    surface = QOffscreenSurface(); surface.setFormat(fmt); surface.create()
    if not surface.isValid() or not context.makeCurrent(surface): pytest.skip("offscreen OpenGL context unavailable")
    # This FBO includes the actual rejected visible footprint.  Smaller
    # snapshots below remain valid sub-rects; the logged custom extent must be
    # projected through its real 1400x268 pixel coordinate space.
    width, height = 1400, 268
    fbo = color = depth = 0
    host = QuickVisualizerRenderHost()
    uploads = 0
    original_buffer_data = sphere_module.gl.glBufferData
    def counted_buffer_data(*args):
        nonlocal uploads
        if args[0] == gl.GL_ARRAY_BUFFER and len(args) > 1 and args[1] > 1000: uploads += 1
        return original_buffer_data(*args)
    monkeypatch.setattr(sphere_module.gl, "glBufferData", counted_buffer_data)
    try:
        color = gl.glGenTextures(1); gl.glBindTexture(gl.GL_TEXTURE_2D, color)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        depth = gl.glGenRenderbuffers(1); gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
        fbo = gl.glGenFramebuffers(1); gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, depth)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        matrix = (2/width, 0, 0, 0, 0, 2/height, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)

        def render(snapshot, *, verify_sentinel=False):
            gl.glViewport(0, 0, width, height); gl.glClearColor(0, 0, 0, 0); gl.glClearDepth(0.37); gl.glDisable(gl.GL_SCISSOR_TEST); gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            gl.glEnable(gl.GL_SCISSOR_TEST); gl.glScissor(0, 0, width, height)
            gl.glDepthFunc(gl.GL_GREATER); gl.glClearDepth(0.37); gl.glDisable(gl.GL_DEPTH_TEST); gl.glDepthMask(gl.GL_FALSE)
            assert host.render(snapshot=snapshot, viewport=(0, 0, width, height), logical_size=(float(width), float(height)), matrix_values=matrix) == "sphere"
            assert gl.glGetIntegerv(gl.GL_DEPTH_FUNC) == gl.GL_GREATER
            assert gl.glGetDoublev(gl.GL_DEPTH_CLEAR_VALUE) == pytest.approx(0.37)
            assert not gl.glIsEnabled(gl.GL_DEPTH_TEST)
            assert not bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))
            assert gl.glIsEnabled(gl.GL_SCISSOR_TEST)
            assert tuple(gl.glGetIntegerv(gl.GL_SCISSOR_BOX)) == (0, 0, width, height)
            # The depth clear is constrained to Sphere's projected content
            # rectangle. An untouched corner remains the caller's sentinel.
            if verify_sentinel:
                sentinel = float(gl.glReadPixels(8, 8, 1, 1, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT)[0][0])
                assert sentinel == pytest.approx(0.37)
            return bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))

        idle = render(_snapshot(inset=32.0), verify_sentinel=True)
        repeated = render(_snapshot(inset=32.0))
        bass = render(_snapshot(energy=(1.0, 0.0, 0.0), inset=32.0))
        mid = render(_snapshot(energy=(0.0, 1.0, 0.0), inset=32.0))
        high = render(_snapshot(energy=(0.0, 0.0, 1.0), inset=32.0))
        materials = [render(_snapshot(material=name, inset=32.0)) for name in ("Chrome", "Obsidian", "Magma", "Silver", "Water")]
        assert idle == repeated
        assert idle != bass and idle != mid and idle != high
        assert len(set(materials)) == 5
        assert uploads == 1
        alpha = idle[3::4]
        assert alpha[0] == 0 and alpha[-1] == 0 and max(alpha) > 0

        def alpha_bounds(image):
            points = [
                (index % width, index // width)
                for index, value in enumerate(image[3::4])
                if value > 8
            ]
            assert points
            xs, ys = zip(*points)
            return min(xs), min(ys), max(xs), max(ys)

        wide_bounds = alpha_bounds(render(_snapshot(extent=(320.0, 180.0))))
        tall_bounds = alpha_bounds(render(_snapshot(extent=(180.0, 320.0))))
        base_scale_bounds = alpha_bounds(render(_snapshot(display_size=(512.0, 512.0))))
        scaled_bounds = alpha_bounds(render(_snapshot(display_size=(512.0, 512.0), scale=0.65)))
        for bounds in (wide_bounds, tall_bounds):
            rendered_width = bounds[2] - bounds[0] + 1
            rendered_height = bounds[3] - bounds[1] + 1
            assert abs(rendered_width - rendered_height) <= 12
        base_diameter = (base_scale_bounds[2] - base_scale_bounds[0] + base_scale_bounds[3] - base_scale_bounds[1] + 2) / 2
        scaled_diameter = (scaled_bounds[2] - scaled_bounds[0] + scaled_bounds[3] - scaled_bounds[1] + 2) / 2
        assert scaled_diameter == pytest.approx(base_diameter * 0.65, abs=8.0)

        # This is a real production-host draw: a 2x resolved Edit scale must
        # enlarge the mesh pixels, not merely alter snapshot metadata.
        small_scale_bounds = alpha_bounds(render(_snapshot(
            extent=(128.0, 128.0), display_size=(256.0, 256.0), scale=1.0,
        )))
        double_scale_bounds = alpha_bounds(render(_snapshot(
            extent=(128.0, 128.0), display_size=(256.0, 256.0), scale=2.0,
        )))
        small_scale_diameter = (
            small_scale_bounds[2] - small_scale_bounds[0] + small_scale_bounds[3] - small_scale_bounds[1] + 2
        ) / 2
        double_scale_diameter = (
            double_scale_bounds[2] - double_scale_bounds[0] + double_scale_bounds[3] - double_scale_bounds[1] + 2
        ) / 2
        assert double_scale_diameter == pytest.approx(small_scale_diameter * 2.0, abs=10.0)

        # Exact rejected persisted geometry: 8240x1579 authored units are
        # uniformly reduced to about 1400x268 visible pixels.  It must render
        # as a sizeable body and retain visible authored-time and band response.
        logged_geometry = {
            "extent": (8240.0, 1579.0),
            "display_size": (1400.0, 268.0),
            "scale": 1.0,
        }
        logged_idle = render(_snapshot(**logged_geometry, authored_time=1.0))
        logged_later = render(_snapshot(**logged_geometry, authored_time=2.0))
        logged_bass = render(_snapshot(**logged_geometry, authored_time=1.0, energy=(1.0, 0.0, 0.0)))
        logged_bounds = alpha_bounds(logged_idle)
        logged_diameter = (
            logged_bounds[2] - logged_bounds[0] + logged_bounds[3] - logged_bounds[1] + 2
        ) / 2
        assert logged_diameter > 110.0
        assert logged_idle != logged_later
        assert logged_idle != logged_bass

        detail_off = render(_snapshot(inset=32.0, overrides={"sphere_surface_detail": 0.0}))
        detail_on = render(_snapshot(inset=32.0, overrides={"sphere_surface_detail": 1.0}))
        assert detail_off != detail_on
        water_still = {
            "sphere_rotation_speed": 0.0,
            "sphere_deformation": 0.0,
            "sphere_idle_motion": 0.0,
        }
        assert render(_snapshot(material="Water", authored_time=1.0, inset=32.0, overrides=water_still)) != render(_snapshot(material="Water", authored_time=2.0, inset=32.0, overrides=water_still))
    finally:
        host.release_resources(); host.release_resources()
        if fbo: gl.glDeleteFramebuffers(1, [fbo])
        if depth: gl.glDeleteRenderbuffers(1, [depth])
        if color: gl.glDeleteTextures([color])
        context.doneCurrent(); surface.destroy()


def test_sphere_release_retries_only_the_failed_resource(monkeypatch):
    renderer = QuickSphereRenderer()
    renderer._program, renderer._vao, renderer._vbo = 11, 12, 13
    deleted = []
    monkeypatch.setattr(sphere_module.gl, "glDeleteProgram", lambda value: deleted.append(("program", value)))
    monkeypatch.setattr(sphere_module.gl, "glDeleteVertexArrays", lambda *_args: deleted.append(("vao", 12)))
    calls = {"vbo": 0}
    def fail_once(*_args):
        calls["vbo"] += 1
        if calls["vbo"] == 1: raise RuntimeError("transient delete")
        deleted.append(("vbo", 13))
    monkeypatch.setattr(sphere_module.gl, "glDeleteBuffers", fail_once)
    with pytest.raises(RuntimeError, match="_vbo"):
        renderer.release_resources()
    assert renderer._vbo == 13 and renderer._vao == renderer._program == 0
    renderer.release_resources(); renderer.release_resources()
    assert deleted.count(("vbo", 13)) == 1
