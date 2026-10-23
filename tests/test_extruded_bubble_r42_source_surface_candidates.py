"""R42 deterministic source->surface and birth spacing falsifiers, not visual acceptance."""
from __future__ import annotations

from tools.visualizer_replay.eb_simulation_support import simulation_module

simulation_module()
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleSimulation, ExtrudedBubbleControls, MusicInput, _Bubble,
)
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters
from core.constants.extruded_bubble_world import WORLD_HALF, WATER_SURFACE_Y
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings


def controls(**kwargs):
    return ExtrudedBubbleControls(
        large_count=(0., 0.), mid_count=(0., 0.),
        stream_path=(0., -1., 0., 0., -0.1, 0.),
        stream_speed=(0., 0.), drift=(0., 0.), sway=0., collision_scope='off',
        **kwargs,
    )


def step(sim, c):
    return sim.advance(MusicInput(1./90., True, body_bands=(0., 0., 0.)), c)


def test_sunlit_surface_ignores_premature_end_and_retires_at_real_visible_water_plane():
    sim = ExtrudedBubbleSimulation(42)
    sim._filled = True
    # Authored End below the surface, but a visible bubble must not fade there.
    low = _Bubble(1, True, 0., 2.0, 0., .35, 0., alpha=1.)
    # The old rim-based rule would release this bubble while its centre was
    # below the water and leave a visibly empty gap at a slow stream velocity.
    near_surface = _Bubble(2, True, 0., WATER_SURFACE_Y - .2, 0., .35, 0., alpha=1.)
    at_breach = _Bubble(3, True, 7., WATER_SURFACE_Y + .01, 0., .35, 0., alpha=1.)
    sim._bubbles = [low, near_surface, at_breach]
    step(sim, controls(surface_scene=True))
    assert not low.leaving and low.alpha == 1.0
    assert not near_surface.leaving and near_surface.alpha == 1.0
    assert at_breach.leaving and 0.9 < at_breach.alpha < 1.0


def test_deep_scene_still_obeys_authored_end_without_surface_override():
    sim = ExtrudedBubbleSimulation(42)
    sim._filled = True
    sim._bubbles = [_Bubble(1, True, 0., 2.0, 0., .35, 0., alpha=1.)]
    step(sim, controls(surface_scene=False))
    assert sim._bubbles[0].leaving


def test_spread_rejection_does_not_clamp_edge_bubble_births_into_one_band():
    sim = ExtrudedBubbleSimulation(123)
    c = ExtrudedBubbleControls(
        stream_path=(1., -1., 0., 1., 1., 0.), bubble_spread=4.,
        columns=0., collision_scope='off',
    )
    offsets = []
    for _ in range(30):
        assert sim._spawn(False, c, (0., 1., 0.), anywhere=False)
        b = sim._bubbles.pop()  # independently sample valid births at the same anchored source
        offsets.append(b.x)
        assert -WORLD_HALF[0] <= b.x <= WORLD_HALF[0]
    assert min(offsets) < WORLD_HALF[0] - 2.
    assert len({round(v, 3) for v in offsets}) >= 25


def test_crowded_inlet_defers_identical_birth_instead_of_overlapping():
    sim = ExtrudedBubbleSimulation(8)
    c = ExtrudedBubbleControls(stream_path=(0., -1., 0., 0., 1., 0.),
                               bubble_spread=0., collision_scope='off')
    assert sim._spawn(True, c, (0., 1., 0.), anywhere=False)
    assert sim._spawn(True, c, (0., 1., 0.), anywhere=False) is False
    assert len(sim._bubbles) == 1


def test_frame_runtime_admits_surface_authority_without_preset_mutation():
    params = {entry.key: require_canonical_default('widgets.spotify_visualizer.' + entry.key)
              for entry in require_mode_settings('extruded_bubble').entries
              if entry.key.startswith('extruded_bubble_')}
    params['extruded_bubble_light_type'] = 'Sunlit Surface'
    assert controls_from_parameters(params).surface_scene
    params['extruded_bubble_light_type'] = 'Deep Light'
    assert not controls_from_parameters(params).surface_scene
