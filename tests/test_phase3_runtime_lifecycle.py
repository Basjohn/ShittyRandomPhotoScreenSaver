"""Phase 3 runtime-generation, GL teardown, and churn gates."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.image_pipeline import _schedule_engine_delay
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


def test_deferred_gl_warmup_rejects_stopped_generation(monkeypatch) -> None:
    scheduled = []
    warmed = []
    widget = SimpleNamespace(
        _gl_lifecycle_generation=8,
        _render_shutdown_requested=False,
    )

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
    widget = SimpleNamespace(
        _gl_pipeline=pipeline,
        _texture_manager=None,
        _startup_transition_warm_queue=[],
        _startup_transition_resource_warm_queue=[],
        _startup_transition_resource_warm_types=set(),
        isValid=lambda: False,
        _reset_pipeline_state=lambda: None,
    )
    monkeypatch.setattr(gl_lifecycle, "gl", object())

    with pytest.raises(RuntimeError, match="context is invalid"):
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
        isValid=lambda: True,
        makeCurrent=lambda: None,
        doneCurrent=lambda: None,
        context=lambda: context,
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
