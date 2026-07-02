"""Regression tests for GLCompositorWidget transition lifecycle safety.

These tests focus on ensuring that compositor transitions can start and tear
down without raising, even when the GL pipeline is unavailable (our CI
environment). They guard against missing helper hooks when adding new
instrumentation around transition cancellation.
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget

from core.animation import AnimationManager, EasingCurve
from core.animation.frame_interpolator import FrameState
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.paint import _sync_transition_progress_from_frame_state
from rendering.gl_profiler import TransitionProfiler
from rendering.gl_transition_renderer import _aspect_fill_source_rect
from transitions.base_transition import WipeDirection
from tests._gl_test_utils import solid_pixmap


class DummySettings:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        if key in self._data:
            return self._data[key]
        if "." in key:
            cur = self._data
            for part in key.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return default
            return cur
        return default

    def get_widgets_map(self):
        widgets = self._data.get("widgets", {})
        if isinstance(widgets, dict):
            return widgets
        return {}


def _setup_compositor(monkeypatch) -> tuple[QWidget, GLCompositorWidget]:
    """Create a GLCompositorWidget with frame pacing patched out."""
    parent = QWidget()
    parent.resize(64, 64)
    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    parent.show()

    def _fake_start_frame_pacing(duration_sec: float) -> FrameState:
        comp._frame_state = FrameState(duration=duration_sec)
        return comp._frame_state

    monkeypatch.setattr(comp, "_start_frame_pacing", _fake_start_frame_pacing)
    monkeypatch.setattr(comp, "_pre_upload_textures", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_release_transition_textures", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_start_render_timer", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_stop_render_timer", lambda *a, **k: None)
    comp._desync_delay_ms = 0
    return parent, comp


def test_base_image_source_crop_preserves_aspect_fill():
    source = _aspect_fill_source_rect(1000, 500, 500, 500)

    assert source.x() == 250
    assert source.y() == 0
    assert source.width() == 500
    assert source.height() == 500


def test_paint_time_progress_sync_ticks_profiler_for_debug_overlay():
    class _FrameState:
        def get_interpolated_progress(self):
            return 0.42

    class _TransitionState:
        progress = 0.0

    class _Widget:
        _frame_state = _FrameState()
        _slide = _TransitionState()
        _blockspin = None
        _blockflip = None
        _raindrops = None
        _warp = None
        _diffuse = None
        _blinds = None
        _crumble = None
        _particle = None
        _burn = None
        _crossfade = None
        _wipe = None

        def __init__(self):
            self._profiler = TransitionProfiler()

    widget = _Widget()
    widget._profiler.start("slide")

    _sync_transition_progress_from_frame_state(widget)

    assert widget._slide.progress == pytest.approx(0.42)
    assert widget._profiler._profiles["slide"].frame_count == 1


@pytest.mark.qt_no_exception_capture
def test_clear_all_transitions_cancels_active_animation(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841 - parent keeps widget alive
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    anim_id = comp.start_slide(
        old_pm,
        new_pm,
        old_start=QPoint(0, 0),
        old_end=QPoint(64, 64),
        new_start=QPoint(0, 0),
        new_end=QPoint(64, 64),
        duration_ms=200,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    comp._clear_all_transitions()

    assert anim_mgr.get_active_count() == 0
    assert comp._current_anim_id is None

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_gl_prewarm_initializes_shared_compositor(qtbot):
    """GL prewarm should create a shared compositor that can make the GL context current."""
    from rendering.display_widget import DisplayWidget
    from rendering.display_modes import DisplayMode

    settings = DummySettings(
        {
            "display.hw_accel": True,
            "widgets": {"clock": {"enabled": False}},
        }
    )

    widget = DisplayWidget(screen_index=0, display_mode=DisplayMode.FILL, settings_manager=settings)
    qtbot.addWidget(widget)

    widget.show_on_screen()
    qtbot.wait(800)

    comp = getattr(widget, "_gl_compositor", None)
    assert isinstance(comp, GLCompositorWidget), "GL compositor should exist after prewarm"

    try:
        comp.makeCurrent()
    except Exception:
        pytest.skip("GL context not available for GLCompositorWidget prewarm")
    finally:
        widget.close()


@pytest.mark.qt_no_exception_capture
def test_cancel_current_transition_snaps_to_new_pixmap(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.green)
    comp.set_base_pixmap(old_pm)

    anim_id = comp.start_slide(
        old_pm,
        new_pm,
        old_start=QPoint(0, 0),
        old_end=QPoint(64, 64),
        new_start=QPoint(0, 0),
        new_end=QPoint(64, 64),
        duration_ms=200,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    comp.cancel_current_transition(snap_to_new=True)

    assert anim_mgr.get_active_count() == 0
    assert comp._current_anim_id is None
    assert comp._base_pixmap is not None
    assert comp._base_pixmap.cacheKey() == new_pm.cacheKey()

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_transition_start_ensures_program_ready_on_first_use(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    ensured: list[object] = []
    monkeypatch.setattr(comp, "_ensure_transition_program_ready", lambda identity: ensured.append(identity) or True)

    anim_id = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    assert "wipe" in ensured

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_stop_rendering_invalidates_late_lazy_animation_callback(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    scheduled: list[tuple[int, object]] = []
    animate_calls: list[object] = []
    update_calls: list[float] = []
    complete_calls: list[str] = []

    class _AnimationManager:
        def animate_custom(self, **kwargs):
            animate_calls.append(kwargs)
            return "anim-late"

    monkeypatch.setattr(comp, "_ensure_transition_program_ready", lambda _label: True)
    monkeypatch.setattr(comp, "_begin_paint_metrics", lambda _label: None)
    monkeypatch.setattr(comp, "_start_render_timer", lambda: None)
    monkeypatch.setattr(
        "core.threading.manager.ThreadManager.single_shot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    anim_id = comp._start_transition_animation(
        duration_ms=200,
        easing=EasingCurve.LINEAR,
        animation_manager=_AnimationManager(),
        update_callback=lambda progress: update_calls.append(progress),
        on_complete=lambda: complete_calls.append("complete"),
        transition_label="wipe",
    )

    assert anim_id.startswith("wipe:timeline:")
    assert animate_calls == []
    assert scheduled and scheduled[0][0] == 200
    comp.stop_rendering(reason="test-late-callback")

    scheduled[0][1]()

    assert update_calls == []
    assert complete_calls == []


@pytest.mark.qt_no_exception_capture
def test_transition_render_timer_starts_before_first_animation_tick(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    calls: list[str] = []
    scheduled: list[tuple[int, object]] = []
    update_calls: list[float] = []
    complete_calls: list[str] = []

    class _AnimationManager:
        def animate_custom(self, **kwargs):
            calls.append("animate")
            return "anim-delayed"

    monkeypatch.setattr(comp, "_ensure_transition_program_ready", lambda _label: calls.append("program") or True)
    monkeypatch.setattr(comp, "_begin_paint_metrics", lambda _label: calls.append("paint_metrics"))
    monkeypatch.setattr(comp, "_start_render_timer", lambda: calls.append("render_timer"))
    monkeypatch.setattr(
        "core.threading.manager.ThreadManager.single_shot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    anim_id = comp._start_transition_animation(
        duration_ms=200,
        easing=EasingCurve.LINEAR,
        animation_manager=_AnimationManager(),
        update_callback=lambda progress: update_calls.append(progress),
        on_complete=lambda: complete_calls.append("complete"),
        transition_label="wipe",
    )

    assert anim_id.startswith("wipe:timeline:")
    assert calls == ["program", "paint_metrics", "render_timer"]
    assert scheduled and scheduled[0][0] == 200
    assert "animate" not in calls
    assert update_calls == []

    scheduled[0][1]()

    assert update_calls == [1.0]
    assert complete_calls == ["complete"]


@pytest.mark.qt_no_exception_capture
def test_non_crossfade_transition_uses_shared_desync_start(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    monkeypatch.setattr(comp, "_apply_desync_strategy", lambda duration_ms: (75, duration_ms + 75))
    scheduled: list[int] = []
    started: list[int] = []
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.ThreadManager.single_shot",
        staticmethod(lambda delay, callback: scheduled.append(delay)),
    )

    start_calls: list[int] = []
    monkeypatch.setattr(comp, "_clear_all_transitions", lambda: start_calls.append(-1))
    monkeypatch.setattr(comp, "_prepare_wipe_textures", lambda: True)
    monkeypatch.setattr(comp, "_pre_upload_textures", lambda prep_fn: prep_fn())
    monkeypatch.setattr(
        comp,
        "_start_transition_animation",
        lambda duration_ms, *args, **kwargs: start_calls.append(duration_ms) or "anim-1",
    )

    anim_id = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
        on_started=lambda duration_ms: started.append(duration_ms),
    )

    assert anim_id is not None
    assert "wipe:deferred:" in anim_id
    assert scheduled == [75]
    assert started == []
    assert start_calls == []

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_deferred_desync_start_is_suppressed_after_compositor_stop(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    scheduled: list[object] = []
    start_calls: list[int] = []
    monkeypatch.setattr(comp, "_apply_desync_strategy", lambda duration_ms: (75, duration_ms + 75))
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.ThreadManager.single_shot",
        staticmethod(lambda _delay, callback: scheduled.append(callback)),
    )
    monkeypatch.setattr(comp, "_clear_all_transitions", lambda: None)
    monkeypatch.setattr(comp, "_prepare_wipe_textures", lambda: True)
    monkeypatch.setattr(comp, "_pre_upload_textures", lambda _prep: None)
    monkeypatch.setattr(
        comp,
        "_start_transition_animation",
        lambda duration_ms, *args, **kwargs: start_calls.append(duration_ms) or "anim-late",
    )

    token = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert token is not None
    assert scheduled
    comp.stop_rendering(reason="test-deferred-stop")
    scheduled[0]()

    assert start_calls == []

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_deferred_desync_start_is_suppressed_after_compositor_deleted(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    scheduled: list[object] = []
    start_calls: list[int] = []
    monkeypatch.setattr(comp, "_apply_desync_strategy", lambda duration_ms: (75, duration_ms + 75))
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.ThreadManager.single_shot",
        staticmethod(lambda _delay, callback: scheduled.append(callback)),
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.Shiboken",
        type("_InvalidShiboken", (), {"isValid": staticmethod(lambda _widget: False)})(),
    )
    monkeypatch.setattr(
        comp,
        "_start_transition_animation",
        lambda duration_ms, *args, **kwargs: start_calls.append(duration_ms) or "anim-late",
    )

    token = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert token is not None
    assert scheduled
    scheduled[0]()

    assert start_calls == []

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_raindrops_desync_returns_deferred_token_instead_of_unavailable(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    comp._gl_disabled_for_session = False
    comp._gl_pipeline = type(
        "_Pipeline",
        (),
        {"initialized": True, "raindrops_program": 1},
    )()
    monkeypatch.setattr(comp, "_apply_desync_strategy", lambda duration_ms: (50, duration_ms + 50))
    scheduled: list[int] = []
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.ThreadManager.single_shot",
        staticmethod(lambda delay, callback: scheduled.append(delay)),
    )

    anim_id = comp.start_raindrops(
        old_pm,
        new_pm,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    assert "raindrops:deferred:" in anim_id
    assert scheduled == [50]

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_apply_desync_strategy_bypasses_single_active_display(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)

    monkeypatch.setattr(parent, "get_all_instances", lambda: [parent], raising=False)
    comp._desync_delay_ms = 150

    delay_ms, compensated_duration = comp._apply_desync_strategy(5000)

    assert delay_ms == 0
    assert compensated_duration == 5000


@pytest.mark.qt_no_exception_capture
def test_warm_transition_resources_uses_single_current_context_cycle(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    comp._gl_disabled_for_session = False
    comp._gl_pipeline = type("_Pipeline", (), {"initialized": True})()
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle._ensure_hidden_shared_warmup_context",
        lambda widget: None,
    )

    calls: list[str] = []
    monkeypatch.setattr(comp, "_ensure_gl_pipeline_ready", lambda: True)
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.bind_transition_program_for_current_context",
        lambda widget, identity: calls.append(f"bind:{identity}") or True,
    )
    monkeypatch.setattr(
        comp,
        "_warm_pixmap_textures_in_current_context",
        lambda old_pixmap, new_pixmap: calls.append("textures") or True,
    )
    monkeypatch.setattr(
        comp,
        "_warm_transition_state_in_current_context",
        lambda transition_name, old_pixmap, new_pixmap: calls.append(f"state:{transition_name}") or True,
    )

    make_current_calls = {"count": 0}
    done_current_calls = {"count": 0}

    monkeypatch.setattr(
        comp,
        "makeCurrent",
        lambda: make_current_calls.__setitem__("count", make_current_calls["count"] + 1),
    )
    monkeypatch.setattr(
        comp,
        "doneCurrent",
        lambda: done_current_calls.__setitem__("count", done_current_calls["count"] + 1),
    )

    assert comp.warm_transition_resources("GLCompositorSlideTransition", old_pm, new_pm) is True
    assert calls == ["bind:GLCompositorSlideTransition", "textures", "state:GLCompositorSlideTransition"]
    assert make_current_calls["count"] == 1
    assert done_current_calls["count"] == 1


@pytest.mark.qt_no_exception_capture
def test_warm_transition_resources_skips_live_surface_when_hidden_context_is_unavailable(
    qt_app,
    monkeypatch,
    caplog,
):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    comp._gl_disabled_for_session = False
    comp._gl_pipeline = type("_Pipeline", (), {"initialized": True})()
    comp._base_pixmap = old_pm

    monkeypatch.setattr(comp, "isVisible", lambda: True)
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle._ensure_hidden_shared_warmup_context",
        lambda widget: None,
    )

    make_current_calls = {"count": 0}
    done_current_calls = {"count": 0}
    bind_calls: list[str] = []
    texture_calls: list[str] = []
    state_calls: list[str] = []

    monkeypatch.setattr(
        comp,
        "makeCurrent",
        lambda: make_current_calls.__setitem__("count", make_current_calls["count"] + 1),
    )
    monkeypatch.setattr(
        comp,
        "doneCurrent",
        lambda: done_current_calls.__setitem__("count", done_current_calls["count"] + 1),
    )
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.bind_transition_program_for_current_context",
        lambda widget, identity: bind_calls.append(str(identity)) or True,
    )
    monkeypatch.setattr(
        comp,
        "_warm_pixmap_textures_in_current_context",
        lambda old_pixmap, new_pixmap: texture_calls.append("textures") or True,
    )
    monkeypatch.setattr(
        comp,
        "_warm_transition_state_in_current_context",
        lambda transition_name, old_pixmap, new_pixmap: state_calls.append(str(transition_name)) or True,
    )

    with caplog.at_level(logging.WARNING):
        assert comp.warm_transition_resources("GLCompositorSlideTransition", old_pm, new_pm) is False

    assert make_current_calls["count"] == 0
    assert done_current_calls["count"] == 0
    assert bind_calls == []
    assert texture_calls == []
    assert state_calls == []
    assert any("deferring GLCompositorSlideTransition resource warmup to first-use warmup" in message for message in caplog.messages)


@pytest.mark.qt_no_exception_capture
def test_warm_shader_textures_skips_live_surface_when_hidden_context_is_unavailable(
    qt_app,
    monkeypatch,
    caplog,
):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    comp._gl_disabled_for_session = False
    comp._gl_pipeline = type("_Pipeline", (), {"initialized": True})()
    comp._base_pixmap = old_pm

    monkeypatch.setattr(comp, "_ensure_gl_pipeline_ready", lambda: True)
    monkeypatch.setattr(comp, "isVisible", lambda: True)
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle._ensure_hidden_shared_warmup_context",
        lambda widget: None,
    )

    make_current_calls = {"count": 0}
    done_current_calls = {"count": 0}
    texture_calls: list[str] = []

    monkeypatch.setattr(
        comp,
        "makeCurrent",
        lambda: make_current_calls.__setitem__("count", make_current_calls["count"] + 1),
    )
    monkeypatch.setattr(
        comp,
        "doneCurrent",
        lambda: done_current_calls.__setitem__("count", done_current_calls["count"] + 1),
    )
    monkeypatch.setattr(
        comp,
        "_warm_pixmap_textures_in_current_context",
        lambda old_pixmap, new_pixmap: texture_calls.append("textures") or True,
    )

    with caplog.at_level(logging.WARNING):
        comp.warm_shader_textures(old_pm, new_pm)

    assert make_current_calls["count"] == 0
    assert done_current_calls["count"] == 0
    assert texture_calls == []
    assert any("deferring pair texture warmup to first-use warmup" in message for message in caplog.messages)
