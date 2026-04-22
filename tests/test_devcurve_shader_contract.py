from __future__ import annotations

from widgets.spotify_visualizer.shaders import load_fragment_shader


def test_devcurve_shader_source_available():
    src = load_fragment_shader("devcurve")
    assert src, "devcurve shader source missing"
    assert "u_devcurve_curve_bass" in src
    assert "u_devcurve_curve_transients" in src
    assert "u_rainbow_hue_offset" in src
    assert "u_devcurve_order0" in src
