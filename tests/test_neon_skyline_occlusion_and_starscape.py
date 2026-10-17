"""Focused mode-only physical contracts, no operator-authored preset goldens."""
from pathlib import Path

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.visualizer_mode_settings import mode_settings, Toggle
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
from rendering.gl_programs.neon_starscape import STARSCAPE_BEAT_MIN_STRENGTH, STARSCAPE_BEAT_RELEASE, starscape_beat_cells

ROOT = Path(__file__).resolve().parents[1]

def _framed_stars(events, tilt, turn):
    return starscape_beat_cells(events,tilt,turn,camera=3.5,fit=(.7,1.1))


def test_canonical_ui_bucket_defaults_cover_all_mode_declared_buckets():
    buckets = {bucket.key for bucket in mode_settings("shockwave_grid").buckets}
    defaults = DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"]
    assert {f"shockwave_grid:{bucket}" for bucket in buckets} <= set(defaults)
    assert all(isinstance(defaults[f"shockwave_grid:{bucket}"], bool) for bucket in buckets)

def test_starscape_beat_is_opt_in_canonical_spec_value():
    entries = mode_settings("shockwave_grid").entries
    assert any(isinstance(item,Toggle) and item.key == "shockwave_grid_starscape_beat" for item in entries)
    assert isinstance(DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]["shockwave_grid_starscape_beat"], bool)

def test_three_spaced_stars_per_strong_beat_with_slower_release():
    events = ((0.3,0.25,-0.63,1.4),)   # past the swell-in (STARSCAPE_BEAT_ATTACK), so later is fading
    first=_framed_stars(events,.35,.07)
    assert len(first)==3
    assert all(a[2]>0 for a in first)
    assert abs(first[0][0]-first[1][0])>25
    assert abs(first[1][0]-first[2][0])>25
    assert first==_framed_stars(events,.35,.07)
    later=_framed_stars(((1.5,0.25,-0.63,1.4),),.35,.07)
    assert all(0.0<b[2]<a[2] for a,b in zip(first,later))
    assert not _framed_stars(((0.01,0.25,-0.63,STARSCAPE_BEAT_MIN_STRENGTH-0.001),),.35,.07)
    assert _framed_stars(((1.76,0.25,-0.63,1.4),),.35,.07)
    assert not _framed_stars(((STARSCAPE_BEAT_RELEASE,0.25,-0.63,1.4),),.35,.07)
    # The fade keeps the original curve, slowed: at age / .3 it is where it was at age.
    age = .9
    slowed = _framed_stars(((age/.3,.25,-.63,1.4),),.35,.07)
    assert abs(slowed[0][2]-(1-(age/1.75)**2)**2)<1e-12
    # The onset ring remembers events for as long as the stars fade.
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_EVENT_MEMORY
    assert STARSCAPE_BEAT_RELEASE < SHOCKWAVE_EVENT_MEMORY

def test_each_admitted_beat_has_three_stars_and_older_beats_give_way_gradually():
    events=((0.5,0.2,-0.7,1.2),(0.1,0.7,-0.4,1.3))
    assert len(_framed_stars(events,.30,.08))==6
    # Four beats keep stars; the oldest fades once three newer beats have theirs, then it is gone.
    def beats(newest):
        return tuple((newest+0.4*k,0.1*k,-0.3-0.1*k,1.2) for k in range(5,-1,-1))
    young = _framed_stars(beats(0.1),.30,.08)
    assert len(young)==12
    oldest = [cell[2] for cell in young[9:]]
    later = [cell[2] for cell in _framed_stars(beats(0.3),.30,.08)[9:]]
    assert all(b<a for a,b in zip(oldest,later))
    assert len(_framed_stars(beats(0.7),.30,.08))==9

def test_thick_glass_sky_and_body_use_existing_depth_surface():
    renderer=(ROOT/"rendering/quick/visualizer/implementations/shockwave_grid.py").read_text()
    program=(ROOT/"rendering/gl_programs/neon_lake_basin_program.py").read_text()
    prepass=renderer.index('gl.glUniform1i(uniforms["uDepthOnly"],1)')
    sky=renderer.index('gl.glUniform1i(sky_uniforms["uSkyPass"],0)')
    land=renderer.index('self._draw_scene(frame,uniforms')
    body=renderer.index('gl.glUniform1i(sky_uniforms["uSkyPass"],2)')
    # The sky stays continuous, then depth + fade erase its light from only
    # the covered terrain. Drawing sky after the prepass caused an opacity band.
    assert sky<prepass<land<body
    assert '_terrain_sky_occlusion_blend(glow > 0.0)' in renderer
    assert 'vec4(0.0,0.0,0.0,distanceFade)' in program
    assert 'glDepthFunc(gl.GL_GREATER)' not in renderer
    assert 'gl_FragDepth=0.999999' in program

def test_forward_migration_yields_clean_canonical_runtime_style():
    normalized=normalize_visualizer_section_mapping(
        {"shockwave_grid_wire_display":"Glass + Both"}, apply_preset_overlay=False)
    assert normalized["shockwave_grid_wire_display"]=="Glass + Vertices"
