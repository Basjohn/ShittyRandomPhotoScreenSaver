"""Stream Speed transfers literally to existing/forming physical identities."""
import pytest

from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput,
)


@pytest.mark.parametrize('size', (.5, 1., 2.))
def test_both_classes_and_forming_actors_receive_the_shared_stream(size):
    sim = ExtrudedBubbleSimulation(282)
    controls = ExtrudedBubbleControls(large_count=(4,4), mid_count=(8,8),
        large_size=size, small_size=size, drift=(0.,0.), sway=0., collision_scope='off')
    music = MusicInput(1/60, True, .5, (), (.5,.3,.2))
    sim.advance(music,controls)
    assert {b.large for b in sim._bubbles} == {True,False}
    for b in sim._bubbles[::2]:
        b.alpha = 0.0  # same stable IDs, still forming
    for _ in range(30):
        old = {b.ident:(b.x,b.y,b.z) for b in sim._bubbles}
        frame = sim.advance(music,controls)
        for b in sim._bubbles:
            if b.ident in old:
                delta = tuple(p-q for p,q in zip((b.x,b.y,b.z),old[b.ident]))
                assert sum(v*d for v,d in zip(delta,frame.stream)) == pytest.approx(frame.stream_speed/60)


def test_fused_centre_receives_the_same_forward_transport():
    sim = ExtrudedBubbleSimulation(283)
    controls = ExtrudedBubbleControls(large_count=(2,2),mid_count=(0,0),
        drift=(0.,0.),sway=0.,collision_scope='off')
    music=MusicInput(1/60,True,.5,(),(.5,.3,.2))
    sim.advance(music,controls)
    a,b=sim._bubbles[:2]
    b.x,b.y,b.z=a.x+a.radius+b.radius,a.y,a.z
    assert sim._fuse(a,b)
    cluster=next(iter(sim._clusters.values()))
    previous=(cluster.x,cluster.y,cluster.z)
    frame=sim.advance(music,controls)
    delta=tuple(p-q for p,q in zip((cluster.x,cluster.y,cluster.z),previous))
    assert sum(v*d for v,d in zip(delta,frame.stream)) == pytest.approx(frame.stream_speed/60)
