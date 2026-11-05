"""Oscilloscope draws through its instanced beam program on the shared scene target."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_oscilloscope_uses_instanced_beam_and_shared_scene_target() -> None:
    renderer_src = (ROOT / "rendering" / "quick" / "visualizer" / "implementations" / "oscilloscope.py").read_text(
        encoding="utf-8"
    )
    program_src = (ROOT / "rendering" / "gl_programs" / "oscilloscope_program.py").read_text(
        encoding="utf-8"
    )
    assert "SceneTarget" in renderer_src
    assert "glDrawArraysInstanced" in renderer_src
    assert "OscilloscopeFrame" in renderer_src
    assert "layout(std430, binding = 3)" in program_src
    assert "Emission" in program_src
    assert "uBright" in program_src
