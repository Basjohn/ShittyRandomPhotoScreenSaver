"""Focused mode-only physical contracts, no operator-authored preset goldens."""
from pathlib import Path

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.visualizer_mode_settings import mode_settings, Toggle
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
from rendering.gl_programs.neon_starscape import starscape_beat_cells

ROOT = Path(__file__).resolve().parents[1]

def test_canonical_ui_bucket_defaults_cover_all_mode_declared_buckets():
    buckets = {bucket.key for bucket in mode_settings("shockwave_grid").buckets}
    defaults = DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"]
    assert {f"shockwave_grid:{bucket}" for bucket in buckets} <= set(defaults)
    assert all(defaults[f"shockwave_grid:{bucket}"] is False for bucket in buckets)

def test_starscape_beat_is_opt_in_canonical_spec_value():
    entries = mode_settings("shockwave_grid").entries
    assert any(isinstance(item,Toggle) and item.key == "shockwave_grid_starscape_beat" for item in entries)
    assert DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]["shockwave_grid_starscape_beat"] is False

def test_three_spaced_stars_per_strong_beat_with_gentle_release():
    events = ((0.05,0.25,-0.63,1.4),)
    first=starscape_beat_cells(events,.35,.07)
    assert len(first)==3
    assert all(a[2]>0 for a in first)
    assert abs(first[0][0]-first[1][0])>75
    assert abs(first[1][0]-first[2][0])>75
    assert first==starscape_beat_cells(events,.35,.07)
    later=starscape_beat_cells(((1.5,0.25,-0.63,1.4),),.35,.07)
    assert all(0.0<b[2]<a[2] for a,b in zip(first,later))
    assert not starscape_beat_cells(((0.01,0.25,-0.63,0.25),),.35,.07)
    assert not starscape_beat_cells(((1.76,0.25,-0.63,1.4),),.35,.07)

def test_two_admitted_beats_have_at_most_six_stars():
    events=((0.5,0.2,-0.7,1.2),(0.1,0.7,-0.4,1.3))
    assert len(starscape_beat_cells(events,.30,.08))==6

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
