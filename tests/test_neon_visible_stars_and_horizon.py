"""Selected event stars must inhabit the camera's actual visible sky."""
from pathlib import Path

from rendering.gl_programs.neon_starscape import _visible_star_cell, starscape_beat_cells


ROOT = Path(__file__).resolve().parents[1]


def test_three_beats_stars_follow_framed_camera_fit_pan_zoom_and_orbit():
    params=dict(camera=3.5,fit=(.7,1.1),pose=(1.25,.06,-.02),aspect=1.8)
    hit=(.06,.3,-.4,.87)
    tilt,turn=.30,.05
    stars=starscape_beat_cells((hit,),tilt,turn,**params)
    assert len(stars)==3
    seed=int(abs(hit[1]*8219.0+hit[2]*3191.0)*1871.0)
    for i,(lon,lat,strength,_) in enumerate(stars):
        x=(.20,.50,.80)[i]+(((seed>>(i*4))&15)-7.5)*.005
        y=.07+(((seed>>(i*3+1))&7))*.007
        wanted=_visible_star_cell(x,y,tilt,turn,**params)
        # Search only a nearby existing bright panorama cell (12-cell limit).
        assert abs(lon-wanted[0])<=12
        assert abs(lat-wanted[1])<=12
        assert strength>.1
    panned=starscape_beat_cells((hit,),tilt,turn,**{**params,'pose':(1.25,-.15,-.02)})
    assert panned != stars
    turned=starscape_beat_cells((hit,),tilt,.30,**params)
    assert turned != stars


def test_sky_alpha_is_continuous_while_real_terrain_controls_distant_silhouette():
    sky=(ROOT/'rendering/gl_programs/neon_celestial.py').read_text()
    terrain=(ROOT/'rendering/gl_programs/neon_lake_basin_program.py').read_text()
    renderer=(ROOT/'rendering/quick/visualizer/implementations/shockwave_grid.py').read_text()
    assert 'float alpha = clamp(uSkyColor.a * uSkyStrength, 0.0, 1.0);' in sky
    assert 'horizonAtmosphere' not in sky
    assert 'float broken = smoothstep(0.33, 0.66, gaps);' in sky
    assert 'vContourFade=basinDistanceFade(aUv);' in terrain
    assert 'vContourFade=max(' not in terrain
    assert 'NEON_SKYLINE_VERTEX_SOURCE' in terrain
    assert 'depth_prepared = body_enabled' in renderer
    assert 'camera=basin_camera(half_width, maximum)' in renderer
    assert 'fit=self._fit' in renderer
