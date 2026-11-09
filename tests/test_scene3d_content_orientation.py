"""Scene3D quarter-turns are exact pixel rotations of an oriented, uniformly scaled world."""
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest
from OpenGL import GL as gl

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.scene3d.frame import item_pixel_rect, orient_visualizer_scene_frame
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.target import SceneTarget
from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
from tests._visualizer_presentation import resolve_presentation
from tests.test_scene3d_target import WIDTH, HEIGHT, _card_frame, _clear, _read, capture


@dataclass(frozen=True)
class _Snapshot:
    logical: object
    presentation: object


def _frame(capture, left, top, width, height, quarter, *, dpr=1.0, viewport=None):
    placed = _card_frame(capture, left, top, width, height)
    viewport = viewport or placed.viewport
    vx, vy, vw, vh = viewport
    matrix = (2*dpr/vw, 0, 0, 0, 0, -2*dpr/vh, 0, 0, 0, 0, 1, 0,
              2*(left-vx)/vw-1, 2*(HEIGHT-top-vy)/vh-1, 0, 1)
    presentation = resolve_presentation(policy=get_visualizer_presentation_policy("waveform_ribbon"),
        display_size=(WIDTH/dpr, HEIGHT/dpr), outer_origin=(left/dpr, top/dpr),
        viewport_extent=(width/dpr, height/dpr), dpr=dpr, content_rotation_quarters=quarter)
    snapshot = _Snapshot(SimpleNamespace(camera=(0.12, -0.2, 4.0), geometry=(2.0, 3.0, 5.0)), presentation)
    return QuickVisualizerRenderFrame(snapshot=snapshot, viewport=viewport,
        logical_size=(width/dpr, height/dpr), matrix_values=matrix, quad_vao=placed.quad_vao)


@pytest.mark.qt
@pytest.mark.parametrize("quarter", range(4))
@pytest.mark.parametrize("samples,overlay,bloom", [(1, None, 0.0), (4, 1.0, 0.0), (4, 1.0, 0.8)])
@pytest.mark.parametrize("dpr,viewport", [(1.0, (0, 0, WIDTH, HEIGHT)), (1.5, (7, 5, 240, 128))])
def test_existing_target_rigidly_rotates_non_square_pixels_without_changing_camera(capture, quarter, samples, overlay, bloom,
                                                                                 dpr, viewport):
    resources, target = MeshResources("orientation pixels"), SceneTarget("orientation pixels")
    left, top, width, height = 42, 20, 120, 80
    try:
        physical = _frame(capture, left, top, width, height, quarter, dpr=dpr, viewport=viewport)
        oriented = orient_visualizer_scene_frame(physical)
        assert oriented.snapshot.logical is physical.snapshot.logical
        assert physical.snapshot.presentation.outer_rect == (left/dpr, top/dpr, width/dpr, height/dpr)
        if quarter == 0:
            assert oriented is physical
        assert oriented.scene_output_rotation == quarter
        logical_width, logical_height = (height, width) if quarter & 1 else (width, height)
        assert oriented.logical_size == (logical_width/dpr, logical_height/dpr)

        # The same test-owned scene at the correct logical aspect, before the rigid output turn.
        reference = _frame(capture, 12, 12, logical_width, logical_height, 0, dpr=dpr, viewport=viewport)
        _clear(capture)
        with target.scope(reference, samples, resources, overlay=overlay, bloom=bloom):
            resources.draw_image(reference, capture.textures[0])
        raw = _read(capture)
        reference_pixels = raw[HEIGHT - 12 - logical_height:HEIGHT - 12, 12:12 + logical_width]

        _clear(capture)
        with target.scope(oriented, samples, resources, overlay=overlay, bloom=bloom):
            resources.draw_image(oriented, capture.textures[0])
        raw = _read(capture)
        actual = raw[HEIGHT - top - height:HEIGHT - top, left:left + width]
        assert np.array_equal(actual, np.rot90(reference_pixels, quarter))
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == physical.viewport
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert item_pixel_rect(physical) == (left, HEIGHT - top - height, width, height)
    finally:
        target.release()
        resources.release_resources()


def test_an_oriented_scene_exception_restores_the_physical_window_state(capture):
    resources, target = MeshResources("orientation unwind"), SceneTarget("orientation unwind")
    physical = _frame(capture, 42, 20, 120, 80, 1, dpr=1.5, viewport=(7, 5, 240, 128))
    _clear(capture)
    gl.glViewport(*physical.viewport)
    gl.glEnable(gl.GL_SCISSOR_TEST)
    gl.glScissor(20, 20, 70, 50)
    try:
        with pytest.raises(RuntimeError, match="scene rejected"):
            with target.scope(orient_visualizer_scene_frame(physical), 4, resources, overlay=1.0):
                raise RuntimeError("scene rejected")
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == physical.viewport
        assert bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)) == (20, 20, 70, 50)
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        target.release()
        resources.release_resources()
