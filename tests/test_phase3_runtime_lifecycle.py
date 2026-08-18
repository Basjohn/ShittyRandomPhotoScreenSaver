"""Phase 3 runtime-generation, GL teardown, and churn gates."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine import image_pipeline as image_pipeline_module
from engine.image_pipeline import (
    _apply_display_pixmap_with_perf,
    _pixmap_from_image_with_perf,
    _schedule_engine_delay,
)
from rendering.gl_compositor_pkg import gl_lifecycle
from rendering.gl_programs import texture_manager as texture_manager_module
from rendering.gl_programs.texture_manager import GLTextureManager
from rendering.gl_programs.geometry_manager import GLGeometryManager
from rendering.gl_programs.program_cache import GLProgramCache
from rendering.gl_state_manager import GLContextState, GLStateManager
from widgets import spotify_bars_gl_overlay as overlay_module
from widgets.spotify_visualizer.media_bridge import destroy_parent_overlay
from tools.phase3_lifecycle_harness import run_harness
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget


def test_lifecycle_churn_50_settings_50_edit_50_mixed() -> None:
    report = run_harness(50)

    assert report["total_cycles"] == 150
    assert report["scenarios"] == {"settings": 50, "edit": 50, "mixed": 50}
    assert report["stale_rejections"] == 150
    assert report["errors"] == []
    assert all(report["pass_criteria"].values())


def test_delayed_image_publication_rejects_old_runtime_manager() -> None:
    scheduled = []
    published = []
    old_manager = object()

    class _Scheduler:
        def single_shot(self, _delay_ms, callback):
            scheduled.append(callback)

    class _Engine:
        def __init__(self):
            self.thread_manager = _Scheduler()
            self.display_manager = old_manager
            self._runtime_generation = 4
            self._shutting_down = False
            self.rejections = []

        def _record_stale_runtime_callback(self, label, generation):
            self.rejections.append((label, generation))

    engine = _Engine()
    _schedule_engine_delay(
        engine,
        10,
        lambda: published.append("old-runtime-publication"),
        reason="phase3_test_delay",
    )
    engine._runtime_generation = 5
    engine.display_manager = object()

    scheduled.pop()()

    assert published == []
    assert engine.rejections == [("phase3_test_delay", 4)]


def test_delayed_image_publication_logs_reason_display_and_nested_cost(monkeypatch) -> None:
    scheduled = []
    published = []
    records = []
    manager = object()

    class _Scheduler:
        def single_shot(self, delay_ms, callback):
            scheduled.append((delay_ms, callback))

    engine = SimpleNamespace(
        thread_manager=_Scheduler(),
        display_manager=manager,
        _runtime_generation=9,
        _shutting_down=False,
    )
    ticks = iter((10.000, 10.012, 10.014, 10.020))
    monkeypatch.setattr(image_pipeline_module, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(image_pipeline_module.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(
        image_pipeline_module.logger,
        "info",
        lambda message, *args: records.append(message % args),
    )

    _schedule_engine_delay(
        engine,
        10,
        lambda: published.append("current-runtime-publication"),
        reason="phase3_perf_delay",
        display_index=1,
        callable_label="display_image_apply",
    )

    assert scheduled[0][0] == 10
    scheduled[0][1]()

    assert published == ["current-runtime-publication"]
    assert len(records) == 1
    assert "[PERF] [IMAGE_UI_DELAY]" in records[0]
    assert "reason=phase3_perf_delay" in records[0]
    assert "display=1" in records[0]
    assert "callable=display_image_apply" in records[0]
    assert "generation=9" in records[0]
    assert "queue_late_ms=2.00" in records[0]
    assert "guard_ms=2.00" in records[0]
    assert "callback_ms=6.00" in records[0]
    assert "total_age_ms=20.00" in records[0]
    assert "scheduled_mono_ms=10000.000" in records[0]
    assert "due_mono_ms=10010.000" in records[0]
    assert "start_mono_ms=10012.000" in records[0]
    assert "end_mono_ms=10020.000" in records[0]
    assert "outcome=completed" in records[0]


def test_delayed_image_publication_logs_stale_without_callback_cost(monkeypatch) -> None:
    scheduled = []
    records = []
    old_manager = object()

    class _Scheduler:
        def single_shot(self, _delay_ms, callback):
            scheduled.append(callback)

    engine = SimpleNamespace(
        thread_manager=_Scheduler(),
        display_manager=old_manager,
        _runtime_generation=3,
        _shutting_down=False,
    )
    ticks = iter((20.000, 20.012, 20.013, 20.014))
    monkeypatch.setattr(image_pipeline_module, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(image_pipeline_module.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(
        image_pipeline_module.logger,
        "info",
        lambda message, *args: records.append(message % args),
    )

    _schedule_engine_delay(engine, 10, lambda: pytest.fail("stale payload ran"), reason="stale")
    engine._runtime_generation = 4
    engine.display_manager = object()
    scheduled.pop()()

    delay_record = next(record for record in records if "[IMAGE_UI_DELAY]" in record)
    assert "guard_ms=1.00" in delay_record
    assert "callback_ms=0.00" in delay_record
    assert "outcome=stale" in delay_record


def test_delayed_image_publication_logs_payload_error_cost(monkeypatch) -> None:
    scheduled = []
    records = []
    manager = object()

    class _Scheduler:
        def single_shot(self, _delay_ms, callback):
            scheduled.append(callback)

    engine = SimpleNamespace(
        thread_manager=_Scheduler(),
        display_manager=manager,
        _runtime_generation=7,
        _shutting_down=False,
    )
    ticks = iter((30.000, 30.011, 30.012, 30.017))
    monkeypatch.setattr(image_pipeline_module, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(image_pipeline_module.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(
        image_pipeline_module.logger,
        "info",
        lambda message, *args: records.append(message % args),
    )

    def _fail() -> None:
        raise RuntimeError("payload failed")

    _schedule_engine_delay(engine, 10, _fail, reason="error")
    with pytest.raises(RuntimeError, match="payload failed"):
        scheduled.pop()()

    assert "guard_ms=1.00" in records[0]
    assert "callback_ms=5.00" in records[0]
    assert "outcome=error" in records[0]


def test_image_ui_conversion_segment_logs_bounded_cost(monkeypatch) -> None:
    records = []
    image = SimpleNamespace(width=lambda: 3840, height=lambda: 2160)
    pixmap = object()
    ticks = iter((40.000, 40.004))
    monkeypatch.setattr(image_pipeline_module, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(image_pipeline_module.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(
        image_pipeline_module,
        "QPixmap",
        SimpleNamespace(fromImage=lambda candidate: pixmap if candidate is image else None),
    )
    monkeypatch.setattr(
        image_pipeline_module.logger,
        "info",
        lambda message, *args: records.append(message % args),
    )

    assert _pixmap_from_image_with_perf(
        image,
        reason="current_image",
        display_index=1,
    ) is pixmap
    assert records == [
        "[PERF] [IMAGE_UI_SEGMENT] reason=current_image display=1 "
        "stage=qimage_to_qpixmap duration_ms=4.00 size=3840x2160"
    ]


@pytest.mark.parametrize(
    ("processed_setter", "expected_stage"),
    ((True, "set_processed_image"), (False, "set_image")),
)
def test_image_ui_apply_segment_preserves_both_setter_paths(
    monkeypatch,
    processed_setter,
    expected_stage,
) -> None:
    calls = []
    records = []
    processed = SimpleNamespace(width=lambda: 1920, height=lambda: 1080)
    original = object()

    class _Display:
        def set_image(self, pixmap, path):
            calls.append(("set_image", pixmap, path))

    display = _Display()
    if processed_setter:
        display.set_processed_image = lambda pixmap, original_pixmap, path: calls.append(
            ("set_processed_image", pixmap, original_pixmap, path)
        )
    ticks = iter((50.000, 50.003))
    monkeypatch.setattr(image_pipeline_module, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(image_pipeline_module.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(
        image_pipeline_module.logger,
        "info",
        lambda message, *args: records.append(message % args),
    )

    _apply_display_pixmap_with_perf(
        display,
        processed,
        original,
        "image.jpg",
        reason="transition_display_immediate",
        display_index=0,
    )

    assert calls[0][0] == expected_stage
    assert f"stage={expected_stage}" in records[0]
    assert "duration_ms=3.00" in records[0]
    assert "size=1920x1080" in records[0]


def test_deferred_gl_warmup_rejects_stopped_generation(monkeypatch) -> None:
    scheduled = []
    warmed = []

    class _WeakrefableWidget:
        _gl_lifecycle_generation = 8
        _render_shutdown_requested = False

    widget = _WeakrefableWidget()

    monkeypatch.setattr(
        gl_lifecycle.ThreadManager,
        "single_shot",
        staticmethod(lambda _delay_ms, callback: scheduled.append(callback)),
    )

    gl_lifecycle._schedule_deferred_gl_warmup(
        widget,
        lambda _widget: warmed.append("ran"),
    )
    widget._render_shutdown_requested = True
    widget._gl_lifecycle_generation = 9
    scheduled.pop()()

    assert warmed == []


def test_live_gl_resources_require_valid_context(monkeypatch) -> None:
    pipeline = SimpleNamespace(initialized=True)
    # No QRhi attached is the QRhiWidget equivalent of the retired
    # QOpenGLWidget "context is invalid" state: live SRPSS GL resources cannot
    # be deleted, so teardown must fail closed and retain ownership.
    widget = SimpleNamespace(
        _gl_pipeline=pipeline,
        _texture_manager=None,
        _startup_transition_warm_queue=[],
        _startup_transition_resource_warm_queue=[],
        _startup_transition_resource_warm_types=set(),
        _rhi_gl=SimpleNamespace(
            is_attached=lambda: False,
            make_current=lambda: False,
            context=None,
            generation=0,
        ),
        _reset_pipeline_state=lambda: None,
    )
    monkeypatch.setattr(gl_lifecycle, "gl", object())

    with pytest.raises(RuntimeError, match="no QRhi OpenGL context is attached"):
        gl_lifecycle.cleanup_gl_pipeline(widget)

    assert pipeline.initialized is True


def test_strict_texture_cleanup_retains_failed_resource_ownership(monkeypatch) -> None:
    class _FailingGL:
        def glDeleteTextures(self, _count, _ids):
            raise RuntimeError("driver refused texture delete")

    monkeypatch.setattr(texture_manager_module, "gl", _FailingGL())
    manager = GLTextureManager(owner="phase3-test", generation=12)
    manager._initialized = True
    manager._texture_cache = {1: 91}
    manager._texture_lru = [1]

    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        manager.cleanup(strict=True)

    assert manager._initialized is True
    assert manager._texture_cache == {1: 91}
    assert manager._texture_lru == [1]

def test_strict_program_cleanup_retains_only_failed_owner_ids() -> None:
    class _SelectiveGL:
        def __init__(self):
            self.deleted = []

        def glDeleteProgram(self, program_id):
            if int(program_id) == 22:
                raise RuntimeError("driver refused program delete")
            self.deleted.append(int(program_id))

    cache = GLProgramCache()
    cache._programs = {"crossfade": 11, "wipe": 22}
    cache._uniforms = {"crossfade": {"u": 1}, "wipe": {"u": 2}}
    cache._initialized = {"crossfade", "wipe"}
    fake_gl = _SelectiveGL()

    with pytest.raises(RuntimeError, match="program cache cleanup incomplete"):
        cache.cleanup(strict=True, gl_api=fake_gl)

    assert fake_gl.deleted == [11]
    assert cache.get_program_ids() == {22}
    assert cache._programs == {"wipe": 22}
    assert cache._uniforms == {"wipe": {"u": 2}}
    assert cache._initialized == {"wipe"}

def test_strict_geometry_cleanup_retains_only_failed_owner_ids() -> None:
    class _SelectiveGL:
        def __init__(self):
            self.deleted_buffers = []
            self.deleted_vaos = []

        def glDeleteBuffers(self, _count, ids):
            handle = int(ids[0])
            if handle == 22:
                raise RuntimeError("driver refused geometry buffer delete")
            self.deleted_buffers.append(handle)

        def glDeleteVertexArrays(self, _count, ids):
            self.deleted_vaos.append(int(ids[0]))

    manager = GLGeometryManager(owner="phase3-geometry", generation=12)
    manager._initialized = True
    manager._quad_vbo = 11
    manager._quad_vao = 12
    manager._box_vbo = 22
    manager._box_vao = 23
    manager._quad_vbo_rid = "rid-11"
    manager._quad_vao_rid = "rid-12"
    manager._box_vbo_rid = "rid-22"
    manager._box_vao_rid = "rid-23"
    released = []
    manager._release_resource_tracking = lambda rid: released.append(rid)
    fake_gl = _SelectiveGL()

    with pytest.raises(RuntimeError, match="geometry cleanup incomplete"):
        manager.cleanup(strict=True, gl_api=fake_gl)

    assert fake_gl.deleted_buffers == [11]
    assert fake_gl.deleted_vaos == [12, 23]
    assert manager._quad_vbo == 0
    assert manager._quad_vao == 0
    assert manager._box_vbo == 22
    assert manager._box_vao == 0
    assert manager._box_vbo_rid == "rid-22"
    assert released == ["rid-11", "rid-12", "rid-23"]
    assert manager.has_live_resources()
    assert manager._initialized is True

def test_strict_visualizer_overlay_cleanup_retains_failed_program_owner(monkeypatch) -> None:
    class _SelectiveGL:
        def __init__(self):
            self.deleted = []

        def glDeleteProgram(self, program_id):
            if int(program_id) == 22:
                raise RuntimeError("driver refused visualizer program delete")
            self.deleted.append(int(program_id))

        def glDeleteBuffers(self, _count, _ids):
            raise AssertionError("no VBO expected")

        def glDeleteVertexArrays(self, _count, _ids):
            raise AssertionError("no VAO expected")

    context = object()
    state = GLStateManager("phase3-visualizer-overlay")
    assert state.transition(GLContextState.INITIALIZING)
    assert state.transition(GLContextState.READY)
    released = []
    overlay = SimpleNamespace(
        _gl_program_warm_timer=None,
        _gl_program_warm_queue=[],
        _gl_programs={"spectrum": 11, "bubble": 22},
        _gl_uniforms={"spectrum": {"u": 1}, "bubble": {"u": 2}},
        _gl_program=11,
        _gl_program_rids={"spectrum": "rid-11", "bubble": "rid-22"},
        _gl_mask_program=None,
        _gl_vbo=None,
        _gl_vbo_rid=None,
        _gl_vao=None,
        _gl_vao_rid=None,
        _gl_state=state,
        _publication_target_compositor=lambda: SimpleNamespace(
            _rhi_gl=SimpleNamespace(
                is_attached=lambda: True,
                make_current=lambda: True,
                context=context,
                generation=1,
            )
        ),
        _release_resource_tracking=lambda rid: released.append(rid),
    )
    fake_gl = _SelectiveGL()
    monkeypatch.setattr(overlay_module, "gl", fake_gl)
    monkeypatch.setattr(
        overlay_module,
        "QCoreApplication",
        SimpleNamespace(instance=lambda: None),
    )
    monkeypatch.setattr(
        overlay_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=lambda: context),
    )

    with pytest.raises(RuntimeError, match="visualizer program delete"):
        overlay_module.SpotifyBarsGLOverlay.cleanup_gl(overlay)

    assert fake_gl.deleted == [11]
    assert overlay._gl_programs == {"bubble": 22}
    assert overlay._gl_uniforms == {"bubble": {"u": 2}}
    assert overlay._gl_program_rids == {"bubble": "rid-22"}
    assert overlay._gl_program == 22
    assert released == ["rid-11"]
    assert state.get_state() == GLContextState.DESTROYING


def test_strict_visualizer_overlay_cleanup_retains_failed_timer_query_owner(monkeypatch) -> None:
    class _TimerQueries:
        def __init__(self) -> None:
            self.poll_calls = 0
            self.cleanup_calls = 0

        def has_live_queries(self) -> bool:
            return True

        def poll(self, _gl) -> None:
            self.poll_calls += 1

        def cleanup(self, _gl) -> None:
            self.cleanup_calls += 1
            raise RuntimeError("driver refused timer query delete")

    context = object()
    state = GLStateManager("phase3-visualizer-query-owner")
    assert state.transition(GLContextState.INITIALIZING)
    assert state.transition(GLContextState.READY)
    timer_queries = _TimerQueries()
    overlay = SimpleNamespace(
        _gl_program_warm_timer=None,
        _gl_program_warm_queue=[],
        _gl_programs={},
        _gl_uniforms={},
        _gl_program=None,
        _gl_program_rids={},
        _gl_mask_program=None,
        _gl_vbo=None,
        _gl_vbo_rid=None,
        _gl_vao=None,
        _gl_vao_rid=None,
        _gpu_timer_queries=timer_queries,
        _gl_state=state,
        _publication_target_compositor=lambda: SimpleNamespace(
            _rhi_gl=SimpleNamespace(
                is_attached=lambda: True,
                make_current=lambda: True,
                context=context,
                generation=1,
            )
        ),
        _release_resource_tracking=lambda _rid: None,
    )
    monkeypatch.setattr(overlay_module, "gl", object())
    monkeypatch.setattr(
        overlay_module,
        "QCoreApplication",
        SimpleNamespace(instance=lambda: None),
    )
    monkeypatch.setattr(
        overlay_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=lambda: context),
    )

    with pytest.raises(RuntimeError, match="timer query delete"):
        overlay_module.SpotifyBarsGLOverlay.cleanup_gl(overlay)

    assert timer_queries.poll_calls == 1
    assert timer_queries.cleanup_calls == 1
    assert state.get_state() == GLContextState.DESTROYING


def test_visualizer_overlay_destroy_retains_parent_reference_on_gl_failure() -> None:
    class _Overlay:
        def __init__(self):
            self.delete_calls = 0

        def hide(self):
            return None

        def clear_overlay_buffer(self):
            return None

        def update(self):
            return None

        def cleanup_gl(self):
            raise RuntimeError("strict overlay cleanup failed")

        def deleteLater(self):
            self.delete_calls += 1

    overlay = _Overlay()
    parent = SimpleNamespace(
        _spotify_bars_overlay=overlay,
        _pixel_shift_manager=None,
    )
    widget = SimpleNamespace(parent=lambda: parent)

    with pytest.raises(RuntimeError, match="strict overlay cleanup failed"):
        destroy_parent_overlay(widget, reason="phase3-test")

    assert parent._spotify_bars_overlay is overlay
    assert overlay.delete_calls == 0

def test_visualizer_cleanup_destroys_overlay_after_prior_stop() -> None:
    events = []
    visualizer = SimpleNamespace(
        _engine=object(),
        stop=lambda: events.append("stop"),
        detach_from_animation_manager=lambda: events.append("detach"),
        _destroy_parent_overlay=lambda *, reason: events.append(f"destroy:{reason}"),
    )

    SpotifyVisualizerWidget.cleanup(visualizer)

    assert events == ["stop", "detach", "destroy:widget_cleanup"]
    assert visualizer._engine is None
