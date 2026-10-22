"""R43 provisional source-to-surface and physical-inlet falsifiers, not visual acceptance."""
from __future__ import annotations

import math

from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput,
)
from core.constants.extruded_bubble_world import WATER_SURFACE_Y


def _c(**kw):
    return ExtrudedBubbleControls(
        large_count=(0., 0.), mid_count=(40., 40.),
        stream_path=(0., -1., 0., 0., 1., 0.), stream_speed=(.5, .5),
        drift=(0., 0.), sway=0., collision_scope="off", bubble_spread=4.,
        **kw,
    )


def test_musical_count_deficit_does_not_create_an_immediate_birth_band():
    sim = ExtrudedBubbleSimulation(73)
    c = _c()
    counts = []
    ids = set()
    for _ in range(90):
        sim.advance(MusicInput(1 / 90, True, body_bands=(1., 1., 1.)), c)
        new = {b.ident for b in sim._bubbles} - ids
        assert len(new) <= 1  # no multi-birth frame at a single physical source
        ids.update(new)
        counts.append(len(ids))
    # A 40-bubble target isn't permission to birth 40 bubbles in a second.
    assert 3 <= counts[-1] <= 12, counts[-1]
    assert counts == sorted(counts)


def test_inlet_keeps_reacted_large_shells_separate_at_birth():
    sim = ExtrudedBubbleSimulation(96)
    sim._body_big_envelope = .75  # louder section, reacted shells much larger than R42 fixed gap
    c = ExtrudedBubbleControls(stream_path=(0., -1., 0., 0., 1., 0.),
        bubble_spread=4., large_count=(12., 12.), mid_count=(0., 0.),
        breathing=(.3, .8), collision_scope="off")
    for _ in range(12):
        if not sim._spawn(True, c, (0., 1., 0.), anywhere=False):
            break
    assert len(sim._bubbles) >= 2
    for i, a in enumerate(sim._bubbles):
        for b in sim._bubbles[i + 1:]:
            assert math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) >= a.current_radius + b.current_radius


def test_surface_retirement_waits_for_centre_to_reach_shared_water_plane():
    sim = ExtrudedBubbleSimulation(19)
    sim._filled = True
    from widgets.spotify_visualizer.extruded_bubble_simulation import _Bubble
    a = _Bubble(1, True, 0., WATER_SURFACE_Y - .02, 0., 1.1, 0., alpha=1.)
    b = _Bubble(2, True, 8., WATER_SURFACE_Y + .02, 0., 1.1, 0., alpha=1.)
    sim._bubbles = [a, b]
    c = ExtrudedBubbleControls(large_count=(0, 0), mid_count=(0, 0),
        stream_path=(0, -1, 0, 0, 1, 0), stream_speed=(0, 0),
        drift=(0, 0), sway=0, surface_scene=True, collision_scope="off")
    sim.advance(MusicInput(1 / 90, True), c)
    assert a.alpha == 1.0 and not a.leaving
    assert b.leaving and 0 < b.alpha < 1.0
