"""Extruded Bubble's scene mapping (pure) and its renderer's resource contract through the production render host on
an offscreen context (no window). No pixel goldens: looks are judged against the operator's mocks in the lab."""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from rendering.gl_programs import extruded_bubble_scene as scene
from tests._visualizer_frozen_settings import frozen_visualizer_settings

SETTINGS = frozen_visualizer_settings("extruded_bubble")


def _record(x=0.0, y=0.0, z=0.5, radius=0.1, alpha=1.0, ident=1.0, cluster=-1.0):
    return (x, y, z, radius, alpha, 0.0, ident, cluster)


@pytest.mark.parametrize("turn, tilt", [(0.0, 0.0), (0.37, -0.3), (-0.8, 0.45), (1.0, 0.0)])
def test_the_camera_is_a_rotation_pitched_up_and_turned_about_the_vertical(turn, tilt):
    view_to_world, world_to_view, tan, projection = scene.camera(turn, tilt, 16 / 9)
    axes = np.asarray(view_to_world).reshape(3, 3)                    # rows: right, up, back
    assert np.allclose(axes @ axes.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(axes) == pytest.approx(1.0)
    assert np.allclose(np.asarray(world_to_view).reshape(3, 3), axes.T)
    assert axes[0][1] == pytest.approx(0.0)                           # the horizon stays level (no roll)
    pitch = math.degrees(math.asin(-axes[2][1]))                      # looking along -back
    assert pitch == pytest.approx(16.0 + 90.0 * tilt)
    assert tan[0] / tan[1] == pytest.approx(16 / 9)
    assert projection[5] == pytest.approx(1.0 / tan[1])


def test_scene_scale_zooms_without_turning_the_view():
    plain, zoomed = scene.camera(0.2, 0.1, 1.5), scene.camera(0.2, 0.1, 1.5, scale=2.0)
    assert zoomed[0] == plain[0]
    assert zoomed[2][1] == pytest.approx(plain[2][1] / 2.0)


def test_a_bubble_keeps_its_share_of_the_view_at_any_depth_and_fades_by_shrinking():
    view_to_world, _w, tan, _p = scene.camera(0.3, 0.2, 1.6)
    rows = scene.bubble_instances(_record(z=0.0) + _record(z=1.0, ident=2.0) + _record(alpha=0.25, ident=3.0),
                                  view_to_world, tan)
    assert len(rows) == 3
    for row, z, alpha in zip(rows, (0.0, 1.0, 0.5), (1.0, 1.0, 0.25)):
        depth = scene.DEPTH_NEAR + scene.DEPTH_SPAN * z
        assert np.linalg.norm(row[:3]) >= depth                       # in front of the eye, at its depth
        assert row[3] / (tan[1] * depth) == pytest.approx(0.1 * math.sqrt(alpha), rel=1e-5)
        assert row[5] == 0.0


def test_fused_members_and_faded_bubbles_are_not_shells_and_clusters_carry_their_members():
    view_to_world, _w, tan, _p = scene.camera(0.0, 0.0, 1.6)
    records = _record(x=-0.1, cluster=0.0) + _record(x=0.1, ident=2.0, cluster=0.0) + _record(alpha=0.0, ident=3.0)
    assert len(scene.bubble_instances(records, view_to_world, tan)) == 0
    clusters = scene.cluster_instances(records, (2.0, 0.0, 1.0, -1.0), view_to_world, tan)
    assert clusters.shape == (1, scene.CLUSTER_FLOATS)
    assert clusters[0, 12] == 2.0 and clusters[0, 8:12].tolist() == [0.0] * 4    # two members, third unused


def test_near_giants_are_drawn_by_the_near_layer_and_drift_without_jumping():
    view_to_world, _w, tan, _p = scene.camera(0.0, 0.0, 1.6)
    now, later = scene.near_giants(10.0, view_to_world, tan), scene.near_giants(10.0 + 1 / 60, view_to_world, tan)
    assert now.shape == (scene.NEAR_GIANTS, scene.SHELL_FLOATS) and np.all(now[:, 5] == 3.0)
    assert np.abs(later[:, :3] - now[:, :3]).max() < 1e-3


def test_glint_proxies_follow_bubbles_toward_the_light():
    view_to_world, _w, tan, _p = scene.camera(0.0, 0.0, 1.6)
    shells = np.concatenate((scene.bubble_instances(_record(), view_to_world, tan),
                             scene.near_giants(0.0, view_to_world, tan)))
    proxies = scene.glint_proxies(shells, (0.0, 1.0, 0.0), 3.0)
    assert len(proxies) == 1                                          # giants mirror nothing into the probe
    assert proxies[0, 1] > shells[0, 1] and proxies[0, 4] == 3.0


@pytest.mark.parametrize("light_type", ["Sunlit Surface", "Deep Light"])
def test_every_light_type_gives_the_knobs_the_renderer_reads(light_type):
    knobs = scene.scene_knobs({**SETTINGS, "extruded_bubble_light_type": light_type})
    for key in ("sun", "sun_below", "spec_dir", "light", "water", "deep", "sky", "shaft", "absorb", "exposure",
                "surface", "shaft_y", "focus", "aperture"):
        assert key in knobs, key
    for key in ("sun", "sun_below", "spec_dir"):
        assert np.linalg.norm(knobs[key]) == pytest.approx(1.0)
    assert knobs["sun_below"][1] > 0.0                                 # the light comes from above


def test_ray_strength_reads_its_range_at_the_level_and_is_off_when_disabled():
    low, high = SETTINGS["extruded_bubble_rays"]
    on = {**SETTINGS, "extruded_bubble_rays_enabled": True}
    assert scene.ray_strength(on, 0.0) == pytest.approx(low)
    assert scene.ray_strength(on, 1.0) == pytest.approx(high)
    assert scene.ray_strength(on, 2.0) == pytest.approx(high)
    assert scene.ray_strength({**SETTINGS, "extruded_bubble_rays_enabled": False}, 0.7) == 0.0


# --- the renderer through the production host -------------------------------------------------------------------


def _snapshot(fade=1.0, **parameters):
    from tests.test_qtquick_extruded_spectrum import H, W
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="extruded_bubble", settings=SETTINGS)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    logical = dataclasses.replace(snapshot.logical, mode_state=state)
    presentation = dataclasses.replace(snapshot.presentation, content_fade=fade)
    return dataclasses.replace(snapshot, logical=logical, presentation=presentation)


@pytest.fixture
def target(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_qtquick_extruded_spectrum import _Target

    capture, host = _Target(), QuickVisualizerRenderHost()
    try:
        yield capture, host
    finally:
        assert capture.capture.context.makeCurrent(capture.capture.surface)
        host.release_resources()
        capture.close()


@pytest.mark.qt
def test_a_prepared_renderer_draws_without_compiling_or_allocating_and_releases_everything(target, monkeypatch):
    from OpenGL import GL as gl

    from rendering.quick.render import gl_resources
    from rendering.quick.scene3d import defocus, probe, resources
    from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer

    capture, host = target
    snapshot = _snapshot()
    renderer = QuickExtrudedBubbleRenderer()
    host._implementations["extruded_bubble"] = renderer
    capture.render(host, _snapshot(fade=0.0))                          # establishes the frame; draws nothing
    frame = _frame(snapshot, capture.capture.vao)
    for _ in range(80):
        if renderer.prepare_step(frame):
            break
    else:
        pytest.fail("the renderer never finished preparing")
    names, allocation = dict(renderer._target._names), renderer._target.allocation

    def forbidden(*_args, **_kwargs):
        pytest.fail("a prepared frame compiled or allocated")
    for module in (resources, defocus, probe, gl_resources):
        if hasattr(module, "compile_program"):
            monkeypatch.setattr(module, "compile_program", forbidden)
    for name in ("glCreateProgram", "glCreateShader", "glCreateTextures", "glGenTextures", "glCreateBuffers",
                 "glCreateVertexArrays", "glCreateFramebuffers", "glCreateRenderbuffers", "glTextureStorage2D",
                 "glTexStorage2D", "glTextureStorage2DMultisample", "glNamedBufferStorage"):
        monkeypatch.setattr(gl, name, forbidden)
    turned = _snapshot(extruded_bubble_turn=0.4, extruded_bubble_tilt=0.2)
    pictures = [capture.render(host, frame_) for frame_ in (snapshot, turned, snapshot)]
    assert renderer._target._names == names and renderer._target.allocation == allocation
    assert np.abs(pictures[0] - pictures[0][0, 0]).max() > 0           # it draws
    assert np.array_equal(pictures[0], pictures[2])                    # the same frame draws the same picture
    assert np.abs(pictures[1] - pictures[0]).mean() > 1.0              # turning the view changes it
    monkeypatch.undo()
    host.release_resources()
    assert not renderer.has_resources


def _frame(snapshot, quad_vao):
    """The frame the host hands the renderer for the capture's card (as ``_Target.render`` draws it)."""
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from tests.test_qtquick_extruded_spectrum import H, W

    return QuickVisualizerRenderFrame(snapshot=snapshot, viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                                      matrix_values=(2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                      quad_vao=quad_vao)
