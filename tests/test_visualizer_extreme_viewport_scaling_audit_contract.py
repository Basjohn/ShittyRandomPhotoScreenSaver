"""Source-only guardrails for the 2026-09-02 cross-mode viewport audit.

This does not declare Oscilloscope/Sine/DevCurve physically accepted at every
extreme aspect. It pins the architecture we audited so a generic larger-axis
compensator cannot quietly spread from Spectrum into every mode.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_no_generic_larger_axis_temporal_compensator_in_visualizer_runtime() -> None:
    roots = [ROOT / "widgets/spotify_visualizer", ROOT / "rendering/quick/visualizer"]
    forbidden = "max(width / baseline_width, height / baseline_height)"
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            if forbidden in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_line_mode_pixel_thickness_is_uniform_scale_owned() -> None:
    """The live renderers must use presentation scale, not authored viewport dimensions.

    The two modes use different beam architectures: Sine has a layout width,
    Oscilloscope takes a beam-width setting into a shader. Neither should
    reintroduce an arbitrary larger-axis compensation or viewport-size pin.
    """
    osc = _read("rendering/quick/visualizer/implementations/oscilloscope.py")
    sine = _read("rendering/quick/visualizer/implementations/sine_wave.py")
    assert "presentation.uniform_visual_scale" in osc
    assert 'parameter(parameters, "osc_beam_width")' in osc
    assert 'gl.glUniform1f(beam_uniforms["uCore"], core)' in osc
    assert "visual_scale=presentation.uniform_visual_scale" in sine
    assert "line_width=" in sine and "glow_sigma=" in sine
    assert "* scale" in sine


def test_line_mode_authored_frame_runtimes_do_not_read_viewport_geometry() -> None:
    for relative in (
        "widgets/spotify_visualizer/oscilloscope_frame_runtime.py",
        "widgets/spotify_visualizer/sine_frame_runtime.py",
    ):
        source = _read(relative)
        assert "viewport_extent" not in source
        assert "viewport_width" not in source
        assert "viewport_height" not in source


def test_devcurve_has_axis_specific_renderer_normalization_not_one_large_axis() -> None:
    source = _read("rendering/quick/visualizer/implementations/devcurve.py")
    assert "normalized_x_scale=(baseline[0] * scale) / content[2]" in source
    assert "normalized_y_scale=(baseline[1] * scale) / content[3]" in source
    assert "layout.normalized_y_scale / layout.normalized_x_scale" in source
