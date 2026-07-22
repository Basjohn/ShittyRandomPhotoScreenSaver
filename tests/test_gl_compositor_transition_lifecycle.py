"""Regression tests for GLCompositorWidget transition lifecycle safety.

These tests focus on ensuring that compositor transitions can start and tear
down without raising, even when the GL pipeline is unavailable (our CI
environment). They guard against missing helper hooks when adding new
instrumentation around transition cancellation.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget

from core.animation import AnimationManager, EasingCurve
from core.animation.frame_interpolator import FrameState
from rendering.gl_compositor import GLCompositorWidget, _TerminalTransitionCompletion
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
    monkeypatch.setattr(comp, "_start_render_timer", lambda *a, **k: True)
    monkeypatch.setattr(comp, "_stop_render_timer", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_request_latched_presentation", lambda: True)
    # These lifecycle tests exercise animation ownership, not real GL admission.
    monkeypatch.setattr(comp, "_ensure_transition_program_ready", lambda _identity: True)
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
        try:
            comp.doneCurrent()
        except Exception:
            pass
        widget.cleanup_for_teardown()
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
    calls = []

    class _TextureManager:
        new_tex_id = 202

        def commit_cached_texture(self, pixmap, *, texture_id=None):
            calls.append(("commit", pixmap, texture_id))
            return int(texture_id or 0)

        def clear_committed_texture(self):
            calls.append(("clear",))

    comp._texture_manager = _TextureManager()
    monkeypatch.setattr(
        comp,
        "_release_transition_textures",
        lambda: calls.append(("release",)),
    )
    comp.cancel_current_transition(snap_to_new=True)

    assert anim_mgr.get_active_count() == 0
    assert comp._current_anim_id is None
    assert comp._base_pixmap is not None
    assert comp._base_pixmap.cacheKey() == new_pm.cacheKey()
    assert calls[0] == ("commit", new_pm, 202)
    assert calls[1] == ("release",)

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
    monkeypatch.setattr(comp, "_start_render_timer", lambda: True)
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
    assert scheduled == []
    comp.stop_rendering(reason="test-late-callback")

    comp._terminal_transaction = _TerminalTransitionCompletion(
        animation_generation=comp._transition_animation_generation - 1,
        transition_name="wipe",
        complete_callback=lambda: complete_calls.append("complete"),
        created_ts=0.0,
        phase="completion_queued",
    )
    comp._terminal_completion_dispatch_pending = True
    comp._srpss_complete_terminal_transition()

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
    monkeypatch.setattr(comp, "_start_render_timer", lambda: calls.append("render_timer") or True)
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
    assert calls == ["program", "render_timer", "paint_metrics"]
    assert scheduled == []
    assert "animate" not in calls
    assert update_calls == []

    queued: list[object] = []

    def _queue_completion(completion):
        completion.phase = "completion_queued"
        queued.append(completion)
        return True

    monkeypatch.setattr(
        comp,
        "_queue_terminal_transition_completion",
        _queue_completion,
    )
    comp._presentation_paint_completed(
        comp._presentation_dirty_generation,
        terminal_transition_rendered=False,
    )
    assert queued == []
    assert complete_calls == []

    comp._presentation_paint_completed(
        comp._presentation_dirty_generation,
        terminal_transition_rendered=True,
    )
    assert len(queued) == 1
    comp._terminal_completion_dispatch_pending = True
    comp._srpss_complete_terminal_transition()

    # Terminal paint is authoritative; wrapper progress is not replayed on a
    # second completion clock after the destination has been rendered.
    assert update_calls == []
    assert complete_calls == ["complete"]


@pytest.mark.qt_no_exception_capture
def test_rejected_terminal_dispatch_defers_once_without_per_paint_retry(
    qt_app,
    monkeypatch,
):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    completions = []
    deferred = []
    pauses = []
    generation = comp._transition_animation_generation
    comp._terminal_transaction = _TerminalTransitionCompletion(
        animation_generation=generation,
        transition_name="wipe",
        complete_callback=lambda: completions.append("complete"),
        created_ts=0.0,
    )
    comp._presentation_dirty_generation = 4
    comp._presentation_requested_generation = 4
    comp._presentation_ack_generation = 3

    monkeypatch.setattr(
        "rendering.gl_compositor.QMetaObject.invokeMethod",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "core.threading.manager.ThreadManager.single_shot",
        lambda delay, callback: deferred.append((delay, callback)),
    )
    monkeypatch.setattr(comp, "_stop_frame_pacing", lambda: pauses.append(True))

    comp._presentation_paint_completed(
        4,
        terminal_transition_rendered=True,
    )
    comp._presentation_paint_completed(
        4,
        terminal_transition_rendered=True,
    )

    assert comp._terminal_transaction is not None
    assert comp._terminal_transaction.phase == "completion_dispatch_failed"
    assert comp._terminal_completion_dispatch_pending is False
    assert pauses == []
    assert deferred == []
    assert completions == []
    assert comp.can_accept_transition() is False


@pytest.mark.qt_no_exception_capture
@pytest.mark.parametrize(
    ("name", "state_attr", "release_textures"),
    [
        ("crossfade", "_crossfade", False),
        ("slide", "_slide", False),
        ("wipe", "_wipe", False),
        ("blockspin", "_blockspin", False),
        ("warp", "_warp", True),
        ("raindrops", "_raindrops", True),
        ("blockflip", "_blockflip", False),
        ("diffuse", "_diffuse", False),
        ("blinds", "_blinds", False),
        ("crumble", "_crumble", False),
        ("particle", "_particle", False),
        ("burn", "_burn", True),
    ],
)
def test_transition_completion_promotes_destination_before_pair_release(
    qt_app,
    monkeypatch,
    name,
    state_attr,
    release_textures,
):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    destination = solid_pixmap(64, 64, Qt.GlobalColor.green)
    calls = []

    class _TextureManager:
        new_tex_id = 202

        def commit_cached_texture(self, pixmap, *, texture_id=None):
            calls.append(("commit", pixmap, texture_id))
            return int(texture_id or 0)

        def clear_committed_texture(self):
            calls.append(("clear",))

    manager = _TextureManager()
    comp._texture_manager = manager
    setattr(comp, state_attr, SimpleNamespace(new_pixmap=destination))
    monkeypatch.setattr(comp, "_stop_frame_pacing", lambda: None)
    monkeypatch.setattr(comp, "_release_transition_textures", lambda: calls.append(("release",)))
    monkeypatch.setattr(comp, "request_scene_update", lambda **_kwargs: True)

    comp._complete_transition(
        name,
        state_attr,
        on_finished=None,
        release_textures=release_textures,
    )

    assert comp._base_pixmap is destination
    assert calls[0] == ("commit", destination, 202)
    if release_textures:
        assert calls[1] == ("release",)
    else:
        assert calls == [("commit", destination, 202)]


@pytest.mark.qt_no_exception_capture
def test_transition_completion_commits_payload_identity(qt_app, monkeypatch):
    from rendering.image_upload_payload import ImageUploadPayload

    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    destination = solid_pixmap(8, 8, Qt.GlobalColor.green)
    payload = ImageUploadPayload.from_rgba8(8, 8, b"\x06" * (8 * 8 * 4))
    calls = []

    class _TextureManager:
        new_tex_id = 303

        def commit_cached_texture(
            self,
            pixmap=None,
            *,
            payload=None,
            texture_id=None,
        ):
            calls.append((pixmap, payload, texture_id))
            return int(texture_id or 0)

        def clear_committed_texture(self):
            calls.append(("clear",))

    comp._texture_manager = _TextureManager()
    comp._wipe = SimpleNamespace(
        new_pixmap=destination,
        new_upload_payload=payload,
    )
    monkeypatch.setattr(comp, "_stop_frame_pacing", lambda: None)
    monkeypatch.setattr(comp, "request_scene_update", lambda **_kwargs: True)

    comp._complete_transition(
        "wipe",
        "_wipe",
        on_finished=None,
    )

    assert comp._base_pixmap is destination
    assert comp._base_upload_payload is payload
    assert calls == [(None, payload, 303)]


@pytest.mark.qt_no_exception_capture
def test_transition_admission_refuses_when_presentation_owner_cannot_start(
    qt_app,
    monkeypatch,
):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    comp._wipe = object()
    monkeypatch.setattr(comp, "_start_render_timer", lambda: False)
    animation_manager = AnimationManager(fps=60)

    try:
        with pytest.raises(RuntimeError, match="Presentation owner admission failed"):
            comp._start_transition_animation(
                duration_ms=200,
                easing=EasingCurve.LINEAR,
                animation_manager=animation_manager,
                update_callback=lambda _progress: None,
                on_complete=lambda: None,
                transition_label="wipe",
            )
    finally:
        animation_manager.stop()

    assert comp._wipe is None
    assert comp._frame_state is None


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
def test_deferred_desync_refusal_returns_to_display_without_false_start(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    scheduled: list[object] = []
    started: list[int] = []
    failures: list[tuple[str, str]] = []
    parent._on_deferred_transition_start_failed = (
        lambda label, reason: failures.append((label, reason))
    )
    monkeypatch.setattr(comp, "_apply_desync_strategy", lambda duration_ms: (75, duration_ms + 75))
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.ThreadManager.single_shot",
        staticmethod(lambda _delay, callback: scheduled.append(callback)),
    )
    monkeypatch.setattr(comp, "_clear_all_transitions", lambda: None)
    monkeypatch.setattr(comp, "_prepare_wipe_textures", lambda: True)
    monkeypatch.setattr(comp, "_pre_upload_textures", lambda _prep: None)
    monkeypatch.setattr(comp, "_start_transition_animation", lambda *_args, **_kwargs: None)

    token = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
        on_started=lambda duration_ms: started.append(duration_ms),
    )

    assert token is not None
    assert len(scheduled) == 1
    scheduled[0]()

    assert started == []
    assert failures == [("wipe", "deferred_animation_refused")]

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
        lambda old_pixmap, new_pixmap, **_kwargs: calls.append("textures") or True,
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
