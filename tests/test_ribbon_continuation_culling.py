"""Native pixel equality and draw work for opt-in monotone-cloth culling."""
import numpy as np
import pytest

from core.ribbon_continuation import continuation_bounds,frustum_axial_span
from core.ribbon_ring import RibbonRing
from core.ribbon_style import RibbonMaterial
from core.waveform_ribbon_scene import FLOOR_CONTACT
from rendering.gl_programs.reflection import mirror_view
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera


def full_packet():
    ring=RibbonRing(3,colours=[(.1,.5,.9,1.),(.5,.1,.9,1.),(.1,.9,.5,1.)])
    for i in range(256):
        x=-52.+i*(68./255)
        ring.append(i/6,[(x,2.+np.sin(x*.6+j),.65*(j-1)) for j in range(3)],
                    [.6,.5,.4],twists=.3*np.sin(x*.4))
    return ring.packet()


@pytest.mark.qt
@pytest.mark.parametrize('aspect,turn,position', (
    (1.5,0.,(0.,0.,0.)),
    (.3,0.,(0.,0.,0.)),
    (12.,.25,(1.,0.,1.)),
    (1.5,-.5,(1.,0.,0.)),
    (1.5,.5,(-1.,0.,0.)),
))
def test_culled_draws_keep_exact_old_pixels_and_vertex_ids(qt_app,monkeypatch,aspect,turn,position):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d import ribbon as owner
    packet=full_packet();target=OffscreenRenderTarget(192,144);primitive=owner.RibbonPrimitive()
    material=RibbonMaterial(cross_curve=.7)
    view,projection,_,_=physical_view(camera(turn=turn,camera_position=position),aspect)
    reflected=mirror_view(view,0.)
    transverse=continuation_bounds(packet,np.zeros(3),material.cross_curve)
    a,b=(frustum_axial_span(projection@v,transverse) for v in (view,reflected))
    span=(min(a[0],b[0]),max(a[1],b[1]),2048)
    ranges=owner._continuation_draw_ranges;draw=gl.glDrawArraysInstanced;calls=[]
    def recorded(mode,first,count,instances):
        calls.append((first,count,instances));return draw(mode,first,count,instances)
    def unculled(packet,continuation,frame_x,cross_divisions):
        body,limits,extensions=ranges(packet,continuation,frame_x,cross_divisions)
        return (0,packet.vertices*cross_divisions),limits,[
            (side,divisions,0,divisions*6*cross_divisions) for side,divisions,_,_ in extensions]
    def render(v):
        target.bind();gl.glEnable(gl.GL_DEPTH_TEST);gl.glDepthFunc(gl.GL_LESS);gl.glDepthMask(gl.GL_TRUE)
        calls.clear()
        primitive.draw(packet,tuple((projection@v).flatten(order='F')),material=material,
                       sweep_axis=(1.,0.,0.),floor=FLOOR_CONTACT,continuation=span)
        return target.read_rgba(),tuple(calls)
    monkeypatch.setattr(gl,'glDrawArraysInstanced',recorded)
    try:
        for v in (view,reflected):
            actual,culled=render(v)
            with monkeypatch.context() as change:
                change.setattr(owner,'_continuation_draw_ranges',unculled)
                expected,baseline=render(v)
            np.testing.assert_array_equal(actual,expected)
            new_vertices=sum(count*instances for first,count,instances in culled)
            old_vertices=sum(count*instances for first,count,instances in baseline)
            assert new_vertices<=old_vertices
            assert new_vertices<old_vertices or aspect==12.
            # Report actual submitted work, not an estimated replacement population.
            print(f'aspect={aspect} turn={turn} mirror={v is reflected}: '
                  f'{old_vertices}->{new_vertices} vertices; {baseline}->{culled}')
    finally:
        primitive.release();target.close()


def test_ring_wrap_culling_uses_original_station_indices():
    from rendering.quick.scene3d.ribbon import _continuation_draw_ranges
    ring=RibbonRing(1,capacity=32)
    for i in range(100):ring.append(i/6,[(i*.25,2.,0.)],[.5])
    packet=ring.packet()
    rows=np.frombuffer(packet.payload,np.float32).reshape(-1,4)
    assert rows[1,1]!=0  # chronological order straddles the physical ring end
    frame_x=packet.world_origin[0]
    body,span,extensions=_continuation_draw_ranges(packet,(20.,22.,2048),frame_x,8)
    assert body[0]>0 and body[1]>0 and not extensions
    assert body[0]%(8*6*8)==0 and body[1]%(8*6*8)==0
