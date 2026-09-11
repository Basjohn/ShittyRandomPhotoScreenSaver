from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_devcurve_shader_source_available() -> None:
    src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "devcurve.frag").read_text(
        encoding="utf-8"
    )
    assert src
    assert "u_devcurve_curve_bass" in src
    assert "u_devcurve_curve_transients" in src
    assert "u_rainbow_hue_offset" in src
    assert "u_devcurve_order0" in src
    assert "u_devcurve_layer_bass_outline_color" in src
    assert "u_devcurve_layer_bass_outline_width" in src
    assert "u_devcurve_foreground_layer_id" in src
    assert "u_devcurve_foreground_shadow_enabled" in src
    assert "u_devcurve_foreground_specular_enabled" in src
    assert "u_devcurve_specular_slot0" in src
    assert "u_devcurve_specular_slot1" in src
    assert "u_devcurve_specular_slot2" in src
    assert "u_devcurve_outline_alpha" not in src


def test_quick_devcurve_renderer_requires_layer_outline_uniforms() -> None:
    source = (
        ROOT / "rendering" / "quick" / "visualizer" / "implementations" / "devcurve.py"
    ).read_text(encoding="utf-8")
    start = source.index("    def _initialize(self) -> None:")
    init_source = source[start:]

    assert 'f"u_devcurve_layer_{name}_outline_color"' in init_source
    assert 'f"u_devcurve_layer_{name}_outline_width"' in init_source
    assert '"u_devcurve_foreground_layer_id"' in init_source
    assert '"u_devcurve_foreground_shadow_alpha"' in init_source
    assert '"u_devcurve_foreground_specular_crest_bias"' in init_source
    assert '"u_devcurve_specular_slot0"' in init_source
    assert '"u_devcurve_specular_slot1"' in init_source
    assert '"u_devcurve_specular_slot2"' in init_source
    assert '"u_devcurve_outline_alpha"' not in init_source
