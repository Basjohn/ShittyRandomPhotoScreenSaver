"""Neon-only controls and scene compositing: no Qt, GL context or operator presets."""
from pathlib import Path

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.visualizer_mode_settings import require_mode_settings, Slider, Toggle
from rendering.gl_programs.neon_starscape import starscape_beat_cells

ROOT=Path(__file__).resolve().parents[1]


def _framed_stars(events, tilt, turn):
    return starscape_beat_cells(events,tilt,turn,camera=3.5,fit=(.7,1.1))


def test_one_glow_bucket_has_canonical_closed_default_and_distinct_controls():
    spec=require_mode_settings('shockwave_grid')
    controls={control.key:control for control in spec.entries if hasattr(control,'key')}
    # Each glow lives beside what it lights: surface glow under Glow, beat stars under Sky, halo and rays
    # under Sun & Moon.
    keys={
        'shockwave_grid_glow': 'glow',
        'shockwave_grid_horizon': 'glow',
        'shockwave_grid_water_line_glow': 'glow',
        'shockwave_grid_celestial_glow_enabled': 'celestial',
        'shockwave_grid_celestial_glow_strength': 'celestial',
        'shockwave_grid_celestial_glow_reactivity': 'celestial',
        'shockwave_grid_sun_rays_enabled': 'celestial',
        'shockwave_grid_sun_rays_strength': 'celestial',
        'shockwave_grid_sun_rays_color': 'celestial',
        'shockwave_grid_starscape_beat': 'sky',
        'shockwave_grid_star_glow_strength': 'sky',
        'shockwave_grid_star_glow_reactivity': 'sky',
    }
    defaults=DEFAULT_SETTINGS['widgets']['spotify_visualizer']
    assert {b.key for b in spec.buckets if b.key=='glow'}=={'glow'}
    bucket_states=DEFAULT_SETTINGS['ui']['visualizer_bucket_states']
    assert isinstance(bucket_states['shockwave_grid:glow'], bool)
    for key, bucket in keys.items():
        assert key in controls and controls[key].bucket==bucket, key
        assert key in defaults
    assert isinstance(controls['shockwave_grid_celestial_glow_enabled'],Toggle)
    assert isinstance(defaults['shockwave_grid_celestial_glow_enabled'], bool)
    assert isinstance(controls['shockwave_grid_sun_orbit_speed'],Slider)
    assert 0.0 <= defaults['shockwave_grid_sun_orbit_speed'] <= controls['shockwave_grid_sun_orbit_speed'].high <= .025
    for key in ('shockwave_grid_celestial_glow_strength','shockwave_grid_celestial_glow_reactivity'):
        assert controls[key].when==(('shockwave_grid_sun_enabled', True),('shockwave_grid_celestial_glow_enabled',True))
    for key in ('shockwave_grid_star_glow_strength','shockwave_grid_star_glow_reactivity'):
        assert controls[key].when==(('shockwave_grid_sky_enabled',True),('shockwave_grid_starscape_beat',True))


def test_sky_is_composited_first_then_subtracted_by_exact_terrain_coverage():
    renderer=(ROOT/'rendering/quick/visualizer/implementations/shockwave_grid.py').read_text()
    terrain=(ROOT/'rendering/gl_programs/neon_lake_basin_program.py').read_text()
    sky=renderer.index('gl.glUniform1i(sky_uniforms["uSkyPass"],0)')
    prepass=renderer.index('gl.glUniform1i(uniforms["uDepthOnly"],1)')
    colour=renderer.index('self._draw_scene(frame,uniforms')
    body=renderer.index('gl.glUniform1i(sky_uniforms["uSkyPass"],2)')
    assert sky < prepass < colour < body
    assert 'gl.GL_ONE_MINUS_SRC_ALPHA' in renderer
    assert 'gl.glBlendFuncSeparatei(1,gl.GL_ZERO' in renderer
    assert 'vec4(0.0,0.0,0.0,distanceFade)' in terrain
    assert 'vTerrainBase=base;' in terrain
    assert 'vTerrainBase<0.035' in terrain
    # Do not let the distant skyline fall back to the rejected flat strip.
    assert 'GL_LINE_STRIP' not in renderer


def test_midstrength_beat_now_selects_actual_visible_panorama_star_cells():
    events=((0.08,0.25,-0.3,.55),)
    cells=_framed_stars(events,.35,.07)
    assert len(cells)==3
    assert all(0.0<c[2]<=1.0 for c in cells)
    assert abs(cells[0][0]-cells[1][0])>25
    assert not _framed_stars(((0.08,0.25,-0.3,.2),),.35,.07)
    # Stars swell in over the attack, then fade: a younger star is still rising, an older one is past its peak.
    peak=_framed_stars(((0.3,.25,-.3,.55),),.35,.07)
    assert all(a[2]<p[2] for a,p in zip(cells,peak))
    assert all(b[2]<p[2] for p,b in zip(peak,_framed_stars(((1.2,.25,-.3,.55),),.35,.07)))
    assert _framed_stars(((0.0,.25,-.3,.55),),.35,.07)[0][2]==0.0
