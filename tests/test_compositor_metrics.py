from types import SimpleNamespace

from rendering.adaptive_timer import _mark_widget_update_pending, _queue_safe_widget_update
from rendering.gl_compositor import GLCompositorWidget, _TerminalTransitionCompletion
from rendering.gl_compositor_pkg.compositor_metrics import _is_active_transition_paint_window
from rendering.gl_compositor_pkg.compositor_metrics import record_render_timer_tick
from rendering.gl_compositor_pkg.compositor_metrics import record_paint_metrics
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
            self._current_transition_name = "wipe"
            self._base_pixmap = "old-pixmap"
            self._texture_manager = None

        def width(self):
            return 640

        def height(self):
            return 480

        def _stop_frame_pacing(self):
            calls.append("stop_frame_pacing")

        def _assign_base_pixmap(self, pixmap, *, payload=None, texture_id=None):
            del payload, texture_id
            self._base_pixmap = pixmap
            return 1

        def _finalize_animation_metrics(self, outcome="stopped"):
            calls.append(f"finalize_anim:{outcome}")

        def _finalize_paint_metrics(self, outcome="stopped"):
            calls.append(f"finalize_paint:{outcome}")

        def request_scene_update(self, *, source="scene"):
            calls.append(f"request:{source}")
            return True

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

        def _paint(_widget, *, perf_enabled=None):
            assert perf_enabled is False
            assert getattr(widget, "_srpss_timer_update_pending") is True
            calls.append("paint")

        monkeypatch.setattr(paint_module, "paintGL_impl", _paint)
        paint_module.handle_paintGL(widget)

        assert calls[:2] == ["update", "paint"]
        assert getattr(widget, "_srpss_timer_update_pending") is False
    finally:
        adaptive_timer.ThreadManager.run_on_ui_thread = original_run
        adaptive_timer.Shiboken = original_shiboken


def test_handle_paintgl_avoids_diagnostic_clock_and_metrics_when_perf_is_off(
    monkeypatch,
):
    widget = SimpleNamespace(
        _frame_state=None,
        _gl_state=SimpleNamespace(is_ready=lambda: False),
        _record_paint_metrics=lambda _duration: (_ for _ in ()).throw(
            AssertionError("normal paint must not enter diagnostic metrics")
        ),
    )
    monkeypatch.setattr(paint_module, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(
        paint_module.time,
        "perf_counter",
        lambda: (_ for _ in ()).throw(
            AssertionError("normal paint must not read the diagnostic clock")
        ),
    )

    paint_module.handle_paintGL(widget)


def test_presentation_owner_acknowledges_latest_latched_generation(monkeypatch):
    queued: list[object] = []

    class _StubCompositor:
        def __init__(self):
            self._render_shutdown_requested = False
            self._presentation_dirty_generation = 1
            self._presentation_requested_generation = 0
            self._presentation_ack_generation = 0
            self._presentation_paint_generation = 0
            self._presentation_paint_active = False
            self._terminal_transaction = None
            self._terminal_completion_dispatch_pending = False
            self._render_strategy_manager = SimpleNamespace(
                notify_presentation_paint_completed=lambda: None,
            )

        def _request_latched_presentation(self):
            raise AssertionError("no generation should remain after acknowledgement")

    widget = _StubCompositor()

    def _queue(target):
        if getattr(target, "_srpss_timer_update_pending", False):
            return False
        _mark_widget_update_pending(target)
        queued.append(target)
        return True

    monkeypatch.setattr("rendering.gl_compositor._queue_safe_widget_update", _queue)

    assert GLCompositorWidget._present_scene_from_coordinator(
        widget,
        continuous=False,
    ) is True
    assert widget._presentation_requested_generation == 1

    widget._presentation_dirty_generation = 2
    assert GLCompositorWidget._present_scene_from_coordinator(
        widget,
        continuous=False,
    ) is False
    assert widget._presentation_requested_generation == 2
    assert queued == [widget]

    paint_generation = GLCompositorWidget._presentation_paint_started(widget)
    assert paint_generation == 2
    assert widget._srpss_timer_update_pending is True

    GLCompositorWidget._presentation_paint_completed(widget, paint_generation)
    assert widget._presentation_ack_generation == 2
    assert widget._srpss_timer_update_pending is False


def test_terminal_transition_waits_for_matching_paint_generation():
    completions: list[str] = []
    queued: list[object] = []
    demand_requests: list[str] = []
    widget = SimpleNamespace(
        _render_shutdown_requested=False,
        _presentation_dirty_generation=4,
        _presentation_requested_generation=4,
        _presentation_ack_generation=2,
        _presentation_paint_active=True,
        _terminal_transaction=_TerminalTransitionCompletion(
            animation_generation=7,
            transition_name="wipe",
            complete_callback=lambda: completions.append("complete"),
            created_ts=0.0,
        ),
        _transition_animation_generation=7,
        _terminal_completion_dispatch_pending=False,
        _render_strategy_manager=SimpleNamespace(
            notify_presentation_paint_completed=lambda: None,
        ),
        _request_latched_presentation=lambda: demand_requests.append("request") or True,
        _queue_terminal_transition_completion=lambda completion: (
            setattr(completion, "phase", "completion_queued")
            or queued.append(completion)
            or True
        ),
    )

    GLCompositorWidget._presentation_paint_completed(
        widget,
        3,
        terminal_transition_rendered=False,
    )
    assert completions == []
    assert demand_requests == ["request"]
    assert queued == []

    GLCompositorWidget._presentation_paint_completed(
        widget,
        4,
        terminal_transition_rendered=True,
    )
    assert completions == []
    assert len(queued) == 1
    widget._terminal_completion_dispatch_pending = True
    GLCompositorWidget._srpss_complete_terminal_transition(widget)

    assert completions == ["complete"]
    assert widget._terminal_transaction is None


def test_paint_completion_queues_terminal_callback_before_notifying_owner():
    events: list[str] = []
    widget = SimpleNamespace(
        _render_shutdown_requested=False,
        _presentation_dirty_generation=4,
        _presentation_requested_generation=4,
        _presentation_ack_generation=2,
        _presentation_paint_active=True,
        _terminal_transaction=_TerminalTransitionCompletion(
            animation_generation=7,
            transition_name="wipe",
            complete_callback=lambda: events.append("terminal"),
            created_ts=0.0,
        ),
        _transition_animation_generation=7,
        _terminal_completion_dispatch_pending=False,
        _render_strategy_manager=SimpleNamespace(
            notify_presentation_paint_completed=lambda: events.append("notify"),
        ),
        _request_latched_presentation=lambda: events.append("request") or True,
        _queue_terminal_transition_completion=lambda _completion: events.append("queue") or True,
    )

    GLCompositorWidget._presentation_paint_completed(
        widget,
        4,
        terminal_transition_rendered=True,
    )

    assert events == ["queue", "notify"]


def test_terminal_callback_failure_still_releases_presentation_owner():
    events: list[str] = []

    def fail_terminal():
        events.append("terminal")
        raise RuntimeError("terminal failed")

    widget = SimpleNamespace(
        _render_shutdown_requested=False,
        _presentation_dirty_generation=4,
        _presentation_requested_generation=4,
        _presentation_ack_generation=2,
        _presentation_paint_active=True,
        _terminal_transaction=_TerminalTransitionCompletion(
            animation_generation=7,
            transition_name="wipe",
            complete_callback=fail_terminal,
            created_ts=0.0,
        ),
        _transition_animation_generation=7,
        _render_strategy_manager=SimpleNamespace(
            notify_presentation_paint_completed=lambda: events.append("notify"),
        ),
        _request_latched_presentation=lambda: True,
        _terminal_completion_dispatch_pending=False,
        _queue_terminal_transition_completion=lambda completion: events.append("queue") or True,
    )

    GLCompositorWidget._presentation_paint_completed(
        widget,
        4,
        terminal_transition_rendered=True,
    )

    widget._terminal_transaction.phase = "completion_queued"
    widget._terminal_completion_dispatch_pending = True
    GLCompositorWidget._srpss_complete_terminal_transition(widget)

    assert events == ["queue", "notify", "terminal"]
    assert widget._terminal_transaction is None
    assert widget._terminal_completion_dispatch_pending is False


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


def test_paint_path_metrics_report_idle_gl_and_qpainter_fallback(monkeypatch, caplog):
    from rendering.gl_compositor_pkg import compositor_metrics

    caplog.set_level("INFO", logger=compositor_metrics.logger.name)
    clock = {"now": 100.0}
    widget = SimpleNamespace(
        _paint_metrics=None,
        _last_paint_path="idle_gl",
        _paint_path_window=None,
        parent=lambda: SimpleNamespace(screen_index=1),
    )
    monkeypatch.setattr(compositor_metrics, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(compositor_metrics.time, "monotonic", lambda: clock["now"])

    record_paint_metrics(widget, 1.25)
    widget._last_paint_path = "idle_qpainter_fallback"
    clock["now"] += 10.1
    record_paint_metrics(widget, 3.5)

    messages = [record.getMessage() for record in caplog.records]
    paint_path = next(message for message in messages if "[GL PAINT PATH]" in message)
    assert "screen=1" in paint_path
    assert "idle_gl=1" in paint_path
    assert "idle_qpainter_fallback=1" in paint_path
    assert "transition_qpainter_fallback=0" in paint_path


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
        _current_transition_name = "raindrops"
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
        _current_transition_name = "raindrops"
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
            self._render_strategy_manager = SimpleNamespace(
                request_stop=lambda: calls.append("request_stop") or False
            )
            self._srpss_timer_update_pending = True
            self._render_owner_stopped_ack = True

        def _finalize_render_timer_metrics(self):
            calls.append("finalize")

    stub = _StubCompositor()

    GLCompositorWidget._stop_render_strategy(stub)

    assert stub._srpss_timer_update_pending is False
    assert stub._render_owner_stopped_ack is False
    assert calls == ["request_stop", "finalize"]


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

        def _ensure_presentation_owner_configured(self):
            return GLCompositorWidget._ensure_presentation_owner_configured(self)

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

        def _ensure_presentation_owner_configured(self):
            return GLCompositorWidget._ensure_presentation_owner_configured(self)

    stub = _StubCompositor()

    GLCompositorWidget._start_render_strategy(stub)

    assert stub._render_timer_fps == 60
    assert calls == [("target", 60), ("configure", 60), "resume"]
