"""3D + frameless Visualizers are not contained to their frame (operator 2026-10-04): with
overflow on, Extruded Spectrum and Shockwave Grid draw past their item wherever the view takes them,
up to the window, and their scene target never cuts what they draw."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

pytest.importorskip("OpenGL")

W, H = 480, 270                     # the item
WW, WH = 3 * W, 3 * H               # the window it sits in the middle of


def _snapshot(mode: str, **parameters):
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode=mode)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))


@pytest.fixture
def window(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(WW, WH)
    host = QuickVisualizerRenderHost()
    yield capture, host
    host.release_resources()
    capture.close()


# Item pixels -> clip space with the item in the middle third of the window.
_MATRIX = (2 / WW, 0, 0, 0, 0, -2 / WH, 0, 0, 0, 0, 1, 0, -1 / 3, 1 / 3, 0, 1)


def _render(window, snapshot):
    from OpenGL import GL as gl

    capture, host = window
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
    gl.glViewport(0, 0, WW, WH)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    host.render(snapshot=snapshot, viewport=(0, 0, WW, WH), logical_size=(float(W), float(H)), matrix_values=_MATRIX)
    pixels = np.frombuffer(bytes(gl.glReadPixels(0, 0, WW, WH, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)), dtype=np.uint8)
    return pixels.reshape(WH, WW, 4)          # bottom-up rows, as GL and item_pixel_rect count them


def _target_rect(window, snapshot):
    from rendering.quick.scene3d.frame import item_pixel_rect
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame

    _capture, host = window
    renderer = host._implementations[snapshot.logical.mode_id]
    frame = QuickVisualizerRenderFrame(snapshot, (0, 0, WW, WH), (float(W), float(H)), _MATRIX, 1)
    parameters = snapshot.logical.mode_state.parameters
    if snapshot.logical.mode_id == "extruded_spectrum":
        return item_pixel_rect(renderer._target_frame(frame, renderer._scene(frame)))
    return item_pixel_rect(renderer._target_frame(frame, parameters))   # Shockwave Grid, Sphere


@pytest.mark.parametrize("mode, views", [
    ("extruded_spectrum", [dict(extruded_spectrum_tilt=1.0, extruded_spectrum_turn=0.9,
                                extruded_spectrum_depth=1.0, extruded_spectrum_reflection=1.0),
                           dict(extruded_spectrum_tilt=-1.0, extruded_spectrum_turn=-0.6)]),
    ("shockwave_grid", [dict(shockwave_grid_tilt=0.0, shockwave_grid_turn=0.5, shockwave_grid_wave_height=1.0),
                        dict(shockwave_grid_tilt=1.0, shockwave_grid_turn=-0.8, shockwave_grid_horizon=1.0)]),
    ("sphere", [dict(sphere_particle_distance=2.25, sphere_fragment_strength=3.6, sphere_shadow_enabled=True,
                     sphere_shadow_distance=2.5, sphere_shadow_size=1.6),
                dict(sphere_particle_distance=0.5, sphere_shadow_enabled=False)]),
])
def test_a_3d_frameless_mode_leaves_its_frame_and_its_target_never_cuts_it(window, mode, views):
    item = (W, H, 2 * W, 2 * H)                         # left, bottom, right, top in window pixels
    left_item = False
    for view in views:
        snapshot = _snapshot(mode, **{f"{mode}_allow_overflow": True}, **view)
        drawn = np.argwhere(_render(window, snapshot)[..., 3] > 0)
        assert drawn.size, view
        bottom, left = drawn.min(axis=0)
        top, right = drawn.max(axis=0) + 1
        tx, ty, tw, th = _target_rect(window, snapshot)
        # Nothing touches the target's edge unless that edge is the window's (never cut short).
        assert left > tx or tx == 0, view
        assert bottom > ty or ty == 0, view
        assert right < tx + tw or tx + tw == WW, view
        assert top < ty + th or ty + th == WH, view
        left_item |= left < item[0] or bottom < item[1] or right > item[2] or top > item[3]
    assert left_item                                       # not contained to its frame


def test_without_overflow_the_scene_stays_in_its_item(window):
    snapshot = _snapshot("extruded_spectrum", extruded_spectrum_allow_overflow=False, extruded_spectrum_tilt=1.0,
                         extruded_spectrum_turn=0.9)
    drawn = np.argwhere(_render(window, snapshot)[..., 3] > 0)
    bottom, left = drawn.min(axis=0)
    top, right = drawn.max(axis=0) + 1
    assert left >= W and bottom >= H and right <= 2 * W and top <= 2 * H


def test_the_reach_grows_in_steps_and_never_past_the_window():
    from types import SimpleNamespace

    from rendering.quick.scene3d.frame import REACH_STEP, item_pixel_rect, reach_item_frame

    frame = SimpleNamespace(viewport=(0, 0, WW, WH), logical_size=(float(W), float(H)), matrix_values=_MATRIX,
                            quad_vao=0)
    small = reach_item_frame(frame, (-1.0, -1.0, W + 1.0, H + 1.0))
    assert small.logical_size == pytest.approx((W + 2 * REACH_STEP * H, H + 2 * REACH_STEP * H))
    assert reach_item_frame(frame, (-2.0, -2.0, W + 2.0, H + 2.0)).logical_size == small.logical_size
    assert reach_item_frame(frame, (0.0, 0.0, W, H)).logical_size == (W, H)
    huge = reach_item_frame(frame, (-1e6, -1e6, 1e6, 1e6))
    assert item_pixel_rect(huge) == (0, 0, WW, WH)
