"""SCENE emission gates. Qt-free; GPU visual/performance acceptance is separate."""
from __future__ import annotations

from math import sqrt
from pathlib import Path
import random

from tools.visualizer_replay.eb_simulation_support import simulation_module
simulation_module()
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings
from widgets.spotify_visualizer.extruded_bubble_geometry import (
    WORLD_CENTER, WORLD_HALF, scene_source_face_weights, upstream_source, scene_track_length, scene_mean_passage,
)
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput, MAX_BUBBLES,
)
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters



def _controls(source=(0., -1., 0.), end=(0., 1., 0.), mode='SCENE'):
    return ExtrudedBubbleControls(
        large_count=(12., 12.), mid_count=(35., 35.),
        stream_path=tuple(source) + tuple(end), emission_geometry=mode,
        collision_scope='off', stream_speed=(0.06, .06), drift=(0., 0.), sway=0.,
    )


def _start(controls, seed=53):
    sim = ExtrudedBubbleSimulation(seed)
    sim.advance(MusicInput(1. / 90., True, body_bands=(.5, .4, .3)), controls)
    return sim


def test_emission_geometry_accepts_explicit_modes_and_legacy_missing_field():
    spec = require_mode_settings('extruded_bubble')
    choice = spec.control('extruded_bubble_emission_geometry')
    assert choice.choices == ('BEAM', 'SCENE')
    # Never assert the mutable authored canonical selection or any preset choice.
    params = {entry.key: require_canonical_default('widgets.spotify_visualizer.' + entry.key)
              for entry in spec.entries if entry.key.startswith('extruded_bubble_')}
    params.pop('extruded_bubble_emission_geometry')
    # Old saved objects with no new field are admitted by the runtime's legacy
    # fallback, regardless of what the user currently authors in Settings.
    assert controls_from_parameters(params).emission_geometry == ExtrudedBubbleControls().emission_geometry
    assert 'extruded_bubble_emission_geometry' not in params
    params['extruded_bubble_emission_geometry'] = 'SCENE'
    assert controls_from_parameters(params).emission_geometry == 'SCENE'


def test_beam_retains_no_mature_interior_on_activation_while_scene_is_preaged():
    assert not _start(_controls(mode='BEAM'))._bubbles
    sim = _start(_controls(mode='SCENE'))
    assert 10 <= len(sim._bubbles) <= 47
    assert len(sim._bubbles) <= MAX_BUBBLES
    assert all(-h <= p <= h for b in sim._bubbles for p, h in zip((b.x,b.y,b.z), WORLD_HALF))
    assert len(set(b.ident for b in sim._bubbles)) == len(sim._bubbles)


def test_floor_scene_emits_over_whole_physical_floor_and_only_floor():
    direction=(0., 1., 0.)
    faces = scene_source_face_weights((0., -1., 0.), direction)
    assert faces[1] > 0 and faces[0] == faces[2] == 0
    rng=random.Random(91)
    samples=[upstream_source(rng, direction, faces) for _ in range(180)]
    assert all(abs(p[1] + WORLD_HALF[1]) < 1e-9 for p in samples)
    assert min(p[0] for p in samples) < -15 and max(p[0] for p in samples) > 15
    assert min(p[2] for p in samples) < -15 and max(p[2] for p in samples) > 15


def test_scene_passage_matches_actual_inlet_tracks_instead_of_longest_box_axis():
    import math
    import pytest
    assert scene_mean_passage((0.,1.,0.)) == 16.
    assert scene_mean_passage((1.,0.,0.)) == 36.
    for raw,source in (((1.,1.,0.),(0.,-1.,0.)),((1.,1.,1.),(-1.,-1.,-1.)),
                       ((-.2,1.,.3),(0.,-1.,0.))):
        direction=tuple(d/math.sqrt(sum(v*v for v in raw)) for d in raw)
        faces=scene_source_face_weights(source,direction)
        rng=random.Random(78)
        tracks=[scene_track_length(upstream_source(rng,direction,faces),direction) for _ in range(12000)]
        assert scene_mean_passage(direction,faces) == pytest.approx(sum(tracks)/len(tracks),rel=.015)


def test_vertical_scene_throughput_can_sustain_authored_occupancy_without_bursts():
    from statistics import mean
    controls=ExtrudedBubbleControls(large_count=(0.,0.),mid_count=(40.,40.),
        stream_path=(0.,-1.,0.,0.,1.,0.),emission_geometry='SCENE',
        stream_speed=(.25,.25),drift=(0.,0.),sway=0.,collision_scope='off',
        small_pulse=(0.,0.),small_size=.5,surface_scene=True)
    sim=ExtrudedBubbleSimulation(73)
    counts=[];previous=set()
    for step in range(1800):
        sim.advance(MusicInput(.1,True,body_bands=(.5,.4,.3)),controls)
        current={b.ident for b in sim._bubbles}
        assert len(current)<=40
        if step:assert len(current-previous)<=1
        previous=current
        if step>=600:counts.append(len(current))
    assert mean(counts)>=.95*40  # low-crowding steady flow stays close to its requested occupancy


def test_corner_source_uses_each_physically_adjoining_inflow_face():
    d=(1./sqrt(2.), 1./sqrt(2.), 0.)
    weights=scene_source_face_weights((-1.,-1.,0.),d)
    assert weights[0]>0 and weights[1]>0 and weights[2]==0
    rng=random.Random(97)
    samples=[upstream_source(rng,d,weights) for _ in range(160)]
    assert any(abs(p[0]+WORLD_HALF[0])<1e-9 for p in samples)
    assert any(abs(p[1]+WORLD_HALF[1])<1e-9 for p in samples)
    assert all(abs(p[0]+WORLD_HALF[0])<1e-9 or abs(p[1]+WORLD_HALF[1])<1e-9 for p in samples)


def test_scene_track_exits_real_box_without_aiming_at_endpoint_or_camera():
    d=(0.,1.,0.)
    p=(-13.,-WORLD_HALF[1],9.)
    travel=scene_track_length(p,d)
    assert abs(travel-2*WORLD_HALF[1])<1e-9
    exit_p=tuple(a+b*travel for a,b in zip(p,d))
    assert exit_p == (-13.,WORLD_HALF[1],9.)
    assert not any(abs(p-c)>h for p,c,h in zip(exit_p,WORLD_CENTER,WORLD_HALF))


def test_mature_scene_deterministic_with_no_camera_or_alternate_clock():
    c=_controls()
    a=_start(c,seed=35)
    b=_start(c,seed=35)
    assert [(x.ident,x.x,x.y,x.z,x.alpha) for x in a._bubbles] == [
        (x.ident,x.x,x.y,x.z,x.alpha) for x in b._bubbles]
    before={x.ident for x in a._bubbles}
    for _ in range(90):
        a.advance(MusicInput(1./90.,True,body_bands=(0.7,0.1,0.4)),c)
    assert before.issubset({x.ident for x in a._bubbles})


def test_scene_new_bubbles_admit_at_actual_upstream_face_not_interior():
    c=_controls()
    sim=ExtrudedBubbleSimulation(5)
    assert sim._spawn(False,c,(0.,1.,0.),anywhere=False)
    b=sim._bubbles[0]
    assert b.y <= -WORLD_HALF[1]  # small pre-boundary fade zone
    assert abs(b.x) <= WORLD_HALF[0] and abs(b.z)<=WORLD_HALF[2]


def test_gpu_bubble_chain_snow_and_speck_use_same_scene_uniform_contract():
    source = (Path(__file__).resolve().parents[1] / 'rendering/gl_programs/extruded_bubble_program.py').read_text(encoding='utf-8')
    assert source.count('uniform int uSceneEmission;') == 2
    assert source.count('uniform vec3 uSceneFaces;') == 2
    assert source.count('sceneInlet(') == 4
    assert source.count('uSceneEmission == 1') >= 4
    assert 'Stable emitter records survive' in source  # attached fizz still follows its parent
