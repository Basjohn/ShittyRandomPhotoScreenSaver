"""The evidence probe must classify the same physical view that it renders."""
import numpy as np
import pytest

from tools.visualizer_replay.eb_simulation_support import simulation_module

simulation_module()
from rendering.gl_programs.extruded_bubble_scene import physical_camera
from tools.visualizer_replay.extruded_bubble_world_probe import camera_space, frustum_candidates, projected_sphere


@pytest.mark.parametrize("surface", (False, True))
def test_probe_subtracts_translated_eye_and_keeps_lens_constant_during_dolly(surface):
    parameters = dict(extruded_bubble_turn=.3, extruded_bubble_tilt=-.2,
                      extruded_bubble_scene_scale=2., extruded_bubble_scene_pan_x=.15,
                      extruded_bubble_scene_pan_y=-.1,
                      extruded_bubble_camera_position=(.5, 1., -.25),
                      extruded_bubble_camera_fov=37.,
                      extruded_bubble_camera_projection='Perspective',
                      extruded_bubble_light_type="Sunlit Surface" if surface else "Deep Light")
    basis, _, eye, tan, _ = physical_camera(.3, -.2, 16/9, 2., pan_x=.15,
        pan_y=-.1, position_offset=(.5, 1., -.25), fov_y_degrees=37., surface_bound=surface)
    # Six world units straight ahead of the actual eye must be centred at depth 6.
    point = np.asarray(eye) - 6. * np.asarray(basis[6:9])
    view, measured_eye, measured_tan = camera_space([point], parameters, (1600, 900))
    np.testing.assert_allclose(view[0], (0., 0., -6.), atol=1e-12)
    assert measured_eye == eye
    assert measured_tan == tan
    _, _, dolly_tan = camera_space([point], {**parameters, "extruded_bubble_scene_scale": .5}, (1600, 900))
    assert dolly_tan == measured_tan


@pytest.mark.parametrize("axis", (0, 1))
def test_probe_retains_spheres_grazing_sloped_frustum_planes(axis):
    tan = (.8, .5)
    radius, depth = .5, 6.
    margin = radius * np.sqrt(1. + tan[axis] ** 2)
    grazing = np.array([0., 0., -depth])
    grazing[axis] = tan[axis] * depth + (radius + margin) / 2.
    outside = grazing.copy()
    outside[axis] = tan[axis] * depth + margin + .01
    assert frustum_candidates(np.array([grazing, outside]), np.array([radius, radius]), tan).tolist() == [True, False]


def test_orthographic_probe_uses_parallel_frustum_planes_and_depth_independent_footprints():
    span=(6.,4.);size=(1200,800)
    near=projected_sphere((2.,1.,-6.),.5,span,size,projection_kind='Orthographic')
    far=projected_sphere((2.,1.,-60.),.5,span,size,projection_kind='Orthographic')
    assert near==far
    assert near['screen_xy']==pytest.approx((800.,300.))
    assert near['projected_radius_px']==50.
    positions=np.array([[6.49,0.,-6.],[6.51,0.,-6.],[6.49,0.,-60.],[6.51,0.,-60.]])
    assert frustum_candidates(positions,np.full(4,.5),span,projection_kind='Orthographic').tolist()==[True,False,True,False]
    assert projected_sphere((0.,0.,-.2),.5,span,size,projection_kind='Orthographic') is None


def test_perspective_forensic_estimate_keeps_depth_scaling():
    near=projected_sphere((0.,0.,-6.),.5,(1.,1.),(1200,800),projection_kind='Perspective')
    far=projected_sphere((0.,0.,-12.),.5,(1.,1.),(1200,800),projection_kind='Perspective')
    assert near['projected_radius_px']==pytest.approx(2*far['projected_radius_px'])
