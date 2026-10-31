"""An absent ordinary population has no near optics; retained targets stay warm."""
from dataclasses import replace

import numpy as np
import pytest

# The NVIDIA driver swaps in re-optimized variants of already-used programs a
# few draws after compiling them, and how many draws depends on how often the
# same sources were compiled earlier in the process (other GPU test files). A
# swap moves a handful of pixels by one 8-bit step, so repeat renders of one
# snapshot are compared within that step; stale near light is far larger.
_DRIVER_STEP = 1


def _same(a, b) -> bool:
    return int(np.abs(a - b).max()) <= _DRIVER_STEP


@pytest.mark.qt
def test_empty_ordinary_population_skips_near_and_cannot_replay_stale_bokeh(qt_app, monkeypatch):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_scene import physical_camera
    from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_extruded_bubble_renderer import _snapshot, _record
    from tests.test_qtquick_extruded_spectrum import _Target, W, H

    snapshot = _snapshot(extruded_bubble_focus=1., extruded_bubble_aperture=1.)
    state = snapshot.logical.mode_state
    p = state.parameters
    axes, _, eye, _, _ = physical_camera(
        p['extruded_bubble_turn'], p['extruded_bubble_tilt'], W / H,
        p['extruded_bubble_scene_scale'], p['extruded_bubble_scene_pan_x'], p['extruded_bubble_scene_pan_y'],
        p['extruded_bubble_camera_fov'], p['extruded_bubble_camera_position'],
        p['extruded_bubble_light_type'] == 'Sunlit Surface')
    centre = np.asarray(eye) - np.asarray(axes).reshape(3, 3)[2] * 6.
    state = replace(state, bubbles=_record(*centre, radius=.55), clusters=())
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=state))
    empty = replace(snapshot, logical=replace(snapshot.logical,
                    mode_state=replace(state, bubbles=(), clusters=())))
    capture, host = _Target(), QuickVisualizerRenderHost()
    fresh = QuickVisualizerRenderHost()
    try:
        renderer = QuickExtrudedBubbleRenderer()
        host._implementations['extruded_bubble'] = renderer
        # The retained transition starts with warm programs/targets, matching
        # prepare_step's admission contract rather than measuring a cold draw.
        capture.render(host, snapshot)
        capture.render(host, snapshot)
        populated = capture.render(host, snapshot)
        assert _same(populated, capture.render(host, snapshot))
        resources = (renderer._near._fbo, renderer._near._colour, renderer._near._circle)
        assert all(resources)
        previous = int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D))
        gl.glBindTexture(gl.GL_TEXTURE_2D, renderer._near._colour)
        near_pixels = np.asarray(gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_FLOAT)).reshape(-1, 4)
        gl.glBindTexture(gl.GL_TEXTURE_2D, previous)
        assert near_pixels[:, 3].max() > .1, 'the populated frame must actually leave near light'
        near_calls = []
        for name in ('begin', 'end', 'composite'):
            original = getattr(renderer._near, name)
            def tracked(*args, method=original, label=name, **kwargs):
                near_calls.append(label)
                return method(*args, **kwargs)
            monkeypatch.setattr(renderer._near, name, tracked)
        cleared = capture.render(host, empty)
        assert near_calls == []
        assert resources == (renderer._near._fbo, renderer._near._colour, renderer._near._circle)
        # A second retained renderer has no prior near light to accidentally replay.
        clean_empty = capture.render(fresh, empty)
        assert _same(cleared, clean_empty)
        returned = capture.render(host, snapshot)
        assert near_calls == ['begin', 'end', 'composite']
        assert resources == (renderer._near._fbo, renderer._near._colour, renderer._near._circle)
        assert _same(populated, returned)
        assert not _same(populated, cleared)
    finally:
        assert capture.capture.context.makeCurrent(capture.capture.surface)
        fresh.release_resources()
        host.release_resources()
        capture.close()
