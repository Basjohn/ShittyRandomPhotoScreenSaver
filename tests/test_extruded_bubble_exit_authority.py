"""Physical lifetime regressions; native breach/opacity acceptance is separate."""
from __future__ import annotations

import pytest

from tools.visualizer_replay.eb_simulation_support import simulation_module

simulation_module()
from core.constants.extruded_bubble_world import WATER_SURFACE_Y, WORLD_HALF, WORLD_MARGIN
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput, _Bubble,
)


def _controls(geometry="SCENE", *, surface=False):
    return ExtrudedBubbleControls(
        large_count=(0., 0.), mid_count=(0., 0.),
        emission_geometry=geometry, surface_scene=surface,
        # Horizontal BEAM: its authored End cannot confound the Y boundary.
        stream_path=(-1., 0., 0., 1., 0., 0.),
        stream_speed=(0., 0.), drift=(0., 0.), sway=0.,
        breathing=(0., 0.), small_pulse=(0., 0.), collision_scope="off",
    )


def _simulation(point):
    sim = ExtrudedBubbleSimulation(42)
    sim._filled = True
    bubble = _Bubble(1, True, *point, .2, 0., alpha=1.)
    sim._bubbles = [bubble]
    return sim, bubble


def _step(sim, controls):
    return sim.advance(MusicInput(.1, True), controls)


@pytest.mark.parametrize("geometry", ("BEAM", "SCENE"))
def test_deep_identity_above_surface_plane_lives_until_physical_world_exit(geometry):
    sim, bubble = _simulation((0., WATER_SURFACE_Y + .3, 0.))
    controls = _controls(geometry)
    snapshot = _step(sim, controls)
    assert not bubble.leaving and bubble.alpha == 1.
    assert snapshot.bubbles[6] == bubble.ident
    assert snapshot.bubbles[4] == 1.

    bubble.y = WORLD_HALF[1] + WORLD_MARGIN + bubble.current_radius + .01
    snapshot = _step(sim, controls)
    assert bubble.leaving and 0. < bubble.alpha < 1.
    assert snapshot.bubbles[6] == bubble.ident
    assert snapshot.bubbles[4] == bubble.alpha
    for _ in range(9):
        _step(sim, controls)
    assert sim._bubbles == []


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("sign", (-1., 1.))
def test_deep_scene_keeps_each_world_boundary_and_existing_gentle_fade(axis, sign):
    point = [0., 0., 0.]
    point[axis] = sign * (WORLD_HALF[axis] + WORLD_MARGIN + .2 + .01)
    sim, bubble = _simulation(point)
    _step(sim, _controls())
    assert bubble.leaving
    assert bubble.alpha == pytest.approx(1. - .1 / .9)


def test_surface_scene_still_retires_a_shell_fully_above_water_on_lateral_flow():
    sim, bubble = _simulation((0., WATER_SURFACE_Y + .3, 0.))
    _step(sim, _controls(surface=True))
    assert bubble.leaving and 0. < bubble.alpha < 1.
