"""The lab optical reduction must follow admitted history, never the camera or a second path."""
from core.ribbon_packet import KNOT_ROWS
from dataclasses import replace

import numpy as np
import pytest

from core.ribbon_ring import RibbonRing
from tools.labs.ribbon_lighting import ribbon_lights


def test_illumination_conserves_segment_strength_after_wrap_and_world_rebase():
    ring=RibbonRing(1,capacity=4,colours=(1.,.5,0.,1.))
    for i in range(20):
        ring.append(float(i),((100.+i,2.,3.),),.5,emission=2.)
    packet=ring.packet()
    positions,flux=ribbon_lights(packet,(0.,0.,0.),(19.,0.,3.,0.))
    np.testing.assert_allclose(flux.sum(axis=0),(6.,3.,0.)) # three retained one-unit segments
    assert np.all((positions[:,0]>=116.)&(positions[:,0]<=119.))
    moved,moved_flux=ribbon_lights(packet,(4.,-1.,2.),(19.,0.,3.,0.))
    np.testing.assert_allclose(moved[:,:3]-positions[:,:3],np.broadcast_to((4.,-1.,2.),moved[:,:3].shape))
    np.testing.assert_array_equal(moved[:,3],positions[:,3])
    np.testing.assert_array_equal(moved_flux,flux)
    rebased=replace(packet,coordinate_origin=packet.coordinate_origin+100.)
    shifted,shifted_flux=ribbon_lights(rebased,(0.,0.,0.),(119.,0.,3.,0.))
    np.testing.assert_allclose(shifted,positions)
    np.testing.assert_allclose(shifted_flux,flux)
    faded_pos,faded_flux=ribbon_lights(packet,(0.,0.,0.),(30.,1.,3.,1.))
    assert faded_pos.shape==(0,4) and faded_flux.shape==(0,3)


def test_reduction_never_bridges_a_break_or_silently_truncates_sources():
    ring=RibbonRing(1,colours=(1.,1.,1.,1.))
    for i in range(8):
        ring.append(float(i),((float(i),2.,0.),),.5)
    packet=ring.packet()
    data=np.frombuffer(packet.payload,np.float32).copy().reshape(-1,4)
    data[4+KNOT_ROWS*4+1,3]=1. # knot four starts a separate strip
    broken=replace(packet,payload=data.tobytes())
    _,flux=ribbon_lights(broken,(0.,0.,0.),(7.,0.,7.,0.),bin_seconds=10.)
    assert len(flux)==2
    np.testing.assert_allclose(flux.sum(axis=0),(6.,6.,6.))
    for i in range(8,110):
        ring.append(float(i)/2.+4. if i>=8 else float(i),((float(i),2.,0.),),.5)
    with pytest.raises(ValueError,match='exceeds'):
        ribbon_lights(ring.packet(),(0.,0.,0.),(60.,0.,60.,0.),bin_seconds=.1)
