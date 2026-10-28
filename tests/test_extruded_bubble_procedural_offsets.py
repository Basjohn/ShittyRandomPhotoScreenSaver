"""Stable-ID cloud drift: exact field transfer and explicit physical recycling."""
import numpy as np
import pytest
from widgets.spotify_visualizer.extruded_bubble_material_paths import ProceduralOffsets
from widgets.spotify_visualizer.extruded_bubble_drift import velocity,DRIFT_DIRECTIONS


def geometry(count=5,span=16.):
    starts=np.zeros((count,3));starts[:,0]=np.linspace(.001,4.,count);starts[:,1]=-span/2
    return starts,np.full(count,span),np.full(count,.4),.3,np.linspace(.1,2.,count)


def step(owner,g,travel,amount=18.,dt=1/60,key='same',direction=(0.,1.,0.),kind='swirl_cw'):
    return owner.advance(g,key,travel,1.,dt,kind=kind,phase=.7,direction=direction,across=(1.,0.,0.),
                         depth_axis=(0.,0.,-1.),origin=(0,0,0),amount=amount)


@pytest.mark.parametrize('kind',DRIFT_DIRECTIONS)
@pytest.mark.parametrize('amount',(-9.,18.))
def test_each_actual_id_receives_the_canonical_scalar_field_without_grid_error(kind,amount):
    owner=ProceduralOffsets();g=geometry();step(owner,g,0.,dt=0.,kind=kind)
    previous=owner.displacement.copy()
    packed=step(owner,g,1/60,amount=amount,kind=kind)
    expected=np.array([velocity(kind,p,phase,.7,(0,1,0),(1,0,0),(0,0,-1),(0,0,0),amount)
                       for p,phase in zip(owner.previous_base+previous,g[-1])])/60
    assert owner.displacement==pytest.approx(previous+expected)
    assert packed[:,:3]==pytest.approx(owner.displacement,abs=1e-7)


def test_zero_gain_preserves_current_offsets_and_span_direction_edits_preserve_world_positions():
    owner=ProceduralOffsets();g=geometry()
    for i in range(120):step(owner,g,(i+1)/60)
    before=owner.previous_base+owner.displacement
    new=list(geometry(span=32.));new[0]=new[0][:,[1,0,2]]+(.4,.2,-.1)
    step(owner,tuple(new),2.,amount=0.,dt=0.,key='edited',direction=(1.,0.,0.))
    assert owner.previous_base+owner.displacement==pytest.approx(before,abs=1e-12)
    assert np.all((owner.phase_offset>=0.)&(owner.phase_offset<1.))
    unchanged=owner.displacement.copy()
    step(owner,tuple(new),2.,amount=0.,dt=0.,key='edited',direction=(1.,0.,0.))
    assert owner.displacement==pytest.approx(unchanged)


def test_actual_inlet_recycle_hides_one_sample_instead_of_resetting_visible_offsets():
    owner=ProceduralOffsets();g=list(geometry(count=1,span=1.));g[2]=np.array([.99]);g[3]=1.;g=tuple(g)
    initial=step(owner,g,0.,amount=18.)
    assert initial[0,3]>=0.
    recycled=step(owner,g,.02,amount=18.,dt=.02)
    assert recycled[0,3]<0.
    assert (-1.<recycled[0,3]<0.)
    resumed=step(owner,g,.04,amount=0.,dt=.02)
    assert resumed[0,3]>=0.
    assert np.isfinite(resumed).all()


def test_growing_count_preserves_existing_material_id_histories():
    owner=ProceduralOffsets();g=geometry(3)
    for i in range(60):step(owner,g,(i+1)/60)
    before=owner.previous_base+owner.displacement
    new=list(geometry(5));new[0][:3]=g[0];new[-1][:3]=g[-1]
    step(owner,tuple(new),1.,amount=0.,dt=0.,key='more')
    assert (owner.previous_base+owner.displacement)[:3]==pytest.approx(before)
