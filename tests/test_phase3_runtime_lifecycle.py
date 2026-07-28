"""Phase 3 runtime-generation, GL teardown, and churn gates."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.image_pipeline import _schedule_engine_delay
from rendering.gl_compositor_pkg import gl_lifecycle
from rendering.gl_programs import texture_manager as texture_manager_module
from rendering.gl_programs.texture_manager import GLTextureManager
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
