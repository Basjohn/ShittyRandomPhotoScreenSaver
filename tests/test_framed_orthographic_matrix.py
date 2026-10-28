"""Parallel projection preserves physical x/y magnification independently of depth."""
import math
import pytest
from core.settings.framed_camera import orthographic_matrix


def project(matrix,point):
    value=(*point,1.)
    clip=tuple(sum(matrix[col*4+row]*value[col] for col in range(4)) for row in range(4))
    return tuple(v/clip[3] for v in clip[:3])


def test_parallel_matrix_has_constant_scale_and_correct_near_far_depth():
    matrix=orthographic_matrix((6.,4.),.05,100.)
    for depth in (.05,1.,10.,100.):
        assert project(matrix,(3.,2.,-depth))[:2]==pytest.approx((.5,.5))
    assert project(matrix,(0.,0.,-.05))[2]==pytest.approx(-1.)
    assert project(matrix,(0.,0.,-100.))[2]==pytest.approx(1.)
    assert project(matrix,(6.,-4.,-10.))[:2]==pytest.approx((1.,-1.))


@pytest.mark.parametrize('extents,near,far',(((0.,1.),.05,100.),((1.,math.nan),.05,100.),
    ((1.,1.),1.,1.),((1.,1.),.05,math.inf)))
def test_invalid_parallel_aperture_or_clip_interval_is_rejected(extents,near,far):
    with pytest.raises(ValueError):orthographic_matrix(extents,near,far)


@pytest.mark.parametrize('size',((630,420),(1260,420),(630,900),(240,960)))
def test_eb_parallel_camera_preserves_eye_and_fixed_world_pixel_scale_during_resize(size):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import physical_camera,ORBIT_DISTANCE
    width,height=size;scale=1.4
    kwargs=dict(scale=scale,pan_x=.03,pan_y=-.02,fov_y_degrees=57.,position_offset=(.05,.01,.03))
    perspective=physical_camera(.14,-.06,width/height,**kwargs)
    parallel=physical_camera(.14,-.06,width/height,**kwargs,projection_kind='Orthographic',aperture_scale=height/420)
    assert parallel[:3]==perspective[:3]
    canonical=float(require_canonical_default('widgets.spotify_visualizer.extruded_bubble_camera_fov'))
    expected=ORBIT_DISTANCE/scale*math.tan(math.radians(canonical)/2)
    assert parallel[3][1]==pytest.approx(expected*height/420)
    assert 2*parallel[3][0]/width==pytest.approx(2*expected/420)
    assert 2*parallel[3][1]/height==pytest.approx(2*expected/420)
    assert parallel[4][15]==1. and perspective[4][15]==0.


def test_eb_parallel_magnification_uses_scene_scale_and_preserves_latent_perspective_fov():
    from rendering.gl_programs.extruded_bubble_scene import physical_camera
    a=physical_camera(0.,0.,1.5,projection_kind='Orthographic',fov_y_degrees=35.)
    b=physical_camera(0.,0.,1.5,projection_kind='Orthographic',fov_y_degrees=62.)
    zoom=physical_camera(0.,0.,1.5,projection_kind='Orthographic',scale=2.)
    assert a[3:]==b[3:]
    assert zoom[3]==pytest.approx(tuple(value/2 for value in a[3]))
    with pytest.raises(ValueError,match='Unknown framed projection'):
        physical_camera(0.,0.,1.5,projection_kind='unadmitted')
