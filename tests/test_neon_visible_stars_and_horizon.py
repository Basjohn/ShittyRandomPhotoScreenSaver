"""Selected event stars must inhabit the camera's actual visible sky."""
from pathlib import Path

from rendering.gl_programs.neon_starscape import _star_hash, starscape_beat_cells


ROOT = Path(__file__).resolve().parents[1]


def _project_cell(cell, tilt, turn, *, camera, fit, pose, aspect):
    """Project a panorama cell centre back through the camera (not selector UVs)."""
    import math
    lon,lat=(cell[0]+.5)/420.,(cell[1]+.5)/420.
    wx,wy,wz=math.sin(lon)*math.cos(lat),math.sin(lat),-math.cos(lon)*math.cos(lat)
    vx=wx*math.cos(turn)+wz*math.sin(turn)
    vz=-wx*math.sin(turn)+wz*math.cos(turn)
    sy=wy*math.cos(tilt)-vz*math.sin(tilt)
    forward=-wy*math.sin(tilt)-vz*math.cos(tilt)
    sx,sy=vx*camera/forward,sy*camera/forward
    scale,px,py=pose
    return (.5+px+sx*fit[0]*scale/aspect,
            .5+py+(fit[1]-.5-sy*fit[0])*scale)


def test_three_beat_stars_cover_upper_middle_lower_framed_sky_and_stay_spaced():
    import math
    params=dict(camera=3.5,fit=(.7,1.1),pose=(1.25,.06,-.02),aspect=1.8)
    tilt,turn=.30,.05
    positions=[]
    for event in range(16):
        hit=(.06,.12+event*.043,-.4-event*.017,.87)
        stars=starscape_beat_cells((hit,),tilt,turn,**params)
        assert len(stars)==3
        assert all(_star_hash(int(star[0]),int(star[1]))>=.99 for star in stars)
        assert stars==starscape_beat_cells((hit,),tilt,turn,**params)
        points=[_project_cell(star,tilt,turn,**params) for star in stars]
        assert all(.04<x<.96 and .005<y<.33 for x,y in points)
        # Actual bright cells can move slightly from the requested strata.
        # Each event still spans the sky; all bands and columns participate
        # over events rather than requiring a specific authored star.
        assert max(y for x,y in points)-min(y for x,y in points)>.09
        assert all(math.dist(a,b)>.14 for i,a in enumerate(points) for b in points[i+1:])
        positions.extend(points)
    assert all(any(abs(x-sector)<.10 and y>=.24 for x,y in positions)
               for sector in (.17,.5,.83))
    assert any(y<.10 for x,y in positions)
    assert any(.10<=y<.24 for x,y in positions)
    hit=(.06,.3,-.4,.87)
    stars=starscape_beat_cells((hit,),tilt,turn,**params)
    panned=starscape_beat_cells((hit,),tilt,turn,**{**params,'pose':(1.25,-.15,-.02)})
    assert panned != stars
    turned=starscape_beat_cells((hit,),tilt,.30,**params)
    assert turned != stars


def test_selection_tries_clear_candidates_around_the_body_and_caches_terrain_checks():
    import math
    from rendering.gl_programs.heightfield import heightfield_surface_bytes
    from rendering.gl_programs.neon_starscape import _body_clear, _star_ray, _terrain_clear
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_DEPTH
    params=dict(camera=3.5,fit=(.7,1.1),aspect=1.8)
    tilt,turn=.3,.05
    event=((.1,.25,-.63,1.),)
    plain=starscape_beat_cells(event,tilt,turn,**params)
    eye=(-3.5*math.cos(tilt)*math.sin(turn),3.5*math.sin(tilt),
         3.5*math.cos(tilt)*math.cos(turn)-.5*SHOCKWAVE_DEPTH)
    ray=_star_ray(plain[0])
    body=tuple(eye[i]+ray[i]*8 for i in range(3))+(.18,)
    assert not _body_clear(plain[0],eye,body)
    chosen=starscape_beat_cells(event,tilt,turn,body=body,**params)
    assert len(chosen)==3 and chosen[0][:2]!=plain[0][:2]
    assert all(_body_clear(cell,eye,body) for cell in chosen)
    data=heightfield_surface_bytes({'size':5,'heights':[.5]*25})
    terrain=(5,data,1.7,1.)
    assert not _terrain_clear((0,-210),(0.,1.,1.),terrain)
    assert _terrain_clear((0,210),(0.,1.,1.),terrain)
    hits=_terrain_clear.cache_info().hits
    assert _terrain_clear((0,210),(0.,1.,1.),terrain)
    assert _terrain_clear.cache_info().hits==hits+1


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
