from types import SimpleNamespace

from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.compositor_metrics import _is_active_transition_paint_window


def test_active_transition_paint_window_true_while_transition_running():
    context = {
        "current_transition": "blockflip",
        "has_frame_state": True,
        "display_transition": {
            "running": True,
            "pending": False,
        },
    }

    assert _is_active_transition_paint_window(context) is True


def test_active_transition_paint_window_false_after_transition_completes():
    context = {
        "current_transition": None,
        "has_frame_state": False,
        "display_transition": {
            "running": False,
            "pending": False,
            "last_transition": "GLCompositorWipeTransition",
            "idle_age": 3.1,
        },
    }

    assert _is_active_transition_paint_window(context) is False


def test_complete_transition_finalizes_paint_metrics():
    calls: list[str] = []

    class _StubCompositor:
        def __init__(self):
            self._profiler = SimpleNamespace(
                complete=lambda name, viewport_size: calls.append(f"profiler:{name}:{viewport_size}")
            )
            self._wipe_state = SimpleNamespace(new_pixmap="new-pixmap")
            self._current_anim_id = "anim"
            self._base_pixmap = "old-pixmap"

        def width(self):
            return 640

        def height(self):
            return 480

        def _stop_frame_pacing(self):
            calls.append("stop_frame_pacing")

        def _finalize_animation_metrics(self, outcome="stopped"):
            calls.append(f"finalize_anim:{outcome}")

        def _finalize_paint_metrics(self, outcome="stopped"):
            calls.append(f"finalize_paint:{outcome}")

        def update(self):
            calls.append("update")

    stub = _StubCompositor()

    GLCompositorWidget._complete_transition(
        stub,
        "wipe",
        "_wipe_state",
        on_finished=None,
        release_textures=False,
    )

    assert "finalize_paint:complete" in calls
    assert stub._wipe_state is None
    assert stub._base_pixmap == "new-pixmap"
