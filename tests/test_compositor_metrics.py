from types import SimpleNamespace

from rendering.adaptive_timer import _queue_safe_widget_update
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.compositor_metrics import _is_active_transition_paint_window
from rendering.gl_compositor_pkg.compositor_metrics import record_render_timer_tick
from rendering.gl_compositor_pkg import paint as paint_module
from rendering.gl_compositor_pkg.paint import _sync_transition_progress_from_frame_state


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


def test_handle_paintgl_consumes_pending_timer_update(monkeypatch):
    calls: list[str] = []

    class _Widget:
        def __init__(self):
            self._frame_state = None
            self._gl_state = SimpleNamespace(is_ready=lambda: False)

        def update(self):
            calls.append("update")

        def _record_paint_metrics(self, _paint_duration_ms):
            calls.append("record")

    widget = _Widget()

    from rendering import adaptive_timer

    original_run = adaptive_timer.ThreadManager.run_on_ui_thread
    original_shiboken = adaptive_timer.Shiboken
    try:
        adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: func())
        adaptive_timer.Shiboken = None

        _queue_safe_widget_update(widget)
        assert getattr(widget, "_srpss_timer_update_pending") is True

        monkeypatch.setattr(paint_module, "paintGL_impl", lambda _widget: calls.append("paint"))
        paint_module.handle_paintGL(widget)

        assert calls[:2] == ["update", "paint"]
        assert getattr(widget, "_srpss_timer_update_pending") is False
    finally:
        adaptive_timer.ThreadManager.run_on_ui_thread = original_run
        adaptive_timer.Shiboken = original_shiboken


def test_render_timer_metrics_separate_wakeups_from_accepted_updates(monkeypatch):
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.compositor_metrics.is_perf_metrics_enabled",
        lambda: True,
    )

    class _Metrics:
        def __init__(self):
            self.accepted: list[bool] = []

        def record_tick(self, *, accepted_update=True):
            self.accepted.append(bool(accepted_update))
            return None

    widget = SimpleNamespace(_render_timer_metrics=_Metrics())

    record_render_timer_tick(widget, accepted_update=False)
    record_render_timer_tick(widget, accepted_update=True)

    assert widget._render_timer_metrics.accepted == [False, True]


def test_paint_time_progress_sync_updates_active_transition_state():
    class _FrameState:
        def get_interpolated_progress(self):
            return 0.42

    widget = SimpleNamespace(
        _frame_state=_FrameState(),
        _raindrops=SimpleNamespace(progress=0.10),
        _warp=None,
        _blockspin=None,
        _blockflip=None,
        _diffuse=None,
        _blinds=None,
        _crumble=None,
        _particle=None,
        _burn=None,
        _crossfade=None,
        _slide=None,
        _wipe=None,
    )

    _sync_transition_progress_from_frame_state(widget)

    assert widget._raindrops.progress == 0.42


def test_paint_time_progress_sync_clamps_progress_and_keeps_inactive_states_untouched():
    class _FrameState:
        def get_interpolated_progress(self):
            return 1.7

    inactive = SimpleNamespace(progress=0.25)
    widget = SimpleNamespace(
        _frame_state=_FrameState(),
        _raindrops=None,
        _warp=SimpleNamespace(progress=0.10),
        _blockspin=None,
        _blockflip=None,
        _diffuse=None,
        _blinds=None,
        _crumble=None,
        _particle=None,
        _burn=None,
        _crossfade=None,
        _slide=None,
        _wipe=None,
        unrelated=inactive,
    )

    _sync_transition_progress_from_frame_state(widget)

    assert widget._warp.progress == 1.0
    assert inactive.progress == 0.25


def test_paint_impl_only_dispatches_active_transition_shader(monkeypatch):
    calls: list[str] = []

    class _ReadyState:
        def is_ready(self):
            return True

    class _Widget:
        _frame_state = None
        _gl_state = _ReadyState()
        _blockspin = None
        _blockflip = None
        _raindrops = SimpleNamespace(progress=0.0)
        _warp = None
        _diffuse = None
        _blinds = None
        _crumble = None
        _particle = None
        _burn = None
        _crossfade = None
        _slide = None
        _wipe = None

        def rect(self):
            return "target"

        def _can_use_raindrops_shader(self):
            calls.append("can:raindrops")
            return True

        def _paint_raindrops_shader(self, target):
            calls.append(f"paint:raindrops:{target}")

        def _try_shader_path(self, name, state, can_use_fn, paint_fn, target, prep_fn=None):
            calls.append(f"try:{name}")
            assert state is self._raindrops
            assert prep_fn is None
            assert can_use_fn() is True
            paint_fn(target)
            return True

    widget = _Widget()

    monkeypatch.setattr(paint_module, "is_perf_metrics_enabled", lambda: False)
    paint_module.paintGL_impl(widget)

    assert calls == ["try:raindrops", "can:raindrops", "paint:raindrops:target"]


def test_paint_impl_does_not_query_inactive_transition_methods(monkeypatch):
    class _ReadyState:
        def is_ready(self):
            return True

    class _Widget:
        _frame_state = None
        _gl_state = _ReadyState()
        _blockspin = None
        _blockflip = None
        _raindrops = SimpleNamespace(progress=0.0)
        _warp = None
        _diffuse = None
        _blinds = None
        _crumble = None
        _particle = None
        _burn = None
        _crossfade = None
        _slide = None
        _wipe = None

        def rect(self):
            return "target"

        def _can_use_raindrops_shader(self):
            return True

        def _paint_raindrops_shader(self, _target):
            pass

        def _can_use_warp_shader(self):  # pragma: no cover - should never be touched
            raise AssertionError("inactive warp capability was queried")

        def _paint_warp_shader(self, _target):  # pragma: no cover - should never be touched
            raise AssertionError("inactive warp paint was queried")

        def _try_shader_path(self, name, state, can_use_fn, paint_fn, target, prep_fn=None):
            assert name == "raindrops"
            assert state is self._raindrops
            assert can_use_fn() is True
            paint_fn(target)
            return True

    monkeypatch.setattr(paint_module, "is_perf_metrics_enabled", lambda: False)
    paint_module.paintGL_impl(_Widget())


def test_pause_render_strategy_clears_stale_pending_update():
    calls: list[str] = []

    class _StubCompositor:
        def __init__(self):
            self._render_strategy_manager = SimpleNamespace(pause=lambda: None)
            self._srpss_timer_update_pending = True

        def _finalize_render_timer_metrics(self, outcome="stopped"):
            calls.append(("finalize", outcome))

    stub = _StubCompositor()

    GLCompositorWidget._pause_render_strategy(stub)

    assert stub._srpss_timer_update_pending is False
    assert calls == [("finalize", "paused")]


def test_stop_render_strategy_clears_stale_pending_update():
    calls: list[str] = []

    class _StubCompositor:
        def __init__(self):
            self._render_strategy_manager = SimpleNamespace(stop=lambda: calls.append("stop"))
            self._srpss_timer_update_pending = True

        def _finalize_render_timer_metrics(self):
            calls.append("finalize")

    stub = _StubCompositor()

    GLCompositorWidget._stop_render_strategy(stub)

    assert stub._srpss_timer_update_pending is False
    assert calls == ["stop", "finalize"]


def test_start_render_strategy_resets_metrics_when_resuming_paused_timer():
    calls: list[str] = []

    class _StubManager:
        def is_running(self):
            return True

        def get_timer_state_name(self):
            return "PAUSED"

        def configure(self, config):
            calls.append(("configure", config.target_fps))

        def resume(self):
            calls.append("resume")

    class _StubCompositor:
        def __init__(self):
            self._render_strategy_manager = _StubManager()
            self._render_timer_fps = 0

        def _get_display_refresh_rate(self):
            return 165

        def _calculate_target_fps(self, display_hz):
            calls.append(("target", display_hz))
            return 165

        def _reset_render_timer_metrics(self, target_fps):
            calls.append(("reset", target_fps))

    stub = _StubCompositor()

    GLCompositorWidget._start_render_strategy(stub)

    assert stub._render_timer_fps == 165
    assert calls == [("target", 165), ("configure", 165), ("reset", 165), "resume"]


def test_start_render_strategy_keeps_metrics_when_timer_already_running():
    calls: list[str] = []

    class _StubManager:
        def is_running(self):
            return True

        def get_timer_state_name(self):
            return "RUNNING"

        def configure(self, config):
            calls.append(("configure", config.target_fps))

        def resume(self):
            calls.append("resume")

    class _StubCompositor:
        def __init__(self):
            self._render_strategy_manager = _StubManager()
            self._render_timer_fps = 0

        def _get_display_refresh_rate(self):
            return 60

        def _calculate_target_fps(self, display_hz):
            calls.append(("target", display_hz))
            return 60

        def _reset_render_timer_metrics(self, target_fps):
            calls.append(("reset", target_fps))

    stub = _StubCompositor()

    GLCompositorWidget._start_render_strategy(stub)

    assert stub._render_timer_fps == 60
    assert calls == [("target", 60), ("configure", 60), "resume"]
