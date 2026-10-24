"""Neon terrain-owned horizon and star admission contracts.

No mutable presets, environment variables, Qt renderer, or GL context required.
"""
from pathlib import Path

from rendering.gl_programs.neon_starscape import (
    STARSCAPE_BEAT_MIN_STRENGTH,
    STARSCAPE_BEAT_RELEASE,
    starscape_beat_cells,
)

ROOT = Path(__file__).resolve().parents[1]


def _framed_stars(events, tilt, turn):
    # Old orbit radians -> the shared framed camera's settings units (tilt quarter turns, turn half turns).
    from math import pi
    from rendering.gl_programs.neon_lake_basin_program import orbit_view
    return starscape_beat_cells(events, orbit_view(turn / pi, tilt / (pi / 2)))


def test_starscape_entry_floor_is_exactly_thirtysix_percent_lower_than_035():
    assert abs(STARSCAPE_BEAT_MIN_STRENGTH - 0.224) < 1e-12
    below = ((0.2, 0.2, -0.5, STARSCAPE_BEAT_MIN_STRENGTH - 0.001),)
    at = ((0.2, 0.2, -0.5, STARSCAPE_BEAT_MIN_STRENGTH),)
    assert _framed_stars(below, 0.3, 0.1) == ()
    assert len(_framed_stars(at, 0.3, 0.1)) == 3
    assert len(_framed_stars(((STARSCAPE_BEAT_RELEASE, 0.2, -0.5, 1.0),), 0.3, 0.1)) == 0


def test_sky_opacity_has_no_independent_angular_cut_and_outline_never_revives_faded_ground():
    sky = (ROOT/'rendering/gl_programs/neon_celestial.py').read_text()
    land = (ROOT/'rendering/gl_programs/neon_lake_basin_program.py').read_text()
    owner = (ROOT/'rendering/quick/visualizer/implementations/shockwave_grid.py').read_text()
    assert 'float alpha = clamp(uSkyColor.a * uSkyStrength, 0.0, 1.0);' in sky
    assert 'float horizonAtmosphere' not in sky
    assert 'float broken = smoothstep(0.33, 0.66, gaps);' in sky
    assert 'float stars = basinStarField(ray, region, tone) * clamp(uStarColor.a, 0.0, 1.0) * starVisibility;' in sky
    assert 'float starVisibility=1.0-basinCelestialSkyMask(eye,ray);' in land
    assert 'vContourFade=basinDistanceFade(aUv);' in land
    assert 'vContourFade=max(' not in land
    assert 'float alpha=uCrestColor.a*vContourFade;' in land
    assert 'vec4(0.0,0.0,0.0,distanceFade)' in land
    assert 'GL_LINE_STRIP' not in owner
