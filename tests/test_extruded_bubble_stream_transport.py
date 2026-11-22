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


@pytest.mark.parametrize('geometry', ('BEAM', 'SCENE'))
def test_bubbles_already_living_accelerate_with_the_music_as_newborns_do(geometry):
    """N5.6: identities born in a quiet passage speed up with a loud one and settle with idle, exactly as those born
    later (no birth-time speed, age or lifetime gate). Drift, sway and collisions stay on: they act across the stream
    and by contact, never along it for a free identity out of contact. Test-owned inputs, no preset values."""
    sim = ExtrudedBubbleSimulation(284)
    controls = ExtrudedBubbleControls(large_count=(3, 6), mid_count=(10, 20), emission_geometry=geometry,
                                      stream_path=(-1., .3, .1, 1., -.9, -.1), collision_scope='all')
    quiet, loud = MusicInput(1/60, True, .12, (), (.1, .08, .05)), MusicInput(1/60, True, .9, (), (.9, .7, .5))
    idle = MusicInput(1/60, False)
    for _ in range(240):
        sim.advance(quiet, controls)
    elders = {b.ident for b in sim._bubbles}
    speeds = {'elders': [], 'newborns': []}
    for phase, music in (('quiet', quiet), ('loud', loud), ('idle', idle)):
        for _ in range(180):
            old = {b.ident: (b.x, b.y, b.z) for b in sim._bubbles}
            frame = sim.advance(music, controls)
            for b in sim._bubbles:
                if b.ident not in old or b.cluster >= 0 or b.popping >= 0.0 or b.push != (0.0, 0.0, 0.0):
                    continue
                along = sum((p - q) * d for p, q, d in zip((b.x, b.y, b.z), old[b.ident], frame.stream)) * 60
                assert along == pytest.approx(frame.stream_speed, rel=1e-6, abs=1e-9), (phase, b.ident)
                speeds['elders' if b.ident in elders else 'newborns'].append((phase, along))
    def median(group, phase):
        values = sorted(v for p, v in speeds[group] if p == phase)
        return values[len(values) // 2]
    # The elders really are moved by the music: faster through the loud passage than the quiet one, slower again idle.
    assert median('elders', 'loud') > 2.0 * median('elders', 'quiet')
    assert median('elders', 'idle') < median('elders', 'loud')
    assert any(p == 'loud' for p, _ in speeds['newborns'])


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
