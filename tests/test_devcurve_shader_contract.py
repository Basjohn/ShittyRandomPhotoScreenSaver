from __future__ import annotations

from widgets.spotify_visualizer.shaders import load_fragment_shader
from widgets.spotify_visualizer.renderers.devcurve import get_uniform_names


def test_devcurve_shader_source_available():
    src = load_fragment_shader("devcurve")
    assert src, "devcurve shader source missing"
    assert "u_devcurve_curve_bass" in src
    assert "u_devcurve_curve_transients" in src
    assert "u_rainbow_hue_offset" in src
    assert "u_devcurve_order0" in src
    assert "u_devcurve_layer_bass_outline_color" in src
    assert "u_devcurve_layer_bass_outline_width" in src
    assert "u_devcurve_foreground_layer_id" in src
    assert "u_devcurve_foreground_shadow_enabled" in src
    assert "u_devcurve_foreground_specular_enabled" in src
    assert "u_devcurve_outline_alpha" not in src


def test_devcurve_renderer_uniform_manifest_uses_layer_outline_uniforms():
    uniforms = set(get_uniform_names())
    assert "u_devcurve_layer_bass_outline_color" in uniforms
    assert "u_devcurve_layer_vocals_outline_width" in uniforms
    assert "u_devcurve_foreground_layer_id" in uniforms
    assert "u_devcurve_foreground_shadow_alpha" in uniforms
    assert "u_devcurve_foreground_specular_crest_bias" in uniforms
    assert "u_devcurve_outline_alpha" not in uniforms
