"""Phase A2 gates for inline OpenGL inside the standalone Quick scene."""

from __future__ import annotations

import ast
from pathlib import Path

from PySide6.QtQuick import QQuickItem

from rendering.quick.render import (
    BackgroundRenderItem,
    RenderNodeTelemetry,
)
from rendering.quick.transitions import TransitionSample


ROOT = Path(__file__).resolve().parents[1]


def _transition_sample(progress: float) -> TransitionSample:
    return TransitionSample(
        run_id=7,
        runtime_generation=3,
        linear_progress=progress,
        eased_progress=progress,
        complete=False,
    )


def test_transition_pixel_probes_keep_nearest_frame_across_cadence_jump():
    telemetry = RenderNodeTelemetry(
        gui_thread_id=1,
        capture_pixels=True,
        transition_probe_progresses=(0.42, 0.50),
    )
    before = _transition_sample(0.39)
    after = _transition_sample(0.47)
    assert telemetry.wants_transition_probe_sample(before)
    telemetry.note_transition_probe_sample(sample=before, colors=("before",))
    assert telemetry.snapshot().transition_probe_colors == ()
    assert telemetry.wants_transition_probe_sample(after)
    telemetry.note_transition_probe_sample(sample=after, colors=("after",))
    assert telemetry.snapshot().transition_probe_linear_progresses == (0.39,)
    assert telemetry.snapshot().transition_probe_colors == (("before",),)

    before_second = _transition_sample(0.48)
    after_second = _transition_sample(0.54)
    telemetry.note_transition_probe_sample(
        sample=before_second,
        colors=("second-before",),
    )
    telemetry.note_transition_probe_sample(
        sample=after_second,
        colors=("second-after",),
    )
    assert telemetry.snapshot().transition_probe_linear_progresses == (
        0.39,
        0.48,
    )
    assert telemetry.snapshot().transition_probe_colors[-1] == ("second-before",)


def test_background_item_uses_the_selected_inline_primitive():
    # N5.2h: the item's Python render node is deleted; the native core draws the background.
    assert issubclass(BackgroundRenderItem, QQuickItem)

    item_tree = ast.parse(
        (ROOT / "rendering" / "quick" / "render" / "background_item.py").read_text(
            encoding="utf-8"
        )
    )
    calls = {
        node.func.attr
        for node in ast.walk(item_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "setFlag" in calls
    assert "updatePaintNode" not in calls


def test_quick_render_node_path_has_no_prohibited_surface_or_compatibility_owner():
    paths = (
        list((ROOT / "rendering" / "quick" / "render").rglob("*.py"))
        + [ROOT / "tools" / "qtquick_render_node_smoke.py"]
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "QQuickWidget",
        "QRhiWidget",
        "DisplayWidget",
        "GLCompositorWidget",
        "QOffscreenSurface",
        "QOpenGLWidget",
        "afterRendering.connect",
        "afterFrameEnd",
        "grabWindow(",
        "glFinish",
        "DwmFlush",
    ):
        assert forbidden not in source

    smoke_source = (ROOT / "tools" / "qtquick_render_node_smoke.py").read_text(
        encoding="utf-8"
    )
    window_source = (ROOT / "rendering" / "quick" / "window.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (ROOT / "rendering" / "quick" / "runtime.py").read_text(
        encoding="utf-8"
    )
    assert "QMetaObject.invokeMethod" in window_source
    assert "self.window.queue_close()" in runtime_source
    assert "probe.runtime.close_runtime()" in smoke_source
    assert "probe.window.close()" not in smoke_source
    assert "probe.window.releaseResources()" not in smoke_source

