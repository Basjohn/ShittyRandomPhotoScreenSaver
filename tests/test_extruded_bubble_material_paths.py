"""Falsifiers for bounded logical displacement transport, independent of pixels."""
import numpy as np
import pytest
from widgets.spotify_visualizer.extruded_bubble_material_paths import MaterialPaths
from widgets.spotify_visualizer.extruded_bubble_drift import DRIFT_DIRECTIONS, velocity

DIRECTION=(0.,1.,0.);ACROSS=(1.,0.,0.);DEPTH=(0.,0.,-1.)


def advance(paths, base, amount, speed=1., steps=120, start=0., kind='right'):
    spans=np.linalg.norm(base[:,-1]-base[:,0],axis=-1)
    for i in range(steps):
        result=paths.advance(base,spans,np.full(len(base),(start+(i+1)/60)*speed),np.full(len(base),speed),
            np.full(len(base),.7),1/60,kind=kind,phase=(start+i/60)*.8,direction=DIRECTION,
            across=ACROSS,depth_axis=DEPTH,origin=(0.,0.,0.),amount=amount)
    return result


def geometry(nodes, x=3., z=2., span=16.):
    return np.stack((np.full(nodes,x),np.linspace(-span/2,span/2,nodes),np.full(nodes,z)),axis=-1)[None,:,:]


@pytest.mark.parametrize('kind',DRIFT_DIRECTIONS)
def test_scalar_and_batched_field_are_the_same_authority(kind):
    points=np.array(((0.,0.,0.),(3.,1.,2.),(-4.,-2.,1.)))
    phases=np.array((.3,.7,1.2))
    batch=np.stack(np.broadcast_arrays(*velocity(kind,tuple(points.T),phases,.8,DIRECTION,ACROSS,DEPTH,
                                                (0.,0.,0.),-2.,ops=np)),axis=-1)
    scalar=[velocity(kind,p,phase,.8,DIRECTION,ACROSS,DEPTH,(0.,0.,0.),-2.) for p,phase in zip(points,phases)]
    assert batch==pytest.approx(np.asarray(scalar))


def test_zero_gain_is_dormant_and_later_zero_retains_visible_history():
    paths=MaterialPaths();base=geometry(paths.nodes)
    assert advance(paths,base,0.) is None
    active=advance(paths,base,1.,speed=0.).copy()
    assert np.linalg.norm(active[0,-1])>.1
    stopped=advance(paths,base,0.,speed=0.,start=2.)
    assert stopped==pytest.approx(active)  # no time×current amount remap or visible reset
    reversed_=advance(paths,base,-1.,speed=0.,start=4.)
    assert np.max(np.abs(reversed_))<.1


@pytest.mark.parametrize('gain',(-9.,9.,18.))
@pytest.mark.parametrize('kind',('right','swirl_cw','swish_across'))
def test_visible_material_converges_against_denser_transport(gain,kind):
    coarse=MaterialPaths(128);fine=MaterialPaths(512)
    a=advance(coarse,geometry(128),gain,kind=kind,steps=240)
    b=advance(fine,geometry(512),gain,kind=kind,steps=240)
    q=np.linspace(.15,.85,80)[None,:]  # excludes the physically fading inlet/end
    error=np.linalg.norm(coarse._sample(a,q,linear=True)-fine._sample(b,q,linear=True),axis=-1)
    assert np.max(error)*350./10.<1.  # projected pixel budget at depth10/reference focal350


def test_source_and_span_edit_preserve_retained_material_world_positions():
    paths=MaterialPaths();base=geometry(paths.nodes)
    before=advance(paths,base,1.,speed=0.).copy()+paths.base
    moved=base+np.array((.4,0.,-.2))
    after=paths.advance(moved,np.full(1,16.),np.zeros(1),np.zeros(1),np.full(1,.7),0.,
        kind='right',phase=2.,direction=DIRECTION,across=ACROSS,depth_axis=DEPTH,origin=(0,0,0),amount=0.)
    assert paths.base[:,2:]+after[:,2:]==pytest.approx(before[:,2:])  # fresh inlet itself is intentionally new


def test_nonzero_travel_span_and_direction_edit_keeps_progress_phase_and_sampled_centreline():
    paths=MaterialPaths();base=geometry(paths.nodes)
    advance(paths,base,9.,speed=2.,steps=240)
    q=np.array([[.2,.4,.6,.8]])
    before=paths._sample(paths.base+paths.displacement,q)
    new=geometry(paths.nodes,span=32.)
    new=new[..., [1,0,2]]+np.array((.4,.2,-.1))
    paths.advance(new,np.array([32.]),np.array([8.]),np.array([2.]),np.array([.7]),0.,kind='right',phase=3.2,
                  direction=(1,0,0),across=(0,-1,0),depth_axis=(0,0,-1),origin=(0,0,0),amount=0.)
    assert paths.phase_offset==pytest.approx((.25,))
    assert paths._sample(paths.base+paths.displacement,q)==pytest.approx(before,abs=1e-12)
    slot=.1
    assert (slot+8/32+paths.phase_offset[0])%1==pytest.approx((slot+8/16)%1)


@pytest.mark.parametrize('speed', (0.,.02,2.))
@pytest.mark.parametrize('span',(.2,36.))
@pytest.mark.parametrize('gain',(-9.,18.))
def test_near_axis_slow_stopped_and_short_long_tracks_remain_finite_and_continuous(speed,span,gain):
    paths=MaterialPaths();base=geometry(paths.nodes,x=.001,z=0.,span=span)
    a=advance(paths,base,gain,speed=speed,kind='swirl_cw',steps=120).copy()
    b=advance(paths,base,0.,speed=speed,kind='swirl_cw',steps=1,start=2.)
    assert np.isfinite(b).all()
    assert np.max(np.linalg.norm(b,axis=-1))<20.
    if speed==0:
        assert b==pytest.approx(a)  # zero gain never remaps/collapses existing swirl


@pytest.mark.parametrize('kind',DRIFT_DIRECTIONS)
@pytest.mark.parametrize('gain',(-9.,18.))
def test_advected_visible_material_tracks_direct_physical_reference(kind,gain):
    paths=MaterialPaths();base=geometry(paths.nodes)
    position=np.array((3.,-1.6,2.))  # q=.4; retained material, no inlet substitution
    for i in range(240):
        v=velocity(kind,position,.7,i/60*.8,DIRECTION,ACROSS,DEPTH,(0,0,0),gain)
        position+=(np.asarray(v)+np.asarray(DIRECTION))/60
    d=advance(paths,base,gain,kind=kind,steps=240)
    q=np.array([[.65]])
    observed=paths._sample(paths.base+d,q,linear=True)
    assert np.linalg.norm(observed[0,0]-position)<.03
