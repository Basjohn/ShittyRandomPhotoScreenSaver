"""Physical EB seams: world births, reacted contacts and continuous lifetime/union geometry."""
import math
import random
from dataclasses import replace

import pytest

from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_HALF, WORLD_UNIT, upstream_source, stream_basis
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput, _Bubble, stream_vector,
)


def controlled(*positions, collision=(1., 0., 0.), strength=(0., 0.)):
    sim = ExtrudedBubbleSimulation(71)
    sim._filled = True
    sim._bubbles = [_Bubble(i + 1, True, *point, 1., 0., alpha=1.) for i, point in enumerate(positions)]
    sim._next_ident = len(positions) + 1
    controls = ExtrudedBubbleControls(large_count=(len(positions),) * 2, mid_count=(0, 0),
        collision=collision, breathing=strength, stream_speed=(0, 0), drift=(0, 0), sway=0)
    return sim, controls


@pytest.mark.parametrize('direction', [stream_vector(0, 0), stream_vector(90, 0), stream_vector(35, 40)])
def test_upstream_births_use_fixed_physical_faces_and_inflow_area_weights(direction):
    rng = random.Random(32)
    counts = [0, 0, 0]
    for _ in range(3000):
        p = upstream_source(rng, direction)
        assert all(abs(v) <= h for v, h in zip(p, WORLD_HALF))
        face = [i for i in range(3) if abs(abs(p[i]) - WORLD_HALF[i]) < 1e-8]
        assert len(face) == 1
        i = face[0]
        assert p[i] * direction[i] < 0
        counts[i] += 1
    weights = [abs(direction[i]) * WORLD_HALF[(i + 1) % 3] * WORLD_HALF[(i + 2) % 3] for i in range(3)]
    assert [v / 3000 for v in counts] == pytest.approx([v / sum(weights) for v in weights], abs=.025)


@pytest.mark.parametrize('height',[0.,40.,82.,88.,89.999,90.])
def test_world_transverse_axes_are_orthonormal_even_for_oblique_depth_streams(height):
    direction=stream_vector(35.,height)
    across,depth=stream_basis(direction)
    axes=(direction,across,depth)
    for i,a in enumerate(axes):
        for j,b in enumerate(axes):
            assert sum(x*y for x,y in zip(a,b))==pytest.approx(1. if i==j else 0.,abs=1e-9)


def test_production_column_births_reproject_to_the_actual_upstream_boundary():
    sim=ExtrudedBubbleSimulation(89)
    controls=ExtrudedBubbleControls(columns=1.)
    direction=stream_vector(35.,40.)
    for _ in range(300):
        sim._spawn(True,controls,direction,anywhere=False)
        b=sim._bubbles[-1]
        entry=tuple(p+d*.08*WORLD_UNIT for p,d in zip((b.x,b.y,b.z),direction))
        assert all(abs(v)<=h+1e-8 for v,h in zip(entry,WORLD_HALF))
        assert any(abs(abs(v)-h)<1e-8 and v*d<0 for v,h,d in zip(entry,WORLD_HALF,direction))


def test_expanded_contact_uses_snapshot_radius_across_old_grid_cells_and_does_not_snap_on_fusion():
    sim, controls = controlled((-3., 0., -8.), (3., 0., -8.), strength=(1., 1.))
    sim._body_big_envelope = .8
    before = [(b.x, b.y, b.z) for b in sim._bubbles]
    state = sim.advance(MusicInput(0., True), controls)
    assert state.bubbles[3] > 3.  # actual reacted surfaces meet, nominal radii do not
    assert state.clusters[0] == 2.
    assert [(b.x, b.y, b.z) for b in sim._bubbles] == before
    assert all(b.current_radius == state.bubbles[i * 8 + 3] for i, b in enumerate(sim._bubbles))
    admitted_ratio = 6. / (2 * state.bubbles[3])
    for _ in range(600):
        previous = [(b.x, b.y, b.z) for b in sim._bubbles]
        state = sim.advance(MusicInput(1/120, False), controls)
        a, b = sim._bubbles
        ratio = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) / (a.current_radius + b.current_radius)
        assert ratio == pytest.approx(admitted_ratio)  # connected throughout deep contraction
        assert max(math.dist(old, (b.x, b.y, b.z)) for old, b in zip(previous, sim._bubbles)) < .025


def test_tiny_reacted_surfaces_do_not_collide_just_because_nominal_radii_overlap():
    sim, controls = controlled((-.5, 0., -8.), (.5, 0., -8.), strength=(.15, .6))
    state = sim.advance(MusicInput(0., False), controls)
    assert state.bubbles[3] == pytest.approx(.13)
    assert not state.clusters


def test_quiet_small_contacts_use_the_larger_resting_shell():
    sim,c = controlled((-.5,0.,-8.),(.5,0.,-8.),collision=(0.,0.,1.))
    for bubble in sim._bubbles:
        bubble.large = False
    c = replace(c,large_count=(0,0),mid_count=(2,2),small_pulse=(.15,.8))
    sim.advance(MusicInput(1/90,False),c)
    a,b = sim._bubbles
    assert a.current_radius == pytest.approx(.7825)
    assert b.current_radius == pytest.approx(.7825)
    assert a.x < -.5 and b.x > .5


def test_third_member_keeps_existing_union_edges_and_admitted_positions():
    sim, controls = controlled((0., 0., -8.), (1.8, 0., -8.))
    sim.advance(MusicInput(0., False), controls)
    cluster = next(iter(sim._clusters.values()))
    edge = cluster.edges[0]
    sim._bubbles.append(_Bubble(3, True, 3.6, 0., -8., 1., 0., alpha=1.))
    before = [(b.x, b.y, b.z) for b in sim._bubbles]
    controls = replace(controls, large_count=(3, 3))
    sim.advance(MusicInput(0., False), controls)
    cluster = next(iter(sim._clusters.values()))
    assert len(cluster.members) == 3 and edge in cluster.edges
    assert [(b.x, b.y, b.z) for b in sim._bubbles] == before
    for _ in range(30):
        sim.advance(MusicInput(1/120, False), controls)
    assert all(math.dist(old, (b.x,b.y,b.z)) < 1e-10 for old,b in zip(before,sim._bubbles))


def test_bounce_is_gradual_and_continues_after_event_choice():
    sim, controls = controlled((-.5, 0., -8.), (.5, 0., -8.), collision=(0., 0., 1.))
    before = [b.x for b in sim._bubbles]
    sim.advance(MusicInput(1/120, False), controls)
    after = [b.x for b in sim._bubbles]
    assert 0 < max(abs(a-b) for a, b in zip(after, before)) < .01
    for _ in range(120):
        sim.advance(MusicInput(1/120, False), controls)
    assert sim._bubbles[1].x - sim._bubbles[0].x > after[1] - after[0] + .5


def test_contact_bounces_an_existing_cluster_as_one_without_splitting_members():
    sim, controls = controlled((-.5,0.,-8.),(.5,0.,-8.))
    sim.advance(MusicInput(0.,False),controls)
    sim._bubbles.append(_Bubble(3,True,1.9,0.,-8.,1.,0.,alpha=1.))
    before = [b.x for b in sim._bubbles]
    sim.advance(MusicInput(.01,False),replace(controls,large_count=(3,3),collision=(0.,0.,1.)))
    delta = [b.x-old for b,old in zip(sim._bubbles,before)]
    assert delta[0] == pytest.approx(delta[1]) and delta[0] < 0 < delta[2]


def test_pop_is_gentle_opacity_only_and_does_not_brighten_a_partly_faded_shell():
    sim, controls = controlled((0., 0., -8.), collision=(0., 0., 0.))
    b = sim._bubbles[0]
    b.alpha = b.pop_alpha = .4
    b.popping = 0.
    states = [sim.advance(MusicInput(1/120, False), controls) for _ in range(144)]
    assert len(states[-1].bubbles) == 8
    alphas = [s.bubbles[4] for s in states]
    assert all(a >= b for a, b in zip(alphas, alphas[1:]))
    assert alphas[-1] == pytest.approx(.2)
    assert min(s.bubbles[3] for s in states) == max(s.bubbles[3] for s in states) == 1.


@pytest.mark.parametrize('victim',[0,1,2])
def test_pruning_each_member_preserves_survivor_positions_and_only_connected_unions(victim):
    sim,controls=controlled((-1.8,0.,-8.),(0.,0.,-8.),(1.8,0.,-8.))
    sim.advance(MusicInput(0.,False),controls)
    assert len(next(iter(sim._clusters.values())).members)==3
    before={b.ident:(b.x,b.y,b.z) for b in sim._bubbles}
    sim._bubbles[victim].popping=2.4
    sim.advance(MusicInput(0.,False),controls)
    sim.advance(MusicInput(.01,False),controls)
    for b in sim._bubbles:
        if b.ident in before:assert (b.x,b.y,b.z)==pytest.approx(before[b.ident])
    assert bool(sim._clusters)==(victim!=1)
