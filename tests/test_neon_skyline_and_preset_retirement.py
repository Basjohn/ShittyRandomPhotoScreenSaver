"""Test-owned contracts for approved Neon Lake style/preset retirement.

No authored preset values are asserted as immutable artistic goldens.
"""
from pathlib import Path

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import Choice, spec_control
from core.settings.visualizer_presets import get_presets, get_custom_preset_index


def test_neon_surface_choice_has_only_retained_styles_and_forward_only_migration():
    key="shockwave_grid_wire_display"
    choice=spec_control(key)
    assert isinstance(choice, Choice)
    assert choice.choices == ("Vertices", "Glass", "Glass + Vertices")
    assert require_canonical_default("widgets.spotify_visualizer."+key)=="Vertices"
    from core.settings.visualizer_settings_contract import migrate_retired_neon_surface_style
    for old, expected in {
        "Edges": "Vertices", "Both": "Vertices",
        "Glass + Edges": "Glass", "Glass + Both": "Glass + Vertices"
    }.items():
        assert choice.admit(old,"Vertices") == "Vertices"  # runtime has no legacy compatibility
        assert migrate_retired_neon_surface_style({key: old})[key] == expected
        dotted = "widgets.spotify_visualizer." + key
        assert migrate_retired_neon_surface_style({dotted: old})[dotted] == expected
    for style in choice.choices:
        assert choice.admit(style,"Vertices")==style


def test_neon_disk_catalog_compacts_authored_slots_and_keeps_custom_distinct():
    presets=get_presets("shockwave_grid")
    assert presets and presets[-1].is_custom and all(not p.is_custom for p in presets[:-1])
    assert get_custom_preset_index("shockwave_grid")==len(presets)-1
    root=Path(__file__).resolve().parents[1]/"presets"/"visualizer_modes"/"shockwave_grid"
    assert len(list(root.glob("preset_*.json")))==len(presets)-1



def test_skyline_renders_actual_terrain_triangles_without_projected_column_maxima():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    shader = (root / "rendering/gl_programs/neon_lake_basin_program.py").read_text()
    renderer = (root / "rendering/quick/visualizer/implementations/shockwave_grid.py").read_text()
    assert "basinLandHeight(aUv,base,smoothed)" in shader
    assert "clip.y+=uOutlineLiftNdc*width*clip.w" in shader
    assert "clip.z+=0.0012*clip.w" in shader
    assert "vTerrainBase<0.035" in shader  # true continued land, no lake-edge duplication
    assert "bestScreen" not in shader
    assert "gl.GL_LINE_STRIP" not in renderer
    assert 'gl.glDrawArrays(gl.GL_TRIANGLES,0,vertices)' in renderer
