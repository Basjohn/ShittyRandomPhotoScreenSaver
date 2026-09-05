"""Production-shaped rendering contracts for the experimental Sphere mode."""

from __future__ import annotations

import math
from pathlib import Path
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
    VisualizerTransientState,
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


def _snapshot(*, energy=(0.0, 0.0, 0.0), transient=0.0, size_pulse=0.0, material="Chrome", authored_time=1.3,
              extent=(256.0, 256.0), display_size=None, scale=1.0, inset=0.0, overrides=None):
    parameters = freeze_render_fields({
        "sphere_material": material,
        "sphere_deformation": 1.0,
        "sphere_rotation_speed": 0.35,
        "sphere_gloss": 0.65,
        "sphere_specular": 0.8,
        "sphere_light_direction": "NW",
        "sphere_idle_motion": 0.12,
        # Historical body/material oracles measure the Sphere itself. Shadow
        # owns dedicated tests below so its halo cannot contaminate body bounds.
        "sphere_shadow_enabled": False,
        "sphere_antialiasing": True,
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
            transient=VisualizerTransientState(mid=transient),
        ),
        mode_state=SphereFrame(
            authored_time=authored_time,
            size_pulse=size_pulse,
            parameters=parameters,
        ),
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


def test_magma_shader_uses_real_macro_fissure_geometry_and_shared_drip_vents():
    vertex = sphere_module._VERTEX_SOURCE
    fragment = sphere_module._FRAGMENT_SOURCE
    effect = sphere_module._EFFECT_VERTEX_SOURCE
    assert "float macroFissureField(vec3 n)" in vertex
    assert "radius -= 0.040 * min(uSurfaceDetail, 2.0) * fissure" in vertex
    assert "0.72 * dripVentField(n)" in vertex
    assert "float macroFissure = macroFissureField(direction);" in fragment
    assert "float vent = dripVentField(direction);" in fragment
    assert "vec3 bodyPoint = turn * surface(anchor);" in effect


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
    assert huge_radius > 60.0


def test_extended_deformation_tail_preserves_positive_radius_without_shrinking_baseline():
    # +50% Deformation intentionally adds expressive positive headroom; forcing
    # the canonical viewport to contain every simultaneous maximum would shrink
    # the normal Sphere and violate the authored presentation contract. Instead
    # protect the dangerous side of that extension: the new negative tail must
    # remain outside the origin even with maximum idle contraction and Magma's
    # deepest geometric fissure.
    worst_driven = -(0.060 + 0.035 + 0.025 + 0.110)
    old_domain_negative = 3.0 * worst_driven
    extended_negative = (4.5 - 3.0) * worst_driven * 0.25
    max_idle_contraction = 0.20 * 0.10
    max_magma_fissure = 0.040 * 2.0
    minimum_radius = 1.0 + old_domain_negative + extended_negative - max_idle_contraction - max_magma_fissure
    assert minimum_radius > 0.10
    source = sphere_module._VERTEX_SOURCE
    assert "if (uDeformation > 3.0 && driven < 0.0)" in source
    assert "(uDeformation - 3.0) * driven * 0.25" in source


def test_sphere_shader_has_bounded_independent_band_transfer_and_optional_effects():
    source = sphere_module._VERTEX_SOURCE
    assert "uniform vec3 uBandResponse;" in source
    assert "uniform float uEnergyCurve;" in source
    assert "pow(clamp(uEnergy, 0.0, 1.0)" in source
    assert "exp(-2.8 * drive)" in source
    assert "_EFFECT_VERTEX_SOURCE" in sphere_module.__dict__
    assert "_FIRE_FRAGMENT_SOURCE" in sphere_module.__dict__
    assert "uEffectPass == 0" in sphere_module._FIRE_FRAGMENT_SOURCE
    assert "fwidth(noise)" in sphere_module._FIRE_FRAGMENT_SOURCE
    effect = sphere_module._EFFECT_VERTEX_SOURCE
    assert "vec3 dripAnchor(float id)" in effect
    assert "vec3 bodyPoint = turn * surface(anchor);" in effect
    assert "float detach = smoothstep" in effect
    assert "vec3 neckAxis = -hang;" in effect
    assert "vec3 center = bodyPoint + hang * scale.y * 0.92 + gravity * fall;" in effect
    assert "dripBulgeField" in sphere_module._VERTEX_SOURCE
    assert "radius += (uMaterial == 2 ? 0.038 : (uMaterial == 4 ? 0.050 : 0.0))" in sphere_module._VERTEX_SOURCE
    assert "waterLane" not in effect
    assert "build_sphere_mesh(3)" in Path(sphere_module.__file__).read_text()


def test_sphere_optional_local_aa_and_cast_shadow_have_dedicated_gpu_contracts():
    assert "uniform int uAntialiasing;" in sphere_module._FRAGMENT_SOURCE
    assert "smoothstep(0.0, edgeWidth, facing)" in sphere_module._FRAGMENT_SOURCE
    assert "uniform int uAntialiasing;" in sphere_module._EFFECT_FRAGMENT_SOURCE
    assert "_SHADOW_VERTEX_SOURCE" in sphere_module.__dict__
    assert "_SHADOW_FRAGMENT_SOURCE" in sphere_module.__dict__
    assert "uOffset" in sphere_module._SHADOW_VERTEX_SOURCE
    assert "uStrength" in sphere_module._SHADOW_FRAGMENT_SOURCE


def test_partial_effect_allocation_is_discarded_before_the_next_lazy_retry(monkeypatch):
    renderer = QuickSphereRenderer()
    renderer._effect_program = 11
    renderer._effect_vao = 12
    renderer._effect_vbo = 13
    renderer._effect_vertex_count = 960
    renderer._fire_program = 14
    renderer._fire_vao = 15
    renderer._fire_vbo = 16
    renderer._effect_uniforms = {"uMatrix": 1}
    renderer._fire_uniforms = {"uTime": 2}
    deleted = []
    monkeypatch.setattr(sphere_module.gl, "glDeleteProgram", lambda resource: deleted.append(resource))
    monkeypatch.setattr(sphere_module.gl, "glDeleteVertexArrays", lambda _count, resources: deleted.extend(resources))
    monkeypatch.setattr(sphere_module.gl, "glDeleteBuffers", lambda _count, resources: deleted.extend(resources))

    renderer._discard_effect_resources()

    assert set(deleted) == {11, 12, 13, 14, 15, 16}
    assert not renderer._effect_program and not renderer._effect_vao and not renderer._effect_vbo
    assert not renderer._fire_program and not renderer._fire_vao and not renderer._fire_vbo
    assert renderer._effect_vertex_count == 0
    assert not renderer._effect_uniforms and not renderer._fire_uniforms


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

        def render(snapshot, *, verify_sentinel=False, clear_color=(0, 0, 0, 0), read_depth=False):
            gl.glViewport(0, 0, width, height); gl.glClearColor(*clear_color); gl.glClearDepth(0.37); gl.glDisable(gl.GL_SCISSOR_TEST); gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
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
            image = bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
            if read_depth:
                depth_pixels = gl.glReadPixels(0, 0, width, height, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT)
                return image, depth_pixels.tobytes()
            return image

        idle = render(_snapshot(inset=32.0), verify_sentinel=True)
        repeated = render(_snapshot(inset=32.0))
        bass = render(_snapshot(energy=(1.0, 0.0, 0.0), inset=32.0))
        mid = render(_snapshot(energy=(0.0, 1.0, 0.0), inset=32.0))
        high = render(_snapshot(energy=(0.0, 0.0, 1.0), inset=32.0))
        materials = [render(_snapshot(material=name, inset=32.0)) for name in ("Chrome", "Obsidian", "Magma", "Silver", "Water")]
        assert idle == repeated
        assert idle != bass and idle != mid and idle != high
        assert len(set(materials)) == 5
        # One body and one 1,280-triangle effect mesh are uploaded once. The
        # fire quad is intentionally below this size threshold; no later frame
        # is allowed to upload geometry again.
        assert uploads == 2
        alpha = idle[3::4]
        assert alpha[0] == 0 and alpha[-1] == 0 and max(alpha) > 0

        # Magma/Water detached effects are analytically moved by the authored
        # frame time, but their shared mesh remains static and FX=0 is a real
        # hard off switch rather than a dim colour branch.
        magma_off = render(_snapshot(material="Magma", inset=32.0, overrides={"sphere_material_fx": 0.0}))
        magma_fx = render(_snapshot(material="Magma", inset=32.0, overrides={"sphere_material_fx": 1.35}))
        water_off = render(_snapshot(material="Water", inset=32.0, overrides={"sphere_material_fx": 0.0}))
        water_fx = render(_snapshot(material="Water", inset=32.0, overrides={"sphere_material_fx": 1.20}))
        assert magma_off != magma_fx
        assert water_off != water_fx
        assert uploads == 2

        # An opaque destination makes the alpha contract observable. With a
        # zero global content fade, newborn lava/smoke/fire cannot alter color
        # or depth; at a half fade their standard-alpha composition remains
        # visible over the real destination rather than transparent black.
        opaque = (.13, .19, .27, 1.0)
        def content_fade(snapshot, value):
            return replace(snapshot, presentation=replace(snapshot.presentation, content_fade=value))
        magma_zero_base = render(content_fade(_snapshot(
            material="Magma", authored_time=1.3, inset=32.0, energy=(.8, .65, .5),
            overrides={"sphere_material_fx": 0.0},
        ), 0.0), clear_color=opaque, read_depth=True)
        magma_zero_fx = render(content_fade(_snapshot(
            material="Magma", authored_time=1.3, inset=32.0, energy=(.8, .65, .5),
            overrides={"sphere_material_fx": 2.0},
        ), 0.0), clear_color=opaque, read_depth=True)
        assert magma_zero_fx == magma_zero_base
        magma_half_base = render(content_fade(_snapshot(
            material="Magma", authored_time=1.3, inset=32.0, energy=(.8, .65, .5),
            overrides={"sphere_material_fx": 0.0},
        ), .5), clear_color=opaque)
        magma_half_fx = render(content_fade(_snapshot(
            material="Magma", authored_time=1.3, inset=32.0, energy=(.8, .65, .5),
            overrides={"sphere_material_fx": 2.0},
        ), .5), clear_color=opaque)
        assert magma_half_fx != magma_half_base
        assert all(alpha == 255 for alpha in magma_half_fx[3::4])

        # FX=2 has a finite, visible life rather than clipped full-frame
        # decoration. Compare against the exact same body at FX=0 so the color
        # oracle sees only detached lava/fire and water pixels.
        magma_fx2 = render(_snapshot(
            material="Magma", authored_time=2.1, inset=32.0,
            energy=(.8, .65, .5), overrides={"sphere_material_fx": 2.0},
        ))
        magma_base = render(_snapshot(
            material="Magma", authored_time=2.1, inset=32.0,
            energy=(.8, .65, .5), overrides={"sphere_material_fx": 0.0},
        ))
        water_fx2 = render(_snapshot(
            material="Water", authored_time=2.1, inset=32.0,
            energy=(.8, .65, .5), overrides={"sphere_material_fx": 2.0},
        ))
        water_base = render(_snapshot(
            material="Water", authored_time=2.1, inset=32.0,
            energy=(.8, .65, .5), overrides={"sphere_material_fx": 0.0},
        ))

        def detached_pixels(base, effect):
            return [
                (index // 4, effect[index], effect[index + 1], effect[index + 2])
                for index in range(0, len(effect), 4)
                if effect[index:index + 3] != base[index:index + 3]
            ]

        magma_pixels = detached_pixels(magma_base, magma_fx2)
        water_pixels = detached_pixels(water_base, water_fx2)
        assert len(magma_pixels) > 90
        assert len(water_pixels) > 50
        # Fire/lava retains a hot red-orange core; liquid is blue/cyan after
        # its Fresnel/specular/transmission fragment pass.
        assert sum(red > 130 and green > 20 and red > blue * 1.35
                   for _, red, green, blue in magma_pixels) > 30
        # Grey translucent smoke is a normal-alpha pass, deliberately unlike
        # the additive flame; ash retains a few dark/orange flakes.
        assert sum(12 < red < 130 and max(red, green, blue) - min(red, green, blue) < 36
                   for _, red, green, blue in magma_pixels) > 8
        assert sum(blue > 110 and blue > red * 1.25
                   for _, red, green, blue in water_pixels) > 8
        for pixels in (magma_pixels, water_pixels):
            xs = [pixel % width for pixel, *_ in pixels]
            ys = [pixel // width for pixel, *_ in pixels]
            assert min(xs) > 1 and max(xs) < width - 2
            assert min(ys) > 1 and max(ys) < height - 2
        assert magma_fx2 != render(_snapshot(
            material="Magma", authored_time=2.7, inset=32.0,
            energy=(.8, .65, .5), overrides={"sphere_material_fx": 2.0},
        ))
        assert water_fx2 != render(_snapshot(
            material="Water", authored_time=2.7, inset=32.0,
            energy=(.8, .65, .5), overrides={"sphere_material_fx": 2.0},
        ))

        # Sample the whole analytic life at maximum FX. Raised clouds/smoke
        # deliberately clear the enlarged body silhouette, yet their finite
        # camera-projected envelope remains within the 1.9-radius reserve.
        center_x, center_y, radius = sphere_pixel_geometry(_snapshot(inset=32.0).presentation)
        for material in ("Magma", "Water"):
            for authored_time in (0.0, .25, .5, .75, 1.0, 1.25, 1.5, 1.75):
                base = render(_snapshot(
                    material=material, authored_time=authored_time, inset=32.0,
                    energy=(1.0, 1.0, 1.0), overrides={"sphere_material_fx": 0.0},
                ))
                effect = render(_snapshot(
                    material=material, authored_time=authored_time, inset=32.0,
                    energy=(1.0, 1.0, 1.0), overrides={"sphere_material_fx": 2.0},
                ))
                pixels = detached_pixels(base, effect)
                assert pixels
                xs = [pixel % width for pixel, *_ in pixels]
                ys = [pixel // width for pixel, *_ in pixels]
                assert min(xs) >= center_x - 1.90 * radius
                assert max(xs) <= center_x + 1.90 * radius
                assert min(ys) >= center_y - 1.90 * radius
                assert max(ys) <= center_y + 1.90 * radius

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

        # Measure silhouette coverage, not just lighting/color inequality. Quiet
        # real band levels must deform the body, and a strong bass passage must
        # not flatten the independent mid lobes against a combined radius cap.
        response_controls = {
            "sphere_idle_motion": 0.0, "sphere_rotation_speed": 0.0,
            "sphere_material_fx": 0.0, "sphere_deformation": 2.0,
            "sphere_bump_reactivity": 0.0,
            "sphere_size_response": 0.0,
            "sphere_bass_response": 2.0, "sphere_mid_response": 2.0,
        }
        quiet = render(_snapshot(**logged_geometry, energy=(0.0, 0.0, 0.0), overrides=response_controls))
        low_bass = render(_snapshot(**logged_geometry, energy=(0.04, 0.0, 0.0), overrides=response_controls))
        full_bass = render(_snapshot(**logged_geometry, energy=(1.0, 0.0, 0.0), overrides=response_controls))
        added_mid = render(_snapshot(**logged_geometry, energy=(1.0, 0.7, 0.0), overrides=response_controls))
        def silhouette_delta(left, right):
            return sum(abs(a-b) for a, b in zip(left[3::4], right[3::4])) / 255.0
        assert silhouette_delta(quiet, low_bass) > 200.0
        assert silhouette_delta(full_bass, added_mid) > 100.0
        no_response = {**response_controls, "sphere_deformation": 0.0}
        assert render(_snapshot(**logged_geometry, energy=(1.0, 0.7, 0.0), overrides=no_response)) == quiet
        vocal_only = {**response_controls, "sphere_bass_response": 0.0,
                      "sphere_mid_response": 0.0, "sphere_high_response": 0.0,
                      "sphere_vocal_response": 2.0}
        vocal_shape = render(_snapshot(**logged_geometry, energy=(0.0, 0.4, 0.1), overrides=vocal_only))
        assert silhouette_delta(quiet, vocal_shape) > 200.0
        assert render(_snapshot(**logged_geometry, energy=(1.0, 0.0, 0.0), overrides=vocal_only)) == quiet
        assert render(_snapshot(**logged_geometry, energy=(0.0, 0.4, 0.1),
                                overrides={**vocal_only, "sphere_vocal_response": 0.0})) == quiet

        # Whole-body breathing is an immutable authored SphereFrame value now;
        # the renderer owns no transient filter/history. Verify that larger
        # authored pulse values change only the body scale monotonically.
        size_only = {**response_controls, "sphere_deformation": 0.0}
        resting = render(_snapshot(**logged_geometry, size_pulse=0.0, overrides=size_only))
        pulse = render(_snapshot(**logged_geometry, size_pulse=0.55, overrides=size_only))
        decaying = render(_snapshot(**logged_geometry, size_pulse=0.18, overrides=size_only))
        def diameter(pixels):
            left, top, right, bottom = alpha_bounds(pixels)
            return (right - left + bottom - top + 2) / 2.0
        assert diameter(pulse) > diameter(resting) * 1.35
        assert diameter(resting) < diameter(decaying) < diameter(pulse)
        assert render(_snapshot(**logged_geometry, size_pulse=0.0, overrides=size_only)) == resting

        detail_off = render(_snapshot(inset=32.0, overrides={"sphere_surface_detail": 0.0}))
        detail_on = render(_snapshot(inset=32.0, overrides={"sphere_surface_detail": 1.0}))
        assert detail_off != detail_on
        static_surface = {"sphere_deformation": 0.0, "sphere_idle_motion": 0.0,
                          "sphere_rotation_speed": 0.0, "sphere_material_fx": 0.0,
                          "sphere_surface_detail": 1.15}
        bump_static = render(_snapshot(energy=(0.2, 0.6, 0.2),
                                      overrides={**static_surface, "sphere_bump_reactivity": 0.0}))
        bump_reactive = render(_snapshot(energy=(0.2, 0.6, 0.2),
                                        overrides={**static_surface, "sphere_bump_reactivity": 1.5}))
        assert bump_static[3::4] == bump_reactive[3::4]  # relief changes normals, not size
        assert bump_static != bump_reactive
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
