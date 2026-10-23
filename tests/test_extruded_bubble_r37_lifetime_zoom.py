"""R37 narrowly scoped logical checks. Native appearance remains unaccepted."""
from __future__ import annotations

from tools.visualizer_replay.eb_simulation_support import simulation_module

simulation_module()  # Same Qt-free package admission as existing R34 probes.
from core.settings.visualizer_mode_settings import require_mode_settings
from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_HALF
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput, _Bubble,
)
from rendering.gl_programs.extruded_bubble_scene import physical_camera


def _controls():
    return ExtrudedBubbleControls(
        large_count=(1., 1.), mid_count=(0., 0.),
        stream_path=(-0.8, 0., 0., 0.8, 0., 0.),
        stream_speed=(0., 0.), drift=(0., 0.), sway=0.,
        collision_scope='off',
    )


def _step(sim, controls):
    return sim.advance(MusicInput(1. / 60., True, body_bands=(0., 0., 0.)), controls)


def test_count_drop_closes_inlet_but_does_not_kill_existing_midstream_identities():
    sim = ExtrudedBubbleSimulation(99)
    sim._filled = True
    sim._bubbles = [_Bubble(i, True, float(i)*0.2, 0., 0., 0.2, 0., alpha=1.) for i in range(1, 5)]
    _step(sim, _controls())
    assert len(sim._bubbles) == 4
    assert all(not bubble.leaving and bubble.alpha == 1. for bubble in sim._bubbles)


def test_existing_bubble_enters_smooth_fade_after_crossing_authored_end():
    sim = ExtrudedBubbleSimulation(99)
    sim._filled = True
    end_x = 0.8 * WORLD_HALF[0]
    sim._bubbles = [_Bubble(1, True, end_x + 0.01, 0., 0., 0.2, 0., alpha=1.)]
    _step(sim, _controls())
    assert sim._bubbles[0].leaving
    assert 0.9 < sim._bubbles[0].alpha < 1.
    for _ in range(60):
        _step(sim, _controls())
    assert sim._bubbles == []


def test_wider_eb_dolly_range_keeps_camera_lens_constant():
    spec = require_mode_settings('extruded_bubble')
    scale = next(c for c in spec.controls if c.key == 'extruded_bubble_scene_scale')
    assert (scale.low, scale.high) == (0.2, 5.0)
    far = physical_camera(0., 0., 16/9, 0.2, surface_bound=False)
    near = physical_camera(0., 0., 16/9, 5., surface_bound=False)
    assert far[3] == near[3] and far[4] == near[4]
    assert far[2] != near[2]
