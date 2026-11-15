"""Source-only guardrails for the 2026-09-02 cross-mode viewport audit.

This does not declare Oscilloscope/DevCurve physically accepted at every
extreme aspect. It pins the architecture we audited so a generic larger-axis
compensator cannot quietly spread from Spectrum into every mode.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

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


def _beam_thickness(pixels) -> int:
    """Lit rows of the flat beam down the item's middle column."""
    column = pixels[:, pixels.shape[1] // 2, :]
    return int(np.count_nonzero(column[:, 1] > 32))


@pytest.mark.qt
def test_line_mode_pixel_thickness_is_uniform_scale_owned(qt_app) -> None:
    """The rendered beam's pixel thickness follows presentation.uniform_visual_scale and
    nothing about the item's size: doubling the scale thickens the beam, while the same
    scale at two very different viewports draws the same thickness."""
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_oscilloscope_rework import _ScopeGlTarget, _scope_gl_snapshot

    def thickness(width: int, height: int, scale: float) -> int:
        snapshot = _scope_gl_snapshot(width, height)
        snapshot = replace(snapshot, presentation=replace(snapshot.presentation, uniform_visual_scale=scale))
        target, host = _ScopeGlTarget(width, height), QuickVisualizerRenderHost()
        try:
            return _beam_thickness(target.render(host, snapshot))
        finally:
            host.release_resources()
            target.close()

    base = thickness(480, 270, 1.0)
    assert base > 0
    assert thickness(480, 270, 2.0) >= 1.6 * base
    # The same scale at a very different viewport and aspect is the same line.
    assert thickness(900, 160, 1.0) == base


def test_line_mode_authored_frame_runtimes_do_not_read_viewport_geometry() -> None:
    for relative in (
        "widgets/spotify_visualizer/oscilloscope_frame_runtime.py",
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
