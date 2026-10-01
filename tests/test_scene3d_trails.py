"""Motion trails: faint, fading, light outlines of where pieces just were, offered only where
they help, never on a piece that is (nearly) still, and dropped with the run.

GPU checks render offscreen through the transition capture harness; no window is shown.
"""
from __future__ import annotations

import numpy as np
import pytest

from rendering.gl_programs import scene3d as lib
from tools.transition_contact_sheet import TransitionCapture

_TRAILED = (("block_spins", "left", "blockspin", 0.45), ("exploding_tiles", "center_out", "exploding_tiles", 0.3),
            ("glass_shatter", "left", "glass_shatter", 0.4), ("crumble", None, "crumble", 0.65),
            ("pixel_accretion", "left", "pixel_accretion", 0.4))


def test_ghosts_trail_the_moment_at_a_fixed_real_time_oldest_and_faintest_first():
    ghosts = lib.scene3d_trail_ghosts(0.5, 8000)
    assert len(ghosts) == lib.SCENE3D_TRAIL_GHOSTS
    times, fades = zip(*ghosts)
    assert list(times) == sorted(times) and max(times) < 0.5
    assert list(fades) == sorted(fades) and 0.0 < fades[0] and fades[-1] < 1.0
    step = lib.SCENE3D_TRAIL_GAP_SECONDS * 1000.0 / 8000
    assert np.allclose(np.diff(times + (0.5,)), step)
    # Twice the duration: half the progress between ghosts (real time, not progress).
    assert np.isclose(0.5 - lib.scene3d_trail_ghosts(0.5, 16000)[-1][0], step / 2)
    assert min(t for t, _fade in lib.scene3d_trail_ghosts(0.001, 8000)) == 0.0   # never before the start


def test_the_ghost_transform_keeps_the_shader_and_writes_only_the_fade_of_moving_pieces():
    fragment = "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\nvoid main() { if (vUv.x < 0.1) discard; FragColor = vec4(vUv, 0.0, 1.0); }\n"
    ghost = lib.scene3d_ghost_fragment(lib.scene3d_motion_fragment(fragment))
    assert ghost.startswith("#version 460 core\n") and "uniform float uGhostFade;" in ghost
    assert "void sceneTrailMain()" in ghost and "discard" in ghost and ghost.count("void main()") == 1
    # Only a piece that moved further than the trail line reaches leaves a ghost.
    assert "sceneVelocity(vClipNow, vClipBefore, uViewport)" in ghost.split("void main()")[1]
    assert ghost.rstrip().endswith("FragColor = vec4(uGhostFade);\n}")
    with pytest.raises(ValueError):   # a fragment that cannot know how far its piece moved
        lib.scene3d_ghost_fragment(fragment)
    with pytest.raises(ValueError):
        lib.scene3d_ghost_fragment("#version 460 core\nout vec4 Colour;\nvoid main() {}\n")


@pytest.mark.qt
@pytest.mark.parametrize("effect,direction,section,progress", _TRAILED)
def test_trails_are_light_lines_where_pieces_moved_and_nothing_on_still_ones(qt_app, effect, direction, section,
                                                                             progress):
    capture = TransitionCapture(480, 270)
    try:
        def change(duration_ms):
            frames = {}
            for trails in ("Off", "On"):
                run = capture.run(effect, direction=direction, duration_ms=duration_ms,
                                  settings={section: {"motion_trails": trails}})
                frames[trails] = np.asarray(capture.render(run, progress)[0], dtype=np.int16)[..., :3]
            return frames["On"] - frames["Off"]

        moving = change(1500)
        changed = np.abs(moving).max(axis=2) > 2
        assert changed.sum() > 50, effect                           # a trail behind what moved...
        assert (moving[changed].sum(axis=1) >= 0).all(), effect    # ...drawn as light lines, never dark
        # Over a run so long that pieces barely move between ghosts, practically nothing trails
        # (no halo around a piece from its own ghosts).
        nearly_still = np.abs(change(600_000)).max(axis=2) > 2
        assert nearly_still.mean() < 0.002, (effect, int(nearly_still.sum()))
        renderer = capture.host._implementations[effect]
        assert renderer._trails.has_resources
        capture.host.park()
        assert not renderer._trails.has_resources
    finally:
        capture.close()
