"""A resized window observes one fixed world through the same authored lens."""
import math
import pytest

from rendering.gl_programs.extruded_bubble_scene import physical_camera
from rendering.gl_programs.neon_lake_basin_program import basin_view
from tests._visualizer_frozen_settings import frozen_visualizer_settings


@pytest.mark.parametrize('size', ((630,420),(1260,420),(315,420),(630,840),(630,210),(240,960),(960,240)))
def test_edge_resize_keeps_eye_pixel_aspect_and_focal_scale(size):
    width,height=size
    aspect=width/height
    aperture=height/420
    base=physical_camera(.13,.04,1.5,fov_y_degrees=52)
    view=physical_camera(.13,.04,aspect,fov_y_degrees=52,aperture_scale=aperture)
    assert view[:3]==base[:3]  # axes and admitted eye, no automatic dolly/fit
    assert view[3][0]/view[3][1]==pytest.approx(aspect)
    fx,fy=width/(2*view[3][0]),height/(2*view[3][1])
    assert fx==pytest.approx(fy)
    assert fy==pytest.approx(420/(2*math.tan(math.radians(52)/2)))
    params=frozen_visualizer_settings('shockwave_grid')
    original=basin_view(params,(0,0,630,420))
    resized=basin_view(params,(0,0,width,height),aperture_scale=aperture)
    assert resized.eye==original.eye
    assert (resized.right,resized.up,resized.back)==(original.right,original.up,original.back)
    for point in ((0,0,-1),(.6,.2,-2),(-.7,.3,-.8)):
        ox,oy=original.item_point(point);rx,ry=resized.item_point(point)
        assert rx-width/2==pytest.approx(ox-315)
        assert ry-height/2==pytest.approx(oy-210)


def test_uniform_presentation_scale_does_not_change_aperture():
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
    # This test only needs the immutable geometry leaves, not a window or renderer.
    from types import SimpleNamespace
    assert framed_aperture_scale(SimpleNamespace(viewport_extent=(420.,280.),baseline_viewport_size=(420.,280.)))==1.
    assert framed_aperture_scale(SimpleNamespace(viewport_extent=(420.,560.),baseline_viewport_size=(420.,280.)))==2.


def test_real_neon_inner_field_preserves_landmarks_with_fixed_chrome():
    from types import SimpleNamespace
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation, framed_aperture_scale
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    params=frozen_visualizer_settings('shockwave_grid')
    observations=[]
    for height in (280,560,140):
        p=resolve_visualizer_presentation(policy=get_visualizer_presentation_policy('shockwave_grid'),
            display_size=(2000,2000),viewport_extent=(420,height),uniform_visual_scale=1.5,
            border_width=2.,corner_radius=8.,content_inset=3.,background_color=(0,0,0,0),border_color=(0,0,0,0),
            shadow_enabled=False,shadow_color=(0,0,0,0),shadow_blur=0.,shadow_offset=(0.,0.),
            shadow_spread=0.,shadow_extensions=(0.,)*4)
        frame=QuickVisualizerRenderFrame(SimpleNamespace(presentation=p),(0,0,630,round(height*1.5)),
            (630.,height*1.5),(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.),1)
        x,y,w,h=frame.logical_content_rect
        view=basin_view(params,frame.logical_content_rect,aperture_scale=framed_aperture_scale(p,content=True))
        px,py=view.item_point((.6,.2,-2))
        observations.append((px-x-w/2,py-y-h/2))
    assert observations[1]==pytest.approx(observations[0])
    assert observations[2]==pytest.approx(observations[0])
