from pathlib import Path

import numpy as np

from tools import qtquick_p0_presentation_benchmark as candidate
from tools.presentation_benchmark_core import (
    COMMON_SLIDE_SOURCE_SPEC,
    COMMON_TIMELINE,
    COMPLETION_SIGNAL_SEMANTICS,
    common_workload_identity,
)


SOURCE = Path(candidate.__file__).read_text(encoding="utf-8")


def test_candidate_is_fixed_to_the_common_two_display_p0_workload():
    assert candidate.SCREEN_COUNT == 2
    assert COMMON_TIMELINE.duration_ns == 15_000_000_000
    assert candidate.common_workload_identity() == common_workload_identity()
    assert 'if args.population != "P0"' in SOURCE
    assert "build_common_bubble_feature_clip" in SOURCE
    assert "COMMON_SLIDE_SOURCE_SPEC" in SOURCE
    assert "VisualizerLogicalRuntime" in SOURCE


def test_candidate_owns_only_standalone_quick_presenters():
    assert "QQuickWindow()" in SOURCE
    assert "window.setScreen(screen)" in SOURCE
    assert SOURCE.index("window.setScreen(screen)") < SOURCE.index("window.show()")
    for forbidden in (
        "QQuickWidget",
        "DisplayWidget",
        "GLCompositorWidget",
        "_ensure_gl_compositor",
        "swapBuffers(",
        "doneCurrent(",
        "setOpacity(",
    ):
        assert forbidden not in SOURCE


def test_candidate_forces_and_proves_the_threaded_opengl_scene_graph():
    assert 'os.environ["QSG_RENDER_LOOP"] = "threaded"' in SOURCE
    assert "window.afterRendering.connect" in SOURCE
    assert "Qt.ConnectionType.DirectConnection" in SOURCE
    assert "rendererInterface().graphicsApi()" in SOURCE
    assert "render_thread_id" in SOURCE
    assert "gui_thread_id" in SOURCE
    assert "afterFrameEnd" not in SOURCE


def test_frame_swapped_is_only_an_internal_queue_proxy():
    assert COMPLETION_SIGNAL_SEMANTICS["qquickwindow.frameSwapped"] == {
        "stage": "queued_for_presentation",
        "physical_presentation_evidence": False,
    }
    assert '"required": True' in SOURCE
    assert '"accepted_signal": "external.presentmon.displayed"' in SOURCE


def test_slide_sources_are_deterministic_and_distinct():
    old = candidate._slide_pixels(320, 180, "old")
    old_again = candidate._slide_pixels(320, 180, "old")
    new = candidate._slide_pixels(320, 180, "new")
    assert old.shape == (180, 320, 4)
    assert old.dtype == np.uint8
    assert np.array_equal(old, old_again)
    assert not np.array_equal(old, new)
    assert COMMON_SLIDE_SOURCE_SPEC["duration_ms"] == 5000
