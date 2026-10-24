"""Selected event stars must inhabit the camera's actual visible sky."""
from pathlib import Path

from rendering.gl_programs.neon_starscape import _star_hash, starscape_beat_cells


ROOT = Path(__file__).resolve().parents[1]


FIELD = (0.0, 0.0, 1800.0, 1000.0)


def _view(turn=.016, tilt=.05, **pose):
    """A shared-camera view looking almost level, so the upper card is sky."""
    from rendering.gl_programs.neon_lake_basin_program import orbit_view
    return orbit_view(turn, tilt, FIELD, **pose)


def _project_cell(cell, view):
    """Project a panorama cell centre back through the camera (not selector UVs)."""
    import math
    lon,lat=(cell[0]+.5)/420.,(cell[1]+.5)/420.
    ray=(math.sin(lon)*math.cos(lat),math.sin(lat),-math.cos(lon)*math.cos(lat))
    far=tuple(e+1e4*r for e,r in zip(view.eye,ray))
    assert view.depth(far)>0
    x,y=view.item_point(far)
    return x/FIELD[2], y/FIELD[3]


def test_three_beat_stars_cover_upper_middle_lower_framed_sky_and_stay_spaced():
    import math
    view=_view(scale=1.25,pan=(.06,-.02))
    positions=[]
    for event in range(16):
        hit=(.06,.12+event*.043,-.4-event*.017,.87)
        stars=starscape_beat_cells((hit,),view)
        assert len(stars)==3
        assert all(_star_hash(int(star[0]),int(star[1]))>=.99 for star in stars)
        assert stars==starscape_beat_cells((hit,),view)
        points=[_project_cell(star,view) for star in stars]
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
    stars=starscape_beat_cells((hit,),view)
    # The panorama is at infinity: moving the physical eye keeps the same sky; turning changes it.
    assert starscape_beat_cells((hit,),_view(scale=1.25,pan=(-.15,-.02)))==stars
    assert starscape_beat_cells((hit,),_view(turn=.1,scale=1.25,pan=(.06,-.02)))!=stars


def test_selection_tries_clear_candidates_around_the_body_and_caches_terrain_checks():
    from rendering.gl_programs.heightfield import heightfield_surface_bytes
    from rendering.gl_programs.neon_starscape import _body_clear, _star_ray, _terrain_clear
    view=_view()
    event=((.1,.25,-.63,1.),)
    plain=starscape_beat_cells(event,view)
    eye=view.eye
    ray=_star_ray(plain[0])
    body=tuple(eye[i]+ray[i]*8 for i in range(3))+(.18,)
    assert not _body_clear(plain[0],eye,body)
    chosen=starscape_beat_cells(event,view,body=body)
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
    # Beat stars are chosen through the frame's own physical camera view.
    assert 'mode_state.events, view,' in renderer
