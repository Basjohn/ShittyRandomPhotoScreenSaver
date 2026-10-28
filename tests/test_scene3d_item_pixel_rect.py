"""Float32 camera-stage boundaries are stable without erasing authored fractional coverage."""
import math
import struct
from types import SimpleNamespace
import pytest

from rendering.quick.scene3d.frame import item_pixel_rect


def f32(value):
    return struct.unpack('f',struct.pack('f',value))[0]


def frame(width,height,dpr,*,x=16.,y=16.,viewport_origin=(0,0)):
    window_width,window_height=width+32,height+32
    # Exact intended affine stage mapped through the same binary32 coefficients
    # Qt supplies to the production node, including translation cancellation.
    matrix=(2/window_width,0,0,0,0,2/window_height,0,0,0,0,1,0,
            -1+2*x/window_width,-1+2*y/window_height,0,1)
    return SimpleNamespace(logical_size=(width,height),matrix_values=tuple(map(f32,matrix)),
        viewport=(*viewport_origin,round(window_width*dpr),round(window_height*dpr)))


@pytest.mark.parametrize('size',((630.,420.),(1260.,420.),(630.,840.)))
@pytest.mark.parametrize('dpr',(1.,1.5,2.))
def test_integer_stage_and_dpr_bounds_survive_qt_float32_matrix(size,dpr):
    width,height=size
    assert item_pixel_rect(frame(width,height,dpr))==(round(16*dpr),round(16*dpr),round(width*dpr),round(height*dpr))


@pytest.mark.parametrize('dpr',(1.,1.5,2.))
def test_actual_fractional_coverage_is_still_outward_and_viewport_origin_preserved(dpr):
    width,height=630.125,420.75;x,y=16.25,16.5;origin=(17,23)
    f=frame(width,height,dpr,x=x,y=y,viewport_origin=origin)
    # Physical scaling uses the actual integer render viewport, as in production.
    sx=f.viewport[2]/(width+32);sy=f.viewport[3]/(height+32)
    left=math.floor(origin[0]+x*sx);right=math.ceil(origin[0]+(x+width)*sx)
    bottom=math.floor(origin[1]+y*sy);top=math.ceil(origin[1]+(y+height)*sy)
    assert item_pixel_rect(f)==(left,bottom,right-left,top-bottom)


def test_subpixel_edge_outside_transform_uncertainty_is_not_snapped():
    assert item_pixel_rect(frame(630.,420.,1.,x=16.001,y=16.001))==(16,16,631,421)


def test_negative_fractional_edge_keeps_viewport_clipping():
    f=frame(630.,420.,1.,x=-.25,y=-.5)
    assert item_pixel_rect(f)==(0,0,630,420)
