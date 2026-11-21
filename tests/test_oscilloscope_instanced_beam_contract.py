"""Oscilloscope draws through its instanced beam program on the shared scene target."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHADERS = ROOT / "widgets" / "spotify_visualizer" / "shaders"


def test_oscilloscope_uses_instanced_beam_and_shared_scene_target() -> None:
    renderer_src = (ROOT / "rendering" / "quick" / "visualizer" / "implementations" / "oscilloscope.py").read_text(
        encoding="utf-8"
    )
    # The beam's shaders are files both renderers draw (N5.1): the vertex stage reads the points' storage buffer, the
    # fragment writes the light into the emission (the glowing pack) and the brightness the record carries.
    vertex_src = (SHADERS / "oscilloscope_beam.vert").read_text(encoding="utf-8")
    fragment_src = (SHADERS / "oscilloscope_beam_body.glsl").read_text(encoding="utf-8")
    block_src = (SHADERS / "oscilloscope_beam_block.glsl").read_text(encoding="utf-8")
    assert "SceneTarget" in renderer_src
    assert "glDrawArraysInstanced" in renderer_src
    assert "OscilloscopeFrame" in renderer_src
    assert "layout(std430, binding = 3)" in vertex_src
    assert "Emission" in fragment_src
    assert "u_bright" in fragment_src and "u_bright" in block_src
