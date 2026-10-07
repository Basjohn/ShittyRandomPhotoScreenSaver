"""Production GL proof for the authored Sphere colour controls.

The tests deliberately use one frozen Sphere frame.  They vary only the
authored parameter under test or its supplied logical timestamp, so a changed
readback identifies the renderer's real uniform consumer rather than a live
audio, clock, backdrop, tracer, or shadow effect.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from tests._visualizer_frozen_settings import frozen_visualizer_settings


pytest.importorskip("OpenGL")

_WIDTH, _HEIGHT = 256, 144
_MATRIX = (2 / _WIDTH, 0, 0, 0, 0, -2 / _HEIGHT, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)


def _frozen_sphere_snapshot():
    """Use the existing deterministic production preview frame, never live capture."""
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    return _build_spectrum_preview_snapshot(
        width=_WIDTH,
        height=_HEIGHT,
        mode="sphere",
        settings=frozen_visualizer_settings("sphere"),
    )


def _authored_snapshot(snapshot, *, timestamp: float, **overrides):
    from widgets.spotify_visualizer.render_state import freeze_render_fields

    state = snapshot.logical.mode_state
    # Keep unrelated visual systems silent.  Colour is then a direct product
    # of the frozen Sphere mesh/frame and the authoring value under test.
    parameters = {
        **dict(state.parameters),
        "scene3d_detail": "High",
        "sphere_shadow_enabled": False,
        "sphere_light_tracer_enabled": False,
        "sphere_mirror": 0.0,
        "backdrop": None,
        "sphere_depth_shading_enabled": False,
        "sphere_cel_shading": False,
        "sphere_gloss": 0.0,
        "sphere_specular": 0.0,
        **overrides,
    }
    state = replace(state, parameters=freeze_render_fields(parameters))
    logical = replace(snapshot.logical, logical_timestamp=timestamp, mode_state=state)
    return replace(snapshot, logical=logical)


@pytest.fixture
def sphere_render_host(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(_WIDTH, _HEIGHT)
    host = QuickVisualizerRenderHost()
    try:
        yield capture, host
    finally:
        host.release_resources()
        capture.close()


def _render(sphere_render_host, snapshot):
    from OpenGL import GL as gl

    capture, host = sphere_render_host
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
    gl.glViewport(0, 0, _WIDTH, _HEIGHT)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    assert host.render(
        snapshot=snapshot,
        viewport=(0, 0, _WIDTH, _HEIGHT),
        logical_size=(float(_WIDTH), float(_HEIGHT)),
        matrix_values=_MATRIX,
    ) == "sphere"
    pixels = gl.glReadPixels(0, 0, _WIDTH, _HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(_HEIGHT, _WIDTH, 4)[::-1].copy()


def _changed_fraction(first, second, *, threshold: int = 6) -> float:
    visible = (first[..., 3] > 0) | (second[..., 3] > 0)
    difference = np.abs(first[..., :3].astype(np.int16) - second[..., :3].astype(np.int16)).max(axis=2)
    return float(np.count_nonzero(visible & (difference > threshold))) / max(1, int(visible.sum()))


def _hue_spread(pixels) -> float:
    """Circular dispersion of sufficiently saturated rendered surface pixels."""
    rgb = pixels[..., :3].astype(np.float32) / 255.0
    hi, lo = rgb.max(axis=2), rgb.min(axis=2)
    delta = hi - lo
    valid = (pixels[..., 3] > 24) & (delta > 0.18)
    assert valid.sum() > 500
    hue = np.zeros_like(hi)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red_max = (hi == red) & valid
    green_max = (hi == green) & valid
    blue_max = (hi == blue) & valid
    hue[red_max] = ((green[red_max] - blue[red_max]) / delta[red_max]) % 6.0
    hue[green_max] = (blue[green_max] - red[green_max]) / delta[green_max] + 2.0
    hue[blue_max] = (red[blue_max] - green[blue_max]) / delta[blue_max] + 4.0
    angle = hue[valid] * (np.pi / 3.0)
    return float(1.0 - np.hypot(np.cos(angle).mean(), np.sin(angle).mean()))


def _alpha_regions(opaque, edge_probe):
    """Classify actual fill and edge pixels from the renderer's own alpha."""
    visible = opaque[..., 3] > 224
    # A transparent fill plus opaque edge exposes the shader's decisive edge
    # alpha mask.  It is a readback-only classifier; the assertions below use
    # separate renders with the authored fill/edge RGBA inputs.
    fill = visible & (edge_probe[..., 3] < 32)
    edge = visible & (edge_probe[..., 3] >= 250)
    assert fill.sum() > 100 and edge.sum() > 100
    return fill, edge


@pytest.mark.qt
def test_rainbow_speed_zero_is_timestamp_stable_and_nonzero_speed_changes_real_colour(sphere_render_host):
    frozen = _frozen_sphere_snapshot()
    common = {
        "sphere_taste_the_rainbow_enabled": True,
        "sphere_taste_the_rainbow_surfaces": True,
        "sphere_taste_the_rainbow_edges": False,
        "sphere_taste_the_rainbow_extent": 0.22,
        "sphere_fill_color": [255, 255, 255, 255],
        "sphere_edge_color": [255, 255, 255, 255],
    }
    stopped_a = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=1.0, sphere_taste_the_rainbow_speed=0.0, **common))
    stopped_b = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=8.0, sphere_taste_the_rainbow_speed=0.0, **common))
    assert np.array_equal(stopped_a, stopped_b)

    moving_a = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=1.0, sphere_taste_the_rainbow_speed=0.05, **common))
    moving_b = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=6.0, sphere_taste_the_rainbow_speed=0.05, **common))
    assert _changed_fraction(moving_a, moving_b) > 0.20


@pytest.mark.qt
def test_rainbow_extent_changes_spatial_colour_over_the_frozen_sphere(sphere_render_host):
    frozen = _frozen_sphere_snapshot()
    common = {
        "sphere_taste_the_rainbow_enabled": True,
        "sphere_taste_the_rainbow_surfaces": True,
        "sphere_taste_the_rainbow_edges": False,
        "sphere_taste_the_rainbow_speed": 0.0,
        "sphere_fill_color": [255, 255, 255, 255],
        "sphere_edge_color": [255, 255, 255, 255],
    }
    uniform = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=4.0, sphere_taste_the_rainbow_extent=0.0, **common))
    spatial = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=4.0, sphere_taste_the_rainbow_extent=0.82, **common))
    assert _changed_fraction(uniform, spatial) > 0.20
    assert _hue_spread(spatial) > _hue_spread(uniform) + 0.15


@pytest.mark.qt
def test_fill_and_edge_rgba_alpha_independently_control_direct_transparency(sphere_render_host):
    frozen = _frozen_sphere_snapshot()
    common = {
        "sphere_taste_the_rainbow_enabled": False,
        # The lowest supported width leaves a decisive interior and edge
        # population for a direct alpha readback from this real mesh.
        "sphere_edge_weight": 0.25,
        "sphere_fill_color": [255, 0, 0, 255],
        "sphere_edge_color": [0, 255, 0, 255],
    }
    opaque = _render(sphere_render_host, _authored_snapshot(frozen, timestamp=4.0, **common))
    edge_probe = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=4.0, **{**common, "sphere_fill_color": [255, 0, 0, 0]}))
    fill_low = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=4.0, **{**common, "sphere_fill_color": [255, 0, 0, 40]}))
    edge_low = _render(sphere_render_host, _authored_snapshot(
        frozen, timestamp=4.0, **{**common, "sphere_edge_color": [0, 255, 0, 40]}))
    fill_region, edge_region = _alpha_regions(opaque, edge_probe)

    opaque_fill_alpha = float(opaque[..., 3][fill_region].mean())
    opaque_edge_alpha = float(opaque[..., 3][edge_region].mean())
    assert float(fill_low[..., 3][fill_region].mean()) < opaque_fill_alpha * 0.55
    assert float(fill_low[..., 3][edge_region].mean()) > opaque_edge_alpha * 0.98
    assert float(edge_low[..., 3][edge_region].mean()) < opaque_edge_alpha * 0.92
    assert float(edge_low[..., 3][fill_region].mean()) > opaque_fill_alpha * 0.98
