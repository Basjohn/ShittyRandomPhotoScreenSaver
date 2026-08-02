import logging

import pytest

from types import SimpleNamespace

from rendering.adaptive_timer import _queue_safe_widget_update
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.compositor_metrics import _is_active_transition_paint_window
from rendering.gl_compositor_pkg.compositor_metrics import _transition_label
from rendering.gl_compositor_pkg.compositor_metrics import record_paint_metrics
from rendering.gl_compositor_pkg.compositor_metrics import record_render_timer_tick
from rendering.gl_compositor_pkg.metrics import _PaintMetrics
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


def test_transition_label_uses_display_snapshot_name_when_frame_state_is_active():
    context = {
        "current_transition": None,
        "has_frame_state": True,
        "display_transition": {
            "running": True,
            "name": "GLCompositorBlockSpinTransition",
            "last_transition": None,
        },
    }

    assert _transition_label(context) == "GLCompositorBlockSpinTransition"


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

        def _record_paint_metrics(self, _paint_duration_ms, **_kwargs):
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


def test_render_timer_metrics_count_only_accepted_update_requests(monkeypatch):
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.compositor_metrics.is_perf_metrics_enabled",
        lambda: True,
    )

    class _Metrics:
        def record_tick(self, *, accepted_update=True):
            return None

    paint_metrics = _PaintMetrics(label="wipe", slow_threshold_ms=24.0)
    widget = SimpleNamespace(
        _render_timer_metrics=_Metrics(),
        _paint_metrics=paint_metrics,
    )

    record_render_timer_tick(widget, accepted_update=False)
    record_render_timer_tick(widget, accepted_update=True)

    assert paint_metrics.render_request_count == 1
    assert paint_metrics.skipped_request_count == 1


@pytest.mark.parametrize(
    ("gap_ms", "severity"),
    ((40.0, "over_33"), (51.0, "over_50")),
)
def test_frame_gap_owner_logs_one_bounded_record_with_delivery_deltas(
    monkeypatch,
    caplog,
    gap_ms,
    severity,
):
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.compositor_metrics.is_perf_metrics_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.compositor_metrics.time",
        SimpleNamespace(time=lambda: 10.0),
    )

    class _Manager:
        def __init__(self):
            self.snapshot = {
                "compute_callbacks_delivered": 10,
                "compute_queue_depth": 0,
                "compute_worker_active": 0,
                "compute_last_queue_wait_ms": 0.2,
                "compute_last_execution_ms": 1.2,
                "compute_last_callback_ms": 0.3,
                "io_callbacks_delivered": 4,
                "io_queue_depth": 0,
                "io_worker_active": 0,
                "io_last_queue_wait_ms": 0.1,
                "io_last_execution_ms": 0.8,
                "io_last_callback_ms": 0.2,
                "ui_delivered": 20,
                "ui_failed": 0,
                "ui_active": 0,
                "ui_queue_depth": 0,
                "ui_last_callback": "MediaWidget.apply",
                "ui_last_duration_ms": 0.4,
                "ui_last_completed_ts": 0.0,
            }

        def get_frame_delivery_snapshot(self):
            return dict(self.snapshot)

    manager = _Manager()
    media = SimpleNamespace(
        _thread_manager=manager,
        _perf_media_display_total=5,
        _perf_media_emit_total=2,
        _perf_media_update_request_total=4,
    )
    visualizer = SimpleNamespace(
        _vis_mode_str="bubble",
        _mode_transition_phase=0,
        _waiting_for_fresh_engine_frame=False,
        _waiting_for_fresh_frame=False,
        _bubble_compute_pending=False,
        _bubble_pending_result=object(),
        _bubble_visible_source_ts=9.900,
        _bubble_visible_simulation_ts=9.950,
        _bubble_visible_render_state_ts=9.980,
    )
    overlay = SimpleNamespace(
        _perf_set_state_total=30,
        _perf_update_request_total=30,
        _perf_paint_total=28,
    )
    parent = SimpleNamespace(
        screen_index=0,
        _thread_manager=manager,
        media_widget=media,
        spotify_visualizer_widget=visualizer,
        _spotify_bars_overlay=overlay,
    )
    metrics = _PaintMetrics(label="wipe", slow_threshold_ms=24.0)
    widget = SimpleNamespace(
        parent=lambda: parent,
        screen_index=0,
        _paint_metrics=metrics,
        _paint_slow_threshold_ms=24.0,
        _paint_warning_last_ts=0.0,
        _render_timer_fps=165,
        _animation_manager=None,
        describe_stall_context=lambda: {
            "current_transition": "wipe",
            "has_frame_state": True,
        },
    )

    metrics.record_render_request(accepted_update=True, request_ts=0.990)
    record_paint_metrics(
        widget,
        1.0,
        paint_start_ts=1.000,
        paint_end_ts=1.001,
    )

    manager.snapshot["compute_callbacks_delivered"] += 2
    manager.snapshot["ui_delivered"] += 1
    media._perf_media_display_total += 1
    media._perf_media_update_request_total += 1
    overlay._perf_set_state_total += 1
    overlay._perf_update_request_total += 1
    overlay._perf_paint_total += 1
    metrics.record_render_request(accepted_update=True, request_ts=1.020)

    with caplog.at_level(
        logging.WARNING,
        logger="rendering.gl_compositor_pkg.compositor_metrics",
    ):
        record_paint_metrics(
            widget,
            1.0,
            paint_start_ts=1.000 + gap_ms / 1000.0,
            paint_end_ts=1.001 + gap_ms / 1000.0,
        )

    owner_records = [
        record.message
        for record in caplog.records
        if "[PERF][FRAME_GAP_OWNER]" in record.message
    ]
    assert len(owner_records) == 1
    message = owner_records[0]
    assert f"severity={severity}" in message
    assert "vis_mode=bubble" in message
    assert "source_age_ms=100.00" in message
    assert "simulation_age_ms=50.00" in message
    assert "render_state_age_ms=20.00" in message
    assert "bubble_result=1" in message
    assert "compute_callbacks=2" in message
    assert "ui_callbacks=1" in message
    assert "media_display=1" in message
    assert "media_repaints=1" in message
    assert "overlay_set=1" in message
    assert "overlay_repaints=1" in message
    assert "overlay_paints=1" in message
    assert "render_requests=1" in message


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


def test_paint_metrics_keep_a_bounded_monotonic_delivery_window():
    metrics = _PaintMetrics(label="wipe", slow_threshold_ms=24.0)

    metrics.record_render_request(accepted_update=False, request_ts=1.000)
    metrics.record_render_request(accepted_update=True, request_ts=1.000)
    metrics.record_paint_start(1.010, scene_generation=7)
    metrics.record(2.0, paint_start_ts=1.010, paint_end_ts=1.012)

    metrics.record_render_request(accepted_update=True, request_ts=1.020)
    metrics.record_paint_start(1.030, scene_generation=7)
    metrics.record(4.0, paint_start_ts=1.030, paint_end_ts=1.034)

    summary = metrics.timing_summary()

    assert summary["window_frames"] == 2
    assert summary["requests"] == 2
    assert summary["skipped_requests"] == 1
    assert summary["request_acceptance_pct"] == pytest.approx(200.0 / 3.0)
    assert summary["last_presented_frame_index"] == 2
    assert summary["last_scene_generation"] == 7
    assert summary["interval_max_ms"] == pytest.approx(20.0)
    assert summary["interval_over_25_ms"] == 0
    assert summary["interval_over_33_ms"] == 0
    assert summary["interval_over_50_ms"] == 0
    assert summary["interval_over_100_ms"] == 0
    assert summary["duration_max_ms"] == 4.0
    assert summary["request_age_max_ms"] == pytest.approx(10.0)
    assert metrics.presented_frame_index == 2
    assert [sample.scene_generation for sample in metrics.samples] == [7, 7]


def test_paint_metrics_window_drops_oldest_samples():
    metrics = _PaintMetrics(label="wipe", slow_threshold_ms=24.0)
    for index in range(513):
        start = float(index)
        metrics.record_paint_start(start, scene_generation=index)
        metrics.record(1.0, paint_start_ts=start, paint_end_ts=start + 0.001)

    assert len(metrics.samples) == 512
    assert metrics.samples[0].frame_index == 2
    assert metrics.samples[-1].scene_generation == 512
